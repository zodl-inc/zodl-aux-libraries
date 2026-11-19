// swift-tools-version:6.0
// Copyright © 2026 Znewco, Inc. (d/b/a Zcash Open Development Lab)
// SPDX-License-Identifier: AGPL-3.0-only
//
// This file is part of ZODL Aux Libraries.
//
// ZODL Aux Libraries is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License,
// version 3 only, as published by the Free Software Foundation.
//
// ZODL Aux Libraries is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
// Affero General Public License for more details.
//
// Commercial licensing: see COMMERCIAL-LICENSE.md.

import PackageDescription

// Development form. On main the generated file holds no values, so a build of main returns nil for both networks.
// A release tag carries a different Package.swift, written by scripts/release_manifest.py: one binary target
// whose XCFramework holds the values. Consume a release tag, never a branch.
let package = Package(
    name: "zodl-app-config",
    platforms: [.iOS(.v16), .macOS(.v14)],
    products: [.library(name: "ZodlAppConfig", targets: ["ZodlAppConfig"])],
    targets: [
        .target(name: "ZodlAppConfig"),
        .testTarget(name: "ZodlAppConfigTests", dependencies: ["ZodlAppConfig"])
    ]
)
