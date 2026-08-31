import pytest

from tools.sound_sim.s12.acoustic_comparator.contracts import SCHEMA_NAMES, load_schema


def test_all_required_comparator_contracts_are_loadable() -> None:
    assert set(SCHEMA_NAMES) == {"reference_recording", "synthetic_candidate", "vehicle_state_trace", "comparison_case", "comparison_result", "parameter_recommendation", "human_feedback"}
    assert all(load_schema(name)["$schema"].endswith("schema") for name in SCHEMA_NAMES)


def test_unknown_contract_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        load_schema("not_a_contract")
