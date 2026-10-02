package com.vico.simulator.sound

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.security.MessageDigest
import java.util.Properties
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Opt-in paired renderer/review-session regression for the external RPM guard candidate. */
class S13C63RpmGuardBankTest {
    private data class Condition(val rpm: Double, val load: Double) {
        val id: String get() = "rpm_${rpm.toInt()}_load_${(load * 100).toInt()}"
    }

    private val fixedConditions = listOf(
        Condition(5200.0, 0.32), Condition(5500.0, 0.32), Condition(6100.0, 0.32),
        Condition(5200.0, 0.92), Condition(5500.0, 0.92), Condition(6100.0, 0.92),
    )
    private val holdoutConditions = listOf(
        Condition(5450.0, 0.32), Condition(5550.0, 0.32),
        Condition(5450.0, 0.92), Condition(5550.0, 0.92),
    )

    @Test
    fun external_candidate_uses_real_renderer_without_touching_production_and_emits_paired_evidence() {
        val outputValue = System.getenv("VICO_S13_C63_RPM_GUARD_OUTPUT_ROOT")
        assumeTrue("Prepare the external RPM guard candidate first", !outputValue.isNullOrBlank())
        val outputRoot = Paths.get(requireNotNull(outputValue))
        assertTrue("Candidate output must be outside the app repository", !outputRoot.toAbsolutePath().startsWith(Paths.get("E:\\project\\Tesla_vico_app")))
        assertTrue("Use a fresh candidate capture root", !Files.exists(outputRoot.resolve("candidate_capture_manifest.json")))

        val candidateManifestPath = outputRoot.resolve("candidate_manifest.json")
        val candidateManifestBytes = Files.readAllBytes(candidateManifestPath)
        val candidateManifestText = String(candidateManifestBytes, Charsets.UTF_8)
        assertTrue(candidateManifestText.contains("\"schema\": \"vico.s13.c63.rpm_guard_candidate.v1\""))
        assertTrue(candidateManifestText.contains("\"vehicle_key\": \"c63_w204_v6\""))
        assertTrue(candidateManifestText.contains("\"new_rpm_levels\""))
        assertTrue(candidateManifestText.contains("5400"))
        assertTrue(candidateManifestText.contains("5600"))
        val candidateManifestSha = S13ReviewContract.sha256(candidateManifestBytes)

        val phase = loadProperties(outputRoot.resolve("phase.properties"))
        assertEquals(candidateManifestSha, phase.getProperty("candidate_manifest_sha256"))
        val appRoot = Paths.get(phase.getProperty("app_root"))
        val experimentRoot = Paths.get(phase.getProperty("r4_root"))
        val experimentProperties = loadProperties(experimentRoot.resolve("inputs/experiment.properties"))
        val traceBytes = Files.readAllBytes(
            appRoot.resolve("Project/android/app/src/main/assets/s12_v10/c63_w204_v6/common_input_trace.json"),
        )
        val trace = S13TraceCursor(readTrace(experimentRoot.resolve("inputs/trace_points.tsv")))
        val events = readEvents(experimentRoot.resolve("inputs/events.tsv"), appRoot, traceBytes)
        val transients = readTransients(experimentRoot.resolve("inputs/transients.tsv"), appRoot)
        val afterfire = transients.single { it.first == "afterfire" }.second
        val shifts = transients.filter { it.first == "shift" }.map { it.second }
        val powertrain = readPowertrain(experimentRoot.resolve("inputs/powertrain.tsv"))

        val parentRows = experimentRoot.resolve("variants/A/loops.tsv")
        val candidateRows = outputRoot.resolve("loops.tsv")
        val aLoops = readLoops(parentRows, appRoot, experimentRoot, outputRoot)
        val bLoops = readLoops(candidateRows, appRoot, experimentRoot, outputRoot)
        assertEquals(16, aLoops.size)
        assertEquals(20, bLoops.size)
        assertEquals(listOf(5400.0, 5600.0), bLoops.map { it.rpm }.distinct().filter { it == 5400.0 || it == 5600.0 })
        assertTrue(bLoops.all { it.samples.size == 17_280 && it.samples.all(Float::isFinite) })

        val bankA = MatlabSoundBank("c63_w204_v6", S13ReviewContract.SAMPLE_RATE, powertrain, aLoops, afterfire.samples, shifts)
        val bankB = MatlabSoundBank("c63_w204_v6", S13ReviewContract.SAMPLE_RATE, powertrain, bLoops, afterfire.samples, shifts)
        val packageA = S13ReviewPackage(
            "c63_w204_v6", experimentProperties.getProperty("source_commit"),
            S13ReviewContract.sha256(traceBytes), experimentProperties.getProperty("manifest_sha256"),
            experimentProperties.getProperty("fixed_vehicle_gain").toDouble(), trace, events,
        )
        val packageB = packageA.copy(bankManifestSha256 = candidateManifestSha)

        val fixedJson = linkedMapOf<String, String>()
        for (condition in fixedConditions) {
            val a = renderConstant(bankA, condition)
            val b = renderConstant(bankB, condition)
            assertTrue("A must remain finite and unclipped at ${condition.id}", a.stats.hardClipFrames == 0L && a.stats.nonFiniteFrames == 0L)
            assertTrue("B must remain finite and unclipped at ${condition.id}", b.stats.hardClipFrames == 0L && b.stats.nonFiniteFrames == 0L)
            if (condition.rpm == 5500.0) assertArrayEquals("5500 center control must remain exact", a.pcm, b.pcm, 0f)
            fixedJson[condition.id] = conditionJson(outputRoot, "fixed", condition, a.pcm, b.pcm, a.stats, b.stats)
        }

        val holdoutJson = linkedMapOf<String, String>()
        for (condition in holdoutConditions) {
            val a = renderConstant(bankA, condition)
            val b = renderConstant(bankB, condition)
            assertTrue("Holdout A must be finite and unclipped at ${condition.id}", a.stats.hardClipFrames == 0L && a.stats.nonFiniteFrames == 0L)
            assertTrue("Holdout B must be finite and unclipped at ${condition.id}", b.stats.hardClipFrames == 0L && b.stats.nonFiniteFrames == 0L)
            holdoutJson[condition.id] = conditionJson(outputRoot, "holdout", condition, a.pcm, b.pcm, a.stats, b.stats)
        }

        val dynamicASession = S13ReviewSession(bankA, packageA)
        val dynamicBSession = S13ReviewSession(bankB, packageB)
        val dynamicA = dynamicASession.renderAll()
        val dynamicB = dynamicBSession.renderAll()
        val dynamicAStats = dynamicASession.mixStats()
        val dynamicBStats = dynamicBSession.mixStats()
        assertEquals(S13ReviewContract.TOTAL_FRAMES, dynamicA.size)
        assertEquals(S13ReviewContract.TOTAL_FRAMES, dynamicB.size)
        assertTrue(dynamicA.all(Float::isFinite) && dynamicB.all(Float::isFinite))
        assertEquals(S13ReviewContract.TOTAL_FRAMES.toLong(), dynamicAStats.evaluatedFrames)
        assertEquals(S13ReviewContract.TOTAL_FRAMES.toLong(), dynamicBStats.evaluatedFrames)
        assertEquals(0L, dynamicAStats.hardClipFrames)
        assertEquals(0L, dynamicBStats.hardClipFrames)
        assertEquals(0L, dynamicAStats.nonFiniteFrames)
        assertEquals(0L, dynamicBStats.nonFiniteFrames)
        writeFloatArray(outputRoot.resolve("dynamic/a.f32le"), dynamicA)
        writeFloatArray(outputRoot.resolve("dynamic/b.f32le"), dynamicB)
        assertEquals(experimentProperties.getProperty("d1_sha256"), sha256File(outputRoot.resolve("dynamic/a.f32le")))

        val fixedObject = fixedJson.entries.joinToString(",") { (key, value) -> "\"$key\":$value" }
        val holdoutObject = holdoutJson.entries.joinToString(",") { (key, value) -> "\"$key\":$value" }
        val dynamicObject = "{\"a_pcm\":${pcmJson("dynamic/a.f32le", outputRoot.resolve("dynamic/a.f32le"), dynamicA.size)}," +
            "\"b_pcm\":${pcmJson("dynamic/b.f32le", outputRoot.resolve("dynamic/b.f32le"), dynamicB.size)}," +
            "\"stats\":{\"a\":${statsJson(dynamicAStats)},\"b\":${statsJson(dynamicBStats)}}}"
        val manifest = "{\"schema\":\"vico.s13.c63.rpm_guard_capture.v2\",\"candidate_manifest_sha256\":\"$candidateManifestSha\"," +
            "\"frozen_d1_sha256\":\"${experimentProperties.getProperty("d1_sha256")}\",\"trace_sha256\":\"${experimentProperties.getProperty("trace_sha256")}\"," +
            "\"source_commit\":\"${experimentProperties.getProperty("source_commit")}\",\"fixed_vehicle_gain\":${experimentProperties.getProperty("fixed_vehicle_gain")}," +
            "\"fixed_conditions\":{$fixedObject},\"holdout_conditions\":{$holdoutObject},\"dynamic\":$dynamicObject}"
        Files.write(outputRoot.resolve("candidate_capture_manifest.json"), manifest.toByteArray(Charsets.UTF_8))
    }

    private data class Rendered(val pcm: FloatArray, val stats: S13MixSnapshot)

    private fun renderConstant(bank: MatlabSoundBank, condition: Condition): Rendered {
        val frameCount = 4 * S13ReviewContract.SAMPLE_RATE
        val renderer = MatlabStatefulBankRenderer(bank)
        val state = SoundState(
            timeS = 0.0, rpm = condition.rpm, frequencyHz = condition.rpm / 60.0 * 4.0,
            amplitude = maxOf(0.08, condition.load), brightness = condition.load, harmonics = floatArrayOf(),
            muted = false, throttle = condition.load, load = condition.load, braking = false,
            shiftGain = 1.0,
        )
        val pcm = FloatArray(frameCount)
        var offset = 0
        while (offset < frameCount) {
            val count = minOf(S13ReviewContract.BLOCK_FRAMES, frameCount - offset)
            renderer.renderReview(state, state, offset, count, emptyList()).copyInto(pcm, offset)
            offset += count
        }
        return Rendered(pcm, renderer.mixStats())
    }

    private fun conditionJson(
        root: Path, directory: String, condition: Condition, a: FloatArray, b: FloatArray,
        aStats: S13MixSnapshot, bStats: S13MixSnapshot,
    ): String {
        val relative = "$directory/${condition.id}"
        val aPath = root.resolve(relative).resolve("a.f32le")
        val bPath = root.resolve(relative).resolve("b.f32le")
        writeFloatArray(aPath, a)
        writeFloatArray(bPath, b)
        return "{\"rpm\":${condition.rpm},\"load\":${condition.load}," +
            "\"a_pcm\":${pcmJson("$relative/a.f32le", aPath, a.size)}," +
            "\"b_pcm\":${pcmJson("$relative/b.f32le", bPath, b.size)}," +
            "\"stats\":{\"a_hard_clip\":${aStats.hardClipFrames},\"b_hard_clip\":${bStats.hardClipFrames}," +
            "\"a_non_finite\":${aStats.nonFiniteFrames},\"b_non_finite\":${bStats.nonFiniteFrames}}}"
    }

    private fun pcmJson(relative: String, path: Path, frames: Int): String =
        "{\"path\":\"$relative\",\"sha256\":\"${sha256File(path)}\",\"frames\":$frames}"

    private fun statsJson(stats: S13MixSnapshot): String =
        "{\"evaluated_frames\":${stats.evaluatedFrames},\"pre_clip_peak\":${stats.preClipPeak}," +
            "\"above_contract_frames\":${stats.aboveContractFrames},\"hard_clip_frames\":${stats.hardClipFrames}," +
            "\"non_finite_frames\":${stats.nonFiniteFrames},\"load_out_of_bank_frames\":${stats.loadOutOfBankFrames}," +
            "\"rpm_out_of_bank_frames\":${stats.rpmOutOfBankFrames},\"rejected_input_blocks\":${stats.rejectedInputBlocks}}"

    private fun loadProperties(path: Path) = Properties().apply { Files.newInputStream(path).use(::load) }

    private fun readLoops(path: Path, appRoot: Path, experimentRoot: Path, candidateRoot: Path): List<MatlabLoop> =
        Files.readAllLines(path).drop(1).map { line ->
            val fields = line.split('\t')
            require(fields.size >= 5)
            val base = when (fields[0]) {
                "app" -> appRoot
                "experiment" -> experimentRoot
                "candidate" -> candidateRoot
                else -> error("Unknown loop root: ${fields[0]}")
            }
            val bytes = Files.readAllBytes(base.resolve(fields[1]))
            assertEquals(fields[4], S13ReviewContract.sha256(bytes))
            val decoded = FloatWavDecoder.decode(bytes)
            assertEquals(S13ReviewContract.SAMPLE_RATE, decoded.sampleRateHz)
            MatlabLoop(fields[2].toDouble(), fields[3].toDouble(), decoded.samples)
        }

    private fun readPowertrain(path: Path): MatlabPowertrainSpec {
        val values = Files.readAllLines(path).drop(1).associate { line ->
            val (key, value) = line.split('\t', limit = 2); key to value
        }
        val ratios = values.getValue("gear_ratios").removePrefix("[").removeSuffix("]")
            .split(',').map { it.trim().toDouble() }.toDoubleArray()
        fun number(key: String) = values.getValue(key).toDouble()
        return MatlabPowertrainSpec(
            idleRpm = number("idle_rpm"), redlineRpm = number("redline_rpm"), gearRatios = ratios,
            finalDrive = number("final_drive"), wheelRadiusM = number("wheel_radius_m"),
            launchRpm = number("launch_rpm"), shiftRpm = number("shift_rpm"),
            shiftAttackS = number("shift_attack_s"), shiftHoldS = number("shift_hold_s"),
            shiftRecoveryS = number("shift_recovery_s"), shiftSettleS = number("shift_settle_s"),
            shiftMinTorque = number("shift_min_torque"), shiftReengageGain = number("shift_reengage_gain"),
            minimumShiftIntervalS = number("minimum_shift_interval_s"), downshiftRatio = number("downshift_ratio"),
            speedCeilingKmh = number("speed_ceiling_kmh"), afterfireMinimumRpm = number("afterfire_minimum_rpm"),
        )
    }

    private fun readTrace(path: Path): List<S13TracePoint> = Files.readAllLines(path).drop(1).map { line ->
        val fields = line.split('\t')
        S13TracePoint(fields[0].toDouble(), fields[1].toDouble(), fields[2].toDouble(), fields[3].toDouble(), fields[4].toDouble())
    }

    private fun readEvents(path: Path, appRoot: Path, traceBytes: ByteArray): List<S13EventPlacement> =
        Files.readAllLines(path).drop(1).map { line ->
            val fields = line.split('\t')
            val assetPath = fields[2]
            val assetBytes = Files.readAllBytes(appRoot.resolve("Project/android/app/src/main/assets").resolve(assetPath))
            val binding = S13EventBinding(
                fields[0], fields[1], assetPath, fields[3], fields[4], fields[5], fields[6].toDouble(),
                fields[7].toInt(), fields[8].toInt(), fields[9].toInt(), fields[10].toInt(),
            )
            val decoded = FloatWavDecoder.decode(assetBytes)
            binding.validate(traceBytes, assetBytes, decoded.samples.size)
        }

    private fun readTransients(path: Path, appRoot: Path): List<Pair<String, MatlabTransient>> =
        Files.readAllLines(path).drop(1).map { line ->
            val fields = line.split('\t')
            val bytes = Files.readAllBytes(appRoot.resolve(fields[2]))
            assertEquals(fields[3], S13ReviewContract.sha256(bytes))
            val decoded = FloatWavDecoder.decode(bytes)
            assertEquals(S13ReviewContract.SAMPLE_RATE, decoded.sampleRateHz)
            fields[0] to MatlabTransient(fields[2].substringAfterLast('/'), decoded.samples)
        }

    private fun writeFloatArray(path: Path, values: FloatArray) {
        Files.createDirectories(requireNotNull(path.parent))
        val buffer = ByteBuffer.allocate(16_384).order(ByteOrder.LITTLE_ENDIAN)
        Files.newOutputStream(path).use { stream ->
            var offset = 0
            while (offset < values.size) {
                buffer.clear()
                repeat(minOf(buffer.capacity() / 4, values.size - offset)) { buffer.putFloat(values[offset++]) }
                stream.write(buffer.array(), 0, buffer.position())
            }
        }
    }

    private fun sha256File(path: Path): String = MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path))
        .joinToString("") { "%02x".format(it.toInt() and 0xff) }
}
