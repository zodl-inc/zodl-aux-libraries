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

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
AWS_ACTION = "zodl-inc/actions/aws-secrets@1089c3325c069e5cdd6ae5aa625006c850388c56"
NAMES = [
    "APP_CONFIG_OHTTP_%s_%s" % (field, network)
    for network in ("MAINNET", "TESTNET")
    for field in ("GATEWAY_HOST", "RELAY_URL", "KEYS_DNS_NAME", "SIGNING_PUBKEY")
]
ALL_NAMES = NAMES + ["APP_CONFIG_NEAR_FEE_RECIPIENT"]


def read(name):
    return (WORKFLOWS / name).read_text()


def job(workflow, name):
    lines = workflow.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line == "  %s:" % name:
            start = index
            break
    if start is None:
        raise AssertionError("job %s not found" % name)
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"^  [A-Za-z0-9_-]+:", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


class PublishWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.text = read("publish.yml")

    def test_started_only_by_hand_with_a_version_input(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger)
        self.assertIn("version:", trigger)
        self.assertIn("required: true", trigger)
        for forbidden in ("push:", "pull_request:", "schedule:"):
            self.assertNotIn(forbidden, trigger)

    def test_the_version_never_reaches_a_script_by_interpolation(self):
        for line in self.text.splitlines():
            if "${{ inputs.version }}" in line:
                self.assertEqual(line.strip(), "VERSION: ${{ inputs.version }}")

    def test_preflight_checks_the_version_and_rehearses_without_publishing(self):
        preflight = job(self.text, "preflight")
        self.assertIn("environment: release", preflight)
        self.assertIn("contents: read", preflight)
        self.assertNotIn("contents: write", preflight)
        check = 'scripts/check_version.sh "$VERSION"'
        self.assertIn(check, preflight)
        self.assertLess(preflight.index(check), preflight.index("uses: zodl-inc/actions/aws-secrets"))
        self.assertIn('scripts/build_release.sh "$VERSION" "$RUNNER_TEMP/release"', preflight)
        for forbidden in ("publish_release.sh", "git push", "gh release", "upload-artifact"):
            self.assertNotIn(forbidden, preflight)

    def test_android_waits_for_preflight_and_pushes_no_tag(self):
        android = job(self.text, "publish-android")
        self.assertIn("\n    needs: preflight\n", android + "\n")
        self.assertIn("contents: read", android)
        for forbidden in ("contents: write", "git tag", "git push"):
            self.assertNotIn(forbidden, android)

    def test_ios_runs_last_and_is_the_only_job_that_publishes_the_tag(self):
        ios = job(self.text, "publish-ios")
        self.assertIn("\n    needs: [preflight, publish-android]\n", ios + "\n")
        self.assertIn("environment: release", ios)
        self.assertIn("      contents: read ", ios)
        self.assertNotIn("      contents: write", ios)
        self.assertIn("actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349", ios)
        self.assertIn("GH_TOKEN: ${{ steps.bot.outputs.token }}", ios)
        self.assertIn("permission-contents: write", ios)
        self.assertLess(ios.index("steps.bot.outputs.token"), ios.index("scripts/publish_release.sh"))
        self.assertLess(ios.index("scripts/build_release.sh"), ios.index("scripts/publish_release.sh"))
        self.assertEqual(self.text.count("scripts/publish_release.sh"), 1)

    def test_both_swift_jobs_read_the_nine_values_through_the_pinned_action(self):
        for name in ("preflight", "publish-ios"):
            body = job(self.text, name)
            self.assertIn(AWS_ACTION, body)
            self.assertIn("id-token: write", body)
            for value_name in ALL_NAMES:
                self.assertIn(value_name, body)
            self.assertIn('scripts/select_xcode.sh >> "$GITHUB_ENV"', body)

    def test_android_reads_the_schema_names_and_the_maven_credentials_through_the_pinned_action(self):
        android = job(self.text, "publish-android")
        self.assertIn(AWS_ACTION, android)
        self.assertIn("id-token: write", android)
        self.assertIn("python3 scripts/appconfig.py env-names", android)
        self.assertIn("secrets: ${{ steps.names.outputs.list }}", android)
        for mapping in ("ORG_GRADLE_PROJECT_mavenCentralUsername=MAVEN_CENTRAL_USERNAME",
                        "ORG_GRADLE_PROJECT_mavenCentralPassword=MAVEN_CENTRAL_PASSWORD",
                        "ORG_GRADLE_PROJECT_signingKeyBase64=MAVEN_SIGNING_KEY_ASCII"):
            self.assertIn(mapping, android)
        self.assertLess(android.index("env-names"), android.index(AWS_ACTION))
        self.assertLess(android.index(AWS_ACTION), android.index("publishAndReleaseToMavenCentral"))

    def test_the_schema_names_are_the_nine_values_of_the_swift_jobs(self):
        names = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "appconfig.py"), "env-names"],
                               capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(names, ALL_NAMES)

    def test_preflight_also_applies_the_android_rules_and_ios_checks_the_android_digest(self):
        preflight = job(self.text, "preflight")
        self.assertLess(preflight.index(AWS_ACTION), preflight.index("scripts/appconfig.py kotlin"))
        self.assertLess(preflight.index("scripts/appconfig.py kotlin"), preflight.index("scripts/build_release.sh"))
        android = job(self.text, "publish-android")
        self.assertIn("digest: ${{ steps.digest.outputs.value }}", android)
        ios = job(self.text, "publish-ios")
        self.assertIn("ANDROID_DIGEST: ${{ needs.publish-android.outputs.digest }}", ios)
        self.assertLess(ios.index("ANDROID_DIGEST"), ios.index("scripts/publish_release.sh"))

    def test_one_publish_at_a_time(self):
        self.assertIn("\nconcurrency:\n  group: publish\n  cancel-in-progress: false\n", self.text)

    def test_every_job_runs_in_the_release_environment(self):
        for name in ("preflight", "publish-android", "publish-ios"):
            self.assertIn("environment: release", job(self.text, name))

    def test_no_step_prints_a_value(self):
        for line in self.text.splitlines():
            self.assertIsNone(re.search(r"(echo|printf)\b.*\$\{?(APP_CONFIG|ZODL)_(OHTTP|NEAR)_", line), line)


class TestWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.text = read("test.yml")

    def test_has_the_five_checks(self):
        for name in ("android-tests", "swift-tests", "xcframework-dry-run", "python-tests", "no-committed-values"):
            self.assertTrue(job(self.text, name))

    def test_reads_no_secret(self):
        for forbidden in ("aws-secrets", "secrets.", "id-token", "environment:"):
            self.assertNotIn(forbidden, self.text)

    def test_android_builds_with_the_public_example_values(self):
        android = job(self.text, "android-tests")
        self.assertIn('eval "$(python3 scripts/swift_values.py example-env)"', android)
        self.assertIn("com/zodl/appconfig/AppConfig$Ohttp.class", android)
        self.assertIn("com/zodl/appconfig/AppConfig$Near.class", android)

    def test_dry_run_uses_the_example_values_and_keeps_only_their_zip(self):
        dry = job(self.text, "xcframework-dry-run")
        self.assertIn('scripts/build_release.sh 0.0.0 "$RUNNER_TEMP/release" example', dry)
        self.assertIn("path: ${{ runner.temp }}/release/ZodlAppConfig.xcframework.zip", dry)
        self.assertNotIn("publish_release.sh", self.text)

    def test_the_macos_jobs_select_the_pinned_xcode(self):
        for name in ("swift-tests", "xcframework-dry-run"):
            self.assertIn('scripts/select_xcode.sh >> "$GITHUB_ENV"', job(self.text, name))


if __name__ == "__main__":
    unittest.main()
