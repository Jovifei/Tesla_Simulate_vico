import unittest,numpy as np
from measure_c63_ar2_event_morphology import isolated_candidate,raw_impulses,distinct_frame_impulses
class AR2EventMorphologyTest(unittest.TestCase):
    def test_both_valleys_required_and_partial_tails_are_censored(self):
        good=np.r_[np.zeros(20),np.array([0.,.1,.3,1.,.3,.1,0.]),np.zeros(40)]
        bad=np.r_[np.zeros(20),np.array([0.,.1,.1,1.,.8,.8,.8]),np.ones(40)*.8]
        self.assertTrue(isolated_candidate(good,23,0,len(good)))
        self.assertFalse(isolated_candidate(bad,23,0,len(bad)))
        self.assertFalse(isolated_candidate(np.array([1.,.3,.1]),0,0,3))
        self.assertFalse(isolated_candidate(np.array([0.,.1,.3,1.]),3,0,4))
    def test_same_frame_hazard_arrivals_are_one_pulse_not_three(self):
        arrivals=np.array([10,10,10,45],dtype=np.int64)
        self.assertEqual(4,raw_impulses(arrivals));self.assertEqual(2,distinct_frame_impulses(arrivals))
    def test_bad_or_unsorted_frame_trace_is_rejected(self):
        with self.assertRaises(ValueError):distinct_frame_impulses(np.array([4,3]))
if __name__=='__main__':unittest.main()
