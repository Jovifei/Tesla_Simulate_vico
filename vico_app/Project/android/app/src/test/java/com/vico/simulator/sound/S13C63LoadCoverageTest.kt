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

/** External, opt-in C63 ablation using the production review renderer and frozen WAV inputs. */
class S13C63LoadCoverageTest {
    @Test
    fun c63_candidate_variants_match_the_frozen_phone_baseline_and_preserve_in_range_pcm() {
        val rootValue = System.getenv("VICO_S13_C63_EXPERIMENT_ROOT")
        assumeTrue("Run the C63 ablation generator first", !rootValue.isNullOrBlank())
        val root = Paths.get(requireNotNull(rootValue))
        val renderDirectory = root.resolve("renders")
        if (Files.exists(renderDirectory)) {
            Files.newDirectoryStream(renderDirectory).use { entries ->
                require(!entries.iterator().hasNext()) {
                    "Render outputs already exist; use a fresh experiment root"
                }
            }
        }
        val properties = Properties().apply {
            Files.newInputStream(root.resolve("inputs/experiment.properties")).use { load(it) }
        }
        val appRoot = Paths.get(properties.getProperty("app_root"))
        val tracePath = appRoot.resolve("Project/android/app/src/main/assets/s12_v10/c63_w204_v6/common_input_trace.json")
        val traceBytes = Files.readAllBytes(tracePath)
        val traceSha = S13ReviewContract.sha256(traceBytes)
        assertEquals(properties.getProperty("trace_sha256"), traceSha)
        assertEquals("c63_w204_v6", properties.getProperty("vehicle_key"))
        assertEquals("29b50961d9628f835e7172b797380ccb36a7f38d", properties.getProperty("source_commit"))

        val trace = S13TraceCursor(readTrace(root.resolve("inputs/trace_points.tsv")))
        val events = readEvents(root.resolve("inputs/events.tsv"), appRoot, traceBytes)
        assertEquals("All four SHA-bound C63 events must load", 4, events.size)
        val transients = readTransients(root.resolve("inputs/transients.tsv"), appRoot)
        val afterfire = transients.single { it.first == "afterfire" }.second
        val shifts = transients.filter { it.first == "shift" }.map { it.second }
        val powertrain = readPowertrain(root.resolve("inputs/powertrain.tsv"))
        val phoneD1 = readF32le(Paths.get(properties.getProperty("d1_path")))
        assertEquals(S13ReviewContract.TOTAL_FRAMES, phoneD1.size)
        assertEquals(properties.getProperty("d1_sha256"), sha256FloatArray(phoneD1))

        val variantsRoot = root.resolve("variants")
        val baseline = renderVariant("A", variantsRoot, root, appRoot, properties, powertrain,
            afterfire.samples, shifts, trace, events)
        val baselineError = compare(phoneD1, baseline.pcm)
        val maxAbsTolerance = properties.getProperty("d1_max_abs_tolerance").toDouble()
        val rmseTolerance = properties.getProperty("d1_rmse_tolerance").toDouble()
        writeRender(root, "A", baseline, baselineError)
        assertTrue("A must reproduce frozen phone D1 before any B result is interpreted: $baselineError",
            baselineError.maxAbs <= maxAbsTolerance && baselineError.rmse <= rmseTolerance)

        val variants = listOf("B-low", "B-high", "B-both").filter {
            Files.isDirectory(variantsRoot.resolve(it))
        }
        assertTrue("At least one trace-derived edge candidate is required", variants.isNotEmpty())

        val inRangeTrace = S13TraceCursor(List(S13ReviewContract.TRACE_POINTS) { index ->
            val fraction = index / (S13ReviewContract.TRACE_POINTS - 1).toDouble()
            S13TracePoint(index / 50.0, 3200.0, 0.32 + 0.60 * fraction, 0.5, 0.0)
        })
        val inRangeReference = renderVariant("A", variantsRoot, root, appRoot, properties, powertrain,
            afterfire.samples, shifts, inRangeTrace, emptyList()).pcm
        writeControl(root, "A", inRangeReference, ErrorMetrics(0.0, 0.0))

        for (variant in variants) {
            val rendered = renderVariant(variant, variantsRoot, root, appRoot, properties, powertrain,
                afterfire.samples, shifts, trace, events)
            val error = compare(phoneD1, rendered.pcm)
            assertEquals(S13ReviewContract.TOTAL_FRAMES.toLong(), rendered.stats.evaluatedFrames)
            assertEquals(0L, rendered.stats.nonFiniteFrames)
            assertEquals(0L, rendered.stats.hardClipFrames)
            writeRender(root, variant, rendered, error)

            val inRangePcm = renderVariant(variant, variantsRoot, root, appRoot, properties, powertrain,
                afterfire.samples, shifts, inRangeTrace, emptyList()).pcm
            val controlError = compare(inRangeReference, inRangePcm)
            assertArrayEquals("$variant must leave the original in-range renderer unchanged",
                inRangeReference, inRangePcm, 0f)
            writeControl(root, variant, inRangePcm, controlError)
        }
    }

    @Test
    fun c63_in_range_anchor_components_reconstruct_the_continuous_renderer_without_phase_reset() {
        val outputValue = System.getenv("VICO_S13_C63_ANCHOR_OUTPUT_ROOT")
        assumeTrue("Prepare the C63 anchor-coherence window package first", !outputValue.isNullOrBlank())
        val outputRoot = Paths.get(requireNotNull(outputValue))
        val componentsDirectory = outputRoot.resolve("components")
        if (Files.exists(componentsDirectory)) {
            Files.newDirectoryStream(componentsDirectory).use { entries ->
                require(!entries.iterator().hasNext()) { "Anchor PCM outputs already exist; use a fresh root" }
            }
        }
        val phaseProperties = Properties().apply {
            Files.newInputStream(outputRoot.resolve("phase.properties")).use { load(it) }
        }
        val experimentRoot = Paths.get(phaseProperties.getProperty("r4_root"))
        val experimentProperties = Properties().apply {
            Files.newInputStream(experimentRoot.resolve("inputs/experiment.properties")).use { load(it) }
        }
        val appRoot = Paths.get(experimentProperties.getProperty("app_root"))
        val traceBytes = Files.readAllBytes(
            appRoot.resolve("Project/android/app/src/main/assets/s12_v10/c63_w204_v6/common_input_trace.json"),
        )
        assertEquals(phaseProperties.getProperty("trace_sha256"), S13ReviewContract.sha256(traceBytes))
        val points = readTrace(experimentRoot.resolve("inputs/trace_points.tsv"))
        val trace = S13TraceCursor(points)
        val windows = Files.readAllLines(outputRoot.resolve("windows.tsv")).drop(1).map { line ->
            val fields = line.split('\t')
            require(fields.size == 5)
            fields[1].toInt() until fields[2].toInt()
        }
        assertEquals(phaseProperties.getProperty("stable_window_count").toInt(), windows.size)
        assertTrue("The phase diagnosis requires several stable in-range windows", windows.size >= 5)

        val powertrain = readPowertrain(experimentRoot.resolve("inputs/powertrain.tsv"))
        val loops = readLoops(
            experimentRoot.resolve("variants/A/loops.tsv"), appRoot, experimentRoot,
        )
        assertEquals(16, loops.size)
        assertTrue(loops.all { it.samples.size == 17_280 })
        val bank = MatlabSoundBank(
            vehicleKey = "c63_w204_v6",
            sampleRateHz = S13ReviewContract.SAMPLE_RATE,
            powertrain = powertrain,
            loops = loops,
            afterfire = FloatArray(0),
            shiftEvents = emptyList(),
        )
        val reviewPackage = S13ReviewPackage(
            vehicleKey = "c63_w204_v6",
            sourceCommit = experimentProperties.getProperty("source_commit"),
            traceSha256 = phaseProperties.getProperty("trace_sha256"),
            bankManifestSha256 = phaseProperties.getProperty("manifest_sha256"),
            fixedVehicleGain = experimentProperties.getProperty("fixed_vehicle_gain").toDouble(),
            trace = trace,
            events = emptyList(),
        )

        val continuous = S13ReviewSession(bank, reviewPackage).renderAll()
        val phoneA = readF32le(experimentRoot.resolve("renders/A.f32le"))
        val continuousWindows = sliceWindows(continuous, windows)
        val phoneWindows = sliceWindows(phoneA, windows)
        val phoneError = compare(continuousWindows, phoneWindows)
        assertTrue("The event-free render must match A on event-free stable windows: $phoneError",
            phoneError.maxAbs <= 2e-5 && phoneError.rmse <= 2e-6)
        writeF32le(outputRoot.resolve("renderer_mix_stable_windows.f32le"), continuousWindows)
        writeF32le(outputRoot.resolve("phone_A_stable_windows.f32le"), phoneWindows)

        val componentRows = ArrayList<List<Any>>()
        val componentSum = FloatArray(continuousWindows.size)
        for (anchor in loops) {
            val isolatedLoops = loops.map { loop ->
                if (loop.rpm == anchor.rpm && loop.load == anchor.load) loop
                else loop.copy(samples = FloatArray(loop.samples.size))
            }
            val isolatedBank = bank.copy(
                loops = isolatedLoops,
                afterfire = FloatArray(bank.afterfire.size),
                shiftEvents = emptyList(),
            )
            val isolated = S13ReviewSession(isolatedBank, reviewPackage)
            val rendered = isolated.renderAll()
            assertEquals(S13ReviewContract.TOTAL_FRAMES.toLong(), isolated.mixStats().evaluatedFrames)
            assertEquals(0L, isolated.mixStats().hardClipFrames)
            assertEquals(0L, isolated.mixStats().nonFiniteFrames)
            val windowed = sliceWindows(rendered, windows)
            for (index in componentSum.indices) componentSum[index] += windowed[index]
            val name = "rpm_${anchor.rpm.toInt().toString().padStart(4, '0')}_load_${(anchor.load * 100).toInt().toString().padStart(2, '0')}.f32le"
            val path = componentsDirectory.resolve(name)
            val hash = writeF32le(path, windowed)
            componentRows += listOf(anchor.rpm.toInt(), anchor.load, "components/$name", hash, windowed.size)
        }
        val reconstructionError = compare(componentSum, continuousWindows)
        assertTrue("The isolated anchor contributions must reconstruct the production mix: $reconstructionError",
            reconstructionError.maxAbs <= 2e-5 && reconstructionError.rmse <= 2e-6)
        val componentSumSha = writeF32le(outputRoot.resolve("anchor_sum_stable_windows.f32le"), componentSum)
        val componentManifest = buildString {
            appendLine("rpm\tload\tpath\tsha256\tframes")
            componentRows.forEach { appendLine(it.joinToString("\t")) }
        }
        Files.write(outputRoot.resolve("components.tsv"), componentManifest.toByteArray(Charsets.UTF_8))
        val decomposition = "window_count\tframes\tphone_max_abs\tphone_rmse\tanchor_max_abs\tanchor_rmse\tanchor_sum_sha256\n" +
            "${windows.size}\t${continuousWindows.size}\t${phoneError.maxAbs}\t${phoneError.rmse}\t" +
            "${reconstructionError.maxAbs}\t${reconstructionError.rmse}\t$componentSumSha\n"
        Files.write(outputRoot.resolve("decomposition.tsv"), decomposition.toByteArray(Charsets.UTF_8))
    }

    private data class Rendered(val pcm: FloatArray, val stats: S13MixSnapshot)
    private data class ErrorMetrics(val maxAbs: Double, val rmse: Double)

    private fun renderVariant(
        variant: String,
        variantsRoot: Path,
        experimentRoot: Path,
        appRoot: Path,
        properties: Properties,
        powertrain: MatlabPowertrainSpec,
        afterfire: FloatArray,
        shifts: List<MatlabTransient>,
        trace: S13TraceCursor,
        events: List<S13EventPlacement>,
    ): Rendered {
        val variantRoot = variantsRoot.resolve(variant)
        val variantProperties = Properties().apply {
            Files.newInputStream(variantRoot.resolve("variant.properties")).use { load(it) }
        }
        val loops = readLoops(variantRoot.resolve("loops.tsv"), appRoot, experimentRoot)
        val bank = MatlabSoundBank(
            vehicleKey = "c63_w204_v6",
            sampleRateHz = S13ReviewContract.SAMPLE_RATE,
            powertrain = powertrain,
            loops = loops,
            afterfire = afterfire,
            shiftEvents = shifts,
        )
        val reviewPackage = S13ReviewPackage(
            vehicleKey = "c63_w204_v6",
            sourceCommit = properties.getProperty("source_commit"),
            traceSha256 = properties.getProperty("trace_sha256"),
            bankManifestSha256 = variantProperties.getProperty("bank_manifest_sha256"),
            fixedVehicleGain = properties.getProperty("fixed_vehicle_gain").toDouble(),
            trace = trace,
            events = events,
        )
        if (events.isNotEmpty()) {
            assertEquals(properties.getProperty("event_schedule_sha256"), reviewPackage.eventScheduleSha256)
        }
        val session = S13ReviewSession(bank, reviewPackage)
        val pcm = session.renderAll()
        assertEquals(S13ReviewContract.TOTAL_FRAMES, pcm.size)
        return Rendered(pcm, session.mixStats())
    }

    private fun readTrace(path: Path): List<S13TracePoint> = Files.readAllLines(path).drop(1).map { line ->
        val fields = line.split('\t')
        require(fields.size == 5)
        S13TracePoint(fields[0].toDouble(), fields[1].toDouble(), fields[2].toDouble(),
            fields[3].toDouble(), fields[4].toDouble())
    }

    private fun readEvents(path: Path, appRoot: Path, traceBytes: ByteArray): List<S13EventPlacement> =
        Files.readAllLines(path).drop(1).map { line ->
            val fields = line.split('\t')
            require(fields.size == 11)
            val assetPath = fields[2]
            val assetBytes = Files.readAllBytes(
                appRoot.resolve("Project/android/app/src/main/assets").resolve(assetPath),
            )
            val binding = S13EventBinding(
                id = fields[0], kind = fields[1], assetPath = assetPath,
                assetSha256 = fields[3], traceSha256 = fields[4], sourceDomain = fields[5],
                sourceTimeS = fields[6].toDouble(), sourceFrame = fields[7].toInt(),
                cropStartFrame = fields[8].toInt(), triggerOffsetFrames = fields[9].toInt(),
                sampleCount = fields[10].toInt(),
            )
            val decoded = FloatWavDecoder.decode(assetBytes)
            assertEquals(S13ReviewContract.SAMPLE_RATE, decoded.sampleRateHz)
            binding.validate(traceBytes, assetBytes, decoded.samples.size)
        }

    private fun readTransients(path: Path, appRoot: Path): List<Pair<String, MatlabTransient>> =
        Files.readAllLines(path).drop(1).map { line ->
            val fields = line.split('\t')
            require(fields.size == 5)
            val bytes = Files.readAllBytes(appRoot.resolve(fields[2]))
            assertEquals(fields[3], S13ReviewContract.sha256(bytes))
            val decoded = FloatWavDecoder.decode(bytes)
            assertEquals(S13ReviewContract.SAMPLE_RATE, decoded.sampleRateHz)
            fields[0] to MatlabTransient(fields[1], decoded.samples)
        }

    private fun readPowertrain(path: Path): MatlabPowertrainSpec {
        val values = Files.readAllLines(path).drop(1).associate { line ->
            val (key, value) = line.split('\t', limit = 2)
            key to value
        }
        val ratios = values.getValue("gear_ratios").removePrefix("[").removeSuffix("]")
            .split(',').map { it.trim().toDouble() }.toDoubleArray()
        fun number(key: String) = values.getValue(key).toDouble()
        return MatlabPowertrainSpec(
            idleRpm = number("idle_rpm"), redlineRpm = number("redline_rpm"),
            gearRatios = ratios, finalDrive = number("final_drive"),
            wheelRadiusM = number("wheel_radius_m"), launchRpm = number("launch_rpm"),
            shiftRpm = number("shift_rpm"), shiftAttackS = number("shift_attack_s"),
            shiftHoldS = number("shift_hold_s"), shiftRecoveryS = number("shift_recovery_s"),
            shiftSettleS = number("shift_settle_s"), shiftMinTorque = number("shift_min_torque"),
            shiftReengageGain = number("shift_reengage_gain"),
            minimumShiftIntervalS = number("minimum_shift_interval_s"),
            downshiftRatio = number("downshift_ratio"), speedCeilingKmh = number("speed_ceiling_kmh"),
            afterfireMinimumRpm = number("afterfire_minimum_rpm"),
        )
    }

    private fun readLoops(path: Path, appRoot: Path, experimentRoot: Path): List<MatlabLoop> =
        Files.readAllLines(path).drop(1).map { line ->
            val fields = line.split('\t')
            require(fields.size == 5)
            val base = when (fields[0]) {
                "app" -> appRoot
                "experiment" -> experimentRoot
                else -> error("Unknown loop asset root: ${fields[0]}")
            }
            val bytes = Files.readAllBytes(base.resolve(fields[1]))
            assertEquals(fields[4], S13ReviewContract.sha256(bytes))
            val decoded = FloatWavDecoder.decode(bytes)
            assertEquals(S13ReviewContract.SAMPLE_RATE, decoded.sampleRateHz)
            MatlabLoop(fields[2].toDouble(), fields[3].toDouble(), decoded.samples)
        }

    private fun readF32le(path: Path): FloatArray {
        val bytes = Files.readAllBytes(path)
        require(bytes.size == S13ReviewContract.TOTAL_FRAMES * 4)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        return FloatArray(S13ReviewContract.TOTAL_FRAMES) { buffer.float }
    }

    private fun compare(first: FloatArray, second: FloatArray): ErrorMetrics {
        require(first.size == second.size)
        var maximum = 0.0
        var sumSquares = 0.0
        for (index in first.indices) {
            val difference = kotlin.math.abs(first[index].toDouble() - second[index].toDouble())
            maximum = maxOf(maximum, difference)
            sumSquares += difference * difference
        }
        return ErrorMetrics(maximum, kotlin.math.sqrt(sumSquares / first.size))
    }

    private fun sliceWindows(pcm: FloatArray, windows: List<IntRange>): FloatArray {
        val frames = windows.sumOf { it.last - it.first + 1 }
        val output = FloatArray(frames)
        var offset = 0
        for (window in windows) {
            val count = window.last - window.first + 1
            pcm.copyInto(output, offset, window.first, window.last + 1)
            offset += count
        }
        return output
    }

    private fun sha256FloatArray(samples: FloatArray): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val page = ByteBuffer.allocate(16_384).order(ByteOrder.LITTLE_ENDIAN)
        var offset = 0
        while (offset < samples.size) {
            page.clear()
            val count = minOf(page.capacity() / 4, samples.size - offset)
            repeat(count) { page.putFloat(samples[offset++]) }
            digest.update(page.array(), 0, page.position())
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }

    private fun writeRender(root: Path, variant: String, rendered: Rendered, error: ErrorMetrics) {
        val directory = root.resolve("renders")
        Files.createDirectories(directory)
        val output = directory.resolve("$variant.f32le")
        val digest = MessageDigest.getInstance("SHA-256")
        val page = ByteBuffer.allocate(16_384).order(ByteOrder.LITTLE_ENDIAN)
        Files.newOutputStream(output).use { stream ->
            var offset = 0
            while (offset < rendered.pcm.size) {
                page.clear()
                val count = minOf(page.capacity() / 4, rendered.pcm.size - offset)
                repeat(count) { page.putFloat(rendered.pcm[offset++]) }
                stream.write(page.array(), 0, page.position())
                digest.update(page.array(), 0, page.position())
            }
        }
        val hash = digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
        val stats = rendered.stats
        val line = listOf(
            variant, rendered.pcm.size, hash, stats.evaluatedFrames, stats.preClipPeak,
            stats.aboveContractFrames, stats.hardClipFrames, stats.nonFiniteFrames,
            stats.loadOutOfBankFrames, stats.rpmOutOfBankFrames, error.maxAbs, error.rmse,
        ).joinToString("\t")
        val report = directory.resolve("render_results.tsv")
        if (!Files.exists(report)) {
            Files.write(report,
                "variant\tframes\tpcm_sha256\tevaluated_frames\tpre_clip_peak\tabove_contract_frames\thard_clip_frames\tnon_finite_frames\tload_out_of_bank_frames\trpm_out_of_bank_frames\tmax_abs_vs_phone_d1\trmse_vs_phone_d1\n"
                    .toByteArray(Charsets.UTF_8))
        }
        Files.write(report, "$line\n".toByteArray(Charsets.UTF_8), java.nio.file.StandardOpenOption.APPEND)
    }

    private fun writeF32le(path: Path, samples: FloatArray): String {
        Files.createDirectories(requireNotNull(path.parent))
        val digest = MessageDigest.getInstance("SHA-256")
        val page = ByteBuffer.allocate(16_384).order(ByteOrder.LITTLE_ENDIAN)
        Files.newOutputStream(path).use { stream ->
            var offset = 0
            while (offset < samples.size) {
                page.clear()
                val count = minOf(page.capacity() / 4, samples.size - offset)
                repeat(count) { page.putFloat(samples[offset++]) }
                stream.write(page.array(), 0, page.position())
                digest.update(page.array(), 0, page.position())
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }

    private fun writeControl(root: Path, variant: String, pcm: FloatArray, error: ErrorMetrics) {
        val report = root.resolve("renders/in_range_control.tsv")
        if (!Files.exists(report)) {
            Files.write(report,
                "variant\tframes\tpcm_sha256\tmax_abs_vs_A\trmse_vs_A\n".toByteArray(Charsets.UTF_8))
        }
        val line = listOf(variant, pcm.size, sha256FloatArray(pcm), error.maxAbs, error.rmse)
            .joinToString("\t")
        Files.write(report, "$line\n".toByteArray(Charsets.UTF_8), java.nio.file.StandardOpenOption.APPEND)
    }
}
