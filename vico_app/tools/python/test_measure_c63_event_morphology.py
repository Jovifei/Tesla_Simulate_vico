import unittest,numpy as np
from measure_c63_event_morphology import isolated_peak,impulse_counts
class EventMorphologyTest(unittest.TestCase):
    def test_both_sides_must_have_independent_valleys(self):
        env=np.r_[np.zeros(12),1.,np.full(26,.9)]
        self.assertFalse(isolated_peak(env,12,0,len(env)))
        self.assertTrue(isolated_peak(np.r_[np.zeros(12),1.,np.zeros(26)],12,0,39))
    def test_censored_boundary_is_not_complete_tail(self):
        self.assertFalse(isolated_peak(np.array([1.,.3,.1,0.]),0,0,4))
    def test_same_frame_arrivals_are_not_multiple_acoustic_impulses(self):
        self.assertEqual({'raw_arrivals':3,'distinct_impulses':1},impulse_counts([12,12,12]))
if __name__=='__main__':unittest.main()
