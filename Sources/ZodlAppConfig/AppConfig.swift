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
        /// The four values of one network.
        public struct NetworkValues: Sendable, Equatable {
            public let gatewayHost: String
            public let relayURL: String
            public let keysDNSName: String
            public let signingPublicKey: String

            public init(gatewayHost: String, relayURL: String, keysDNSName: String, signingPublicKey: String) {
                self.gatewayHost = gatewayHost
                self.relayURL = relayURL
                self.keysDNSName = keysDNSName
                self.signingPublicKey = signingPublicKey
            }
        }

        public static let mainnet: NetworkValues? = decode(key: EncodedValues.key, network: EncodedValues.mainnet)
        public static let testnet: NetworkValues? = decode(key: EncodedValues.key, network: EncodedValues.testnet)

        /// Decodes one network as `scripts/swift_values.py` writes it: four values in the order gateway host, relay URL,
        /// keys DNS name and signing public key, each value's UTF-8 bytes XORed with the key, byte `i` with
        /// `key[i % key.count]`. Nil when the network is absent, the key is empty, there are not exactly four values, or
        /// a value does not decode to UTF-8.
        static func decode(key: [UInt8], network: [[UInt8]]?) -> NetworkValues? {
            guard let network, network.count == 4, !key.isEmpty else {
                return nil
            }
            let values = network.compactMap { value in
                String(bytes: value.enumerated().map { index, byte in byte ^ key[index % key.count] }, encoding: .utf8)
            }
            guard values.count == 4 else {
                return nil
            }
            return NetworkValues(
                gatewayHost: values[0],
                relayURL: values[1],
                keysDNSName: values[2],
                signingPublicKey: values[3]
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
