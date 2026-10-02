import unittest,numpy as np
from fit_c63_bark_modes import FitBudget
class FitBudgetTest(unittest.TestCase):
    def test_budget_cannot_be_reset_or_overrun(self):
        b=FitBudget(2);self.assertEqual(1,b.evaluate(np.ones(4)*.5,lambda _:1))
        b.evaluate(np.ones(4)*.5,lambda _:2)
        with self.assertRaises(RuntimeError):b.evaluate(np.ones(4)*.5,lambda _:3)
    def test_invalid_domain_does_not_reach_objective(self):
        b=FitBudget(32)
        with self.assertRaises(ValueError):b.evaluate(np.ones(4)*.2,lambda _:self.fail('invalid fit'))
        with self.assertRaises(ValueError):b.evaluate(np.array([.5,.5,.5,np.nan]),lambda _:self.fail('invalid fit'))
        self.assertEqual(0,b.count)
if __name__=='__main__':unittest.main()
