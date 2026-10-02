package com.vico.simulator.sound

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.security.MessageDigest
import java.util.Properties
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Opt-in fixed-condition capture for the S13.5 5500-RPM anchor diagnostic. */
class S13C63AnchorResonanceTest {
    private data class Condition(val rpm: Double, val load: Double) {
        val id: String get() = "rpm_${rpm.toInt()}_load_${(load * 100).toInt()}"
    }

    private val conditions = listOf(
        Condition(5200.0, 0.32), Condition(5500.0, 0.32), Condition(6100.0, 0.32),
        Condition(5200.0, 0.92), Condition(5500.0, 0.92), Condition(6100.0, 0.92),
    )

    @Test
    fun fixed_conditions_capture_real_5500_paths_without_events_or_production_writes() {
        val outputValue = System.getenv("VICO_S13_C63_RESONANCE_OUTPUT_ROOT")
        assumeTrue("Prepare the S13.5 resonance package first", !outputValue.isNullOrBlank())
        val outputRoot = Paths.get(requireNotNull(outputValue))
        val phase = loadProperties(outputRoot.resolve("phase.properties"))
        val appRoot = Paths.get(phase.getProperty("app_root"))
        val experimentRoot = Paths.get(phase.getProperty("r4_root"))
        val properties = loadProperties(experimentRoot.resolve("inputs/experiment.properties"))
        assertEquals("c63_w204_v6", properties.getProperty("vehicle_key"))
        assertEquals("8fd92ebc4ee716d62f728a82f07c6cafdb7936520ffba3a100ab04c87f8c01d0",
            phase.getProperty("r4_experiment_sha256"))
        assertEquals("3.7075542301539652", phase.getProperty("fixed_vehicle_gain"))

        val loops = readLoops(experimentRoot.resolve("variants/A/loops.tsv"), appRoot, experimentRoot)
        assertEquals(16, loops.size)
        val bank = MatlabSoundBank(
            vehicleKey = "c63_w204_v6",
            sampleRateHz = S13ReviewContract.SAMPLE_RATE,
            powertrain = readPowertrain(experimentRoot.resolve("inputs/powertrain.tsv")),
            loops = loops,
            afterfire = FloatArray(0),
            shiftEvents = emptyList(),
        )
        val frameCount = phase.getProperty("condition_frames").toInt()
        val blockFrames = S13ReviewContract.BLOCK_FRAMES
        val manifestRows = ArrayList<String>()
        for (condition in conditions) {
            val renderer = MatlabStatefulBankRenderer(bank)
            val capture = S13RpmBlendCapture(frameCount)
            renderer.enableRpmBlendCapture(capture)
            val state = SoundState(
                timeS = 0.0,
                rpm = condition.rpm,
                frequencyHz = condition.rpm / 60.0 * 4.0,
                amplitude = maxOf(0.08, condition.load),
                brightness = condition.load,
                harmonics = floatArrayOf(),
                muted = false,
                throttle = condition.load,
                load = condition.load,
                braking = false,
                shiftGain = 1.0,
            )
            val pcm = FloatArray(frameCount)
            var offset = 0
            while (offset < frameCount) {
                val count = minOf(blockFrames, frameCount - offset)
                renderer.renderReview(state, state, offset, count, emptyList())
                    .copyInto(pcm, offset)
                offset += count
            }
            assertEquals(frameCount, capture.frameCount)
            assertEquals(0L, renderer.mixStats().hardClipFrames)
            assertEquals(0L, renderer.mixStats().nonFiniteFrames)
            assertTrue(capture.lowerPath.all { it.isFinite() })
            assertTrue(capture.upperPath.all { it.isFinite() })
            assertTrue(capture.sharedGain.all { it == 1f })
            val anchorIndex = bank.rpmLevels.binarySearch(5500.0)
            when {
                condition.rpm < 5500.0 -> assertTrue(capture.rpmUpperIndex.all { it.toInt() == anchorIndex })
                condition.rpm > 5500.0 -> assertTrue(capture.rpmLowerIndex.all { it.toInt() == anchorIndex })
                else -> {
                    assertTrue(capture.rpmLowerIndex.all { it.toInt() == anchorIndex })
                    assertTrue(capture.rpmUpperIndex.all { it.toInt() == anchorIndex })
                }
            }
            val conditionRoot = outputRoot.resolve("conditions").resolve(condition.id)
            val files = linkedMapOf(
                "lower_path" to writeFloatArray(conditionRoot.resolve("lower_path.f32le"), capture.lowerPath),
                "upper_path" to writeFloatArray(conditionRoot.resolve("upper_path.f32le"), capture.upperPath),
                "shared_gain" to writeFloatArray(conditionRoot.resolve("shared_gain.f32le"), capture.sharedGain),
                "renderer_mix" to writeFloatArray(conditionRoot.resolve("renderer_mix.f32le"), pcm),
                "rpm_lower_index" to writeBytes(conditionRoot.resolve("rpm_lower_index.u8"), capture.rpmLowerIndex),
                "rpm_upper_index" to writeBytes(conditionRoot.resolve("rpm_upper_index.u8"), capture.rpmUpperIndex),
            )
            val fileJson = files.entries.joinToString(",") { (name, sha) ->
                val file = if (name.endsWith("index")) "$name.u8" else "$name.f32le"
                "\"$name\":{\"path\":\"conditions/${condition.id}/$file\",\"sha256\":\"$sha\"}"
            }
            manifestRows += "\"${condition.id}\":{\"rpm\":${condition.rpm},\"load\":${condition.load},\"frames\":$frameCount,\"files\":{$fileJson}}"
        }
        val manifest = """
            {
              "schema":"vico.s13.c63_anchor_resonance_capture.v1",
              "sample_rate_hz":${S13ReviewContract.SAMPLE_RATE},
              "condition_frames":$frameCount,
              "fixed_vehicle_gain":${phase.getProperty("fixed_vehicle_gain")},
              "source_code_snapshot_sha256":"${phase.getProperty("source_code_snapshot_sha256")}",
              "conditions":{${manifestRows.joinToString(",")}}
            }
        """.trimIndent()
        Files.write(outputRoot.resolve("capture_manifest.json"), manifest.toByteArray(Charsets.UTF_8))
    }

    private fun loadProperties(path: Path) = Properties().apply {
        Files.newInputStream(path).use(::load)
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

    private fun writeFloatArray(path: Path, values: FloatArray): String {
        Files.createDirectories(requireNotNull(path.parent))
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
        Files.createDirectories(requireNotNull(path.parent))
        Files.write(path, values)
        return MessageDigest.getInstance("SHA-256").digest(values).hex()
    }

    private fun ByteArray.hex(): String = joinToString("") { "%02x".format(it.toInt() and 0xff) }
}
