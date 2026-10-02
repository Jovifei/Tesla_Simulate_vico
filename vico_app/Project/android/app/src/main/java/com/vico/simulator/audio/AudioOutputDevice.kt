package com.vico.simulator.audio

data class AudioOutputDevice(
    val id: Int,
    val type: Int,
    val category: AudioOutputCategory,
    val label: String,
    val connected: Boolean,
    val selectable: Boolean,
    val routed: Boolean,
)
