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
            /// The relays with their weights, `URL|WEIGHT` entries separated by `,`, `relayURL` first: the relay URL
            /// value of SDKs on zodl-ohttp-client 2.2.0 or later, which split the requests between the relays by weight.
            public let relayURLs: String

            /// `relayURLs` defaults to `relayURL` alone.
            public init(
                gatewayHost: String,
                relayURL: String,
                keysDNSName: String,
                signingPublicKey: String,
                relayURLs: String? = nil
            ) {
                self.gatewayHost = gatewayHost
                self.relayURL = relayURL
                self.keysDNSName = keysDNSName
                self.signingPublicKey = signingPublicKey
                self.relayURLs = relayURLs ?? relayURL
            }
        }

        public static let mainnet: NetworkValues? = decode(key: EncodedValues.key, network: EncodedValues.mainnet)
        public static let testnet: NetworkValues? = decode(key: EncodedValues.key, network: EncodedValues.testnet)

        /// Decodes one network as `scripts/swift_values.py` writes it: five values in the order gateway host, relay URL,
        /// keys DNS name, signing public key and relay list, each value's UTF-8 bytes XORed with the key, byte `i` with
        /// `key[i % key.count]`. Nil when the network is absent, the key is empty, there are not exactly five values, or
        /// a value does not decode to UTF-8.
        static func decode(key: [UInt8], network: [[UInt8]]?) -> NetworkValues? {
            guard let network, network.count == 5, !key.isEmpty else {
                return nil
            }
            let values = network.compactMap { value in
                String(bytes: value.enumerated().map { index, byte in byte ^ key[index % key.count] }, encoding: .utf8)
            }
            guard values.count == 5 else {
                return nil
            }
            return NetworkValues(
                gatewayHost: values[0],
                relayURL: values[1],
                keysDNSName: values[2],
                signingPublicKey: values[3],
                relayURLs: values[4]
            )
        }
    }
}
