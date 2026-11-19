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

# Usage: scripts/publish_release.sh VERSION RELEASE_DIR
#
# Publishes what scripts/build_release.sh left in RELEASE_DIR: commits its Package.swift on a release-only commit
# (never on a branch), tags it VERSION, pushes the tag, creates the GitHub release with the XCFramework zip and
# checks that the published zip is the one the manifest names. Needs GH_TOKEN and GITHUB_REPOSITORY; the manifest
# must name the zip of this version in GITHUB_REPOSITORY's release.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$1"
RELEASE="$(cd "$2" && pwd)"
ASSET=ZodlAppConfig.xcframework.zip
URL="https://github.com/${GITHUB_REPOSITORY}/releases/download/${VERSION}/${ASSET}"
REMOTE="${RELEASE_REMOTE:-https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git}"

checksum() {
    shasum -a 256 "$1" | cut -d ' ' -f 1
}

if ! grep -q -F "url: \"$URL\"," "$RELEASE/Package.swift"; then
    echo "error: $RELEASE/Package.swift does not name $URL" >&2
    exit 1
fi
if ! grep -q "checksum: \"$(checksum "$RELEASE/$ASSET")\"" "$RELEASE/Package.swift"; then
    echo "error: $RELEASE/Package.swift does not name the checksum of $RELEASE/$ASSET" >&2
    exit 1
fi

cd "$ROOT"
git config user.name "zodl-app-config CI"
git config user.email "noreply@zodl.com"
git checkout --quiet --detach
# The release holds the values in the XCFramework only. Its commit has no sources, so the generated values file
# of this working tree is never committed.
git rm -r --quiet --force Sources Tests
cp "$RELEASE/Package.swift" Package.swift
git add Package.swift
git commit --quiet -m "Release $VERSION"
if git ls-tree -r --name-only HEAD | grep -q -E '^(Sources|Tests)/'; then
    echo "error: the release commit still has sources" >&2
    exit 1
fi
git tag "$VERSION"
git push --quiet "$REMOTE" "refs/tags/$VERSION"

gh release create "$VERSION" "$RELEASE/$ASSET" --repo "$GITHUB_REPOSITORY" --verify-tag --title "$VERSION" \
    --notes "App config $VERSION. Swift: pin this version exactly. Android: com.zodl.android:app-config:$VERSION."

DOWNLOAD="$(mktemp -d)"
trap 'rm -rf "$DOWNLOAD"' EXIT
gh release download "$VERSION" --repo "$GITHUB_REPOSITORY" --pattern "$ASSET" --dir "$DOWNLOAD"
if ! grep -q "checksum: \"$(checksum "$DOWNLOAD/$ASSET")\"" Package.swift; then
    echo "error: the published $ASSET differs from the one the manifest names" >&2
    exit 1
fi
echo "published $VERSION"
