"""Production wiring guard: normal overlay must not become the frozen S13 reference bank."""
from pathlib import Path
import hashlib,re,unittest,json
ROOT=Path(__file__).resolve().parents[3]
MAIN=ROOT/'vico_app/Project/android/app/src/main'
class LiveLoopVariantWiring(unittest.TestCase):
 def test_controller_and_review_use_original_bank_not_live_overlay(self):
  s=(MAIN/'java/com/vico/simulator/sound/MatlabV6SoundBankEngine.kt').read_text()
  self.assertIn('referenceBank = loaded',s)
  self.assertIn('controller = MatlabPowertrainController(loaded.powertrain)',s)
  self.assertIn('renderer = MatlabStatefulBankRenderer(normal.bank)',s)
  body=s.split('fun newS13ReviewSession(',1)[1]
  self.assertIn('cache.getOrPut(vehicleKey) { MatlabSoundBankLoader.load(assets, vehicleKey) }',body)
  self.assertNotIn('normalCache',body);self.assertNotIn('setVehicle(',body);self.assertNotIn('loadForNormalPlayback',body)
 def test_audio_review_does_not_require_normal_variant(self):
  s=(MAIN/'java/com/vico/simulator/sound/AudioEngine.kt').read_text()
  body=s.split('fun startS13Review(',1)[1].split('fun ',1)[0]
  self.assertNotIn('setVehicle(',body);self.assertIn('model.newS13ReviewSession(vehicleKey)',body)
  self.assertIn('sampleRate = S13ReviewContract.SAMPLE_RATE',body)
  self.assertIn('!model.normalPlaybackReady()',s)
 def test_only_four_c63_low_loops_are_versioned(self):
  p=MAIN/'assets/live_loop_variants/c63_low_rpm_preroll_v1'
  self.assertEqual({x.name for x in p.iterdir()}, {'manifest.properties','rpm_0700_load_32.wav','rpm_0700_load_92.wav','rpm_1400_load_32.wav','rpm_1400_load_92.wav'})
  manifest=(p/'manifest.properties').read_bytes();s=(MAIN/'java/com/vico/simulator/sound/LiveLoopVariantManifest.kt').read_text()
  digest=re.search(r'MANIFEST_SHA256="([a-f0-9]{64})"',s).group(1)
  self.assertEqual(hashlib.sha256(manifest).hexdigest(),digest)
 def test_normal_identity_is_visible_and_bound_to_recording_profile(self):
  main=(MAIN/'java/com/vico/simulator/MainActivity.kt').read_text()
  self.assertEqual(main.count('append("\\"normalBankVariant\\":\\"")'),2)
  self.assertIn('$activeVehicleKey:${audioEngine.normalBankIdentity()}',main)
  html=(MAIN/'assets/screens/dashboard.html').read_text()
  self.assertIn("s.normalBankVariant==='c63_low_rpm_preroll_v1'",html)
 def test_all_original_twenty_wav_assets_keep_their_identity(self):
  hashes=json.loads((ROOT/'review_packages/vico-input-loop-20261004/replay/reference-bank-sha256.json').read_text())
  self.assertEqual(len(hashes),20)
  for name,digest in hashes.items():self.assertEqual(hashlib.sha256((MAIN/'assets/s12_v10/c63_w204_v6'/name).read_bytes()).hexdigest(),digest,name)
 def test_original_reference_manifest_identity_is_unchanged(self):
  original=(MAIN/'assets/s12_v10/c63_w204_v6/manifest.json').read_bytes()
  self.assertEqual(hashlib.sha256(original).hexdigest(),'7a03686ce671562fabd6f5160ce6fe6d2e04887e84d89a0ae4f3594bfb7d8869')
if __name__=='__main__':unittest.main()
