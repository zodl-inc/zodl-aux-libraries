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

import os
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(SCRIPTS, "release_manifest.py")
sys.path.insert(0, SCRIPTS)

import release_manifest  # noqa: E402

CHECKSUM = "0123456789abcdef" * 4
REPOSITORY = "example-org/example-repo"


class RenderTest(unittest.TestCase):
    def test_renders_the_binary_target_with_url_and_checksum(self):
        text = release_manifest.render("1.2.3", CHECKSUM, REPOSITORY)
        self.assertTrue(text.startswith("// swift-tools-version:6.0\n"))
        self.assertIn(
            '            url: "https://github.com/example-org/example-repo/releases/download/1.2.3/ZodlAppConfig.xcframework.zip",\n',
            text,
        )
        self.assertIn('            checksum: "%s"\n' % CHECKSUM, text)
        self.assertIn('    name: "zodl-app-config",\n', text)
        self.assertIn(
            '    products: [.library(name: "ZodlAppConfig", targets: ["ZodlAppConfig"])],\n',
            text,
        )

    def test_the_url_names_the_repository_it_is_given(self):
        text = release_manifest.render("1.2.3", CHECKSUM, "other-org/other.repo_1")
        self.assertIn('url: "https://github.com/other-org/other.repo_1/releases/download/1.2.3/', text)

    def test_has_no_source_or_test_target(self):
        text = release_manifest.render("1.2.3", CHECKSUM, REPOSITORY)
        self.assertNotIn(".target(", text)
        self.assertNotIn(".testTarget(", text)

    def test_rejects_a_bad_version(self):
        for version in ["v1.0.0", "1.0", "1.0.0-rc1", "1.0.0 ", ""]:
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    release_manifest.render(version, CHECKSUM, REPOSITORY)

    def test_rejects_a_bad_checksum(self):
        for checksum in ["", "abc", CHECKSUM.upper(), CHECKSUM + "0"]:
            with self.subTest(checksum=checksum):
                with self.assertRaises(ValueError):
                    release_manifest.render("1.2.3", checksum, REPOSITORY)

    def test_rejects_a_bad_repository(self):
        for repository in ["", "example-org", "example-org/", "/example-repo", "a/b/c", 'a/b"', "a b/c", "a/b\n",
                           "https://github.com/a/b"]:
            with self.subTest(repository=repository):
                with self.assertRaises(ValueError):
                    release_manifest.render("1.2.3", CHECKSUM, repository)

    def test_local_form_points_at_a_path(self):
        text = release_manifest.render_local("ZodlAppConfig.xcframework")
        self.assertIn('path: "ZodlAppConfig.xcframework"', text)
        self.assertNotIn("url:", text)


class CommandTest(unittest.TestCase):
    def test_command_writes_nothing_for_a_bad_version(self):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "Package.swift")
            result = subprocess.run(
                [sys.executable, "-B", SCRIPT, "--version", "v1", "--checksum", CHECKSUM, "--repository", REPOSITORY,
                 "--output", output],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: version must be X.Y.Z", result.stderr)
            self.assertFalse(os.path.exists(output))

    def test_command_needs_the_repository_for_a_release(self):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "Package.swift")
            result = subprocess.run(
                [sys.executable, "-B", SCRIPT, "--version", "1.2.3", "--checksum", CHECKSUM, "--output", output],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("--repository", result.stderr)
            self.assertFalse(os.path.exists(output))


if __name__ == "__main__":
    unittest.main()
