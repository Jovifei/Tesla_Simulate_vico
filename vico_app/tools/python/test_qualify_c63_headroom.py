import math,pytest
from qualify_c63_headroom import calibrate
def row():return {'id':'case','frames':'960','input_sha256':'a'*64,'A_peak':'2'}
def test_fixed_scalar_follows_peak_and_one_db_reserve_not_rms():
    r=calibrate([row()],{'case':960},{'case':'a'*64})
    assert r['headroom_scalar']==pytest.approx(.8413951416451951*10**(-1/20)/2)
    assert r['reserve_db']==1
def test_missing_duplicate_changed_hash_and_nonfinite_rejected():
    for rows in ([],[row(),row()],[dict(row(),input_sha256='b'*64)],[dict(row(),A_peak='nan')]):
        with pytest.raises(ValueError):calibrate(rows,{'case':960},{'case':'a'*64})
