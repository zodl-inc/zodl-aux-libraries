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

import Foundation

/// The build-time configuration this build of the package carries.
public enum AppConfig {
    /// The ohttp group. A release carries both networks; a build of `main` carries none.
    public enum Ohttp {
        /// The values of one network.
        public struct NetworkValues: Sendable, Equatable {
            public let gatewayHost: String
            /// One relay URL, for SDKs that take a single relay.
            public let relayURL: String
            public let keysDNSName: String
            public let signingPublicKey: String
            /// The relays, relay URLs separated by `,`, `relayURL` first: the relay URL value of SDKs on
            /// zodl-ohttp-client 2.2.0 or later, which split the requests between the relays equally.
            public let relayURLs: String
            /// The raw Ed25519 public key, 64 hex digits, of the network's relay weights block: pass it to
            /// `OhttpConfig::with_relay_weights_key` (zodl-ohttp-client 2.5.0 or later). Empty means the SDK reads no
            /// block and the relays keep equal shares.
            public let relayWeightsPublicKey: String

            /// `relayURLs` defaults to `relayURL` alone, `relayWeightsPublicKey` to empty (no relay weights key).
            public init(
                gatewayHost: String,
                relayURL: String,
                keysDNSName: String,
                signingPublicKey: String,
                relayURLs: String? = nil,
                relayWeightsPublicKey: String = ""
            ) {
                self.gatewayHost = gatewayHost
                self.relayURL = relayURL
                self.keysDNSName = keysDNSName
                self.signingPublicKey = signingPublicKey
                self.relayURLs = relayURLs ?? relayURL
                self.relayWeightsPublicKey = relayWeightsPublicKey
            }
        }

        public static let mainnet: NetworkValues? = decode(key: EncodedValues.key, network: EncodedValues.mainnet)
        public static let testnet: NetworkValues? = decode(key: EncodedValues.key, network: EncodedValues.testnet)

        /// Decodes one network as `scripts/swift_values.py` writes it: six values in the order gateway host, relay URL,
        /// keys DNS name, signing public key, relay list and relay weights public key, each value's UTF-8 bytes XORed with the key, byte `i` with
        /// `key[i % key.count]`. Nil when the network is absent, the key is empty, there are not exactly six values, or
        /// a value does not decode to UTF-8.
        static func decode(key: [UInt8], network: [[UInt8]]?) -> NetworkValues? {
            guard let network, network.count == 6, !key.isEmpty else {
                return nil
            }
            let values = network.compactMap { value in
                String(bytes: value.enumerated().map { index, byte in byte ^ key[index % key.count] }, encoding: .utf8)
            }
            guard values.count == 6 else {
                return nil
            }
            return NetworkValues(
                gatewayHost: values[0],
                relayURL: values[1],
                keysDNSName: values[2],
                signingPublicKey: values[3],
                relayURLs: values[4],
                relayWeightsPublicKey: values[5]
            )
        }
    }

    /// The near group. A release carries the fee recipient; a build of `main` carries none.
    public enum Near {
        public static let feeRecipient: String? = decode(key: EncodedValues.key, value: EncodedValues.near)

        /// Decodes the fee recipient as `scripts/swift_values.py` writes it: exactly one value, its UTF-8 bytes XORed
        /// with the key, byte `i` with `key[i % key.count]`. Nil when the value is absent, the key is empty, there is
        /// not exactly one value, or the value does not decode to UTF-8.
        static func decode(key: [UInt8], value: [[UInt8]]?) -> String? {
            guard let value, value.count == 1, !key.isEmpty else {
                return nil
            }
            return String(bytes: value[0].enumerated().map { index, byte in byte ^ key[index % key.count] }, encoding: .utf8)
        }
    }
}
