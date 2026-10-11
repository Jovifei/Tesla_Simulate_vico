package com.vico.simulator.sound

import kotlin.math.max

/** Actual bank-engine mapping, pure so the controller-to-audio validity bridge can be regression tested. */
fun MatlabPowertrainState.toMappedSoundState(point: DrivePoint, control: DriveInputControl?): SoundState {
    val effectiveControl = if (control?.source == DriveInputSource.REAL) control.copy(
        speedUsable = control.speedUsable && measuredInputUsable,
        accelerationUsable = control.accelerationUsable && measuredInputUsable,
        modelContinuityRevision = modelContinuityRevision,
    ) else control
    return SoundState(
        timeS = point.timeS,
        rpm = rpm,
        frequencyHz = rpm / 60.0 * 4.0,
        amplitude = max(0.08, load),
        brightness = load,
        harmonics = floatArrayOf(),
        muted = point.speedKmh >= 148.0,
        throttle = virtualDemand ?: point.throttle,
        load = load,
        braking = point.brake,
        gear = gear,
        shiftGain = torqueGain,
        afterfireTrigger = afterfireTrigger,
        shiftTrigger = shiftTrigger,
        inputControl = effectiveControl,
        afterfireCauseCode = afterfireCauseCode,
        afterfireSourceId = afterfireSourceId,
        modelSpeedKmh = point.speedKmh.takeIf { effectiveControl?.usable == true },
        modelAccelerationMps2 = point.accelMps2.takeIf { effectiveControl?.usable == true },
    )
}
