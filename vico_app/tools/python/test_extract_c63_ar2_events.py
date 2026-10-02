import unittest,numpy as np
from extract_c63_ar2_events import summarize,envelope
class EventExtractionTest(unittest.TestCase):
    def test_attack_tail_and_distinct_interval_fields_are_derived(self):
        env=np.zeros(100);env[20:23]=[.25,.7,1];env[23:29]=[.8,.5,.2,.1,.04,.01];env[50:53]=[.3,.8,1];env[53:59]=[.8,.5,.2,.1,.04,.01]
        report=summarize(env,48000)
        self.assertEqual(2,report['distinct_peaks'])
        self.assertIn('attack_ms',report['events'][0]);self.assertIn('tail_10pct_ms',report['events'][0]);self.assertIn('interval_ms_median',report)
    def test_only_one_sided_ringing_is_not_separable(self):
        env=np.zeros(100);env[20:23]=[.3,.7,1];env[23:]=.8
        self.assertEqual(0,summarize(env,48000)['distinct_peaks'])
    def test_silent_reference_has_no_acoustic_evidence(self):
        with self.assertRaises(ValueError):summarize(np.zeros(100),48000)
    def test_resample_envelope_rejects_invalid_pcm(self):
        with self.assertRaises(ValueError):envelope(np.array([0.0,np.nan]),48000)
if __name__=='__main__':unittest.main()
