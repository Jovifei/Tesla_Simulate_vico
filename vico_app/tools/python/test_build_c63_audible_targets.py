import unittest,numpy as np
from build_c63_audible_targets import validate_windows,features,feature_distance,improved
class TargetsTest(unittest.TestCase):
    def windows(self,end=10,start=10):
        return [{'id':'cal','source_sha256':'a'*64,'start_sample':0,'end_sample':end,'split':'calibration'},
                {'id':'held','source_sha256':'a'*64,'start_sample':start,'end_sample':20,'split':'holdout'}]
    def test_overlap_is_not_independent_holdout(self):
        with self.assertRaises(ValueError):validate_windows(self.windows(11,10))
        validate_windows(self.windows())
    def test_duplicate_window_identity_fails(self):
        rows=self.windows();rows[1]['id']='cal'
        with self.assertRaises(ValueError):validate_windows(rows)
    def test_silence_is_not_an_improved_event(self):
        with self.assertRaises(ValueError):features(np.zeros(48000))
    def test_gain_only_change_is_not_feature_improvement(self):
        t=np.arange(48000)/48000;x=np.sin(2*np.pi*80*t)+.2*np.sin(2*np.pi*540*t)
        a=features(x);b=features(.4*x)
        scales={key:1.0 for key in a if key!='rms'}
        self.assertLess(feature_distance(a,b,scales),1e-8)
        self.assertFalse(improved(1.0,1.0))
    def test_missing_protection_band_fails(self):
        t=np.arange(48000)/48000;a=features(np.sin(2*np.pi*100*t));b=dict(a);del b['mid']
        with self.assertRaises(ValueError):feature_distance(a,b,{key:1.0 for key in a if key!='rms'})
if __name__=='__main__':unittest.main()
