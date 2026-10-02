import importlib
import importlib.util
import numpy as np
import pytest


def module():
    assert importlib.util.find_spec('build_s14_reference_bundle'), 'S14 implementation missing'
    return importlib.import_module('build_s14_reference_bundle')


def test_only_desktop_endpoint_is_removed():
    m = module()
    a = np.arange(9, dtype=np.float32)
    assert np.array_equal(m.canonical_pcm(a, 48000, 8, allow_endpoint=True), a[:8])
    with pytest.raises(ValueError):
        m.canonical_pcm(a, 48000, 8, allow_endpoint=False)


@pytest.mark.parametrize('rate,shape,value', [(44100,(8,),0), (48000,(8,2),0), (48000,(7,),0), (48000,(8,),float('nan'))])
def test_invalid_pcm_contract_is_rejected(rate, shape, value):
    with pytest.raises(ValueError):
        module().canonical_pcm(np.full(shape,value), rate, 8, allow_endpoint=True)


def test_original_pcm_bytes_preserved():
    x = np.array([0.1,-0.2,0.3,0],dtype='<f4')
    assert module().canonical_pcm(x,48000,4,allow_endpoint=False).tobytes() == x.tobytes()


def test_nonempty_destination_is_rejected(tmp_path):
    p = tmp_path/'existing'; p.mkdir(); (p/'receipt').write_text('keep')
    with pytest.raises(FileExistsError):
        module().require_new_directory(p)
    assert (p/'receipt').read_text() == 'keep'

def test_missing_desktop_source_is_rejected_before_generating_any_files():
    with pytest.raises(ValueError,match='Incomplete'):
        module().validate_material_sources({'D0_D1_D2':{'D1':{}}})

def test_fake_source_identity_is_rejected():
    with pytest.raises(ValueError,match='identity'):
        module().validate_material_sources({'D0_D1_D2':{'D0':{'sha256':'bad'},'D1':{}}})
