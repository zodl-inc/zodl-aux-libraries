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

# Usage: scripts/build_xcframework.sh OUTPUT_DIR [VERSION]
#
# Compiles Sources/ZodlAppConfig into a static Swift framework for iOS, the iOS Simulator and macOS (arm64 only)
# and packs them as OUTPUT_DIR/ZodlAppConfig.xcframework and OUTPUT_DIR/ZodlAppConfig.xcframework.zip.
# It builds whatever EncodedValues.generated.swift holds, with the Xcode that DEVELOPER_DIR or xcode-select names.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCES="$ROOT/Sources/ZodlAppConfig"
OUT="$1"
VERSION="${2:-0.0.0}"
NAME=ZodlAppConfig

rm -rf "$OUT"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
xcodebuild -version | sed -n 1p

write_plist() { # path platform minimum-version-key minimum-version
    cat > "$1" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>$NAME</string>
    <key>CFBundleIdentifier</key>
    <string>co.zodl.$NAME</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$NAME</string>
    <key>CFBundlePackageType</key>
    <string>FMWK</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleSupportedPlatforms</key>
    <array>
        <string>$2</string>
    </array>
    <key>$3</key>
    <string>$4</string>
</dict>
</plist>
PLIST
}

build_slice() { # sdk target interface-name directory
    local framework="$OUT/$4/$NAME.framework"
    mkdir -p "$framework/Modules/$NAME.swiftmodule" "$OUT/$4/intermediates"
    xcrun --sdk "$1" swiftc -parse-as-library -module-name "$NAME" -target "$2" -O -swift-version 6 \
        -enable-library-evolution -emit-library -static -o "$framework/$NAME" \
        -emit-module -emit-module-path "$OUT/$4/intermediates/$NAME.swiftmodule" \
        -emit-module-interface-path "$framework/Modules/$NAME.swiftmodule/$3.swiftinterface" \
        "$SOURCES"/*.swift
}

build_slice iphoneos arm64-apple-ios16.0 arm64-apple-ios ios
write_plist "$OUT/ios/$NAME.framework/Info.plist" iPhoneOS MinimumOSVersion 16.0
build_slice iphonesimulator arm64-apple-ios16.0-simulator arm64-apple-ios-simulator simulator
write_plist "$OUT/simulator/$NAME.framework/Info.plist" iPhoneSimulator MinimumOSVersion 16.0
build_slice macosx arm64-apple-macos14.0 arm64-apple-macos macos

# A macOS framework is a versioned bundle: Xcode refuses a shallow one when it embeds it.
MACOS="$OUT/macos/$NAME.framework"
mkdir -p "$MACOS/Versions/A/Resources"
mv "$MACOS/$NAME" "$MACOS/Versions/A/$NAME"
mv "$MACOS/Modules" "$MACOS/Versions/A/Modules"
write_plist "$MACOS/Versions/A/Resources/Info.plist" MacOSX LSMinimumSystemVersion 14.0
ln -sfn A "$MACOS/Versions/Current"
ln -sfn "Versions/Current/$NAME" "$MACOS/$NAME"
ln -sfn Versions/Current/Modules "$MACOS/Modules"
ln -sfn Versions/Current/Resources "$MACOS/Resources"

xcodebuild -create-xcframework \
    -framework "$OUT/ios/$NAME.framework" \
    -framework "$OUT/simulator/$NAME.framework" \
    -framework "$OUT/macos/$NAME.framework" \
    -output "$OUT/$NAME.xcframework" > /dev/null
(cd "$OUT" && ditto -c -k --sequesterRsrc --keepParent "$NAME.xcframework" "$NAME.xcframework.zip")
echo "built $OUT/$NAME.xcframework.zip"
