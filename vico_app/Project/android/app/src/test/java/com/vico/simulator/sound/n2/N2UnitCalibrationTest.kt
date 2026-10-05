package com.vico.simulator.sound.n2

import com.vico.simulator.sound.HybridTestProfiles
import java.io.File
import kotlin.math.sqrt
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test

/** Initial synthetic energy calibration only; no reference/objective/held-out data is used. */
class N2UnitCalibrationTest {
    @Test fun measureInitialUnitSourceBeforeObjectiveEvaluation() {
        val destination = System.getenv("VICO_C63_N2_UNIT_CALIBRATION_OUTPUT")
        Assume.assumeTrue(!destination.isNullOrBlank())
        val root = File(requireNotNull(destination))
        assertFalse(root.exists()); assertTrue(root.mkdirs())
        val baselineProfile = HybridTestProfiles.create()
        val profile = N2Profile.preregistered()
        val rows = mutableListOf("rpm\tload\tbaseline_bark_rms\tn2_unit_bark_rms")
        val before = mutableListOf<Double>(); val unit = mutableListOf<Double>()
        for (rpm in listOf(700.0,1400.0,2200.0,3200.0,4300.0,5500.0,6800.0,7200.0)) for (load in listOf(.32,.92)) {
            val old = N2Source(baselineProfile, profile, N2Mode.T)
            val source = N2Source(baselineProfile, profile, N2Mode.S)
            var oldEnergy = 0.0; var newEnergy = 0.0
            repeat(144000) { n ->
                old.sample(rpm, load, load); source.sample(rpm, load, load)
                if (n >= 48000) {
                    val a = old.lastStems[1]; val b = source.lastStems[1]
                    assertTrue(a.isFinite() && b.isFinite())
                    oldEnergy += a*a; newEnergy += b*b
                }
            }
            val a = sqrt(oldEnergy/96000); val b = sqrt(newEnergy/96000)
            assertTrue(a > 0 && b > 0)
            before += a; unit += b; rows += "$rpm\t$load\t$a\t$b"
        }
        fun median(values: List<Double>): Double { val sorted=values.sorted(); return (sorted[7]+sorted[8])/2 }
        val factor = median(before)/median(unit)
        File(root, "unit-calibration.tsv").writeText(rows.joinToString("\n")+"\n")
        File(root, "initialization.txt").writeText("profile_identity=${profile.identity}\nsource_scale_once=$factor\nobjective_evaluations=0\nheldout_used=false\n")
        println("Initial unit-only source scale=$factor; no objective/held-out evaluation performed")
    }
}
