package com.vico.simulator.sound.n2

import com.vico.simulator.sound.s17.C63AR2AfterfireRuntime
import com.vico.simulator.sound.s18.C63FiniteResponseSource
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Frozen occurrence semantics with an N2-only finite response and an independent response RNG.
 * Muting is handled by N2Source after this process advances, so event-on/off comparisons keep
 * identical occurrence and response streams.
 */
internal class N2EventProcess(private val profile: N2Profile) {
    private val key = "C63_N2_EVENT_V1|" + profile.identity
    private val occurrence = C63AR2AfterfireRuntime(profile.occurrenceSeed, 0.0)
    private var responseRng = profile.responseSeed
    private val response = C63FiniteResponseSource(
        profile.eventResponse().map {
            it * profile.eventScale * sqrt(1.0 - profile.eventNoiseFraction)
        }.toDoubleArray(),
        profile.eventNoiseA().map {
            it * profile.eventScale * sqrt(profile.eventNoiseFraction)
        }.toDoubleArray(),
        profile.eventNoiseB().map {
            it * profile.eventScale * sqrt(profile.eventNoiseFraction)
        }.toDoubleArray(),
    )

    var lastAngle = 0.0
        private set
    var lastSignal = 0.0
        private set
    val lastImpulse get() = occurrence.lastImpulse
    val pendingFrames get() = response.pendingFrames
    val thermalState get() = occurrence.thermalState
    val episodeAgeFrames get() = occurrence.episodeAgeFrames

    fun observation() = occurrence.observation()

    fun sample(
        rpm: Double,
        load: Double,
        throttle: Double,
        opportunity: Boolean,
        validInput: Boolean = true,
    ): Double {
        occurrence.sample(rpm, load, throttle, opportunity, validInput)
        if (occurrence.lastImpulse > 0.0) {
            responseRng = next(responseRng)
            val uniform = ((responseRng * 2685821657736338717L) ushr 11).toDouble() / 9007199254740992.0
            val angle = 2.0 * PI * uniform
            lastAngle = angle
            response.inject(
                occurrence.distinctImpulseFrames - 1L,
                ((occurrence.distinctImpulseFrames - 1L) and 1L).toInt(),
                occurrence.lastImpulse,
                .25 * cos(angle),
                .25 * sin(angle),
            )
        }
        response.step()
        lastSignal = response.left + response.right
        check(lastSignal.isFinite()) { "N2 event response became nonfinite" }
        return lastSignal
    }

    internal class Snapshot internal constructor(
        internal val key: String,
        internal val occurrence: C63AR2AfterfireRuntime.Snapshot,
        internal val response: C63FiniteResponseSource.Snapshot,
        internal val responseRng: Long,
        internal val angle: Double,
        internal val signal: Double,
    )

    fun snapshot() = Snapshot(
        key,
        occurrence.snapshot(),
        response.snapshot(),
        responseRng,
        lastAngle,
        lastSignal,
    )

    fun restore(saved: Snapshot) {
        val expectedResponse = response.snapshot().identity
        require(
            saved.key == key &&
                saved.response.identity == expectedResponse &&
                saved.responseRng != 0L &&
                saved.angle.isFinite() &&
                saved.signal.isFinite()
        ) { "N2 event snapshot mismatch" }
        occurrence.restore(saved.occurrence)
        response.restore(saved.response)
        responseRng = saved.responseRng
        lastAngle = saved.angle
        lastSignal = saved.signal
    }

    private fun next(value: Long): Long {
        var x = value
        x = x xor (x shl 13)
        x = x xor (x ushr 7)
        x = x xor (x shl 17)
        return x
    }
}
