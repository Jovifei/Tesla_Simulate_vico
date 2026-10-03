package com.vico.simulator.sound.n2.diagnostic

/**
 * Bounded qualification-only frame tap storage.
 *
 * The buffer is deliberately caller-owned and allocation-free after construction.
 * It stores generated diagnostic observations only; it does not access references,
 * files, network resources, or production routing state.
 */
internal class N2QualificationTapBuffer(
    private val capacity: Int,
) {
    init {
        require(capacity > 0)
    }

    private val frames = Array(capacity) { DoubleArray(CHANNEL_COUNT) }
    private var size = 0

    fun reset() {
        size = 0
    }

    /** A renderer reserves its whole block before advancing any DSP state. */
    fun requireCapacity(count: Int) {
        require(count >= 0 && count <= capacity - size) { "N2 qualification tap capacity exceeded" }
    }

    fun append(
        sourceStems: DoubleArray,
        combustionImpulse: Double,
        afterfireImpulse: Double,
    ) {
        require(sourceStems.size == STEM_COUNT)
        requireCapacity(1)
        require(sourceStems.all { it.isFinite() } && combustionImpulse.isFinite() && afterfireImpulse.isFinite())
        sourceStems.copyInto(frames[size])
        frames[size][COMBUSTION_IMPULSE] = combustionImpulse
        frames[size][AFTERFIRE_IMPULSE] = afterfireImpulse
        size++
    }

    fun frameCount(): Int = size

    fun copyFrames(): Array<DoubleArray> = Array(size) { index ->
        frames[index].copyOf()
    }

    companion object {
        const val STEM_COUNT = 7
        const val COMBUSTION_IMPULSE = 7
        const val AFTERFIRE_IMPULSE = 8
        const val CHANNEL_COUNT = 9
        val CHANNEL_NAMES: List<String> get() = listOf(
            "exhaust", "bark", "intake", "mechanical", "afterfire", "body", "rumble",
            "combustion_impulse", "afterfire_impulse",
        )
    }
}
