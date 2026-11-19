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

import java.util.Base64

plugins {
    kotlin("jvm") version "2.1.21"
    signing
    id("com.vanniktech.maven.publish") version "0.32.0"
}

group = providers.gradleProperty("GROUP").get()
version = providers.gradleProperty("VERSION_NAME").get()
val artifact = providers.gradleProperty("ARTIFACT_ID").get()
val repoUrl = providers.gradleProperty("REPO_URL").get()

kotlin { jvmToolchain(17) }

// AppConfig.kt is generated from config/schema.json and the APP_CONFIG_* environment (set in CI from AWS
// Secrets Manager). Nothing is read from a file with values; the generated source is never committed.
val generatedDir = layout.buildDirectory.dir("generated/appconfig/kotlin")
val generateConfig by tasks.registering(Exec::class) {
    inputs.file("config/schema.json")
    outputs.dir(generatedDir)
    outputs.upToDateWhen { false } // always regenerate from the current environment
    commandLine("python3", "scripts/appconfig.py", "kotlin", generatedDir.get().asFile.absolutePath)
}

sourceSets.main { kotlin.srcDir(generateConfig.map { generatedDir.get() }) }
tasks.named("compileKotlin") { dependsOn(generateConfig) }

mavenPublishing {
    coordinates(group.toString(), artifact, version.toString())
    publishToMavenCentral(com.vanniktech.maven.publish.SonatypeHost.CENTRAL_PORTAL)
    signAllPublications()
    pom {
        name.set("Zodl app config")
        description.set("Build-time configuration constants for the Zodl apps, generated in CI.")
        url.set(repoUrl)
        licenses { license { name.set("AGPL-3.0-only"); url.set("https://www.gnu.org/licenses/agpl-3.0.txt") } }
        developers { developer { id.set("zodl"); name.set("Zodl") } }
        scm {
            url.set(repoUrl)
            connection.set("scm:git:$repoUrl.git")
            developerConnection.set("scm:git:$repoUrl.git")
        }
    }
}

// The release environment's MAVEN_SIGNING_KEY_ASCII is the one the SDK release uses: an ASCII-armored key without a
// passphrase, base64-encoded. publish.yml passes it as signingKeyBase64. signingInMemoryKey (plain armored key) still
// works for local and test builds.
providers.gradleProperty("signingKeyBase64").orNull?.trim()?.takeIf { it.isNotEmpty() }?.let { encoded ->
    signing { useInMemoryPgpKeys(String(Base64.getMimeDecoder().decode(encoded)), "") }
}
