import unittest
import numpy as np
from fit_c63_hybrid import FitBudget,distribution_distance,improves,pack_profile

class HybridFitTest(unittest.TestCase):
    def test_budget_counts_every_attempt_and_never_restarts(self):
        budget=FitBudget(2)
        self.assertEqual(1.0,budget.evaluate([1.0],lambda p:{'score':float(p[0])})['score'])
        budget.evaluate([2.0],lambda p:{'score':float(p[0])})
        with self.assertRaises(RuntimeError):budget.evaluate([3.0],lambda p:{'score':float(p[0])})
        self.assertEqual(2,budget.count)
    def test_nonfinite_parameter_is_rejected_before_callback(self):
        b=FitBudget(3)
        with self.assertRaises(ValueError):b.evaluate([np.nan],lambda p:self.fail('invalid parameter reached model'))
        self.assertEqual(0,b.count)
    def test_distribution_comparison_does_not_assign_rpm_pairs(self):
        x=[{'a':1.0},{'a':3.0}];y=[{'a':3.0},{'a':1.0}]
        self.assertEqual(0.0,distribution_distance(x,y,{'a':1.0},{'a':1.0}))
        self.assertFalse(improves(1.0,1.0));self.assertTrue(improves(1.0,.79));self.assertFalse(improves(0.0,0.0))
    def test_binary_matches_runtime_contract_size_and_magic(self):
        def pair(n,k):
            x=np.zeros(n);x[k:k+2]=np.array([1,-1])/np.sqrt(2);return x
        payload=pack_profile(pair(2048,0),(pair(12288,0),pair(12288,2),pair(12288,4)),
            1.0,1.0,.1,.2,np.ones(4)*.5,'0'*64)
        self.assertEqual(311432,len(payload));self.assertEqual(b'C63HY1V1',payload[:8])

if __name__=='__main__':unittest.main()
