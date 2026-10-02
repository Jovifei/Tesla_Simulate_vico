package com.vico.simulator.sound

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.floor
import kotlin.math.max

data class S13MixSnapshot(
    val evaluatedFrames: Long,
    val preClipPeak: Double,
    val aboveContractFrames: Long,
    val hardClipFrames: Long,
    val nonFiniteFrames: Long,
    val loadOutOfBankFrames: Long,
    val rpmOutOfBankFrames: Long,
    val rejectedInputBlocks: Long,
)

/** Preallocated, test-only copies of the two actual RPM interpolation paths. */
internal class S13RpmBlendCapture(capacity: Int) {
    init {
        require(capacity in 1..S13ReviewContract.TOTAL_FRAMES)
    }

    internal val lowerPath = FloatArray(capacity)
    internal val upperPath = FloatArray(capacity)
    internal val rpmWeight = FloatArray(capacity)
    internal val sharedGain = FloatArray(capacity)
    internal val eventContribution = FloatArray(capacity)
    internal val rpmLowerIndex = ByteArray(capacity)
    internal val rpmUpperIndex = ByteArray(capacity)
    var frameCount = 0
        private set

    internal fun reset() {
        frameCount = 0
    }

    internal fun record(
        frameIndex: Int,
        lower: Float,
        upper: Float,
        weight: Float,
        gain: Float,
        events: Float,
        lowerIndex: Int,
        upperIndex: Int,
    ) {
        check(frameIndex == frameCount && frameCount < lowerPath.size) {
            "RPM diagnostic capture must be sequential and stay within its fixed capacity"
        }
        check(lowerIndex in 0..255 && upperIndex in 0..255)
        val index = frameCount++
        lowerPath[index] = lower
        upperPath[index] = upper
        rpmWeight[index] = weight
        sharedGain[index] = gain
        eventContribution[index] = events
        rpmLowerIndex[index] = lowerIndex.toByte()
        rpmUpperIndex[index] = upperIndex.toByte()
    }
}

/** Renders S12 bank loops without resetting phase between sensor blocks. */
class MatlabStatefulBankRenderer(private val bank: MatlabSoundBank) {
    private var evaluatedFrames = 0L
    private var preClipPeak = 0.0
    private var aboveContractFrames = 0L
    private var hardClipFrames = 0L
    private var nonFiniteFrames = 0L
    private var loadOutOfBankFrames = 0L
    private var rpmOutOfBankFrames = 0L
    private var rejectedInputBlocks = 0L

    /** Read on the renderer-owning thread, or after rendering stops. */
    fun mixStats() = S13MixSnapshot(
        evaluatedFrames, preClipPeak, aboveContractFrames, hardClipFrames,
        nonFiniteFrames, loadOutOfBankFrames, rpmOutOfBankFrames, rejectedInputBlocks,
    )

    private var engineCycles = 0.0
    private var smoothedRpm = Double.NaN
    private var smoothedLoad = Double.NaN
    private var afterfireIndex = -1
    private var shiftIndex = 0
    private var activeShift: FloatArray? = null
    private var activeShiftIndex = -1
    private var consumedAfterfireTimeS = Double.NaN
    private var consumedShiftTimeS = Double.NaN
    private var rpmBlendCapture: S13RpmBlendCapture? = null

    internal fun enableRpmBlendCapture(capture: S13RpmBlendCapture) {
        require(evaluatedFrames == 0L) { "RPM diagnostic capture must be enabled before rendering" }
        require(rpmBlendCapture == null) { "RPM diagnostic capture is already enabled" }
        capture.reset()
        rpmBlendCapture = capture
    }

    fun reset() {
        evaluatedFrames = 0L
        preClipPeak = 0.0
        aboveContractFrames = 0L
        hardClipFrames = 0L
        nonFiniteFrames = 0L
        loadOutOfBankFrames = 0L
        rpmOutOfBankFrames = 0L
        rejectedInputBlocks = 0L
        engineCycles = 0.0
        smoothedRpm = Double.NaN
        smoothedLoad = Double.NaN
        afterfireIndex = -1
        shiftIndex = 0
        activeShift = null
        activeShiftIndex = -1
        consumedAfterfireTimeS = Double.NaN
        consumedShiftTimeS = Double.NaN
        rpmBlendCapture?.reset()
    }

    fun render(state: SoundState, frameCount: Int): FloatArray {
        return renderCore(state, state, 0, frameCount, null)
    }

    /** Review-only path: linearly interpolates controls and schedules sourced events by frame. */
    fun renderReview(
        startState: SoundState,
        endState: SoundState,
        firstFrame: Int,
        frameCount: Int,
        events: List<S13EventPlacement>,
    ): FloatArray {
        require(firstFrame >= 0 &&
            firstFrame.toLong() + frameCount <= S13ReviewContract.TOTAL_FRAMES.toLong())
        return renderCore(startState, endState, firstFrame, frameCount, events)
    }

    private fun renderCore(
        startState: SoundState,
        endState: SoundState,
        firstFrame: Int,
        frameCount: Int,
        scheduledEvents: List<S13EventPlacement>?,
    ): FloatArray {
        require(frameCount >= 0) { "frameCount must be non-negative" }
        if (frameCount == 0) return FloatArray(0)
        if (!isFiniteState(startState) || !isFiniteState(endState)) {
            rejectedInputBlocks++
            throw IllegalArgumentException("Non-finite S13 render input")
        }

        if (scheduledEvents == null && startState.muted) {
            if (startState.load < bank.loadLevels.first() || startState.load > bank.loadLevels.last()) {
                loadOutOfBankFrames += frameCount.toLong()
            }
            if (startState.rpm < bank.rpmLevels.first() || startState.rpm > bank.rpmLevels.last()) {
                rpmOutOfBankFrames += frameCount.toLong()
            }
            evaluatedFrames += frameCount.toLong()
            return FloatArray(frameCount)
        }

        val reviewEventsByOffset = scheduledEvents?.groupBy { event ->
            require(event.startsIn(firstFrame, frameCount)) { "Review event is outside this frame block" }
            event.startFrame - firstFrame
        }.orEmpty()

        if (scheduledEvents == null) {
            if (startState.afterfireTrigger && startState.timeS != consumedAfterfireTimeS) {
                consumedAfterfireTimeS = startState.timeS
                afterfireIndex = 0
            }
            if (startState.shiftTrigger && startState.timeS != consumedShiftTimeS) {
                consumedShiftTimeS = startState.timeS
                activeShift = if (bank.shiftEvents.isEmpty()) null
                else bank.shiftEvents[shiftIndex % bank.shiftEvents.size].samples
                activeShiftIndex = if (activeShift == null) -1 else 0
                shiftIndex++
            }
        }

        val firstRpm = startState.rpm.coerceIn(bank.rpmLevels.first(), bank.rpmLevels.last())
        val firstLoad = startState.load.coerceIn(bank.loadLevels.first(), bank.loadLevels.last())
        if (!smoothedRpm.isFinite()) smoothedRpm = firstRpm
        if (!smoothedLoad.isFinite()) smoothedLoad = firstLoad
        val output = FloatArray(frameCount)
        val diagnosticCapture = rpmBlendCapture
        val smoothingAlpha = 1.0 - exp(-1.0 / (bank.sampleRateHz * STATE_SMOOTHING_SECONDS))
        repeat(frameCount) { index ->
            val progress = index.toDouble() / frameCount
            val rawRpm = mix(startState.rpm, endState.rpm, progress)
            val rawLoad = mix(startState.load, endState.load, progress)
            if (rawRpm < bank.rpmLevels.first() || rawRpm > bank.rpmLevels.last()) {
                rpmOutOfBankFrames++
            }
            if (rawLoad < bank.loadLevels.first() || rawLoad > bank.loadLevels.last()) {
                loadOutOfBankFrames++
            }
            for (event in reviewEventsByOffset[index].orEmpty()) {
                when (event.binding.kind) {
                    "afterfire" -> afterfireIndex = 0
                    "shift" -> {
                        val filename = event.binding.assetPath.substringAfterLast('/')
                        activeShift = bank.shiftEvents.firstOrNull { it.file == filename }?.samples
                            ?: error("Missing reviewed shift asset: $filename")
                        activeShiftIndex = 0
                    }
                    else -> error("Unsupported reviewed event: ${event.binding.kind}")
                }
            }
            val targetRpm = rawRpm.coerceIn(bank.rpmLevels.first(), bank.rpmLevels.last())
            val targetLoad = rawLoad.coerceIn(bank.loadLevels.first(), bank.loadLevels.last())
            smoothedRpm += smoothingAlpha * (targetRpm - smoothedRpm)
            smoothedLoad += smoothingAlpha * (targetLoad - smoothedLoad)
            val rpmPair = bounds(bank.rpmLevels, smoothedRpm)
            val loadPair = bounds(bank.loadLevels, smoothedLoad)
            val rpmBlend = blend(rpmPair.first, rpmPair.second, smoothedRpm)
            val loadBlend = blend(loadPair.first, loadPair.second, smoothedLoad)
            val lowLow = bank.loop(rpmPair.first, loadPair.first)
            val lowHigh = bank.loop(rpmPair.first, loadPair.second)
            val highLow = bank.loop(rpmPair.second, loadPair.first)
            val highHigh = bank.loop(rpmPair.second, loadPair.second)
            val low = lerp(sample(lowLow), sample(lowHigh), loadBlend)
            val high = lerp(sample(highLow), sample(highHigh), loadBlend)
            val shiftGain = mix(startState.shiftGain, endState.shiftGain, progress).toFloat()
            var value = lerp(low, high, rpmBlend) * shiftGain
            var eventContribution = 0f
            if (afterfireIndex in bank.afterfire.indices) {
                val contribution = bank.afterfire[afterfireIndex++]
                value += contribution
                if (diagnosticCapture != null) eventContribution += contribution
            }
            val shift = activeShift
            if (shift != null && activeShiftIndex in shift.indices) {
                val contribution = shift[activeShiftIndex++]
                value += contribution
                if (diagnosticCapture != null) eventContribution += contribution
                if (activeShiftIndex >= shift.size) {
                    activeShift = null
                    activeShiftIndex = -1
                }
            }
            if (diagnosticCapture != null) {
                diagnosticCapture.record(
                    firstFrame + index, low, high, rpmBlend, shiftGain, eventContribution,
                    bank.rpmLevels.binarySearch(rpmPair.first), bank.rpmLevels.binarySearch(rpmPair.second),
                )
            }
            evaluatedFrames++
            if (!value.isFinite()) {
                nonFiniteFrames++
                throw IllegalStateException("Non-finite S13 mix at frame $evaluatedFrames")
            }
            val magnitude = abs(value.toDouble())
            preClipPeak = max(preClipPeak, magnitude)
            if (magnitude > CONTRACT_SAMPLE_PEAK) aboveContractFrames++
            if (magnitude > 1.0) hardClipFrames++
            output[index] = value.coerceIn(-1f, 1f)
            engineCycles += smoothedRpm / 120.0 / bank.sampleRateHz
        }
        return output
    }

    private fun isFiniteState(state: SoundState): Boolean =
        state.timeS.isFinite() && state.rpm.isFinite() && state.load.isFinite() &&
            state.shiftGain.isFinite()

    private fun mix(start: Double, end: Double, progress: Double): Double =
        start + (end - start) * progress

    private fun sample(loop: MatlabLoop): Float {
        val cycles = loop.samples.size.toDouble() / bank.sampleRateHz * loop.rpm / 120.0
        if (cycles <= 0.0 || loop.samples.isEmpty()) return 0f
        val normalized = (engineCycles % cycles) / cycles
        val position = normalized * loop.samples.size
        val first = floor(position).toInt() % loop.samples.size
        val second = (first + 1) % loop.samples.size
        return lerp(loop.samples[first], loop.samples[second], (position - floor(position)).toFloat())
    }

    private fun bounds(levels: DoubleArray, value: Double): Pair<Double, Double> {
        val lower = levels.lastOrNull { it <= value } ?: levels.first()
        val upper = levels.firstOrNull { it >= value } ?: levels.last()
        return lower to upper
    }

    private fun blend(lower: Double, upper: Double, value: Double): Float =
        if (upper <= lower) 0f else ((value - lower) / (upper - lower)).coerceIn(0.0, 1.0).toFloat()

    private fun lerp(start: Float, finish: Float, progress: Float): Float =
        start + (finish - start) * progress

    companion object {
        private const val STATE_SMOOTHING_SECONDS = 0.035
        private const val CONTRACT_SAMPLE_PEAK = 0.8413951416451951
    }
}
