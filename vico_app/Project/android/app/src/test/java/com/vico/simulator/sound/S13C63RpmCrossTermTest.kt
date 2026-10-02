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

/** External, opt-in diagnostic; never produces a playable counterfactual. */
class S13C63RpmCrossTermTest {
    @Test
    fun test_only_tap_preserves_frozen_c63_renderer_pcm_and_captures_bounded_rpm_paths() {
        val outputValue = System.getenv("VICO_S13_C63_RPM_OUTPUT_ROOT")
        assumeTrue("Prepare the S13.4 C63 capture package first", !outputValue.isNullOrBlank())
        val outputRoot = Paths.get(requireNotNull(outputValue))
        val phase = loadProperties(outputRoot.resolve("phase.properties"))
        val r4Root = Paths.get(phase.getProperty("r4_root"))
        val appRoot = Paths.get(phase.getProperty("app_root"))
        val experiment = loadProperties(r4Root.resolve("inputs/experiment.properties"))
        assertEquals("8fd92ebc4ee716d62f728a82f07c6cafdb7936520ffba3a100ab04c87f8c01d0",
            phase.getProperty("r4_experiment_sha256"))
        assertEquals("c63_w204_v6", experiment.getProperty("vehicle_key"))
        assertEquals(S13ReviewContract.TOTAL_FRAMES.toString(), phase.getProperty("total_frames"))

        val tracePath = r4Root.resolve("inputs/trace_points.tsv")
        val trace = S13TraceCursor(readTrace(tracePath))
        val powertrain = readPowertrain(r4Root.resolve("inputs/powertrain.tsv"))
        val loops = readLoops(r4Root.resolve("variants/A/loops.tsv"), appRoot, r4Root)
        assertEquals(16, loops.size)
        val bank = MatlabSoundBank(
            vehicleKey = "c63_w204_v6",
            sampleRateHz = S13ReviewContract.SAMPLE_RATE,
            powertrain = powertrain,
            loops = loops,
            afterfire = FloatArray(0),
            shiftEvents = emptyList(),
        )
        val variant = loadProperties(r4Root.resolve("variants/A/variant.properties"))
        val reviewPackage = S13ReviewPackage(
            vehicleKey = "c63_w204_v6",
            sourceCommit = experiment.getProperty("source_commit"),
            traceSha256 = experiment.getProperty("trace_sha256"),
            bankManifestSha256 = variant.getProperty("bank_manifest_sha256"),
            fixedVehicleGain = experiment.getProperty("fixed_vehicle_gain").toDouble(),
            trace = trace,
            events = emptyList(),
        )

        val tapOff = S13ReviewSession(bank, reviewPackage).renderAll()
        val tapOnSession = S13ReviewSession(bank, reviewPackage)
        val capture = tapOnSession.enableRpmBlendCapture(S13ReviewContract.TOTAL_FRAMES)
        val tapOn = tapOnSession.renderAll()
        assertEquals(S13ReviewContract.TOTAL_FRAMES, capture.frameCount)
        assertArrayEquals("Opt-in diagnostics must not alter one PCM sample", tapOff, tapOn, 0f)
        assertEquals(S13ReviewContract.TOTAL_FRAMES, tapOn.size)

        val windows = Files.readAllLines(outputRoot.resolve("windows.tsv")).drop(1).map { line ->
            val fields = line.split('\t')
            require(fields.size == 5)
            fields[1].toInt() until fields[2].toInt()
        }
        assertEquals(75, windows.size)
        val phoneA = readF32le(r4Root.resolve("renders/A.f32le"))
        val rendererWindow = sliceWindows(tapOn, windows)
        val phoneWindow = sliceWindows(phoneA, windows)
        val error = compare(rendererWindow, phoneWindow)
        assertTrue("Tap-enabled stable windows must reproduce frozen D1 A: $error",
            error.first <= 2e-5 && error.second <= 2e-6)

        val stats = tapOnSession.mixStats()
        assertEquals(0L, stats.hardClipFrames)
        assertEquals(0L, stats.nonFiniteFrames)
        assertTrue(capture.lowerPath.all { it.isFinite() })
        assertTrue(capture.upperPath.all { it.isFinite() })
        assertTrue(capture.rpmWeight.all { it.isFinite() && it in 0f..1f })
        assertTrue(capture.sharedGain.all { it.isFinite() && it >= 0f })

        val files = linkedMapOf<String, String>()
        files["lower_path"] = writeFloatArray(outputRoot.resolve("lower_path.f32le"), capture.lowerPath)
        files["upper_path"] = writeFloatArray(outputRoot.resolve("upper_path.f32le"), capture.upperPath)
        files["rpm_weight"] = writeFloatArray(outputRoot.resolve("rpm_weight.f32le"), capture.rpmWeight)
        files["shared_gain"] = writeFloatArray(outputRoot.resolve("shared_gain.f32le"), capture.sharedGain)
        files["event_contribution"] = writeFloatArray(
            outputRoot.resolve("event_contribution.f32le"), capture.eventContribution,
        )
        files["renderer_mix"] = writeFloatArray(outputRoot.resolve("renderer_mix.f32le"), tapOn)
        files["rpm_lower_index"] = writeBytes(outputRoot.resolve("rpm_lower_index.u8"), capture.rpmLowerIndex)
        files["rpm_upper_index"] = writeBytes(outputRoot.resolve("rpm_upper_index.u8"), capture.rpmUpperIndex)

        val fileRows = files.entries.joinToString(",\n") { (name, sha) ->
            val fileName = when (name) {
                "rpm_lower_index" -> "rpm_lower_index.u8"
                "rpm_upper_index" -> "rpm_upper_index.u8"
                else -> "$name.f32le"
            }
            "    \"$name\": {\"path\": \"$fileName\", \"sha256\": \"$sha\"}"
        }
        val manifest = """
            {
              "schema": "vico.s13.c63_rpm_capture.v1",
              "frames": ${tapOn.size},
              "sample_rate_hz": ${S13ReviewContract.SAMPLE_RATE},
              "source_snapshot_sha256": "${phase.getProperty("source_snapshot_sha256")}",
              "tap_pcm_identical": true,
              "tap_off_pcm_sha256": "${sha256FloatArray(tapOff)}",
              "tap_on_pcm_sha256": "${sha256FloatArray(tapOn)}",
              "mix_stats": {
                "evaluated_frames": ${stats.evaluatedFrames},
                "pre_clip_peak": ${stats.preClipPeak},
                "hard_clip_frames": ${stats.hardClipFrames},
                "non_finite_frames": ${stats.nonFiniteFrames}
              },
              "files": {
            $fileRows
              }
            }
        """.trimIndent()
        Files.write(outputRoot.resolve("capture_manifest.json"), manifest.toByteArray(Charsets.UTF_8))
    }

    private fun loadProperties(path: Path) = Properties().apply {
        Files.newInputStream(path).use(::load)
    }

    private fun readTrace(path: Path): List<S13TracePoint> = Files.readAllLines(path).drop(1).map { line ->
        val fields = line.split('\t')
        require(fields.size == 5)
        S13TracePoint(fields[0].toDouble(), fields[1].toDouble(), fields[2].toDouble(),
            fields[3].toDouble(), fields[4].toDouble())
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
            idleRpm = number("idle_rpm"), redlineRpm = number("redline_rpm"), gearRatios = ratios,
            finalDrive = number("final_drive"), wheelRadiusM = number("wheel_radius_m"),
            launchRpm = number("launch_rpm"), shiftRpm = number("shift_rpm"),
            shiftAttackS = number("shift_attack_s"), shiftHoldS = number("shift_hold_s"),
            shiftRecoveryS = number("shift_recovery_s"), shiftSettleS = number("shift_settle_s"),
            shiftMinTorque = number("shift_min_torque"), shiftReengageGain = number("shift_reengage_gain"),
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
                else -> error("Unknown loop root: ${fields[0]}")
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

    private fun sliceWindows(samples: FloatArray, windows: List<IntRange>): FloatArray {
        val result = FloatArray(windows.sumOf { it.last - it.first + 1 })
        var offset = 0
        windows.forEach { window ->
            val count = window.last - window.first + 1
            samples.copyInto(result, offset, window.first, window.last + 1)
            offset += count
        }
        return result
    }

    private fun compare(first: FloatArray, second: FloatArray): Pair<Double, Double> {
        require(first.size == second.size)
        var maxAbs = 0.0
        var sumSquares = 0.0
        first.indices.forEach { index ->
            val delta = kotlin.math.abs(first[index].toDouble() - second[index])
            maxAbs = maxOf(maxAbs, delta)
            sumSquares += delta * delta
        }
        return maxAbs to kotlin.math.sqrt(sumSquares / first.size)
    }

    private fun writeFloatArray(path: Path, values: FloatArray): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteBuffer.allocate(16_384).order(ByteOrder.LITTLE_ENDIAN)
        Files.newOutputStream(path).use { stream ->
            var offset = 0
            while (offset < values.size) {
                buffer.clear()
                repeat(minOf(buffer.capacity() / 4, values.size - offset)) { buffer.putFloat(values[offset++]) }
                stream.write(buffer.array(), 0, buffer.position())
                digest.update(buffer.array(), 0, buffer.position())
            }
        }
        return digest.digest().hex()
    }

    private fun writeBytes(path: Path, values: ByteArray): String {
        Files.write(path, values)
        return MessageDigest.getInstance("SHA-256").digest(values).hex()
    }

    private fun sha256FloatArray(values: FloatArray): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteBuffer.allocate(16_384).order(ByteOrder.LITTLE_ENDIAN)
        var offset = 0
        while (offset < values.size) {
            buffer.clear()
            repeat(minOf(buffer.capacity() / 4, values.size - offset)) { buffer.putFloat(values[offset++]) }
            digest.update(buffer.array(), 0, buffer.position())
        }
        return digest.digest().hex()
    }

    private fun ByteArray.hex(): String = joinToString("") { "%02x".format(it.toInt() and 0xff) }
}
