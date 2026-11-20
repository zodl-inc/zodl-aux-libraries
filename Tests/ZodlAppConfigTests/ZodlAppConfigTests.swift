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

import Testing
@testable import ZodlAppConfig

@Suite struct ZodlAppConfigTests {
    let key: [UInt8] = (0..<32).map { UInt8(0xA0 + $0) }

    let example = AppConfig.Ohttp.NetworkValues(
        gatewayHost: "ohttp-gateway.example",
        relayURL: "https://relay-mainnet.example/relay",
        keysDNSName: "mainnet.ohttp-keys.example",
        signingPublicKey: "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        relayURLs: "https://relay-mainnet.example/relay|70,https://relay-b-mainnet.example/gateway|30"
    )

    func encoded(_ values: AppConfig.Ohttp.NetworkValues) -> [[UInt8]] {
        [values.gatewayHost, values.relayURL, values.keysDNSName, values.signingPublicKey, values.relayURLs].map { value in
            value.utf8.enumerated().map { index, byte in byte ^ key[index % key.count] }
        }
    }

    @Test func decodeRoundTripsFiveValuesInFieldOrder() {
        #expect(AppConfig.Ohttp.decode(key: key, network: encoded(example)) == example)
    }

    @Test func decodeReturnsNilForAnAbsentNetwork() {
        #expect(AppConfig.Ohttp.decode(key: key, network: nil) == nil)
    }

    @Test func decodeReturnsNilForTheWrongNumberOfValues() {
        let five = encoded(example)
        #expect(AppConfig.Ohttp.decode(key: key, network: Array(five.prefix(4))) == nil)
        #expect(AppConfig.Ohttp.decode(key: key, network: five + [five[0]]) == nil)
        #expect(AppConfig.Ohttp.decode(key: key, network: []) == nil)
    }

    @Test func decodeReturnsNilForAValueThatIsNotUTF8() {
        var network = encoded(example)
        network[2] = [0xFF ^ key[0]]
        #expect(AppConfig.Ohttp.decode(key: key, network: network) == nil)
    }

    @Test func theRelayListDefaultsToTheRelayURL() {
        let single = AppConfig.Ohttp.NetworkValues(
            gatewayHost: "g.example", relayURL: "https://r.example/relay", keysDNSName: "k.example", signingPublicKey: "00"
        )
        #expect(single.relayURLs == "https://r.example/relay")
    }

    @Test func decodeReturnsNilWithoutAKey() {
        #expect(AppConfig.Ohttp.decode(key: [], network: encoded(example)) == nil)
    }
}
