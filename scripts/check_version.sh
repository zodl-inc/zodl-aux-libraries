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

# Usage: scripts/check_version.sh VERSION
#
# Preflight of a release: the version is X.Y.Z, equals VERSION_NAME of gradle.properties and is not a tag yet.
# Needs GH_TOKEN and GITHUB_REPOSITORY, unless RELEASE_REMOTE names the git remote.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1-}"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "error: the version must be X.Y.Z with digits only" >&2
    exit 1
fi

GRADLE_VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | sed -n 1p)"
if [ "$VERSION" != "$GRADLE_VERSION" ]; then
    echo "error: the version differs from VERSION_NAME in gradle.properties ($GRADLE_VERSION)" >&2
    exit 1
fi

REMOTE="${RELEASE_REMOTE:-https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git}"
status=0
git ls-remote --exit-code --tags "$REMOTE" "refs/tags/$VERSION" > /dev/null 2>&1 || status=$?
if [ "$status" -eq 0 ]; then
    echo "error: the tag $VERSION already exists" >&2
    exit 1
elif [ "$status" -ne 2 ]; then
    echo "error: could not list the tags of the repository" >&2
    exit 1
fi
echo "version $VERSION is free"
