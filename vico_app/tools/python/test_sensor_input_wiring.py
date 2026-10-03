"""Android source wiring checks, complementary to JVM state tests and device validation."""
from pathlib import Path
import os
import unittest

ROOT = Path(os.environ.get("VICO_SENSOR_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
SOURCE = ROOT / "Project/android/app/src/main/java/com/vico/simulator"


class SensorInputWiringTest(unittest.TestCase):
    def setUp(self):
        self.provider = (SOURCE / "sensor/SensorProvider.kt").read_text()
        self.activity = (SOURCE / "MainActivity.kt").read_text()

    def test_sensor_uses_event_timestamp_and_explicit_zero_batch_latency(self):
        self.assertIn("linearAcceleration.update(event.values, event.timestamp, SystemClock.elapsedRealtimeNanos())", self.provider)
        self.assertIn("SensorManager.SENSOR_DELAY_GAME, 0)", self.provider)
        self.assertIn("!started || event.timestamp < sessionStartedNanos", self.provider)

    def test_location_batch_keeps_latest_timestamp_and_coalesces_publish(self):
        self.assertIn("locationSpeed.updateLatest(samples, SystemClock.elapsedRealtimeNanos())", self.provider)
        callback = self.provider.split("private fun acceptLocations", 1)[1].split("private val tickRunnable", 1)[0]
        self.assertIn("if (!started) return", callback)
        self.assertIn("locations.filter { it.elapsedRealtimeNanos >= locationStartedNanos }", callback)
        self.assertIn("if (accepted && !demoMode)", callback)
        self.assertIn("handler.removeCallbacks(tickRunnable)", callback)
        self.assertIn("handler.post(tickRunnable)", callback)
        self.assertIn("LocationManager.GPS_PROVIDER, 100L, 0f", self.provider)

    def test_real_input_expires_during_demo_and_before_switching_back(self):
        tick = self.provider.split("private val tickRunnable", 1)[1].split("@Volatile private var started", 1)[0]
        self.assertIn("if (!started) return", tick)
        self.assertIn("if (demoMode) sourceState.updateDemo(stepDemo())\n            expireRealInput()", tick)
        switch = self.provider.split("fun setDemoMode", 1)[1].split("fun isDemoMode", 1)[0]
        self.assertLess(switch.index("expireRealInput()"), switch.index("sourceState.updateReal(realFrame())"))
        self.assertLess(switch.index("sourceState.updateReal(realFrame())"), switch.index("emit(sourceState.setDemoMode(on))"))

    def test_stop_start_clear_measured_input_and_inactive_callbacks_are_ignored(self):
        stop = self.provider.split("fun stop()", 1)[1].split("fun setDemoMode", 1)[0]
        start = self.provider.split("fun start()", 1)[1].split("fun refreshLocation", 1)[0]
        self.assertIn("started = false", stop)
        self.assertIn("clearRealInput()", stop)
        self.assertLess(start.index("clearRealInput()"), start.index("started = true"))
        self.assertIn("sessionStartedNanos = SystemClock.elapsedRealtimeNanos()", start)
        refresh = self.provider.split("fun refreshLocation()", 1)[1].split("fun stop()", 1)[0]
        self.assertIn("if (started && hasLocationPermission())", refresh)
        self.assertIn("locationSpeed.clear()", refresh)

    def test_input_and_preview_time_use_same_monotonic_clock(self):
        self.assertNotIn("System.currentTimeMillis()", self.provider)
        self.assertIn("startMs = android.os.SystemClock.elapsedRealtime()", self.activity)
        sample = self.activity.split("private fun onSensorSample", 1)[1].split("// ---- bridge handlers", 1)[0]
        self.assertIn("val now = android.os.SystemClock.elapsedRealtime()", sample)
        self.assertNotIn("System.currentTimeMillis()", sample)
        self.assertIn("previewUntilMs = android.os.SystemClock.elapsedRealtime() + 2500", self.activity)
        self.assertIn("if (android.os.SystemClock.elapsedRealtime() >= previewUntilMs)", self.activity)

    def test_invalid_acceleration_is_not_bias_corrected_into_phantom_motion(self):
        self.assertIn("if (linearAcceleration.valid) calibration.correct(linearAcceleration.sample()) else FloatArray(3)", self.provider)

    def test_calibration_lifecycle_and_epoch_are_wired_to_real_adapters(self):
        bridge = (SOURCE / "web/VicoBridge.kt").read_text()
        self.assertIn("calibration.add(linearAcceleration.sample(), event.timestamp)", self.provider)
        self.assertIn("available = started", self.provider)
        stop = self.provider.split("fun stop()", 1)[1].split("fun setDemoMode", 1)[0]
        self.assertIn("calibration.cancel()", stop)
        self.assertIn("fun resetCalibration() = calibration.reset()", self.provider)
        self.assertIn("val epoch = activity.calibrationPageEpoch", bridge)
        self.assertIn("if (activity.acceptsCalibrationCommand(epoch)) action()", bridge)
        self.assertIn("activity.invalidateCalibrationPage()", bridge)
        self.assertIn("!activityDestroyed && calibrationResumed && calibrationPageActive && epoch == calibrationPageEpoch", self.activity)
        for name, end in [("onPause", "onDestroy"), ("onDestroy", "onRequestPermissionsResult")]:
            lifecycle = self.activity.split("override fun " + name, 1)[1].split("override fun " + end, 1)[0]
            self.assertIn("calibrationPageEpoch++", lifecycle)
            self.assertIn("calibrationResumed = false", lifecycle)
        self.assertEqual(self.activity.count('append(calibrationStateJson())'), 2)



if __name__ == "__main__":
    unittest.main()
