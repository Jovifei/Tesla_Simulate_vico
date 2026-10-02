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

    private val frames = Array(capacity) { DoubleArray(STEM_COUNT) }
    private var size = 0

    fun reset() {
        size = 0
    }

    fun append(
        sourceStems: DoubleArray,
        combustionImpulse: Double,
        afterfireImpulse: Double,
    ) {
        require(sourceStems.size == STEM_COUNT)
        if (size >= capacity) {
            return
        }
        sourceStems.copyInto(frames[size])
        frames[size][5] = combustionImpulse
        frames[size][6] = afterfireImpulse
        size++
    }

    fun frameCount(): Int = size

    fun copyFrames(): Array<DoubleArray> = Array(size) { index ->
        frames[index].copyOf()
    }

    companion object {
        const val STEM_COUNT = 7
    }
}
