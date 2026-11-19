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

# Usage: scripts/select_xcode.sh
#
# Prints DEVELOPER_DIR=<directory> of the Xcode named in .xcode-version, for $GITHUB_ENV. Releases are built with
# that Xcode, so the file must never name an Xcode newer than the one the apps build with.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/.xcode-version")"
DEVELOPER="${XCODE_APPLICATIONS_DIR:-/Applications}/Xcode_${VERSION}.app/Contents/Developer"

if [ ! -d "$DEVELOPER" ]; then
    echo "error: Xcode $VERSION, named in .xcode-version, is not installed here ($DEVELOPER)" >&2
    exit 1
fi
echo "DEVELOPER_DIR=$DEVELOPER"
