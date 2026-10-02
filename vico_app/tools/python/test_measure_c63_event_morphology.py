import unittest,numpy as np
from measure_c63_event_morphology import isolated_peak,impulse_counts
class EventMorphologyTest(unittest.TestCase):
    def test_both_sides_must_have_independent_valleys(self):
        env=np.array([0.,.1,.3,1.,.9,.9,.9])
        self.assertFalse(isolated_peak(env,3,0,7))
        self.assertTrue(isolated_peak(np.array([0.,.1,.3,1.,.3,.1,0.]),3,0,7))
    def test_censored_boundary_is_not_complete_tail(self):
        self.assertFalse(isolated_peak(np.array([1.,.3,.1,0.]),0,0,4))
    def test_same_frame_arrivals_are_not_multiple_acoustic_impulses(self):
        self.assertEqual({'raw_arrivals':3,'distinct_impulses':1},impulse_counts([12,12,12]))
if __name__=='__main__':unittest.main()
