package com.vico.simulator.sound.n2

import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.s15.C63HeadroomProfile
import com.vico.simulator.sound.s15.C63IdleRuntime
import com.vico.simulator.sound.s15.C63ShiftRuntime
import com.vico.simulator.sound.s15.FrozenC63Output
import com.vico.simulator.sound.s18.C63HybridProfile
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.max

/**
 * Qualification-only N2 renderer. It deliberately copies the frozen idle/shift/output/headroom
 * chain used by C63HybridRenderer and never self-selects into the production sound bank.
 */
internal class N2Renderer(
    private val baselineProfile: C63HybridProfile,
    private val profile: N2Profile,
    private val mode: N2Mode,
    private val qualificationOnly: Boolean = true,
    private val eventsAudible: Boolean = true,
) {
    init {
        require(qualificationOnly) { "N2 remains qualification-only until every hard gate passes" }
    }

    val candidateId: String
        get() = if (mode == N2Mode.SE && eventsAudible) {
            N2Profile.CANDIDATE_ID
        } else {
            N2Profile.CANDIDATE_ID + "_" + mode + if (eventsAudible) "" else "_EVENT_OFF"
        }

    private val snapshotKey =
        "C63_N2_CHAIN_V1|" + baselineProfile.identity + "|" + profile.identity + "|" + mode + "|" + eventsAudible
    private val source = N2Source(baselineProfile, profile, mode, eventsAudible)
    private val idle = C63IdleRuntime()
    private val shift = C63ShiftRuntime()
    private val output = FrozenC63Output()
    private val audioBuffer = FloatArray(960)
    private val bodyDelay = DoubleArray(192)
    private val shiftDelay = BooleanArray(192)
    private var delayIndex = 0

    private var rpm = Double.NaN
    private var load = Double.NaN
    private var throttle = Double.NaN
    private var lastShift = Double.NaN

    var peak = 0.0
        private set
    var rawPeak = 0.0
        private set
    var frames = 0L
        private set

    fun sourceStems(): DoubleArray = source.lastStems.copyOf()
    fun eventObservation() = source.eventObservation()
    val pendingFrames get() = source.pendingFrames

    internal class Snapshot internal constructor(
        internal val key: String,
        internal val source: N2Source.Snapshot,
        internal val idle: C63IdleRuntime.Snapshot,
        internal val shift: C63ShiftRuntime.Snapshot,
        internal val output: FrozenC63Output.Snapshot,
        internal val scalars: DoubleArray,
        internal val frames: Long,
        internal val delayIndex: Int,
        internal val bodyDelay: DoubleArray,
        internal val shiftDelay: BooleanArray,
    )

    fun snapshot() = Snapshot(
        snapshotKey,
        source.snapshot(),
        idle.snapshot(),
        shift.snapshot(),
        output.snapshot(),
        doubleArrayOf(rpm, load, throttle, lastShift, peak, rawPeak),
        frames,
        delayIndex,
        bodyDelay.copyOf(),
        shiftDelay.copyOf(),
    )

    fun restore(saved: Snapshot) {
        require(saved.scalars.size == 6) { "N2 renderer snapshot scalar mismatch" }
        val initializedStateValid =
            if (saved.frames == 0L) {
                saved.scalars[0].isNaN() && saved.scalars[1].isNaN() && saved.scalars[2].isNaN()
            } else {
                saved.scalars[0].isFinite() && saved.scalars[0] in 0.0..7200.0 &&
                    saved.scalars[1].isFinite() && saved.scalars[1] in 0.0..1.0 &&
                    saved.scalars[2].isFinite() && saved.scalars[2] in 0.0..1.0
            }
        val idleValid =
            saved.idle.values.size == 2 && saved.idle.values.all { it.isFinite() } &&
                saved.idle.counters.size == 5 &&
                saved.idle.counters[2] >= 0L &&
                saved.idle.counters[3] in 0L..384L &&
                saved.idle.counters[4] in 0L..191L &&
                saved.idle.arrays.size == 6 &&
                saved.idle.arrays[0].size == 2 &&
                saved.idle.arrays[1].size == 2 &&
                saved.idle.arrays[2].size == 385 &&
                saved.idle.arrays.slice(3..5).all { it.size == 192 } &&
                saved.idle.arrays.all { array -> array.all { it.isFinite() } }
        val shiftValid =
            saved.shift.age >= 0L && saved.shift.z1.isFinite() && saved.shift.z2.isFinite()
        val outputValid =
            saved.output.states.size == 5 && saved.output.states.all { it.isFinite() } &&
                saved.output.delay.size == 20 && saved.output.delay.all { it.isFinite() } &&
                saved.output.index in 0 until 20
        require(
            saved.key == snapshotKey &&
                initializedStateValid &&
                (saved.scalars[3].isFinite() || saved.scalars[3].isNaN()) &&
                saved.scalars[4].isFinite() && saved.scalars[4] >= 0.0 &&
                saved.scalars[5].isFinite() && saved.scalars[5] >= 0.0 &&
                saved.frames >= 0 &&
                saved.delayIndex in bodyDelay.indices &&
                saved.bodyDelay.size == bodyDelay.size &&
                saved.shiftDelay.size == shiftDelay.size &&
                saved.bodyDelay.all { it.isFinite() } &&
                idleValid && shiftValid && outputValid
        ) { "N2 renderer snapshot mismatch" }

        source.restore(saved.source)
        idle.restore(saved.idle)
        shift.restore(saved.shift)
        output.restore(saved.output)
        rpm = saved.scalars[0]
        load = saved.scalars[1]
        throttle = saved.scalars[2]
        lastShift = saved.scalars[3]
        peak = saved.scalars[4]
        rawPeak = saved.scalars[5]
        frames = saved.frames
        delayIndex = saved.delayIndex
        saved.bodyDelay.copyInto(bodyDelay)
        saved.shiftDelay.copyInto(shiftDelay)
    }

    fun render(state: SoundState, count: Int, validInput: Boolean = true): FloatArray {
        require(count > 0 && count <= 4800)
        require(
            state.timeS.isFinite() &&
                state.rpm.isFinite() && state.rpm in 0.0..7200.0 &&
                state.load.isFinite() && state.load in 0.0..1.0 &&
                state.throttle.isFinite() && state.throttle in 0.0..1.0
        )

        val result = if (count == 960) audioBuffer else FloatArray(count)
        if (!rpm.isFinite()) {
            rpm = state.rpm
            load = state.load
            throttle = state.throttle
        }
        val alpha = 1.0 - exp(-1.0 / (.035 * 48000.0))
        val shiftEvent = validInput && state.shiftTrigger && state.timeS != lastShift
        if (shiftEvent) lastShift = state.timeS

        for (n in result.indices) {
            rpm += alpha * (state.rpm - rpm)
            load += alpha * (state.load - load)
            throttle += alpha * (state.throttle - throttle)
            val r = rpm.coerceIn(0.0, 7200.0)
            val l = load.coerceIn(0.0, 1.0)
            val t = throttle.coerceIn(0.0, 1.0)

            val delayedBody = bodyDelay[delayIndex]
            val delayedShift = shiftDelay[delayIndex]
            bodyDelay[delayIndex] = source.sample(r, l, t, validInput).toDouble()
            shiftDelay[delayIndex] = shiftEvent && n == 0
            delayIndex = (delayIndex + 1) % bodyDelay.size

            val body = delayedBody + idle.sample(r, l, t)
            val raw = output.sample(shift.sample(body, delayedShift))
            rawPeak = max(rawPeak, abs(raw))
            val value = raw * C63HeadroomProfile.SCALAR
            peak = max(peak, abs(value))
            frames++
            check(value.isFinite()) { "N2 candidate nonfinite output rejected" }
            result[n] = value.toFloat()
        }
        return result
    }
}
