import unittest
from qualify_c63_audible import validate_profile,decide_acoustics
class AudibleVerdictTest(unittest.TestCase):
    def test_changed_fixed_gain_or_candidate_identity_fails(self):
        with self.assertRaises(ValueError):validate_profile({'candidate_id':'C63_AR1','headroom_scalar':1.,'original_gain':3.7075542301539652})
    def test_no_coverage_no_acceptance(self):
        self.assertFalse(decide_acoustics({'spectral_improvement':.3,'event_support':False,'modal_reduction_db':4.,'body_protection':True}))
    def test_silence_or_gain_only_never_substitutes_for_structure(self):
        self.assertFalse(decide_acoustics({'spectral_improvement':0.,'event_support':True,'modal_reduction_db':4.,'body_protection':True}))
if __name__=='__main__':unittest.main()
