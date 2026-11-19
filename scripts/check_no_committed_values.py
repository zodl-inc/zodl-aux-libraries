#!/usr/bin/env python3
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

"""Repository guards, run on every pull request (job no-committed-values):

1. No value is committed: the generated Swift file must be exactly the form without values
   (swift_values.encode(None)) and no Kotlin source may be tracked (the Android AppConfig.kt is generated in the
   build), nor a built artifact (XCFramework, zip, class, jar other than the Gradle wrapper). Values exist only in
   CI-built artifacts.
2. No workflow reads a GitHub-stored secret: values and credentials come from AWS Secrets Manager through OIDC
   (zodl-inc/actions/aws-secrets). Any reference to the `secrets` context (any case, `secrets.X`, `secrets['X']`,
   `toJSON(secrets)`, `secrets.GITHUB_TOKEN` included; use `github.token`) and `secrets: inherit` fail.
   This is a guard against accidents, not the security boundary: the repository has no GitHub secrets at all.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swift_values  # noqa: E402

SWIFT = "Sources/ZodlAppConfig/EncodedValues.generated.swift"
SECRETS_CONTEXT = re.compile(r"(?<![\w-])secrets\s*(\.|\[|\)|,|\}\}|[=!]=|&&|\|\|)", re.IGNORECASE)
SECRETS_INHERIT = re.compile(r"(?<![\w-])secrets\s*:\s*inherit\b", re.IGNORECASE)
# Built artifacts that would carry values. The Gradle wrapper jar is the one tracked binary.
ARTIFACT = re.compile(r"(\.xcframework/|\.(xcframework|zip|class|jar|kt)$)")
WRAPPER = "gradle/wrapper/gradle-wrapper.jar"
# Inside an expression (${{ ... }}, or the bare condition of an if:), any standalone `secrets` identifier is a read.
EXPRESSION = re.compile(r"\$\{\{(.*?)(\}\}|$)")
BARE_IF = re.compile(r"^\s*(-\s+)?if\s*:(.*)$")
SECRETS_WORD = re.compile(r"(?<![\w.-])secrets(?![\w-])", re.IGNORECASE)


def secret_references(text):
    """Return the 1-based numbers of the lines of a workflow that read the secrets context."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        # Comments are not skipped: inside a run block a '#' is shell text and an expression there is expanded.
        expressions = [m.group(1) for m in EXPRESSION.finditer(line)]
        bare_if = BARE_IF.match(line)
        if bare_if:
            expressions.append(bare_if.group(2))
        if (SECRETS_CONTEXT.search(line) or SECRETS_INHERIT.search(line)
                or any(SECRETS_WORD.search(e) for e in expressions)):
            found.append(number)
    return found


def main() -> int:
    errors = []
    try:
        with open(SWIFT) as fh:
            current = fh.read()
    except OSError:
        current = None
    if current != swift_values.encode(None):
        errors.append(f"{SWIFT}: must be the form without values (python3 scripts/swift_values.py generate --mode none)")
    listed = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True).stdout
    tracked = [path for path in listed.split("\0") if path]
    for path in tracked:
        if (ARTIFACT.search(path) and path != WRAPPER) or path.startswith("generated/") or "/generated/" in path:
            errors.append(f"{path}: generated source must not be tracked")
        if path.startswith(".github/") and path.endswith((".yml", ".yaml")):
            with open(path) as fh:
                for number in secret_references(fh.read()):
                    errors.append(f"{path}:{number}: no GitHub secrets here; read it from AWS "
                                  "(zodl-inc/actions/aws-secrets, OIDC), or use github.token")
    for e in errors:
        print(e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
