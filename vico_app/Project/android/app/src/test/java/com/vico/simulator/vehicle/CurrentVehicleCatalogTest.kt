package com.vico.simulator.vehicle

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CurrentVehicleCatalogTest {
    @Test
    fun exposes_the_six_current_vehicle_keys_in_product_order() {
        assertEquals(
            listOf("hellcat_v6", "ferrari_458", "lfa", "gtr_r35", "c63_w204_v6", "supra_jza80"),
            CurrentVehicleCatalog.keys,
        )
        assertEquals("c63_w204_v6", CurrentVehicleCatalog.defaultKey)
    }

    @Test
    fun accepts_only_the_current_vehicle_set() {
        CurrentVehicleCatalog.keys.forEach { assertTrue(CurrentVehicleCatalog.isSupported(it)) }
        assertTrue(!CurrentVehicleCatalog.isSupported("v8_crossplane"))
        assertTrue(!CurrentVehicleCatalog.isSupported("classic_rotary"))
    }

    @Test
    fun provides_display_names_without_loading_legacy_vehicle_json() {
        assertEquals("Ferrari 458 Italia", CurrentVehicleCatalog.displayName("ferrari_458"))
        assertEquals("Toyota Supra JZA80", CurrentVehicleCatalog.displayName("supra_jza80"))
    }
}
