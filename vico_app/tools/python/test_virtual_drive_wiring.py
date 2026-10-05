"""Source-route guards complement actual Kotlin tests; not Android or road acceptance."""
from pathlib import Path
import hashlib,unittest
ROOT=Path(__file__).resolve().parents[3]
S=ROOT/'vico_app/Project/android/app/src/main/java/com/vico/simulator/sound'
class VirtualDriveWiringTest(unittest.TestCase):
 def test_reference_controller_body_is_unchanged(self):
  b=(S/'MatlabPowertrainController.kt').read_bytes();tail=b[b.index(b'    fun update(timeS:'):]
  self.assertEqual('3d68baf5eeeb1103093f9019f9aeedec610f83d6eca540fafd507677237fea49',hashlib.sha256(tail).hexdigest())
 def test_bank_calls_actual_pure_mapping_bridge(self):
  s=(S/'MatlabV6SoundBankEngine.kt').read_text();self.assertIn('state.toMappedSoundState(point, control)',s)
  m=(S/'MatlabSoundStateMapping.kt').read_text();self.assertIn('control?.source == DriveInputSource.REAL',m);self.assertIn('modelContinuityRevision = modelContinuityRevision',m)
  self.assertIn('speedUsable = control.speedUsable && measuredInputUsable',m)
 def test_main_carries_reported_accuracy_and_identifiable_real_policy(self):
  s=(ROOT/'vico_app/Project/android/app/src/main/java/com/vico/simulator/MainActivity.kt').read_text()
  self.assertIn('reportedSpeedUncertaintyMps = diagnostics.gpsAccuracy?.takeIf',s)
  self.assertIn('SpeedAccuracy.Status.AVAILABLE',s);self.assertIn('VirtualDriveDemand.POLICY_ID',s)
 def test_virtual_load_is_not_multiplied_by_shift_gain(self):
  s=(S/'MatlabPowertrainController.kt').read_text().split('    fun update(timeS:')[0]
  self.assertIn('demandState.bankLoad,gear,torqueGain',s);self.assertNotIn('demandState.bankLoad *',s)
 def test_gate_keeps_upstream_epoch_and_model_segment_separate(self):
  s=(S/'AudioInputGate.kt').read_text();self.assertIn('previousEpoch != control?.epoch',s)
  self.assertIn('previousModelRevision != control?.modelContinuityRevision',s)
if __name__=='__main__':unittest.main()
