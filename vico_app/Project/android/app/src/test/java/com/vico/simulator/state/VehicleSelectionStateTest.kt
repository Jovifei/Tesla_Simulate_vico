package com.vico.simulator.state

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class VehicleSelectionStateTest {

    @Test
    fun selecting_a_vehicle_stages_it_until_the_engine_starts() {
        val state = VehicleSelectionState("v8_crossplane")

        state.select("v12")

        assertEquals("v12", state.selectedKey)
        assertNull(state.playingKey)
        state.startEngine()
        assertEquals("v12", state.playingKey)
    }

    @Test
    fun changing_selection_while_running_does_not_replace_the_playing_vehicle() {
        val state = VehicleSelectionState("v8_crossplane")
        state.startEngine()

        state.select("v12")

        assertEquals("v12", state.selectedKey)
        assertEquals("v8_crossplane", state.playingKey)
    }
}
