from pathlib import Path
from tools.sound_sim.s12.acoustic_comparator.cli import compare_packages
def test_empty_package_list_is_deterministic():
    result=compare_packages([])
    assert result["vehicles"] == {}
    assert result["analysis_domain"] == "unaltered_final_pcm"
