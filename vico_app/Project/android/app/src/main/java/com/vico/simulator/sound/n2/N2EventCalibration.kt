package com.vico.simulator.sound.n2

/** Event energy contract: no hidden .25 attenuation. */
internal object N2EventCalibration {
    const val LEGACY_UNIT_ENERGY = 331.3820481828321
    const val LEGACY_UNIT_L2 = 18.2039020043

    fun scale(unitEnergy: Double, targetEnergy: Double): Double {
        require(unitEnergy.isFinite() && unitEnergy > 0)
        require(targetEnergy.isFinite() && targetEnergy > 0)
        return kotlin.math.sqrt(targetEnergy / unitEnergy)
    }
}
