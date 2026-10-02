package com.vico.simulator.sound

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.max

/** Deterministic 30-second common-trace renderer shared by desktop JVM and Android. */
class S13ReviewSession(
    private val bank: MatlabSoundBank,
    private val reviewPackage: S13ReviewPackage,
) {
    private val renderer = MatlabStatefulBankRenderer(bank)
    private val runEnvelope = GainEnvelope()
    private val contentEnvelope = GainEnvelope()
    private var nextFrame = 0

    val framesRendered: Int
        get() = nextFrame

    val isComplete: Boolean
        get() = nextFrame == S13ReviewContract.TOTAL_FRAMES

    val captureBinding: S13CaptureBinding
        get() = reviewPackage.captureBinding

    internal fun enableRpmBlendCapture(maxFrames: Int): S13RpmBlendCapture =
        S13RpmBlendCapture(maxFrames).also(renderer::enableRpmBlendCapture)

    init {
        require(bank.vehicleKey == reviewPackage.vehicleKey)
        require(bank.sampleRateHz == S13ReviewContract.SAMPLE_RATE)
        require(S13ReviewContract.TOTAL_FRAMES % S13ReviewContract.BLOCK_FRAMES == 0)
    }

    /** Returns one fixed audio block, or null once the half-open [0, 30 s) window is done. */
    fun renderNext(): FloatArray? {
        if (isComplete) return null
        val frameCount = minOf(
            S13ReviewContract.BLOCK_FRAMES,
            S13ReviewContract.TOTAL_FRAMES - nextFrame,
        )
        val firstPoint = reviewPackage.trace.at(nextFrame)
        val endPoint = reviewPackage.trace.atBoundary(nextFrame + frameCount)
        val firstGain = shiftGainAt(nextFrame)
        val endGain = shiftGainAt(nextFrame + frameCount)
        val startState = state(firstPoint, firstGain)
        val endState = state(endPoint, endGain)
        val events = reviewPackage.events.filter { it.startsIn(nextFrame, frameCount) }
        val pcm = renderer.renderReview(
            startState, endState, nextFrame, frameCount, events,
        )

        val fadeOutStart = S13ReviewContract.TOTAL_FRAMES -
            S13ReviewContract.REVIEW_STOP_FADE_BLOCKS * S13ReviewContract.BLOCK_FRAMES
        val audible = nextFrame < fadeOutStart
        val envelope = (runEnvelope.step(audible) * contentEnvelope.step(audible))
            .coerceIn(0f, 1f)
        if (envelope < 1f) {
            for (index in pcm.indices) pcm[index] *= envelope
        }
        nextFrame += frameCount
        return pcm
    }

    /** Host-side D1 reference generation; the caller owns the returned 5.76 MB PCM array. */
    fun renderAll(): FloatArray {
        check(nextFrame == 0) { "A review session can only render once" }
        val output = FloatArray(S13ReviewContract.TOTAL_FRAMES)
        var offset = 0
        while (!isComplete) {
            val block = requireNotNull(renderNext())
            block.copyInto(output, offset)
            offset += block.size
        }
        check(offset == S13ReviewContract.TOTAL_FRAMES)
        return output
    }

    fun mixStats(): S13MixSnapshot = renderer.mixStats()

    private fun state(point: S13TracePoint, shiftGain: Double) = SoundState(
        timeS = point.timeS,
        rpm = point.rpm,
        frequencyHz = point.rpm / 60.0 * 4.0,
        amplitude = max(0.08, point.load),
        brightness = point.load,
        harmonics = floatArrayOf(),
        muted = false,
        throttle = point.throttle,
        load = point.load,
        braking = point.accelerationMps2 < -1.2,
        shiftGain = shiftGain,
    )

    private fun shiftGainAt(frame: Int): Double {
        val sourceFrame = reviewPackage.events.asSequence()
            .filter { it.binding.kind == "shift" }
            .mapNotNull { it.binding.sourceFrame }
            .filter { it <= frame }
            .maxOrNull() ?: return 1.0
        val spec = bank.powertrain
        val elapsed = (frame - sourceFrame).toDouble() / bank.sampleRateHz
        return when {
            elapsed < spec.shiftAttackS -> cosineBlend(
                1.0, spec.shiftMinTorque, elapsed / spec.shiftAttackS,
            )
            elapsed < spec.shiftAttackS + spec.shiftHoldS -> spec.shiftMinTorque
            elapsed < spec.shiftAttackS + spec.shiftHoldS + spec.shiftRecoveryS -> {
                val progress = (elapsed - spec.shiftAttackS - spec.shiftHoldS) / spec.shiftRecoveryS
                cosineBlend(spec.shiftMinTorque, spec.shiftReengageGain, progress)
            }
            elapsed < spec.totalShiftTimeS -> {
                val progress = (elapsed - spec.shiftAttackS - spec.shiftHoldS - spec.shiftRecoveryS) /
                    spec.shiftSettleS
                cosineBlend(spec.shiftReengageGain, 1.0, progress)
            }
            else -> 1.0
        }
    }

    private fun cosineBlend(start: Double, finish: Double, progress: Double): Double {
        val blend = 0.5 - 0.5 * cos(PI * progress.coerceIn(0.0, 1.0))
        return start + (finish - start) * blend
    }
}
