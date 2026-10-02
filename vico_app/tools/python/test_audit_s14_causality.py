from pathlib import Path
import audit_s14_causality as audit
import numpy as np

def test_prefix_metrics_reports_first_divergence_without_alignment():
    a=np.zeros((8,2));b=a.copy();b[3:,0]=1
    result=audit.prefix_metrics(a,b,6)
    assert result['first_divergence_frame']==3
    assert result['max_abs']==1

def test_matching_prefix_is_not_marked_divergent():
    a=np.zeros((8,2));b=a.copy();b[6:]=1
    assert audit.prefix_metrics(a,b,6)['first_divergence_frame'] is None

def test_real_source_prefix_probes_detect_documented_future_dependencies():
    result=audit.probe(Path(r'E:\Tesla_speed\prj\tools'))
    assert result['low_frequency_future_dependency_detected']
    assert result['mechanical_texture_total_length_dependency_detected']
    assert result['T1']=='NOT_IMPLEMENTED'
    assert result['source_changes']=='NONE'
    shift=result['shift_detection_vs_fixed_plan_tail']
    assert shift['past_detected_events_a']==[]
    assert len(shift['past_detected_events_b'])>0
    assert shift['fixed_plan_tail_prefix']['first_divergence_frame'] is None
    assert all(row['identical'] for row in result['ptr_partition_probe']['rows'])
