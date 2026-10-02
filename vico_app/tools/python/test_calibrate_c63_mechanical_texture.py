import unittest,numpy as np
from calibrate_c63_mechanical_texture import fixed_scale
class TextureScaleTest(unittest.TestCase):
    def test_fixed_scale_is_stem_only_and_does_not_depend_on_mixed_audio(self):
        self.assertEqual(2.,fixed_scale(np.ones(100)*2,np.ones(100),10,90))
    def test_silence_or_mismatched_stem_is_rejected(self):
        with self.assertRaises(ValueError):fixed_scale(np.ones(100),np.zeros(100),10,90)
        with self.assertRaises(ValueError):fixed_scale(np.ones(100),np.ones(99),10,90)
if __name__=='__main__':unittest.main()
