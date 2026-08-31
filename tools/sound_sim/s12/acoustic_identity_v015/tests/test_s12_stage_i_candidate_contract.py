from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE = _ROOT / "targets" / "stage_i_candidates" / "Hellcat_candidate_v6.json"


def _candidate_module():
    return importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_profiles"
    )


def test_stage_i_package_exports_candidate_api_lazily() -> None:
    package = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i"
    )
    assert package.StageICandidateProfile
    assert callable(package.load_stage_i_candidate)
    assert callable(package.render_stage_i_candidate)


def test_stage_i_candidate_v6_is_strict_reference_bound_and_hellcat_only() -> None:
    module = _candidate_module()
    candidate = module.load_stage_i_candidate(_CANDIDATE)
    assert candidate.vehicle_id == "hellcat"
    assert candidate.candidate_id == "hellcat_stage_i_v6"
    assert candidate.status == "Candidate"
    assert candidate.parent_candidate_id == "hellcat_stage_h_v5"
    assert candidate.base_commit == module.BASE_COMMIT
    assert set(candidate.section_values("source")) == set(module.SOURCE_KEYS)
    assert candidate.requested_parameters()


def test_stage_i_json_schema_declares_exact_source_parameter_keys() -> None:
    module = _candidate_module()
    schema = json.loads(
        (_ROOT / "targets" / "stage_i_hellcat_candidate.schema.json").read_text(
            encoding="utf-8"
        )
    )
    source = schema["properties"]["source"]
    assert source["additionalProperties"] is False
    assert set(source["required"]) == set(module.SOURCE_KEYS)
    assert set(source["properties"]) == set(module.SOURCE_KEYS)


def test_stage_i_candidate_rejects_unknown_source_parameter(tmp_path: Path) -> None:
    module = _candidate_module()
    payload = json.loads(_CANDIDATE.read_text(encoding="utf-8"))
    payload["source"]["pretend_whine"] = dict(payload["source"]["blower_gain_scale"])
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown Stage-I source override"):
        module.load_stage_i_candidate(bad)


@pytest.mark.parametrize(
    "field,value",
    (
        ("source_level", "B"),
        ("source", "measured"),
        ("verification_state", "approved"),
    ),
)
def test_stage_i_candidate_rejects_provenance_promotion(
    tmp_path: Path, field: str, value: str
) -> None:
    module = _candidate_module()
    payload = json.loads(_CANDIDATE.read_text(encoding="utf-8"))
    payload["source"]["blower_gain_scale"][field] = value
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        module.load_stage_i_candidate(bad)
