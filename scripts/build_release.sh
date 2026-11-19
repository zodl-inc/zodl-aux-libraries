#!/bin/bash
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

# Usage: scripts/build_release.sh VERSION OUTPUT_DIR [release|example]
#
# Everything a release needs except publishing: generates the values file (from the environment in release mode,
# from the public example values in example mode), builds the XCFramework, verifies it as a consumer, and writes
# OUTPUT_DIR/Package.swift, the manifest the release tag carries. It publishes and uploads nothing.
# GITHUB_REPOSITORY (OWNER/NAME, set by GitHub Actions) names the repository whose release will hold the zip.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$1"
OUT="$2"
MODE="${3:-release}"

if [ -z "${GITHUB_REPOSITORY:-}" ]; then
    echo "error: set GITHUB_REPOSITORY to OWNER/NAME, the repository whose GitHub release will hold the zip" >&2
    exit 1
fi

if [ "$MODE" = example ]; then
    eval "$(python3 "$ROOT/scripts/swift_values.py" example-env)"
elif [ "$MODE" != release ]; then
    echo "error: mode must be release or example" >&2
    exit 1
fi
python3 "$ROOT/scripts/swift_values.py" generate --mode "$MODE"
"$ROOT/scripts/build_xcframework.sh" "$OUT" "$VERSION"
"$ROOT/scripts/verify_release_package.sh" "$OUT/ZodlAppConfig.xcframework"
CHECKSUM="$(swift package compute-checksum "$OUT/ZodlAppConfig.xcframework.zip")"
python3 "$ROOT/scripts/release_manifest.py" --version "$VERSION" --checksum "$CHECKSUM" \
    --repository "$GITHUB_REPOSITORY" --output "$OUT/Package.swift"
echo "release $VERSION built in $OUT"
