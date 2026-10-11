package com.vico.simulator.sound

import com.vico.simulator.vehicle.CurrentVehicleCatalog
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.security.MessageDigest

/** JVM fixture adapter reads real manifests without Android's JSONObject stubs. */
internal object ProfileBankFixtures {
    private val assets = File("app/src/main/assets").takeIf { it.isDirectory } ?: File("src/main/assets")
    fun loaded(vehicleKey: String): MatlabSoundBank {
        val root = "s12_v10/$vehicleKey"
        val reader = BankArtifactReader { File(assets, it).readBytes() }
        val manifest = reader.read("$root/manifest.json").toString(Charsets.UTF_8)
        fun number(key: String): Double = Regex(""""$key"\s*:\s*([-+0-9.eE]+)""")
            .find(manifest)!!.groupValues[1].toDouble()
        val ratios = Regex(""""gear_ratios"\s*:\s*\[([^]]+)]""")
            .find(manifest)!!.groupValues[1].split(',').map { it.trim().toDouble() }.toDoubleArray()
        val spec = MatlabPowertrainSpec(
            number("idle_rpm"), number("redline_rpm"), ratios,
            number("final_drive"), number("wheel_radius_m"), number("launch_rpm"), number("shift_rpm"),
            number("shift_attack_s"), number("shift_hold_s"), number("shift_recovery_s"), number("shift_settle_s"),
            number("shift_min_torque"), number("shift_reengage_gain"), number("minimum_shift_interval_s"),
            number("downshift_ratio"), number("speed_ceiling_kmh"), number("afterfire_minimum_rpm"),
        )
        val files = Regex(""""file"\s*:\s*"([^"]+\.wav)"""").findAll(manifest)
            .map { it.groupValues[1] }.toList()
        assertTrue(files.isNotEmpty())
        val decodedWaves = linkedMapOf<String, FloatWav>()
        files.forEach { file ->
            val bytes = reader.read("$root/$file")
            val decoded = FloatWavDecoder.decode(bytes)
            decodedWaves[file] = decoded
            assertEquals(number("sample_rate_hz").toInt(), decoded.sampleRateHz)
            val independent = MessageDigest.getInstance("SHA-256").digest(File(assets, "$root/$file").readBytes())
                .joinToString("") { "%02x".format(it.toInt() and 255) }
            assertEquals(independent, reader.hashes()["$root/$file"])
        }
        val loops = decodedWaves.mapNotNull { (file, decoded) ->
            val match = Regex("rpm_([0-9]+)_load_([0-9]+)\\.wav").matchEntire(file)
            match?.let { MatlabLoop(it.groupValues[1].toDouble(), it.groupValues[2].toDouble() / 100.0, decoded.samples) }
        }
        return MatlabSoundBank(vehicleKey, number("sample_rate_hz").toInt(), spec, loops,
            floatArrayOf(), artifactHashes = reader.hashes())
    }
    fun normal(bank: MatlabSoundBank): NormalLiveBank =
        LiveLoopBankVariantLoader.loadForNormalPlayback(bank) { File(assets, it).readBytes() }
}

class VehicleSoundProfileLoaderCompatibilityTest {
    @Test fun sixProductionManifestSpecsAndRealWavHashesRemainCompatible() {
        val loader = VehicleSoundProfileLoader
        assertEquals(CurrentVehicleCatalog.keys.toSet(), SupportedVehicleProfiles.keys)
        val families = mapOf("c63_w204_v6" to "v8", "hellcat_v6" to "v8", "ferrari_458" to "v8",
            "gtr_r35" to "v6", "lfa" to "v10", "supra_jza80" to "i6")
        for (key in CurrentVehicleCatalog.keys) {
            val bank = ProfileBankFixtures.loaded(key)
            val normal = ProfileBankFixtures.normal(bank)
            val profile = loader.fromLoadedBank(bank, normal.identity, normal.variantArtifactHashes)
            assertEquals(families[key], profile.engineFamily)
            assertEquals(bank.artifactHashes, profile.artifactHashes)
            if (key == "c63_w204_v6") assertEquals(
                "7a03686ce671562fabd6f5160ce6fe6d2e04887e84d89a0ae4f3594bfb7d8869",
                profile.artifactHashes["s12_v10/$key/manifest.json"],
            )
            assertTrue(loader.validateLoaded(bank, profile).isSuccess)
            assertArrayEquals(bank.powertrain.gearRatios, profile.powertrain.gearRatios, 0.0)
            assertEquals(bank.powertrain, profile.powertrain.copy(gearRatios = bank.powertrain.gearRatios))
            if (key != "c63_w204_v6") {
                assertTrue(loader.fromLoadedBank(bank.copy(sampleRateHz = 96000), normal.identity).validate().isSuccess)
            } else {
                assertThrows(IllegalArgumentException::class.java) {
                    loader.fromLoadedBank(bank.copy(sampleRateHz = 96000), normal.identity, normal.variantArtifactHashes)
                }
            }
        }
    }

    @Test fun realNormalOverlayHasSeparateHashesAndNoAdditionalAssetReads() {
        val bank = ProfileBankFixtures.loaded("c63_w204_v6")
        val assets = File("app/src/main/assets").takeIf { it.isDirectory } ?: File("src/main/assets")
        val calls = linkedMapOf<String, Int>()
        val normal = LiveLoopBankVariantLoader.loadForNormalPlayback(bank) { path ->
            calls[path] = (calls[path] ?: 0) + 1
            File(assets, path).readBytes()
        }
        assertEquals(10, calls.size) // variant manifest + source manifest + four source + four variant WAVs
        assertTrue(calls.values.all { it == 1 })
        assertEquals(5, normal.variantArtifactHashes.size)
        for ((path, hash) in normal.variantArtifactHashes) {
            assertTrue(path.startsWith("${LiveLoopVariantManifest.C63_ROOT}/"))
            val independent = MessageDigest.getInstance("SHA-256").digest(File(assets, path).readBytes())
                .joinToString("") { "%02x".format(it.toInt() and 255) }
            assertEquals(independent, hash)
        }
        val profile = VehicleSoundProfileLoader.fromLoadedBank(bank, normal.identity, normal.variantArtifactHashes)
        assertEquals(bank.artifactHashes, profile.referenceArtifactHashes)
        assertEquals(normal.variantArtifactHashes, profile.normalVariantArtifactHashes)
        assertSame(bank.powertrain, normal.bank.powertrain)
        assertEquals(bank.artifactHashes, normal.bank.artifactHashes)
        for (reference in bank.loops) {
            val live = normal.bank.loop(reference.rpm, reference.load)
            if (reference.rpm <= 1400) assertFalse(reference.samples.contentEquals(live.samples))
            else assertSame(reference.samples, live.samples)
        }
        assertThrows(IllegalArgumentException::class.java) {
            VehicleSoundProfileLoader.fromLoadedBank(bank, normal.identity)
        }
        val missing = normal.variantArtifactHashes.filterKeys { !it.endsWith("rpm_0700_load_32.wav") }
        assertThrows(IllegalArgumentException::class.java) {
            VehicleSoundProfileLoader.fromLoadedBank(bank, normal.identity, missing)
        }
        val legacy = ProfileBankFixtures.loaded("lfa")
        var legacyReads = 0
        val unchanged = LiveLoopBankVariantLoader.loadForNormalPlayback(legacy) { legacyReads++; error("unexpected IO") }
        assertSame(legacy, unchanged.bank)
        assertEquals(0, legacyReads)
        assertTrue(unchanged.variantArtifactHashes.isEmpty())
        assertThrows(IllegalArgumentException::class.java) {
            VehicleSoundProfileLoader.fromLoadedBank(legacy, unchanged.identity, normal.variantArtifactHashes)
        }
    }

    @Test fun readerRejectsTraversalAndChangedBytesWithoutInventingMissingArtifacts() {
        var call = 0
        val reader = BankArtifactReader { path ->
            require(!path.endsWith("missing.wav"))
            (++call).toString().toByteArray()
        }
        assertThrows(IllegalArgumentException::class.java) { reader.read("s12_v10/lfa/../manifest.json") }
        assertThrows(IllegalArgumentException::class.java) { reader.read("s12_v10/lfa/missing.wav") }
        assertTrue(reader.hashes().isEmpty())
        reader.read("s12_v10/lfa/loop.wav")
        assertThrows(IllegalArgumentException::class.java) { reader.read("s12_v10/lfa/loop.wav") }
    }

    @Test fun readerHashesExactBytesAndNeverReadsAnAssetForHashingAgain() {
        val calls = mutableMapOf<String, Int>()
        val bytes = "abc".toByteArray()
        val reader = BankArtifactReader { path -> calls[path] = (calls[path] ?: 0) + 1; bytes }
        assertSame(bytes, reader.read("s12_v10/lfa/manifest.json"))
        assertEquals(mapOf("s12_v10/lfa/manifest.json" to 1), calls)
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            reader.hashes().values.single())
        val snapshot = reader.hashes()
        reader.read("s12_v10/lfa/loop.wav")
        assertEquals(1, snapshot.size)
        assertThrows(UnsupportedOperationException::class.java) {
            (snapshot as MutableMap<String, String>)["new"] = "new"
        }
    }
}
