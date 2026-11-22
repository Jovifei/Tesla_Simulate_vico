package com.vico.simulator.vehicle

import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class V14ReleaseGateTest {
    @Test fun missingOwnerVerifierAndRuntimeBindingLocksEveryKnownVehicle() {
        CurrentVehicleCatalog.keys.forEach { assertFalse(V14ReleaseGate.canPlay(it)) }
        assertFalse(V14ReleaseGate.canPlay("unknown"))
    }

    @Test fun rejectsUnexpectedRegistryBytes() {
        assertNull(V14ReleaseGate.checkedRegistry("{}".toByteArray()))
    }

    @Test fun bridgeAndActivitySourceEnforceTheGateOnEveryOrdinaryEntry() {
        val bridge = File("src/main/java/com/vico/simulator/web/VicoBridge.kt").readText()
        val activity = File("src/main/java/com/vico/simulator/MainActivity.kt").readText()
        for (method in listOf("setVehicle", "previewVehicle")) {
            assertTrue(bridge.contains("activity.$method(key)"))
            val body = activity.substringAfter("fun $method(key: String) {").substringBefore("\n    }")
            assertTrue(body.contains("V14ReleaseGate.canPlay(key)"))
        }
        val start = activity.substringAfter("fun startAudio() {").substringBefore("\n    }")
        assertTrue(start.contains("V14ReleaseGate.canPlay(vehicleState.selectedKey)"))
        assertTrue(bridge.contains("V14ReleaseGate.canPlay(key)"))
    }
}
