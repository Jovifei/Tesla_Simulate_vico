package com.vico.simulator.audio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioOutputCatalogTest {

    @Test
    fun classifies_android_output_types_into_user_facing_categories() {
        assertEquals(AudioOutputCategory.BUILTIN, AudioOutputCatalog.categoryFor(2))
        assertEquals(AudioOutputCategory.BLUETOOTH, AudioOutputCatalog.categoryFor(8))
        assertEquals(AudioOutputCategory.WIRED, AudioOutputCatalog.categoryFor(4))
        assertEquals(AudioOutputCategory.WIRED, AudioOutputCatalog.categoryFor(22))
        assertTrue(AudioOutputCatalog.isSelectable(AudioOutputCategory.BUILTIN, connected = true))
    }
}
