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
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(SCRIPTS, "swift_values.py")
sys.path.insert(0, SCRIPTS)

import swift_values  # noqa: E402

EXAMPLE = swift_values.EXAMPLE_VALUES
NAMES = swift_values.NAMES


def run(args, env):
    return subprocess.run(
        [sys.executable, "-B", SCRIPT, *args],
        env={"PATH": os.environ["PATH"], **env},
        capture_output=True,
        text=True,
    )


class ValidateTest(unittest.TestCase):
    def test_example_values_are_valid(self):
        self.assertEqual(swift_values.validate(EXAMPLE), [])

    def test_each_missing_value_is_named(self):
        for name in NAMES:
            values = {n: v for n, v in EXAMPLE.items() if n != name}
            problems = swift_values.validate(values)
            self.assertEqual(len(problems), 1, name)
            self.assertEqual(problems[0][0], name)
            self.assertIn("missing", problems[0][1])

    def test_malformed_values_are_rejected_by_rule(self):
        cases = {
            "APP_CONFIG_OHTTP_GATEWAY_HOST_MAINNET": ["Gateway.example", "https://gateway.example", "gateway.example:443",
                                                "gateway.example/path", "gateway.example.", "gateway .example",
                                                "gateway.example\n", " gateway.example", "-gateway.example"],
            "APP_CONFIG_OHTTP_KEYS_DNS_NAME_TESTNET": ["keys.example\n", "keys.example\r\n", "keys.example ", "keys\n.example"],
            "APP_CONFIG_OHTTP_RELAY_URL_MAINNET": ["http://relay.example/relay", "relay.example", "https:///relay", "https://user@relay.example",
                                             "https://relay.example/relay?query", "https://relay.example/relay#fragment",
                                             "https://relay.example/a b", "https://relay.example:0/relay",
                                             "https://relay.example:65536/relay", "https://relay.example/relay\n"],
            "APP_CONFIG_OHTTP_SIGNING_PUBKEY_TESTNET": ["abcd1234", "g" * 64, EXAMPLE["APP_CONFIG_OHTTP_SIGNING_PUBKEY_TESTNET"] + "\n",
                                                  "0100000000000000000000000000000000000000000000000000000000000000",
                                                  "02" + "00" * 31],
            "APP_CONFIG_OHTTP_RELAY_WEIGHTS_PUBKEY_MAINNET": ["abcd1234", "g" * 64, " " + EXAMPLE["APP_CONFIG_OHTTP_RELAY_WEIGHTS_PUBKEY_MAINNET"],
                                                         "0100000000000000000000000000000000000000000000000000000000000000",
                                                         "02" + "00" * 31],
        }
        for name, bad_values in cases.items():
            for value in bad_values:
                problems = swift_values.validate({**EXAMPLE, name: value})
                self.assertEqual(len(problems), 1, (name, value))
                self.assertEqual(problems[0][0], name)
                self.assertNotIn(value.strip(), problems[0][1])

    def test_valid_relay_forms_are_accepted(self):
        for value in ["https://relay.example", "https://relay.example:8443/relay", "https://192.0.2.1/relay",
                      "https://[2001:db8::1]:8443/relay", "https://Relay.Example/relay"]:
            problems = swift_values.validate({**EXAMPLE, "APP_CONFIG_OHTTP_RELAY_URL_MAINNET": value,
                                              "APP_CONFIG_OHTTP_RELAY_URLS_MAINNET": value})
            self.assertEqual(problems, [], value)

    def test_relay_lists_follow_the_client_rules(self):
        name = "APP_CONFIG_OHTTP_RELAY_URLS_MAINNET"
        first = EXAMPLE["APP_CONFIG_OHTTP_RELAY_URL_MAINNET"]
        for good in [first, first + ",https://b.example/x", first + "/,https://b.example:8443/x",
                     ",".join([first] + ["https://r%d.example/relay" % i for i in range(7)])]:
            self.assertEqual(swift_values.validate({**EXAMPLE, name: good}), [], good)
        for bad in [first + ",,https://b.example/x", first + ",https://",
                    first + ",https://RELAY-MAINNET.example:443/relay/", first + ",https://b.example/a b",
                    ",".join([first] + ["https://r%d.example/relay" % i for i in range(8)])]:
            problems = swift_values.validate({**EXAMPLE, name: bad})
            self.assertEqual([p[0] for p in problems], [name], bad)
            self.assertNotIn("example", problems[0][1])

    def test_a_relay_list_starts_with_the_relay_url_and_shares_no_relay_across_networks(self):
        name = "APP_CONFIG_OHTTP_RELAY_URLS_MAINNET"
        problems = swift_values.validate({**EXAMPLE, name: "https://b.example/x,%s"
                                          % EXAMPLE["APP_CONFIG_OHTTP_RELAY_URL_MAINNET"]})
        self.assertEqual(problems, [(name, "must list RELAY_URL_MAINNET first")])
        shared = EXAMPLE["APP_CONFIG_OHTTP_RELAY_URL_TESTNET"] + ",https://relay-b-mainnet.example/gateway"
        problems = swift_values.validate({**EXAMPLE, "APP_CONFIG_OHTTP_RELAY_URLS_TESTNET": shared})
        self.assertEqual(problems, [("APP_CONFIG_OHTTP_RELAY_URLS_TESTNET", "must share no relay with RELAY_URLS_MAINNET")])

    def test_a_relay_weights_key_in_either_case_is_accepted(self):
        name = "APP_CONFIG_OHTTP_RELAY_WEIGHTS_PUBKEY_TESTNET"
        self.assertEqual(swift_values.validate({**EXAMPLE, name: EXAMPLE[name].upper()}), [])

    def test_a_relay_weights_key_differs_from_every_signing_and_weights_key(self):
        def check(name, other, rule):
            for value in (EXAMPLE[other], EXAMPLE[other].upper()):
                problems = swift_values.validate({**EXAMPLE, name: value})
                self.assertEqual(len(problems), 1, (name, other))
                self.assertEqual(problems[0][0], name)
                self.assertIn(rule, problems[0][1])
                self.assertNotIn(value.lower(), problems[0][1].lower())
        for network in ("MAINNET", "TESTNET"):
            check("APP_CONFIG_OHTTP_RELAY_WEIGHTS_PUBKEY_%s" % network, "APP_CONFIG_OHTTP_SIGNING_PUBKEY_%s" % network,
                  "must differ from SIGNING_PUBKEY_%s" % network)
        testnet = "APP_CONFIG_OHTTP_RELAY_WEIGHTS_PUBKEY_TESTNET"
        for other in ("APP_CONFIG_OHTTP_RELAY_WEIGHTS_PUBKEY_MAINNET", "APP_CONFIG_OHTTP_SIGNING_PUBKEY_MAINNET"):
            check(testnet, other, other)
        check("APP_CONFIG_OHTTP_SIGNING_PUBKEY_TESTNET", "APP_CONFIG_OHTTP_RELAY_WEIGHTS_PUBKEY_MAINNET",
              "APP_CONFIG_OHTTP_RELAY_WEIGHTS_PUBKEY_MAINNET")

    def test_a_testnet_value_equal_to_a_mainnet_value_is_rejected(self):
        values = {**EXAMPLE, "APP_CONFIG_OHTTP_GATEWAY_HOST_TESTNET": EXAMPLE["APP_CONFIG_OHTTP_GATEWAY_HOST_MAINNET"]}
        problems = swift_values.validate(values)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], "APP_CONFIG_OHTTP_GATEWAY_HOST_TESTNET")
        self.assertIn("APP_CONFIG_OHTTP_GATEWAY_HOST_MAINNET", problems[0][1])
        relay = EXAMPLE["APP_CONFIG_OHTTP_RELAY_URL_MAINNET"].replace("relay-mainnet", "Relay-Mainnet")
        problems = swift_values.validate({**EXAMPLE, "APP_CONFIG_OHTTP_RELAY_URL_TESTNET": relay,
                                          "APP_CONFIG_OHTTP_RELAY_URLS_TESTNET": "https://relay-testnet.example/relay"})
        self.assertEqual(problems[0][0], "APP_CONFIG_OHTTP_RELAY_URL_TESTNET")
        self.assertIn("APP_CONFIG_OHTTP_RELAY_URL_MAINNET", problems[0][1])


def parse_arrays(source):
    arrays = []
    for line in source.splitlines():
        if "0x" not in line:
            continue
        inside = line[line.index("[0x") + 1:line.rindex("]")]
        arrays.append([int(part.strip(), 16) for part in inside.split(",")])
    return arrays


class EncodeTest(unittest.TestCase):
    def test_encode_round_trips_all_twelve_in_order(self):
        source = swift_values.encode(EXAMPLE)
        arrays = parse_arrays(source)
        key, rest = arrays[0], arrays[1:]
        self.assertEqual(len(rest), 12)
        decoded = [bytes(b ^ key[i % len(key)] for i, b in enumerate(array)).decode("utf-8") for array in rest]
        self.assertEqual(decoded, [EXAMPLE[name] for name in NAMES])
        for value in EXAMPLE.values():
            self.assertNotIn(value, source)

    def test_key_is_the_digest_of_the_domain_and_the_values(self):
        source = swift_values.encode(EXAMPLE)
        key_line = next(line for line in source.splitlines() if "static let key" in line)
        expected = hashlib.sha256(swift_values.KEY_DOMAIN + "\0".join(EXAMPLE[name] for name in NAMES).encode()).digest()
        self.assertEqual(bytes(parse_arrays(key_line)[0]), expected)

    def test_output_is_stable(self):
        self.assertEqual(swift_values.encode(EXAMPLE), swift_values.encode(dict(EXAMPLE)))

    def test_form_without_values(self):
        self.assertEqual(swift_values.encode(None), "\n".join([
            "// Generated by scripts/swift_values.py. Never edit it, and never commit a version that holds values.",
            "enum EncodedValues {",
            "    static let key: [UInt8] = []",
            "    static let mainnet: [[UInt8]]? = nil",
            "    static let testnet: [[UInt8]]? = nil",
            "}",
        ]) + "\n")


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.output = os.path.join(self.folder.name, "out", "EncodedValues.generated.swift")

    def test_release_mode_writes_both_networks(self):
        result = run(["generate", "--mode", "release", "--output", self.output], EXAMPLE)
        self.assertEqual(result.returncode, 0)
        with open(self.output, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), swift_values.encode(EXAMPLE))
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_release_mode_with_a_missing_value_writes_nothing_and_names_it(self):
        env = {n: v for n, v in EXAMPLE.items() if n != "APP_CONFIG_OHTTP_RELAY_URL_TESTNET"}
        result = run(["generate", "--mode", "release", "--output", self.output], env)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(os.path.exists(self.output))
        self.assertIn("error: APP_CONFIG_OHTTP_RELAY_URL_TESTNET: missing", result.stderr)
        for value in EXAMPLE.values():
            self.assertNotIn(value, result.stdout + result.stderr)

    def test_release_mode_with_an_invalid_value_never_prints_it(self):
        env = {**EXAMPLE, "APP_CONFIG_OHTTP_GATEWAY_HOST_MAINNET": "Secret-Host.example"}
        result = run(["generate", "--mode", "release", "--output", self.output], env)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(os.path.exists(self.output))
        self.assertIn("error: APP_CONFIG_OHTTP_GATEWAY_HOST_MAINNET: must be lower-case", result.stderr)
        self.assertNotIn("Secret-Host", result.stdout)
        self.assertNotIn("Secret-Host", result.stderr)

    def test_example_and_none_modes_ignore_the_environment(self):
        env = {"APP_CONFIG_OHTTP_GATEWAY_HOST_MAINNET": "other.example"}
        result = run(["generate", "--mode", "example", "--output", self.output], env)
        self.assertEqual(result.returncode, 0)
        with open(self.output, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), swift_values.encode(EXAMPLE))
        result = run(["generate", "--mode", "none", "--output", self.output], env)
        self.assertEqual(result.returncode, 0)
        with open(self.output, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), swift_values.encode(None))

    def test_example_env_prints_the_twelve_exports(self):
        result = run(["example-env"], {})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ["export %s='%s'" % (name, EXAMPLE[name]) for name in NAMES])


if __name__ == "__main__":
    unittest.main()
