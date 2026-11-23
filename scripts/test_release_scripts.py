# Copyright © 2026 Znewco, Inc. (d/b/a Zcash Open Development Lab)
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of ZODL Aux Libraries.
#
# ZODL Aux Libraries is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License,
# version 3 only, as published by the Free Software Foundation.
#
# ZODL Aux Libraries is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Affero General Public License for more details.
#
# Commercial licensing: see COMMERCIAL-LICENSE.md.

import hashlib
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
GIT = {"PATH": os.environ["PATH"], "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}

GH_STAND_IN = """#!/bin/bash
# Stand-in for gh: records each call, keeps a created asset and hands it back on download.
set -euo pipefail
echo "$*" >> "$GH_LOG"
command="$1 $2"
if [ "$command" = "release create" ]; then
    cp "$4" "$GH_STORE/"
    if [ -n "${GH_TAMPER:-}" ]; then echo tampered > "$GH_STORE/$(basename "$4")"; fi
elif [ "$command" = "release download" ]; then
    while [ "$#" -gt 0 ]; do
        if [ "$1" = "--dir" ]; then cp "$GH_STORE"/* "$2/"; fi
        shift
    done
fi
"""


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, env=GIT, check=True, capture_output=True, text=True).stdout


def run(args, env, cwd=None):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)


def version_name():
    for line in (ROOT / "gradle.properties").read_text().splitlines():
        if line.startswith("VERSION_NAME="):
            return line.split("=", 1)[1].strip()
    raise AssertionError("VERSION_NAME missing")


class PublishReleaseTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.remote = self.tmp / "remote.git"
        git("init", "--quiet", "--bare", str(self.remote))
        self.repo = self.tmp / "repository"
        self.repo.mkdir()
        git("init", "--quiet", "-b", "main", cwd=self.repo)
        for name, text in [("Package.swift", "// source manifest\n"),
                           ("Sources/ZodlAppConfig/EncodedValues.generated.swift", "// placeholder\n"),
                           ("Tests/ZodlAppConfigTests/Tests.swift", "// tests\n"),
                           ("README.md", "readme\n")]:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        (self.repo / "scripts").mkdir()
        script = self.repo / "scripts" / "publish_release.sh"
        script.write_bytes((SCRIPTS / "publish_release.sh").read_bytes())
        script.chmod(0o755)
        git("add", "-A", cwd=self.repo)
        git("commit", "--quiet", "-m", "initial", cwd=self.repo)
        git("push", "--quiet", str(self.remote), "main", cwd=self.repo)
        self.main = git("rev-parse", "HEAD", cwd=self.repo).strip()
        (self.repo / "Sources/ZodlAppConfig/EncodedValues.generated.swift").write_text("// VALUES-MARKER\n")

        self.release = self.tmp / "release"
        self.release.mkdir()
        self.zip = self.release / "ZodlAppConfig.xcframework.zip"
        self.zip.write_bytes(b"zip bytes")
        digest = hashlib.sha256(self.zip.read_bytes()).hexdigest()
        self.write_manifest(digest=digest)

        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(GH_STAND_IN)
        gh.chmod(0o755)
        self.gh_log = self.tmp / "gh.log"
        self.gh_store = self.tmp / "gh-store"
        self.gh_store.mkdir()

    def write_manifest(self, digest=None, url=None):
        digest = digest or hashlib.sha256(self.zip.read_bytes()).hexdigest()
        url = url or "https://github.com/example/repository/releases/download/1.2.3/ZodlAppConfig.xcframework.zip"
        (self.release / "Package.swift").write_text('// release manifest\nurl: "%s",\nchecksum: "%s"\n' % (url, digest))

    def run_script(self, **extra):
        env = dict(GIT)
        env.update({"PATH": "%s:%s" % (self.bin, GIT["PATH"]), "RELEASE_REMOTE": str(self.remote),
                    "GITHUB_REPOSITORY": "example/repository", "GH_TOKEN": "unused",
                    "GH_LOG": str(self.gh_log), "GH_STORE": str(self.gh_store), "HOME": str(self.tmp)})
        env.update(extra)
        return run([str(self.repo / "scripts" / "publish_release.sh"), "1.2.3", str(self.release)], env, cwd=self.tmp)

    def remote_refs(self):
        out = git("for-each-ref", "--format=%(refname) %(objectname)", cwd=self.remote)
        return dict(line.split(" ") for line in out.splitlines())

    def gh_calls(self):
        return self.gh_log.read_text().splitlines() if self.gh_log.exists() else []

    def test_pushes_only_the_tag_on_a_commit_without_sources(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("published 1.2.3", result.stdout)
        refs = self.remote_refs()
        self.assertEqual(set(refs), {"refs/heads/main", "refs/tags/1.2.3"})
        self.assertEqual(refs["refs/heads/main"], self.main)
        tag = refs["refs/tags/1.2.3"]
        self.assertEqual(git("rev-parse", tag + "^", cwd=self.remote).strip(), self.main)
        files = git("ls-tree", "-r", "--name-only", tag, cwd=self.remote).split()
        self.assertEqual(sorted(files), ["Package.swift", "README.md", "scripts/publish_release.sh"])
        self.assertEqual(git("show", tag + ":Package.swift", cwd=self.remote),
                         (self.release / "Package.swift").read_text())
        self.assertNotIn("VALUES-MARKER", git("log", "-p", "--all", cwd=self.remote))

    def test_creates_the_release_for_the_existing_tag_and_checks_the_published_asset(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.gh_calls()
        self.assertEqual(len(calls), 2)
        create = calls[0]
        self.assertTrue(create.startswith("release create 1.2.3 "), create)
        self.assertRegex(create.split(" ")[3], r"/release/ZodlAppConfig\.xcframework\.zip$")
        self.assertIn("--verify-tag", create)
        self.assertIn("--repo example/repository", create)
        self.assertTrue(calls[1].startswith("release download 1.2.3 "), calls[1])

    def test_refuses_before_any_push_when_the_manifest_names_another_checksum(self):
        self.zip.write_bytes(b"other bytes")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not name the checksum", result.stderr)
        self.assertEqual(set(self.remote_refs()), {"refs/heads/main"})
        self.assertEqual(self.gh_calls(), [])

    def test_refuses_before_any_push_when_the_manifest_names_another_repository_or_version(self):
        for url in ["https://github.com/example/other/releases/download/1.2.3/ZodlAppConfig.xcframework.zip",
                    "https://github.com/example/repository/releases/download/1.2.4/ZodlAppConfig.xcframework.zip"]:
            with self.subTest(url=url):
                self.write_manifest(url=url)
                result = self.run_script()
                self.assertEqual(result.returncode, 1)
                self.assertIn("does not name https://github.com/example/repository/releases/download/1.2.3/", result.stderr)
                self.assertEqual(set(self.remote_refs()), {"refs/heads/main"})
                self.assertEqual(self.gh_calls(), [])

    def test_fails_without_creating_a_release_when_the_tag_already_exists(self):
        git("push", "--quiet", str(self.remote), "main:refs/tags/1.2.3", cwd=self.repo)
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.remote_refs()["refs/tags/1.2.3"], self.main)
        self.assertEqual(self.gh_calls(), [])

    def test_fails_when_the_published_asset_differs(self):
        result = self.run_script(GH_TAMPER="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs from the one the manifest names", result.stderr)


class PipefailTest(unittest.TestCase):
    def test_no_script_closes_a_pipe_early(self):
        # Under pipefail, `cmd | head` fails whenever cmd is still writing when head exits: xcodebuild -version
        # then aborts on the closed pipe. Read the whole output instead (sed -n 1p).
        for script in sorted(SCRIPTS.glob("*.sh")):
            text = script.read_text()
            self.assertIn("set -euo pipefail", text, script.name)
            for number, line in enumerate(text.splitlines(), 1):
                self.assertIsNone(re.search(r"\|\s*head\b", line), "%s:%d: %s" % (script.name, number, line))


class VerifyReleasePackageTest(unittest.TestCase):
    def test_the_consumer_also_compares_the_near_value(self):
        text = (SCRIPTS / "verify_release_package.sh").read_text()
        self.assertIn("AppConfig.Near.feeRecipient", text)
        self.assertIn('"APP_CONFIG_NEAR_FEE_RECIPIENT"', text)
        # The consumer must actually fold the near comparison into the verdict.
        lines = [line for line in text.splitlines() if line.startswith("let differing")]
        self.assertEqual(len(lines), 1)
        statement = text[text.index(lines[0]):].split("if differing.isEmpty", 1)[0]
        self.assertIn("nearDifferences()", statement)


class CheckVersionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.remote = Path(self._tmp.name) / "remote.git"
        git("init", "--quiet", "--bare", str(self.remote))
        self.version = version_name()

    def check(self, version, remote=None):
        env = dict(GIT)
        env["RELEASE_REMOTE"] = str(remote or self.remote)
        return run([str(SCRIPTS / "check_version.sh"), version], env)

    def test_accepts_the_gradle_version_when_it_is_not_a_tag(self):
        result = self.check(self.version)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "version %s is free\n" % self.version)

    def test_rejects_a_malformed_version(self):
        for bad in ["v" + self.version, "1.0", self.version + "-rc1", self.version + "\n9.9.9", ""]:
            with self.subTest(version=bad):
                result = self.check(bad)
                self.assertEqual(result.returncode, 1)
                self.assertIn("must be X.Y.Z", result.stderr)

    def test_rejects_a_version_that_differs_from_gradle_properties(self):
        result = self.check("999.0.0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs from VERSION_NAME", result.stderr)

    def test_rejects_an_existing_tag(self):
        work = Path(self._tmp.name) / "work"
        work.mkdir()
        git("init", "--quiet", "-b", "main", cwd=work)
        (work / "f").write_text("x")
        git("add", "f", cwd=work)
        git("commit", "--quiet", "-m", "c", cwd=work)
        git("tag", self.version, cwd=work)
        git("push", "--quiet", str(self.remote), "refs/tags/" + self.version, cwd=work)
        result = self.check(self.version)
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr)

    def test_fails_when_the_tags_cannot_be_listed(self):
        result = self.check(self.version, remote=Path(self._tmp.name) / "missing.git")
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not list the tags", result.stderr)


class SelectXcodeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.apps = Path(self._tmp.name)
        self.version = (ROOT / ".xcode-version").read_text().strip()

    def select(self):
        env = dict(GIT)
        env["XCODE_APPLICATIONS_DIR"] = str(self.apps)
        return run([str(SCRIPTS / "select_xcode.sh")], env)

    def test_prints_the_developer_directory_of_the_named_xcode(self):
        self.assertRegex(self.version, r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")
        developer = self.apps / ("Xcode_%s.app" % self.version) / "Contents" / "Developer"
        developer.mkdir(parents=True)
        result = self.select()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "DEVELOPER_DIR=%s\n" % developer)

    def test_fails_when_that_xcode_is_not_installed(self):
        result = self.select()
        self.assertEqual(result.returncode, 1)
        self.assertIn("is not installed here", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
