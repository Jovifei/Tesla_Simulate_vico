"""Complementary source wiring checks; executable value/format tests live in Kotlin."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'Project/android/app/src/main/java/com/vico/simulator'

class InputDiagnosticsWiringTest(unittest.TestCase):
    def test_existing_csv_prefix_and_user_started_recording_are_preserved(self):
        csv = (SRC / 'csv/CsvExporter.kt').read_text() + (SRC / 'csv/CsvTraceFormat.kt').read_text()
        activity = (SRC / 'MainActivity.kt').read_text()
        self.assertIn('time_s,speed_kmh,accel_mps2,rpm,freq_hz,profile', csv)
        self.assertIn('%.3f,%.1f,%.2f,%.0f,%.1f,%s', csv)
        self.assertIn('InputDiagnostics.CSV_HEADER', csv)
        self.assertIn('diagnostics.toCsvColumns()', csv)
        self.assertIn('if (recording)', activity)
        self.assertEqual(activity.count('recording = true'), 1)
        sample = activity.split('private fun onSensorSample', 1)[1].split('// ---- bridge handlers', 1)[0]
        self.assertLess(sample.index('if (s13ReviewActive)'), sample.index('if (recording)'))

    def test_optional_accuracy_is_guarded_for_min_sdk_24(self):
        provider = (SRC / 'sensor/SensorProvider.kt').read_text()
        self.assertIn('Build.VERSION.SDK_INT >= Build.VERSION_CODES.O', provider)
        self.assertIn('hasSpeedAccuracy()', provider)
        self.assertIn('speedAccuracyMetersPerSecond', provider)
        for forbidden in ('.latitude', '.longitude', '.altitude', '.bearing', 'getLatitude(', 'getLongitude('):
            self.assertNotIn(forbidden, provider)

    def test_native_callback_and_both_state_builders_carry_diagnostics(self):
        provider = (SRC / 'sensor/SensorProvider.kt').read_text()
        activity = (SRC / 'MainActivity.kt').read_text()
        self.assertIn('diagnostics: InputDiagnostics', provider)
        self.assertIn('inputSession += 1', provider)
        self.assertIn('lastInputSnapshot = SensorInputSnapshot.capture(speedKmh, forwardAccel, gpsOk, rawAccel, gravity, diagnostics)', activity)
        state = activity.split('private fun buildStateJson()', 1)[1].split('private fun refreshOutputDevices', 1)[0]
        self.assertIn('val input = lastInputSnapshot', state)
        self.assertIn('input.speedKmh', state)
        self.assertIn('input.diagnostics.toJson()', state)
        self.assertNotIn('lastSpeedKmh', state)
        self.assertNotIn('sensorProvider.isDemoMode()', state)
        self.assertIn('input.diagnostics.sourceMode == InputDiagnostics.SourceMode.DEMO', state)
        self.assertIn('val consumedNanos = android.os.SystemClock.elapsedRealtimeNanos()', activity)
        self.assertEqual(activity.count('append("\\\"inputDiagnostics\\\":")'), 2)
        self.assertIn('DriveInputMode.REFERENCE_BYPASS', activity)
        self.assertIn('DriveInputMode.PREVIEW', activity)
        pause = activity.split('override fun onPause()', 1)[1].split('override fun onDestroy()', 1)[0]
        self.assertIn('lastInputSnapshot = SensorInputSnapshot(diagnostics = InputDiagnostics(', pause)

if __name__ == '__main__':
    unittest.main()
