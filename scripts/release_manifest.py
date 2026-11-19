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

"""Write the release form of Package.swift for zodl-app-config."""

import argparse
import re
import sys

TEMPLATE = """// swift-tools-version:6.0
import PackageDescription

// Release form, written by scripts/release_manifest.py. The XCFramework holds the values.
let package = Package(
    name: "zodl-app-config",
    platforms: [.iOS(.v16), .macOS(.v14)],
    products: [.library(name: "ZodlAppConfig", targets: ["ZodlAppConfig"])],
    targets: [
        .binaryTarget(
            name: "ZodlAppConfig",
%s
        )
    ]
)
"""

# The repository whose GitHub release holds the zip: the one the Publish workflow runs in (GITHUB_REPOSITORY).
URL = "https://github.com/%s/releases/download/%s/ZodlAppConfig.xcframework.zip"


def render(version, checksum, repository):
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        raise ValueError("version must be X.Y.Z with digits only")
    if re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
        raise ValueError("checksum must be 64 lower-case hex digits")
    if re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repository) is None:
        raise ValueError("repository must be OWNER/NAME")
    lines = '            url: "%s",\n            checksum: "%s"' % (URL % (repository, version), checksum)
    return TEMPLATE % lines


def render_local(path):
    if path == "" or any(c in path for c in ('"', "\\", "\n", "\r")):
        raise ValueError("path must not be empty or contain a quote, a backslash or a newline")
    return TEMPLATE % ('            path: "%s"' % path)


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--version")
    parser.add_argument("--checksum")
    parser.add_argument("--repository")
    parser.add_argument("--local-path")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        release = (args.version, args.checksum, args.repository)
        if args.local_path is not None and release == (None, None, None):
            text = render_local(args.local_path)
        elif None not in release and args.local_path is None:
            text = render(*release)
        else:
            raise ValueError("give either --version, --checksum and --repository, or --local-path")
    except ValueError as error:
        print("error: %s" % error, file=sys.stderr)
        return 1
    with open(args.output, "w") as handle:
        handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
