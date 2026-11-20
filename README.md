# Zodl app config

Tiny package, published for both platforms from one CI run, that carries build-time configuration for the Zodl apps:
today one group, `ohttp`, with 10 values (gateway host, relay URL, keys DNS name, signing public key and relay
list, for mainnet and testnet; all 10 are required). There is no runtime code besides the Swift decoder. The repository holds code and
names only; the values exist only in the published artifacts.

- Android: Maven artifact `com.zodl.android:app-config` on Maven Central, so public F-Droid (which only accepts
  allowlisted repositories) can resolve it. Kotlin object `com.zodl.appconfig.AppConfig.Ohttp`, one `const val` per
  key, for example `AppConfig.Ohttp.GATEWAY_HOST_MAINNET`.
- iOS and macOS: Swift package `ZodlAppConfig`, a binary XCFramework attached to the GitHub release of each version.

The libraries the apps use stay free of configuration: the apps depend on this package and pass the values to them at
startup.

## Design notes
- One published dependency carries the values for every build of the apps (store, FOSS and F-Droid builds alike), so
  there is one source of values and no per-workflow secret handling, and F-Droid builds get the same configuration.
- Anything published here is public and permanent, like any value that ships inside an app. Access control for any
  service belongs on the server side, never in this package.

## Android artifact
`config/schema.json` lists the groups and keys, names only. `scripts/appconfig.py kotlin`, run by the Gradle task
`generateConfig`, writes `AppConfig.kt` into the build directory from the environment variables
`APP_CONFIG_<GROUP>_<KEY>`; the generated source is never committed. A group marked `required` needs every key. Values
are printable ASCII without quotes, backslashes or `$`, and the `ohttp` values must also pass the rules of
`scripts/swift_values.py` that the Swift release applies, so both platforms accept the same values. Errors name the
variable, never the value.

```kotlin
import com.zodl.appconfig.AppConfig

AppConfig.Ohttp.GATEWAY_HOST_MAINNET // also RELAY_URL_, KEYS_DNS_NAME_, SIGNING_PUBKEY_, RELAY_URLS_ for _MAINNET and _TESTNET
```

`RELAY_URLS_<NETWORK>` lists the relays of a network, relay URLs separated by `,` (each after the first starting
`https://`; at most 8, no relay twice), `RELAY_URL_<NETWORK>` first and no relay shared with the other network. It is
the relay URL value for SDKs on `zodl-ohttp-client` 2.2.0 or later, which split the requests between the relays
equally and fail over to another while one fails; `RELAY_URL_<NETWORK>` stays the single relay for older SDKs (a list
is a configuration error there). The order is significant: the first relay is the stable one and the source of the
signed key configuration, and relays fail over in list order.

## Swift package
Product `ZodlAppConfig`, for iOS 16 and macOS 14, arm64 only (devices, the simulator on Apple silicon, and Mac).

```swift
import ZodlAppConfig

AppConfig.Ohttp.mainnet // AppConfig.Ohttp.NetworkValues?: gatewayHost, relayURL, keysDNSName, signingPublicKey, relayURLs
AppConfig.Ohttp.testnet
```

Pin an exact release version, never a branch:

```swift
.package(url: "https://github.com/zodl-inc/zodl-aux-libraries", exact: "X.Y.Z")
```

- A release tag holds one binary target. Its XCFramework carries the ten values XOR-encoded, so none appears as plain
  text in the binary or in an app. Every release carries both networks.
- `main` holds no values. `Sources/ZodlAppConfig/EncodedValues.generated.swift` is committed in its form without
  values, so a build of `main` returns nil for both networks. `python3 scripts/swift_values.py generate --mode example`
  writes public example values for local tests, and `--mode none` restores the committed form.
- Xcode rule: a release works with the Xcode that built it and with every newer one. `.xcode-version` names the Xcode
  the workflows build with. Raise it on purpose, and never above the Xcode the apps are built with.

## Release
Manual `Publish` workflow on `main` with the input `version` (`X.Y.Z`). It must equal `VERSION_NAME` in
`gradle.properties`, so bump that file first, in a pull request. The workflow runs in the environment `release`
(limited to `main`, set up in `zodl-inc/github-config`). The 10 values and the Maven credentials are read from AWS by
`zodl-inc/actions/aws-secrets`; nothing is stored on GitHub. In that environment the values are named
`APP_CONFIG_OHTTP_<KEY>`, for example `APP_CONFIG_OHTTP_RELAY_URL_MAINNET`. Three jobs run in order:

1. `preflight` checks the version (its form, that it equals `VERSION_NAME`, that it is not a tag yet), checks the real
   values against the Android rules too, and rehearses the whole Swift release with them. It publishes nothing.
2. `publish-android` reads the names from `config/schema.json` (`scripts/appconfig.py env-names`), uploads
   `com.zodl.android:app-config` to Maven Central and waits up to 60 minutes until Central serves the POM. It pushes no
   tag. `MAVEN_SIGNING_KEY_ASCII` is the SDK release's key: ASCII-armored without a passphrase, then base64-encoded.
3. `publish-ios` builds the XCFramework, pushes the tag `X.Y.Z` on a release-only commit and creates the GitHub release
   with `ZodlAppConfig.xcframework.zip`. The release-only commit is never on a branch: its `Package.swift` names the
   zip, as an asset of the release in the repository the workflow runs in, and its checksum, and it has no sources.
   Before that it checks that its values have the digest that `publish-android` published, so both platforms of a
   version carry the same values.
   The tag and the release are written with a short-lived token of the `zodl-release-bot` app (contents write on this
   repository only), the one non-maintainer the release tag ruleset lets create `X.Y.Z` tags; its id and key come from
   AWS like the values.

The tag is pushed only after Android is published, right before the GitHub release is created. Maven Central versions
are immutable: any change of a value is a new version, then bump `ZODL_APP_CONFIG_VERSION` in the Android app and the
pinned version in the iOS project.

Only one `Publish` runs at a time. If `publish-android` gives up waiting and Central publishes later, re-run that job:
on a re-run it skips the upload when the version is already on Central and only waits, then `publish-ios` runs.

If `publish-ios` fails after `publish-android` succeeded:
- A transient failure: re-run only the failed job. If the run got as far as the tag or the GitHub release, a
  maintainer deletes both first.
- A failure that needs a fix on `main`: bump `VERSION_NAME`, merge, and run `Publish` again with the new version. A
  re-run would use the old commit, and a new run of the old version stops at "already on Maven Central". The Maven
  artifact of the failed version stays without a Swift release.

## Adding a value
1. Add the key to `config/schema.json` (or a new group, which reaches Android only). `publish-android` reads every
   schema name, so each needs its mapping in step 2; `required: false` only lets the Kotlin generator accept an empty
   value. A new `ohttp` key also needs
   `scripts/swift_values.py` (names and rules) and the Swift API in `Sources/ZodlAppConfig/AppConfig.swift`; the tests
   fail while the schema and `swift_values.NAMES` differ. Then `python3 scripts/swift_values.py generate --mode none`
   keeps the committed Swift file in its form without values.
2. Map `APP_CONFIG_<GROUP>_<KEY>` for the `release` environment in `zodl-inc/github-config`, pointing at the existing
   Secrets Manager entry. The Swift jobs of `publish.yml` list the ten `ohttp` names themselves.
3. Bump `VERSION_NAME` in `gradle.properties`, merge, run `Publish`, then bump the version in the apps.

Anything published here is public and permanent. Only put values here that already ship inside the apps; access
control for any service belongs on the server side, never in this artifact.

## Checks (PR)
`android-tests`, `swift-tests`, `xcframework-dry-run`, `python-tests`, `no-committed-values` (see
`.github/workflows/test.yml`); these names are the required checks in `zodl-inc/github-config`. `android-tests`
publishes to Maven local with the public example values and a throwaway signing key. `no-committed-values` fails when
the Swift values file is not its form without values, when a Kotlin source is tracked, or when a workflow reads the
GitHub `secrets` context (a guard against accidents; the repository has no GitHub secrets). `xcframework-dry-run`
builds a release with public example values and keeps its zip as a workflow artifact, so the framework can be checked
with a newer Xcode.

The same dry run on a Mac: `GITHUB_REPOSITORY=zodl-inc/zodl-aux-libraries scripts/build_release.sh 0.0.0 .build-release example`.
`GITHUB_REPOSITORY` names the repository whose release the manifest points at; GitHub Actions sets it.

## License

Copyright © 2026 Znewco, Inc. (d/b/a Zcash Open Development Lab)

ZODL Aux Libraries is free software, licensed under the GNU Affero General Public License, version 3 only
(AGPL-3.0-only). See [LICENSE](LICENSE). The published artifacts (the Maven artifact and the Swift package) carry the
same license. Source files carry the header `SPDX-License-Identifier: AGPL-3.0-only`; generated files do not.

In short: you may use, study, modify, and redistribute ZODL Aux Libraries, but if you incorporate it into an
application, the complete source of that application must be made available under the AGPL to its users, including
users who interact with it over a network.

If those terms don't fit your project, **commercial licenses are available**; see
[COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md). Official ZODL builds distributed through the Apple App Store are
released by Znewco under separate terms; no App Store distribution permission is granted to AGPL licensees; see
[LICENSE-EXCEPTIONS.md](LICENSE-EXCEPTIONS.md).
