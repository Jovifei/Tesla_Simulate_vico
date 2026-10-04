import unittest
import numpy as np

class PeriodPreservingTests(unittest.TestCase):
 def test_length_and_body_phase_remain_unchanged(self):
  from loop_preroll import make_period_preserving_loop
  rng=np.random.default_rng(9);x=rng.normal(0,.1,24960).astype(np.float32);y,m=make_period_preserving_loop(x,48000)
  self.assertEqual(len(y),17280);self.assertEqual(m['body_samples_preserved_before_dc'],16896)
  np.testing.assert_allclose(y[:16896]+m['dc_removed'],x[-17280:-384],atol=3e-8,rtol=1e-6)
 def test_both_joins_are_natural_adjacent_source_steps(self):
  from loop_preroll import make_period_preserving_loop
  x=np.sin(np.arange(24960)*.017).astype(np.float32);y,m=make_period_preserving_loop(x,48000)
  self.assertAlmostEqual(float(y[0]-y[-1]),float(x[-17280]-x[-17281]),places=6)
  self.assertAlmostEqual(float(y[16896]-y[16895]),float(x[-384]-x[-385]),places=6)
 def test_preroll_is_required_instead_of_silently_reusing_processed_loop(self):
  from loop_preroll import make_period_preserving_loop
  with self.assertRaises(ValueError):make_period_preserving_loop(np.zeros(17280,dtype=np.float32),48000)



class PeriodPreservingSafetyTests(unittest.TestCase):
 def test_invalid_finite_mono_rate_and_missing_preroll(self):
  from loop_preroll import make_period_preserving_loop as make
  for x,rate in [(np.full(24960,np.nan),48000),(np.full(24960,np.inf),48000),(np.zeros((24960,2)),48000),(np.zeros(24960),44100),(np.zeros(17280),48000)]:
   with self.assertRaises(ValueError):make(x,rate)
 def test_finite_huge_input_rejects_dc_accumulator_overflow(self):
  from loop_preroll import make_period_preserving_loop as make
  with self.assertRaises(ValueError):make(np.full(24960,np.float32(3e38)),48000)
 def test_96khz_preserves_period_and_correct_overlap(self):
  from loop_preroll import make_period_preserving_loop as make
  y,m=make(np.linspace(-.4,.4,49920,dtype=np.float32),96000)
  self.assertEqual(len(y),34560);self.assertEqual(m['overlap_samples'],768);self.assertEqual(m['period_seconds'],.36)
 def test_zero_dc_and_convex_peak_bound(self):
  from loop_preroll import make_period_preserving_loop as make
  x=np.random.default_rng(123).uniform(-.6,.8,24960).astype(np.float32);y,m=make(x,48000)
  self.assertTrue(np.isfinite(y).all());self.assertLess(abs(float(np.mean(y))),5e-8)
  self.assertLessEqual(float(max(abs(y))),float(max(abs(x)))+abs(m['dc_removed'])+1e-7)
 def test_multiharmonic_frequency_bins_do_not_shift_vs_same_period_reference(self):
  from loop_preroll import make_period_preserving_loop as make
  sr=48000;n=np.arange(24960)
  for rpm in [700,910,1234,5500,6800]:
   for order in [.5,1,2,4,8]:
    freq=rpm/60*order;x=(.2*np.sin(2*np.pi*freq*n/sr)).astype(np.float32);y,_=make(x,sr)
    old=x[-17280:].copy();old-=np.mean(old,dtype=np.float32)
    def peak(z):
     z=np.tile(z,28)[:480000];bins=np.fft.rfftfreq(len(z),1/sr);f=abs(np.fft.rfft(z*np.hanning(len(z))));mask=(bins>max(0,freq-4))&(bins<freq+4);return bins[mask][np.argmax(f[mask])]
    self.assertLessEqual(abs(peak(y)-peak(old)),.100001,(rpm,order))
 def test_a_single_body_impulse_is_not_duplicated(self):
  from loop_preroll import make_period_preserving_loop as make
  x=np.zeros(24960,dtype=np.float32);x[-17280+1000]=.3;y,m=make(x,48000)
  self.assertEqual(int(np.count_nonzero(y+m['dc_removed']>.15)),1)

if __name__=='__main__':unittest.main(verbosity=2)
