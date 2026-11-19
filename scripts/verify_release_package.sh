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

# Usage: scripts/verify_release_package.sh PATH/TO/ZodlAppConfig.xcframework
#
# Assembles the release form of the package around the given XCFramework and uses it as an app would:
# a consumer compares the package's values with the eight APP_CONFIG_OHTTP_* of the environment, then builds and links
# for iOS, the iOS Simulator and macOS (arm64). It prints names only, never a value.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
XCFRAMEWORK="$(cd "$1" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/package" "$WORK/consumer/Sources/verify-values" "$WORK/consumer/Sources/VerifyLinks"
cp -R "$XCFRAMEWORK" "$WORK/package/ZodlAppConfig.xcframework"
python3 "$ROOT/scripts/release_manifest.py" --local-path ZodlAppConfig.xcframework --output "$WORK/package/Package.swift"

cat > "$WORK/consumer/Package.swift" <<'SWIFT'
// swift-tools-version:6.0
import PackageDescription

let package = Package(
    name: "consumer",
    platforms: [.iOS(.v16), .macOS(.v14)],
    products: [.library(name: "VerifyLinks", type: .dynamic, targets: ["VerifyLinks"])],
    dependencies: [.package(name: "zodl-app-config", path: "../package")],
    targets: [
        .executableTarget(
            name: "verify-values",
            dependencies: [.product(name: "ZodlAppConfig", package: "zodl-app-config")]
        ),
        .target(name: "VerifyLinks", dependencies: [.product(name: "ZodlAppConfig", package: "zodl-app-config")])
    ]
)
SWIFT

cat > "$WORK/consumer/Sources/verify-values/main.swift" <<'SWIFT'
import Foundation
import ZodlAppConfig

func differences(_ network: String, _ values: AppConfig.Ohttp.NetworkValues?) -> [String] {
    let fields: [(String, String?)] = [
        ("GATEWAY_HOST", values?.gatewayHost),
        ("RELAY_URL", values?.relayURL),
        ("KEYS_DNS_NAME", values?.keysDNSName),
        ("SIGNING_PUBKEY", values?.signingPublicKey)
    ]
    return fields.compactMap { field, value in
        let name = "APP_CONFIG_OHTTP_\(field)_\(network)"
        let expected = ProcessInfo.processInfo.environment[name] ?? ""
        return !expected.isEmpty && value == expected ? nil : name
    }
}

let differing = differences("MAINNET", AppConfig.Ohttp.mainnet) + differences("TESTNET", AppConfig.Ohttp.testnet)
if differing.isEmpty {
    print("values match")
} else {
    print("values differ: " + differing.joined(separator: ", "))
    exit(1)
}
SWIFT

cat > "$WORK/consumer/Sources/VerifyLinks/VerifyLinks.swift" <<'SWIFT'
import ZodlAppConfig

public func hasMainnetValues() -> Bool {
    AppConfig.Ohttp.mainnet != nil
}
SWIFT

cd "$WORK/consumer"
swift run verify-values

for destination in "generic/platform=iOS" "generic/platform=iOS Simulator" "generic/platform=macOS"; do
    echo "linking for $destination"
    if ! xcodebuild build -scheme VerifyLinks -destination "$destination" -derivedDataPath "$WORK/derived-data" \
        -skipMacroValidation CODE_SIGNING_ALLOWED=NO ARCHS=arm64 > "$WORK/xcodebuild.log" 2>&1; then
        grep -E "error:|BUILD FAILED" "$WORK/xcodebuild.log" >&2 || tail -20 "$WORK/xcodebuild.log" >&2
        exit 1
    fi
    rm -rf "$WORK/derived-data"
done
echo "release package verified"
