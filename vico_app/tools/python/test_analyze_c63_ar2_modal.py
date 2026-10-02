import unittest,numpy as np
from analyze_c63_ar2_modal import line_power,band_prominence
class ModalMetricsTest(unittest.TestCase):
    def test_coherent_sine_has_positive_power_and_cleaner_line(self):
        t=np.arange(48000)/48000;x=np.sin(2*np.pi*820*t).astype('<f4')
        self.assertGreater(line_power(x,820),0)
        self.assertGreater(band_prominence(x,820),10)
    def test_power_is_nonnegative_for_silence_and_mixed_phase(self):
        self.assertEqual(0,line_power(np.zeros(1024,dtype='<f4'),1000))
        t=np.arange(48000)/48000;x=(.3*np.sin(2*np.pi*540*t+.7)+.2*np.sin(2*np.pi*620*t)).astype('<f4')
        self.assertGreaterEqual(line_power(x,540),0)
        self.assertTrue(np.isfinite(band_prominence(x,540)))
if __name__=='__main__':unittest.main()
