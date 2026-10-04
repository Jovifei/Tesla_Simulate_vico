"""Adapter routing checks complement executable policy/controller/renderer regressions."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'Project/android/app/src/main/java/com/vico/simulator'
class InputQualityWiringTest(unittest.TestCase):
    def test_real_entrypoints_are_explicit_and_reassess_cached_start(self):
        activity=(SRC/'MainActivity.kt').read_text()
        self.assertNotIn('audioEngine.mapPoint(',activity)
        self.assertIn('mapCurrentInput(realPoint, diagnostics, consumedNanos)',activity)
        start=activity.split('fun startAudio()',1)[1].split('fun stopAudio',1)[0]
        self.assertIn('val nowNanos = android.os.SystemClock.elapsedRealtimeNanos()',start)
        self.assertIn('input.diagnostics, nowNanos',start)
        self.assertEqual(activity.count('append("\\\"inputQuality\\\":")'),2)
    def test_direction_cannot_be_inferred_from_successful_static_calibration(self):
        activity=(SRC/'MainActivity.kt').read_text()
        self.assertIn('private val mountingFrameConfirmed = false',activity)
        self.assertNotIn('mountingFrameConfirmed = sensorProvider.isCalibrated',activity)
    def test_audio_uses_deadline_and_no_unqualified_public_mapping(self):
        audio=(SRC/'sound/AudioEngine.kt').read_text()
        self.assertNotIn('fun mapPoint(',audio)
        self.assertIn('fun mapMeasuredPoint(',audio)
        self.assertIn('fun mapSyntheticPoint(',audio)
        self.assertIn('inputGate.evaluate(',audio)
        self.assertIn('selectAudioWriterSnapshot(writerRunning, published, lastContinuousState)',audio)
        self.assertIn('if (!writerRunning && lastContinuousState == null) break',audio)
        self.assertLess(audio.index('val published = current'), audio.index('val writerRunning = running'))
        self.assertIn('SystemClock.elapsedRealtimeNanos()',audio)
    def test_synthetic_source_does_not_share_measurement_controller(self):
        bank=(SRC/'sound/MatlabV6SoundBankEngine.kt').read_text()
        self.assertIn('updateMeasured(',bank)
        self.assertIn('val checkedControl = control.validatedFor(point)',bank)
        self.assertIn('return toSoundState(point, state, checkedControl)',bank)
        self.assertIn('synthetic',bank.lower())
if __name__=='__main__': unittest.main()
