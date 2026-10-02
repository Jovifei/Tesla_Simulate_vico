package com.vico.simulator.sound.n2

/** Frozen-independent N2 source representation. HY1 and old sound banks are untouched. */
data class N2Profile(
    val identity: String = "C63_N2_CONTINUOUS_V1",
    val sampleRate: Int = 48000,
    val basisLength: Int = 4096,
    val basisCount: Int = 8,
    val eventLength: Int = 12288,
    val continuousBudget: Int = 48,
    val eventBudget: Int = 24,
    val seed: Long = 0x4E32534F55524345L
)
