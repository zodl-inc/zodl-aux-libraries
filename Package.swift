// swift-tools-version:6.0
import PackageDescription

// Release form, written by scripts/release_manifest.py. The XCFramework holds the values.
let package = Package(
    name: "zodl-app-config",
    platforms: [.iOS(.v16), .macOS(.v14)],
    products: [.library(name: "ZodlAppConfig", targets: ["ZodlAppConfig"])],
    targets: [
        .binaryTarget(
            name: "ZodlAppConfig",
            url: "https://github.com/zodl-inc/zodl-aux-libraries/releases/download/1.0.0/ZodlAppConfig.xcframework.zip",
            checksum: "c246b2348b98d0d242b03f0706d3b8994041fc5c1d9a8e632736c70c83077086"
        )
    ]
)
