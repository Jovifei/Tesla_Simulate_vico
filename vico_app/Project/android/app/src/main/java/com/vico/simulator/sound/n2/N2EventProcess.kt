package com.vico.simulator.sound.n2

import com.vico.simulator.sound.s17.C63AR2AfterfireRuntime
import com.vico.simulator.sound.s18.C63FiniteResponseSource
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Event response path with registered energy semantics.
 * Occurrence and response state remain independent; event-off mutes later in N2Source.
 */
internal class N2EventProcess(private val profile: N2Profile) {
    private val key = "C63_N2_EVENT_V2|" + profile.identity
    private val occurrence = C63AR2AfterfireRuntime(profile.occurrenceSeed, 0.0)
    private var responseRng = profile.responseSeed
    private val response = createResponse()
    private fun createResponse() = C63FiniteResponseSource(
        profile.eventResponse().map { it * profile.eventScale * sqrt(1.0 - profile.eventNoiseFraction) }.toDoubleArray(),
        profile.eventNoiseA().map { it * profile.eventScale * sqrt(profile.eventNoiseFraction) }.toDoubleArray(),
        profile.eventNoiseB().map { it * profile.eventScale * sqrt(profile.eventNoiseFraction) }.toDoubleArray(),
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
            val unit = ((responseRng ushr 11).toDouble() / 9007199254740992.0) * 2.0 - 1.0
            val angle = PI * unit
            lastAngle = angle
            // Registered orthogonal phase rotation. No hidden attenuation multiplier.
            response.inject(
                occurrence.distinctImpulseFrames - 1L,
                ((occurrence.distinctImpulseFrames - 1L) and 1L).toInt(),
                occurrence.lastImpulse,
                cos(angle),
                sin(angle),
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
        val prepared = validateSnapshot(saved)
        occurrence.restore(prepared.occurrence)
        response.restore(prepared.response)
        responseRng = prepared.responseRng
        lastAngle = prepared.angle
        lastSignal = prepared.signal
    }

    private fun validateSnapshot(saved: Snapshot): Snapshot {
        val currentResponse = response.snapshot()
        require(
            saved.key == key &&
                saved.response.identity == currentResponse.identity &&
                saved.responseRng != 0L &&
                saved.angle.isFinite() &&
                saved.signal.isFinite()
        ) { "N2 event snapshot mismatch" }
        // Child restore checks run on disposable objects, not the live thermal/queue state.
        C63AR2AfterfireRuntime(profile.occurrenceSeed, 0.0).restore(saved.occurrence)
        createResponse().restore(saved.response)
        return saved
    }

    private fun next(value: Long): Long {
        var x = value
        x = x xor (x shl 13)
        x = x xor (x ushr 7)
        x = x xor (x shl 17)
        return x
    }
}
