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
            url: "https://github.com/zodl-inc/zodl-aux-libraries/releases/download/1.1.0/ZodlAppConfig.xcframework.zip",
            checksum: "a4a4d1141efeb04ea8e4b4e15d9acad8326b86fcb5fbbe33babaa5aeb36cd01c"
        )
    ]
)
