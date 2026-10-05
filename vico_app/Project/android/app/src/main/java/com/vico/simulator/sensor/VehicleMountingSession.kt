package com.vico.simulator.sensor

/** Android's physical sensor axes in the device's natural orientation, not rotated UI axes. */
enum class VehicleMountAxis(val component: Int, val sign: Double, val label: String) {
    TOP(1, 1.0, "手机顶部朝车头（+Y）"),
    BOTTOM(1, -1.0, "手机底部朝车头（−Y）"),
    RIGHT(0, 1.0, "手机右边朝车头（+X，自然竖屏）"),
    LEFT(0, -1.0, "手机左边朝车头（−X，自然竖屏）"),
    SCREEN(2, 1.0, "屏幕正面朝车头（+Z）"),
    BACK(2, -1.0, "手机背面朝车头（−Z）"),
}

/** Saved choice is not proof of the current physical mounting. Navigation does not reset this object. */
class VehicleMountingSession(saved: VehicleMountAxis? = null) {
    data class Snapshot(val selected: VehicleMountAxis?, val trusted: Boolean = false,
        val reason: String = "CONFIRM_FIXED_MOUNT", val inputSession: Long = 0,
        val calibrationSession: String = "", val calibrationRevision: Long = -1)
    @Volatile var snapshot = Snapshot(saved)
        private set
    val selected: VehicleMountAxis? get() = snapshot.selected
    val trusted: Boolean get() = snapshot.trusted
    val reason: String get() = snapshot.reason

    fun confirm(axis: VehicleMountAxis, parkedAcknowledged: Boolean, currentInputSession: Long,
                calibration: CalibrationSession.Snapshot, imuFresh: Boolean, knownSpeedKmh: Double?): Boolean {
        if (!parkedAcknowledged || currentInputSession <= 0 || !imuFresh ||
            calibration.status != CalibrationSession.Status.COMPLETE ||
            knownSpeedKmh != null && (!knownSpeedKmh.isFinite() || knownSpeedKmh > 3.0 || knownSpeedKmh < 0.0)) return false
        snapshot = Snapshot(axis, true, "CONFIRMED_FIXED_AXIS", currentInputSession, calibration.session, calibration.revision)
        return true
    }

    fun invalidate(why: String) { snapshot = snapshot.copy(trusted = false, reason = why) }

    fun project(correctedDeviceAxes: FloatArray, currentInputSession: Long,
                calibration: CalibrationSession.Snapshot): Double? {
        val bound = snapshot
        if (!bound.trusted) return null
        if (currentInputSession != bound.inputSession || calibration.session != bound.calibrationSession ||
            calibration.revision != bound.calibrationRevision || calibration.status != CalibrationSession.Status.COMPLETE) {
            invalidate("INPUT_OR_CALIBRATION_CHANGED")
            return null
        }
        if (correctedDeviceAxes.size < 3 || (0..2).any { !correctedDeviceAxes[it].isFinite() }) {
            invalidate("INVALID_DEVICE_AXES")
            return null
        }
        val axis = bound.selected ?: return null
        return correctedDeviceAxes[axis.component].toDouble() * axis.sign
    }
}

/** Detect the supported diagram convention; never remap sensor axes to the current UI rotation. */
fun hasPortraitNaturalOrientation(rotationQuarterTurns: Int, currentPortrait: Boolean): Boolean = when (rotationQuarterTurns) {
    0, 2 -> currentPortrait
    1, 3 -> !currentPortrait
    else -> false
}
