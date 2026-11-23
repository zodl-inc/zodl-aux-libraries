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

"""Tests for appconfig.py (Android generator) and the workflow secrets guard of check_no_committed_values.py.
The generator runs against temporary copies, so the real files stay untouched."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import check_no_committed_values  # noqa: E402
import swift_values  # noqa: E402

SCHEMA = {
    "kotlin_package": "com.example.cfg",
    "root": "AppConfig",
    "groups": {
        "net": {"required": True, "keys": ["HOST_MAINNET", "URL_MAINNET"]},
        "extra": {"required": False, "keys": ["FLAG"]},
    },
}
FULL = {
    "APP_CONFIG_NET_HOST_MAINNET": "gw.example.invalid",
    "APP_CONFIG_NET_URL_MAINNET": "https://relay.example.invalid/r",
}


def run_generator(root, env, *args):
    return subprocess.run([sys.executable, "-B", os.path.join(root, "scripts", "appconfig.py"), *args],
                          env={"PATH": os.environ["PATH"], **env}, capture_output=True, text=True)


class AppConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        shutil.copytree(SCRIPTS, os.path.join(self.tmp, "scripts"), ignore=shutil.ignore_patterns("__pycache__"))
        os.makedirs(os.path.join(self.tmp, "config"))
        self.write_schema(SCHEMA)
        self.out = os.path.join(self.tmp, "gen")
        self.kt = os.path.join(self.out, "com", "example", "cfg", "AppConfig.kt")

    def write_schema(self, schema):
        with open(os.path.join(self.tmp, "config", "schema.json"), "w") as fh:
            json.dump(schema, fh)

    def kotlin(self, env):
        return run_generator(self.tmp, env, "kotlin", self.out)

    def test_env_names(self):
        r = run_generator(self.tmp, {}, "env-names")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), [*FULL, "APP_CONFIG_EXTRA_FLAG"])

    def test_kotlin_full(self):
        r = self.kotlin(FULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.kt) as fh:
            text = fh.read()
        self.assertIn("package com.example.cfg", text)
        self.assertIn("object Net {", text)
        self.assertIn('const val HOST_MAINNET: String = "gw.example.invalid"', text)
        self.assertIn('const val FLAG: String = ""', text)  # an optional group may stay empty

    def test_missing_required_fails_and_names_the_variable_only(self):
        env = dict(FULL)
        del env["APP_CONFIG_NET_URL_MAINNET"]
        r = self.kotlin(env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("APP_CONFIG_NET_URL_MAINNET", r.stderr)
        self.assertNotIn("gw.example.invalid", r.stderr)
        self.assertFalse(os.path.exists(self.kt))

    def test_bad_characters(self):
        for bad in ['a"b', "a\\b", "a$b", "a b", "a\tb", "é"]:
            r = self.kotlin(dict(FULL, APP_CONFIG_NET_HOST_MAINNET=bad))
            self.assertNotEqual(r.returncode, 0, bad)
            self.assertIn("Illegal character in APP_CONFIG_NET_HOST_MAINNET", r.stderr)
            self.assertFalse(os.path.exists(self.kt))

    def test_bad_schema(self):
        for schema in (
            {**SCHEMA, "groups": {"Bad-Group": {"keys": ["A"]}}},
            {**SCHEMA, "groups": {"g": {"keys": ["lower"]}}},
            {**SCHEMA, "groups": {"g": {"keys": ["A", "A"]}}},
            {**SCHEMA, "groups": {"g": {"keys": ["A=B"]}}},
            {**SCHEMA, "groups": {}},
        ):
            self.write_schema(schema)
            self.assertNotEqual(run_generator(self.tmp, {}, "env-names").returncode, 0, schema)


class RealSchemaTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out)
        self.kt = os.path.join(self.out, "com", "zodl", "appconfig", "AppConfig.kt")

    def test_ohttp_keys_are_the_names_the_swift_package_uses(self):
        r = run_generator(ROOT, {}, "env-names")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), swift_values.ALL_NAMES)

    def test_example_values_give_the_kotlin_api(self):
        r = run_generator(ROOT, swift_values.EXAMPLE_VALUES, "kotlin", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.kt) as fh:
            text = fh.read()
        self.assertIn("package com.zodl.appconfig\n", text)
        self.assertIn("object AppConfig {\n    object Ohttp {\n", text)
        for name, value in swift_values.EXAMPLE_VALUES.items():
            if name.startswith("APP_CONFIG_OHTTP_"):
                key = name[len("APP_CONFIG_OHTTP_"):]
                self.assertIn('        const val %s: String = "%s"\n' % (key, value), text)
        self.assertIn('    object Near {\n        const val FEE_RECIPIENT: String = "fee-recipient.example"\n', text)

    def test_near_value_follows_the_near_rule(self):
        name = "APP_CONFIG_NEAR_FEE_RECIPIENT"
        for bad in ("Fee.Example", "fee-recipient.example\n"):
            r = run_generator(ROOT, dict(swift_values.EXAMPLE_VALUES, **{name: bad}), "kotlin", self.out)
            self.assertNotEqual(r.returncode, 0, repr(bad))
            self.assertIn(name, r.stderr)
            self.assertNotIn(bad, r.stderr)
            self.assertFalse(os.path.exists(self.kt))

    def test_the_near_value_is_required(self):
        name = "APP_CONFIG_NEAR_FEE_RECIPIENT"
        env = {n: v for n, v in swift_values.EXAMPLE_VALUES.items() if n != name}
        r = run_generator(ROOT, env, "kotlin", self.out)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(name, r.stderr)

    def test_swift_values_follow_the_swift_release_rules(self):
        for name, bad in (("APP_CONFIG_OHTTP_GATEWAY_HOST_MAINNET", "https://gw.example"),
                          ("APP_CONFIG_OHTTP_SIGNING_PUBKEY_TESTNET", "abcd1234"),
                          ("APP_CONFIG_OHTTP_RELAY_URL_TESTNET",
                           swift_values.EXAMPLE_VALUES["APP_CONFIG_OHTTP_RELAY_URL_MAINNET"])):
            r = run_generator(ROOT, dict(swift_values.EXAMPLE_VALUES, **{name: bad}), "kotlin", self.out)
            self.assertNotEqual(r.returncode, 0, name)
            self.assertIn(name, r.stderr)
            self.assertNotIn(bad, r.stderr)
            self.assertFalse(os.path.exists(self.kt))

    def test_all_eight_values_are_required(self):
        env = {n: v for n, v in swift_values.EXAMPLE_VALUES.items() if not n.endswith("_TESTNET")}
        r = run_generator(ROOT, env, "kotlin", self.out)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("APP_CONFIG_OHTTP_GATEWAY_HOST_TESTNET", r.stderr)

    def test_digest_is_stable_and_names_no_value(self):
        env = dict(swift_values.EXAMPLE_VALUES)
        first = run_generator(ROOT, env, "digest")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertRegex(first.stdout, r"^[0-9a-f]{64}\n$")
        self.assertEqual(run_generator(ROOT, env, "digest").stdout, first.stdout)
        env["APP_CONFIG_OHTTP_RELAY_URL_TESTNET"] = "https://relay-testnet.example/other"
        self.assertNotEqual(run_generator(ROOT, env, "digest").stdout, first.stdout)
        env = dict(swift_values.EXAMPLE_VALUES, APP_CONFIG_NEAR_FEE_RECIPIENT="other-recipient.example")
        self.assertNotEqual(run_generator(ROOT, env, "digest").stdout, first.stdout)

    def test_values_are_not_stripped(self):
        env = dict(swift_values.EXAMPLE_VALUES, APP_CONFIG_OHTTP_GATEWAY_HOST_MAINNET="ohttp-gateway.example\n")
        r = run_generator(ROOT, env, "digest")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("APP_CONFIG_OHTTP_GATEWAY_HOST_MAINNET", r.stderr)


class SecretsGuardTest(unittest.TestCase):
    def test_flags_every_read_of_the_secrets_context(self):
        for line in ("        run: echo ${{ secrets.FOO }}",
                     "        if: ${{ Secrets.FOO != '' }}",
                     "    if: secrets.FOO",
                     "          X: ${{ secrets['FOO'] }}",
                     "          X: ${{ toJSON(secrets) }}",
                     "          X: ${{ format('{0}', secrets) }}",
                     "          X: ${{ secrets }}",
                     "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
                     "          echo hi # ${{ secrets.FOO }}",
                     "          X: ${{ secrets && 'a' }}",
                     "          X: ${{ secrets || '{}' }}",
                     "          X: ${{ !secrets }}",
                     "    if: ${{ github.event_name == 'x' && secrets }}",
                     "      - if: secrets == null",
                     "          X: ${{ secrets == x }}",
                     "          X: ${{ secrets != null }}",
                     "    with: { secrets: inherit }",
                     "    secrets: inherit",
                     "    SECRETS: Inherit"):
            self.assertEqual(check_no_committed_values.secret_references("x: 1\n" + line), [2], line)

    def test_allows_the_aws_secrets_action_and_its_input(self):
        text = "\n".join((
            "# Values come from AWS by zodl-inc/actions/aws-secrets, no copy lives on GitHub.",
            "        uses: zodl-inc/actions/aws-secrets@1089c3325c069e5cdd6ae5aa625006c850388c56 # v1",
            "          secrets: |",
            "          secrets: ${{ steps.names.outputs.list }}",
            "          GH_TOKEN: ${{ github.token }}",
            "      - name: Read from aws-secrets.",
        ))
        self.assertEqual(check_no_committed_values.secret_references(text), [])

    def test_the_workflows_of_this_repository_pass(self):
        for directory, _, files in os.walk(os.path.join(ROOT, ".github")):
            for name in files:
                if name.endswith((".yml", ".yaml")):
                    with open(os.path.join(directory, name)) as fh:
                        self.assertEqual(check_no_committed_values.secret_references(fh.read()), [], name)


class LicenseHeaderTest(unittest.TestCase):
    def test_every_first_party_source_file_carries_the_header(self):
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        for path in filter(None, listed.split("\0")):
            if not path.endswith((".py", ".sh", ".swift", ".kts")) or path.endswith(".generated.swift"):
                continue
            with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
                head = fh.read(1200)
            self.assertIn("Copyright © 2026 Znewco, Inc. (d/b/a Zcash Open Development Lab)", head, path)
            self.assertIn("SPDX-License-Identifier: AGPL-3.0-only", head, path)


if __name__ == "__main__":
    unittest.main()
