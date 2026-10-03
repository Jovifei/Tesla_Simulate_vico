package com.vico.simulator.sensor

data class SensorFrame(
    val speedKmh: Double,
    val forwardAccelMps2: Double,
    val gpsOk: Boolean,
    val correctedAccel: FloatArray,
    val diagnostics: InputDiagnostics = InputDiagnostics(),
)

class SensorSourceState {
    private var real = SensorFrame(0.0, 0.0, false, FloatArray(3))
    private var demo = SensorFrame(0.0, 0.0, true, FloatArray(3))
    var isDemoMode: Boolean = false
        private set

    fun updateReal(frame: SensorFrame): SensorFrame {
        real = frame.copy(correctedAccel = frame.correctedAccel.copyOf())
        return current()
    }

    fun updateDemo(frame: SensorFrame): SensorFrame {
        demo = frame.copy(correctedAccel = frame.correctedAccel.copyOf())
        return current()
    }

    fun setDemoMode(on: Boolean): SensorFrame {
        isDemoMode = on
        return current()
    }

    fun current(): SensorFrame {
        val frame = if (isDemoMode) demo else real
        return frame.copy(
            correctedAccel = frame.correctedAccel.copyOf(),
            diagnostics = real.diagnostics.copy(sourceMode = if (isDemoMode)
                InputDiagnostics.SourceMode.DEMO else InputDiagnostics.SourceMode.REAL),
        )
    }
}
