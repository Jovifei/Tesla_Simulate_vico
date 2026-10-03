package com.vico.simulator.sound.n2

import com.vico.simulator.sound.SoundState
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.Collections
import kotlin.math.roundToInt

/** Test-only reconstruction of the historical 333 qualification + 297 holdout cases.
 * Missing external inputs are inventory entries, never substituted trajectories or passes.
 */
internal class N2HistoricalStateCatalog(originalTraceBytes: ByteArray) {
    internal class Entry internal constructor(
        val id: String,
        val group: String,
        val missingInput: String?,
        private val make: (() -> N2QualificationFixture)?,
    ) {
        val frames: Int?
        val segments: Int?
        val fixtureSha256: String?
        val historicalInputSha256: String?
        init {
            val initial = make?.invoke()
            frames = initial?.frames
            segments = initial?.segments()?.size
            fixtureSha256 = initial?.sha256
            // Same LE six-double row contract used by C63HeadroomCalibrationTest.
            historicalInputSha256 = initial?.let { fixture ->
            val hash = MessageDigest.getInstance("SHA-256")
            val row = ByteBuffer.allocate(48).order(ByteOrder.LITTLE_ENDIAN)
            fixture.segments().forEach { segment ->
                val s = segment.state
                row.clear(); row.putDouble(s.timeS).putDouble(s.rpm).putDouble(s.load)
                    .putDouble(s.throttle).putDouble(if (s.shiftTrigger) 1.0 else 0.0)
                    .putDouble(segment.frames.toDouble())
                hash.update(row.array())
            }
            hash.digest().joinToString("") { "%02x".format(it) }
            }
        }
        val available: Boolean get() = make != null
        fun fixture(): N2QualificationFixture {
            check(make != null) { "$id unavailable: $missingInput" }
            return make.invoke().also { check(it.sha256 == fixtureSha256 && it.frames == frames) }
        }
    }

    val entries: List<Entry>
    val available: List<Entry>
    val totalAvailableFrames: Long
    private val manifest: ByteArray
    val sha256: String

    init {
        require(N2QualificationExport.sha(originalTraceBytes) == ORIGINAL_TRACE_SHA256) {
            "Historical Q1 source bytes do not match the frozen checked-in trace"
        }
        val text = originalTraceBytes.toString(Charsets.UTF_8)
        fun field(name: String) = Regex("\"$name\"\\s*:\\s*([-+0-9.eE]+)")
            .findAll(text).map { it.groupValues[1].toDouble() }.toList()
        val r = field("rpm"); val l = field("load"); val h = field("throttle")
        require(r.size == 1501 && l.size == 1501 && h.size == 1501)
        val shifts = doubleArrayOf(6.100416666666667, 8.620291666666667, 11.1424375)
        var event = 0
        // Historical generator deliberately consumes 1500 of the trace's 1501 records.
        val original = (0 until 1500).map { n ->
            val t = n * .02
            val trigger = event < shifts.size && t >= shifts[event]
            if (trigger) event++
            state(t, r[n], l[n], h[n], trigger)
        }
        val all = mutableListOf<Entry>()
        fun add(id: String, group: String, points: () -> List<SoundState>) {
            all.add(Entry(id, group, null) {
                N2QualificationFixture(id, points().map { N2TrajectorySegment(it, 960) })
            })
        }
        fun missing(id: String, group: String, input: String) { all.add(Entry(id, group, input, null)) }
        for (rpm in listOf(700.0, 1400.0, 2200.0, 3200.0, 4300.0, 5500.0, 6800.0, 7200.0))
            for (load in listOf(0.0, .32, .92, 1.0))
                add("Q0_steady_${rpm}_$load", "Q0") { (0 until 150).map { state(it * .02, rpm, load, load) } }
        for (start in listOf(700.0, 1800.0, 5500.0, 7200.0)) for (end in listOf(700.0, 1800.0, 5500.0, 7200.0))
            add("Q0_transition_${start}_$end", "Q0") {
                (0 until 200).map { n -> val t = n * .02; val f = ((t - .5) / .6).coerceIn(0.0, 1.0)
                    state(t, start + (end - start) * f, if (t < 2) 1.0 else .1, if (t < 2) 1.0 else .05, n == 75) }
            }
        missing("Q0_phone", "Q0", PHONE_INPUT)
        add("Q1_original", "Q1") { original }
        missing("Q1_phone_plus_hold", "Q1", PHONE_INPUT)
        for (f in listOf(540.0, 820.0, 1100.0, 1500.0)) for (k in 1..32) {
            val rpm = 15 * f / k
            if (rpm >= 700 && rpm <= 7200)
                add("Q2_${f}_$k", "Q2") { (0 until 150).map { state(it * .02, rpm, 1.0, 1.0) } }
        }
        for (up in listOf(true, false)) add("Q3_sweep_$up", "Q3") {
            (0 until 3250).map { n -> val f = n / 3249.0
                state(n * .02, if (up) 700 + 6500 * f else 7200 - 6500 * f, 1.0, 1.0) }
        }
        add("Q3_hot_events", "Q3") { (0 until 600).map { n ->
            val t = n * .02; val high = t < 3 || t >= 5 && t < 8
            state(t, if (high) 5000.0 else 4000.0, if (high) .9 else .05, if (high) .9 else .05, n == 150 || n == 400)
        } }
        repeat(3) { add("Q3_restart_$it", "Q3") { original.take(250) } }
        for (rpm in listOf(700.0, 1400.0, 1849.0, 1850.0, 1851.0)) for (load in listOf(0.0, .2, .32, .5, 1.0))
            for (throttle in listOf(0.0, .2, .35, 1.0)) for (hot in listOf(false, true))
                add("Q4_${rpm}_${load}_${throttle}_$hot", "Q4") {
                    val warm = if (hot) (0 until 100).map { state(-2 + it * .02, 5000.0, .9, .9) } else emptyList()
                    warm + (0 until 150).map { state(it * .02, rpm, load, throttle) }
                }
        // Preserve the known frozen inventory size without inventing its missing RPM values.
        repeat(290) { missing("H1_$it", "H1", "holdout-manifest.json:sha256=$HOLDOUT_MANIFEST_SHA256") }
        for (duration in listOf(.12, 1.5, 12.0)) for (hot in listOf(false, true))
            add("H2_${duration}_$hot", "H2") {
                val points = mutableListOf<SoundState>(); var t = 0.0
                if (hot) repeat(100) { points.add(state(t, 5000.0, .9, .9)); t += .02 }
                val rpms = listOf(700.0, 2050.0, 4100.0, 6150.0, 7200.0, 700.0)
                for (i in 0 until rpms.size - 1) {
                    val count = (duration / .02).roundToInt()
                    repeat(count) { n -> points.add(state(t, rpms[i] + (rpms[i + 1] - rpms[i]) * (n + 1) / count, 1.0, 1.0)); t += .02 }
                    repeat(50) { points.add(state(t, rpms[i + 1], 1.0, 1.0)); t += .02 }
                }
                points
            }
        add("H3_events", "H3") { (0 until 450).map { n -> val t = n * .02
            when {
                t < 2 -> state(t, 700.0, .14, .14)
                t < 5 -> state(t, 5000.0, .9, .9)
                t < 6 -> state(t, 4000.0, .05, .05, n == 250)
                t < 8 -> state(t, 4000.0, .8, .8)
                else -> state(t, 3000.0, .05, .05, n == 400)
            }
        } }
        entries = Collections.unmodifiableList(all.toList())
        available = Collections.unmodifiableList(all.filter { it.available })
        check(entries.size == 630 && entries.map { it.id }.toSet().size == 630 && available.size == 338)
        totalAvailableFrames = available.sumOf { requireNotNull(it.frames).toLong() }
        check(totalAvailableFrames == 74_697_600L)
        manifest = buildString {
            append("schema\tc63.n2.historical_state_catalog.v1\n")
            append("status\tINCOMPLETE_INPUT_INVENTORY_NOT_QUALIFICATION\n")
            append("original_trace_sha256\t$ORIGINAL_TRACE_SHA256\n")
            append("holdout_manifest_required_sha256\t$HOLDOUT_MANIFEST_SHA256\n")
            append("id\tgroup\tinput_status\tframes\tsegments\tfixture_sha256\thistorical_input_sha256\tmissing_input\n")
            entries.forEach { append(listOf(it.id, it.group, if (it.available) "AVAILABLE" else "MISSING",
                it.frames ?: "", it.segments ?: "", it.fixtureSha256 ?: "", it.historicalInputSha256 ?: "", it.missingInput ?: "")
                .joinToString("\t")).append('\n') }
        }.toByteArray(Charsets.UTF_8)
        sha256 = N2QualificationExport.sha(manifest)
    }

    fun bytes() = manifest.copyOf()
    fun entry(id: String): Entry = entries.single { it.id == id }

    companion object {
        const val ORIGINAL_TRACE_SHA256 = "ab1bf8c8335ec5224b18d501bf1fcf16d70c84f6a6371cdb88da5a08db554619"
        const val HOLDOUT_MANIFEST_SHA256 = "757d9405b5e9b69a3247a671e27079081d373dfc012b77c3d525b871cd2954b1"
        const val PHONE_INPUT = "device-smoke-performance-fix.json:exact-row-frame-counts-required-1..4800"
        const val TRACE_PATH = "app/src/main/assets/s12_v10/c63_w204_v6/common_input_trace.json"
        /** Standalone runner starts at android/; Gradle's app tests start at android/app/. */
        fun checkedInTraceFile(workingDirectory: File = File(".")): File {
            val candidates = listOf(TRACE_PATH, TRACE_PATH.removePrefix("app/"))
                .map { File(workingDirectory, it) }.filter { it.isFile }
            require(candidates.size == 1) { "Expected one historical trace under the Android project or app module root" }
            return candidates.single()
        }
        fun fromCheckedInTrace() = N2HistoricalStateCatalog(checkedInTraceFile().readBytes())
        private fun state(t: Double, r: Double, l: Double, h: Double, shift: Boolean = false) =
            SoundState(t, r, r / 60 * 4, l, l, floatArrayOf(), false, h, l, shiftTrigger = shift)
    }
}
