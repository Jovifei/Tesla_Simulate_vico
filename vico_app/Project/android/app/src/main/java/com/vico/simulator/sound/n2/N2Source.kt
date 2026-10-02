package com.vico.simulator.sound.n2

import com.vico.simulator.sound.s18.C63FiniteResponseSource
import com.vico.simulator.sound.s18.C63HybridMode
import com.vico.simulator.sound.s18.C63HybridProfile
import com.vico.simulator.sound.s18.C63HybridSource
import kotlin.math.sqrt

/**
 * Qualification-only N2 source adapter.
 *
 * C63HybridSource(T) owns the frozen low/body/mechanical source state. N2 substitutes only the
 * bark stem for S/SE and only the afterfire response for E/SE.
 */
internal class N2Source(
    private val baselineProfile: C63HybridProfile,
    private val profile: N2Profile,
    private val mode: N2Mode,
    private val eventsAudible: Boolean = true,
) {
    private val sustainedChange = mode == N2Mode.S || mode == N2Mode.SE
    private val eventChange = mode == N2Mode.E || mode == N2Mode.SE
    private val baseline = C63HybridSource(baselineProfile, C63HybridMode.T, true)
    private val coefficients = profile.coefficients()
    private val responses = if (sustainedChange) {
        Array(N2Profile.BASIS_COUNT) { C63FiniteResponseSource(profile.basis(it)) }
    } else {
        emptyArray()
    }
    private val eventProcess = if (eventChange) N2EventProcess(profile) else null
    private val snapshotKey =
        "C63_N2_SOURCE_V1|" + baselineProfile.identity + "|" + profile.identity + "|" + mode + "|" + eventsAudible

    private var textureRng = profile.sourceSeed
    private var combustionEventId = 0L
    private var sourceFrame = 0L
    private var lastCombustionAmplitude = 0.0

    val lastStems = DoubleArray(7)
    var lastNewBark = 0.0
        private set
    var lastEventSignal = 0.0
        private set
    val lastCombustionImpulse get() = baseline.lastCombustionImpulse
    val lastCombustionBank get() = baseline.lastCombustionBank
    val driveState get() = baseline.driveState
    val lastAfterfireImpulse get() = eventProcess?.lastImpulse ?: baseline.lastAfterfireImpulse
    val lastResponseAngle get() = eventProcess?.lastAngle ?: 0.0
    val pendingFrames: Int
        get() = maxOf(
            responses.maxOfOrNull { it.pendingFrames } ?: 0,
            eventProcess?.pendingFrames ?: 0,
            baseline.pendingFrames,
        )

    internal data class EventObservation(
        val rawArrivals: Long,
        val distinctImpulseFrames: Long,
        val episodes: Long,
        val arrivalFrames: LongArray,
        val arrivalAmplitudes: DoubleArray,
        val impulseFrames: LongArray,
        val impulseAmplitudes: DoubleArray,
        val truncated: Boolean,
    )

    fun eventObservation(): EventObservation {
        eventProcess?.observation()?.let {
            return EventObservation(
                it.rawArrivals,
                it.distinctImpulses,
                it.episodes,
                it.arrivalFrames,
                it.arrivalAmplitudes,
                it.impulseFrames,
                it.impulseAmplitudes,
                it.truncated,
            )
        }
        val old = baseline.eventObservation()
        return EventObservation(
            old.rawArrivals,
            old.distinctImpulseFrames,
            old.episodes,
            old.arrivalFrames,
            old.arrivalAmplitudes,
            old.impulseFrames,
            old.impulseAmplitudes,
            old.truncated,
        )
    }

    internal class Snapshot internal constructor(
        internal val key: String,
        internal val baseline: C63HybridSource.Snapshot,
        internal val responses: List<C63FiniteResponseSource.Snapshot>,
        internal val event: N2EventProcess.Snapshot?,
        internal val counters: LongArray,
        internal val scalars: DoubleArray,
        internal val stems: DoubleArray,
    )

    fun snapshot() = Snapshot(
        snapshotKey,
        baseline.snapshot(),
        responses.map { it.snapshot() },
        eventProcess?.snapshot(),
        longArrayOf(textureRng, combustionEventId, sourceFrame),
        doubleArrayOf(lastCombustionAmplitude, lastNewBark, lastEventSignal),
        lastStems.copyOf(),
    )

    fun restore(saved: Snapshot) {
        val baselineIdentity = baseline.snapshot().key
        val responseIdentities = responses.map { it.snapshot().identity }
        val eventIdentity = eventProcess?.snapshot()?.key
        require(
            saved.key == snapshotKey &&
                saved.baseline.key == baselineIdentity &&
                saved.responses.size == responses.size &&
                saved.responses.indices.all { saved.responses[it].identity == responseIdentities[it] } &&
                saved.event?.key == eventIdentity &&
                saved.counters.size == 3 &&
                saved.counters[0] != 0L &&
                saved.counters[1] >= 0L &&
                saved.counters[2] >= 0L &&
                saved.counters[1] <= saved.counters[2] &&
                saved.scalars.size == 3 &&
                saved.scalars.all { it.isFinite() } &&
                saved.scalars[0] in 0.0..2.0 &&
                saved.stems.size == 7 &&
                saved.stems.all { it.isFinite() }
        ) { "N2 source snapshot mismatch" }

        baseline.restore(saved.baseline)
        saved.responses.indices.forEach { responses[it].restore(saved.responses[it]) }
        if (saved.event != null) eventProcess!!.restore(saved.event)
        textureRng = saved.counters[0]
        combustionEventId = saved.counters[1]
        sourceFrame = saved.counters[2]
        lastCombustionAmplitude = saved.scalars[0]
        lastNewBark = saved.scalars[1]
        lastEventSignal = saved.scalars[2]
        saved.stems.copyInto(lastStems)
    }

    fun sample(
        rpm: Double,
        load: Double,
        throttle: Double,
        validInput: Boolean = true,
    ): Float {
        val baselineOutput = baseline.sample(rpm, load, throttle, validInput)
        val base = baseline.lastStems

        if (sustainedChange) {
            val impulse = baseline.lastCombustionImpulse
            if (impulse > 0.0) {
                lastCombustionAmplitude = impulse
                val amplitude = (impulse * baseline.driveState).coerceIn(0.0, 2.0)
                val eventId = combustionEventId++
                responses.forEach { it.inject(eventId, baseline.lastCombustionBank, amplitude) }
            }
            var finiteBank = 0.0
            responses.forEachIndexed { index, response ->
                response.step()
                finiteBank += coefficients[index] * (response.left + response.right)
            }
            val random = nextTexture()
            val randomLevel =
                sqrt(profile.randomFraction * rpm * 4.0 / (60.0 * N2Profile.SAMPLE_RATE)) *
                    lastCombustionAmplitude * baseline.driveState
            val periodicLevel = sqrt(1.0 - profile.randomFraction)
            lastNewBark =
                profile.sourceScale *
                    (periodicLevel * finiteBank + randomLevel * random) *
                    .125 * (.60 + .40 * throttle) * .70
        } else {
            lastNewBark = base[1]
        }

        val newEvent = if (eventChange) {
            eventProcess!!.sample(
                rpm,
                load,
                throttle,
                baseline.lastCombustionImpulse > 0.0,
                validInput,
            )
        } else {
            base[4]
        }
        lastEventSignal = newEvent

        if (mode == N2Mode.T) {
            base.copyInto(lastStems)
            sourceFrame++
            return baselineOutput
        }

        lastStems[0] = base[0]
        lastStems[1] = if (sustainedChange) lastNewBark else base[1]
        lastStems[2] = base[2]
        lastStems[3] = base[3]
        lastStems[4] = if (eventChange) {
            if (eventsAudible) newEvent else 0.0
        } else {
            base[4]
        }
        lastStems[5] = base[5]
        lastStems[6] = base[6]

        val output =
            lastStems[0] + lastStems[1] + lastStems[2] + lastStems[3] +
                lastStems[4] + lastStems[5] + lastStems[6]
        check(output.isFinite()) { "N2 source output became nonfinite" }
        sourceFrame++
        return output.toFloat()
    }

    private fun nextTexture(): Double {
        var x = textureRng
        x = x xor (x shl 13)
        x = x xor (x ushr 7)
        x = x xor (x shl 17)
        textureRng = x
        return (x ushr 11).toDouble() / 9007199254740992.0 * 2.0 - 1.0
    }
}
