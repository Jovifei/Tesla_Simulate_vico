package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

class VehicleSoundProfileConsumerRegressionTest {
    private val bank by lazy { ProfileBankFixtures.loaded("c63_w204_v6") }
    private val normal by lazy { ProfileBankFixtures.normal(bank) }
    private fun profile(
        spec: MatlabPowertrainSpec = bank.powertrain,
        identity: String = LiveLoopVariantManifest.C63_ID,
        hashes: Map<String, String> = bank.artifactHashes,
        key: String = bank.vehicleKey,
        family: String = "v8",
        sampleRate: Int = bank.sampleRateHz,
        channels: Int = 1,
        version: Int = 1,
        qualification: String = "FROZEN_COMPATIBILITY_ONLY",
        variantHashes: Map<String, String> = normal.variantArtifactHashes,
    ) = VehicleSoundProfile(version, key, family, identity, sampleRate, channels,
        hashes, qualification, spec, variantHashes)

    @Test fun malformedIdentityFormatAndArtifactFieldsRejectIndependently() {
        assertTrue(profile().validate().isSuccess)
        for (identity in listOf("", " ", "unavailable", "not_prepared", " normal", "normal\n", LiveLoopVariantManifest.LEGACY_ID)) {
            assertTrue(identity, profile(identity = identity).validate().isFailure)
        }
        assertTrue(profile(version = 2).validate().isFailure)
        assertTrue(profile(key = "unknown").validate().isFailure)
        assertTrue(profile(family = "v6").validate().isFailure)
        assertTrue(profile(sampleRate = 44100).validate().isFailure)
        assertTrue(profile(channels = 2).validate().isFailure)
        assertTrue(profile(qualification = "ACOUSTIC_PASS").validate().isFailure)
        assertTrue(profile(hashes = emptyMap()).validate().isFailure)
        val malformed = bank.artifactHashes.toMutableMap()
        malformed[malformed.keys.first()] = "a".repeat(63)
        assertTrue(profile(hashes = malformed).validate().isFailure)
        assertTrue(profile(hashes = bank.artifactHashes.filterKeys { !it.endsWith(".wav") }).validate().isFailure)
    }

    @Test fun malformedPowertrainFieldsRejectIndependently() {
        val s = bank.powertrain
        val bad = listOf(
            s.copy(idleRpm = -1.0), s.copy(redlineRpm = s.idleRpm),
            s.copy(gearRatios = doubleArrayOf(1.0, -1.0)), s.copy(gearRatios = doubleArrayOf(1.0, 2.0)),
            s.copy(finalDrive = Double.NaN), s.copy(wheelRadiusM = 0.0),
            s.copy(launchRpm = s.redlineRpm + 1), s.copy(shiftRpm = Double.POSITIVE_INFINITY),
            s.copy(afterfireMinimumRpm = s.idleRpm - 1), s.copy(shiftAttackS = -0.01),
            s.copy(shiftHoldS = Double.NaN), s.copy(shiftRecoveryS = -0.01),
            s.copy(shiftSettleS = Double.POSITIVE_INFINITY), s.copy(minimumShiftIntervalS = 0.0),
            s.copy(shiftMinTorque = 1.1), s.copy(shiftReengageGain = 0.0),
            s.copy(downshiftRatio = 1.0), s.copy(speedCeilingKmh = -1.0),
        )
        bad.forEachIndexed { index, spec -> assertTrue("case $index", profile(spec).validate().isFailure) }
    }

    @Test fun profileSnapshotProtectsCompleteSpecAndArtifactMap() {
        val spec = bank.powertrain.copy(gearRatios = bank.powertrain.gearRatios.copyOf())
        val hashes = bank.artifactHashes.toMutableMap()
        val variantHashes = normal.variantArtifactHashes.toMutableMap()
        val snapshot = profile(spec, hashes = hashes, variantHashes = variantHashes)
        val original = snapshot.powertrain
        spec.gearRatios[0] = 999.0
        hashes.clear()
        variantHashes.clear()
        snapshot.powertrain.gearRatios[0] = 888.0
        snapshot.powertrain.upshiftSpeedKmh[0] = 777.0
        assertArrayEquals(original.gearRatios, snapshot.powertrain.gearRatios, 0.0)
        assertArrayEquals(original.upshiftSpeedKmh, snapshot.powertrain.upshiftSpeedKmh, 0.0)
        assertEquals(bank.artifactHashes, snapshot.referenceArtifactHashes)
        assertEquals(normal.variantArtifactHashes, snapshot.normalVariantArtifactHashes)
        assertTrue(VehicleSoundProfileLoader.validateLoaded(bank, snapshot).isSuccess)
    }

    @Test fun loadedCompatibilityChecksRatiosShiftAndAfterfireNotOnlyScalars() {
        val original = profile()
        assertTrue(VehicleSoundProfileLoader.validateLoaded(bank, original).isSuccess)
        val s = bank.powertrain
        for (changed in listOf(s.copy(gearRatios = s.gearRatios.map { it * 1.01 }.toDoubleArray()),
            s.copy(shiftHoldS = s.shiftHoldS + 0.01), s.copy(afterfireMinimumRpm = s.afterfireMinimumRpm + 1))) {
            assertTrue(profile(changed).validate().isSuccess)
            assertTrue(VehicleSoundProfileLoader.validateLoaded(bank, profile(changed)).isFailure)
        }
        val alteredHashes = bank.artifactHashes.mapValues { "0".repeat(64) }
        assertTrue(VehicleSoundProfileLoader.validateLoaded(bank, profile(hashes = alteredHashes)).isFailure)
    }

    @Test fun frozenProfileControllerProducesIdenticalStatesForEachProductionSpec() {
        for (key in SupportedVehicleProfiles.keys) {
            val loaded = ProfileBankFixtures.loaded(key)
            val normal = ProfileBankFixtures.normal(loaded)
            val frozen = VehicleSoundProfileLoader.fromLoadedBank(loaded, normal.identity, normal.variantArtifactHashes)
            val original = MatlabPowertrainController(loaded.powertrain)
            val consumer = MatlabPowertrainController(frozen.powertrain)
            repeat(240) { frame ->
                val speed = if (frame < 120) frame.toDouble() else (240 - frame).toDouble()
                val throttle = if (frame < 160) 0.85 else 0.0
                assertEquals("$key frame $frame", original.update(frame * 0.02, speed, 1.2, throttle),
                    consumer.update(frame * 0.02, speed, 1.2, throttle))
            }
        }
    }
}
