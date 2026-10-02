import pytest
from qualify_c63_finite_pressure import evaluate,expected_cases

def row(peak):return {'id':'sample','frames':'960','A_peak':'1.4','B_peak':str(peak),'B_first_exceed':'-1','B_worst_frame':'55'}
def test_one_exceeded_case_rejects_candidate():
    assert evaluate([row(.9)],{'sample':960})['status']=='CANDIDATE_REJECTED_NUMERICAL'
def test_no_rows_duplicate_or_nonfinite_cannot_pass():
    for rows in ([],[row(.8),row(.8)],[row(float('nan'))]):
        with pytest.raises(ValueError):evaluate(rows,{'sample':960})
def test_numeric_pass_is_not_sound_or_phone_acceptance():
    r=evaluate([row(.8)],{'sample':960})
    assert r['status']=='NUMERICAL_PASS_ONLY'
    assert r['human_acceptance']=='NOT_RUN'
def test_fixed_set_has_expected333_cases():assert len(expected_cases(38))==333
