package com.vico.simulator.sound.n2.diagnostic

import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.n2.N2QualificationExport
import com.vico.simulator.sound.n2.N2QualificationFixture
import com.vico.simulator.sound.n2.N2TrajectorySegment
import java.io.File

/** Opt-in synthetic diagnostic export. Both profiles must be imported files, never regenerated. */
internal object N2SyntheticReferenceExporter {
    fun fixture(): N2QualificationFixture {
        fun state(n: Int, closed: Boolean) = SoundState(
            timeS = n * .02, rpm = if (closed) 4000.0 else 5000.0,
            frequencyHz = 0.0, amplitude = if (closed) .05 else .9,
            brightness = .9, harmonics = floatArrayOf(), muted = false,
            throttle = if (closed) .05 else .9, load = if (closed) .05 else .9,
            shiftTrigger = n == 90,
        )
        val trajectory = (0 until 130).map { n -> N2TrajectorySegment(state(n, n >= 100), 960) } +
            N2TrajectorySegment(state(130, true).copy(rpm = 0.0, throttle = 0.0, load = 0.0),
                15360, validInput = false)
        return N2QualificationFixture("synthetic-hot-lift-shift-tail-v1", trajectory)
    }

    fun export(output: File, baselineArtifact: ByteArray, profileArtifact: ByteArray,
        partitions: IntArray = intArrayOf(960)): String =
        N2QualificationExport.write(output, fixture(), baselineArtifact, profileArtifact, partitions)

    @JvmStatic
    fun main(args: Array<String>) {
        require(args.size in 3..4) { "usage: baseline.bin profile.bin NEW_OUTPUT_DIR [960|333,297]" }
        val partitions = if (args.size == 4) args[3].split(',').map(String::toInt).toIntArray() else intArrayOf(960)
        val digest = export(File(args[2]), File(args[0]).readBytes(), File(args[1]).readBytes(), partitions)
        println("RENDERED_ONLY_NOT_ACOUSTIC_QUALIFICATION manifest_sha256=$digest")
    }
}
