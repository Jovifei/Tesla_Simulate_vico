"""Stage-L Hellcat-only candidate lineage and provenance contract."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path

import pytest
import jsonschema
from jsonschema import ValidationError

from tools.sound_sim.s12.acoustic_identity_v015.stage_l import candidate_profiles as module

from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import (
    BASE_COMMIT,
    PARENT_CANDIDATE_ID,
    PARENT_CANDIDATE_PATH,
    PARENT_CANDIDATE_SHA256,
    SCHEMA_VERSION,
    TOP_LEVEL,
    load_stage_l_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
CANDIDATE_PATH = ROOT / "targets" / "stage_l_candidates" / "hellcat_candidate_v8.json"
SCHEMA_PATH = ROOT / "targets" / "stage_l_hellcat_candidate.schema.json"


def _payload() -> dict[str, object]:
    return json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(payload, allow_nan=True), encoding="utf-8")
    return path


def test_stage_l_v8_loads_with_exact_top_level_and_frozen_lineage() -> None:
    candidate = load_stage_l_candidate(CANDIDATE_PATH)
    assert set(candidate.payload) == TOP_LEVEL
    assert candidate.payload["schema_version"] == SCHEMA_VERSION
    assert candidate.vehicle_id == "hellcat"
    assert candidate.status == "Candidate"
    assert candidate.payload["base_commit"] == BASE_COMMIT
    assert candidate.payload["parent_candidate_id"] == PARENT_CANDIDATE_ID
    assert candidate.payload["parent_candidate_path"] == PARENT_CANDIDATE_PATH
    assert candidate.payload["parent_candidate_sha256"] == PARENT_CANDIDATE_SHA256

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == TOP_LEVEL


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda value: value.update({"unknown": True}), "top-level"),
        (lambda value: value.__setitem__("vehicle_id", "c63_w204"), "vehicle_id"),
        (lambda value: value.__setitem__("base_commit", "0" * 40), "base_commit"),
        (lambda value: value.__setitem__("parent_candidate_id", "hellcat_stage_i_v6"), "parent"),
        (lambda value: value.__setitem__("parent_candidate_path", "targets/stage_i_candidates/Hellcat_candidate_v6_C_SofterMechanical.json"), "parent"),
        (lambda value: value.__setitem__("parent_candidate_sha256", "0" * 64), "parent"),
        (lambda value: value.__setitem__("status", "Approved"), "Candidate"),
    ],
)
def test_stage_l_candidate_fails_closed_on_lineage_vehicle_status_and_unknown_fields(
    tmp_path: Path, mutator, match: str,
) -> None:
    payload = _payload()
    mutator(payload)
    with pytest.raises(ValueError, match=match):
        load_stage_l_candidate(_write(tmp_path, payload))


@pytest.mark.parametrize(
    "value,bounds",
    [
        (0.10, [0.20, 0.20]),
        (0.10, [0.20, 0.10]),
        (0.25, [0.06, 0.20]),
        (math.nan, [0.06, 0.20]),
        (math.inf, [0.06, 0.20]),
        (0.10, [0.06, math.inf]),
    ],
)
def test_stage_l_candidate_rejects_nonfinite_out_of_range_and_nonascending_parameters(
    tmp_path: Path, value: float, bounds: list[float],
) -> None:
    payload = _payload()
    record = payload["combustion_and_blowdown"]["cylinder_strength_variation"]  # type: ignore[index]
    record["value"] = value
    record["range"] = bounds
    with pytest.raises(ValueError, match="value/range"):
        load_stage_l_candidate(_write(tmp_path, payload))


@pytest.mark.parametrize("invented_fact", ("rotor_pocket_count", "timing_gear_tooth_count"))
def test_unknown_rotor_or_timing_gear_counts_cannot_masquerade_as_official_facts(
    tmp_path: Path, invented_fact: str,
) -> None:
    payload = _payload()
    payload["provenance"]["official_facts"][invented_fact] = 5  # type: ignore[index]
    with pytest.raises(ValueError, match="official_facts"):
        load_stage_l_candidate(_write(tmp_path, payload))


def test_every_tunable_parameter_retains_c_synthetic_candidate_assumption_provenance() -> None:
    candidate = load_stage_l_candidate(CANDIDATE_PATH)
    names = candidate.requested_parameters()
    assert names
    for qualified_name in names:
        section, name = qualified_name.split(".", 1)
        record = candidate.payload[section][name]
        assert set(record) == {
            "value", "unit", "range", "source_level", "source", "source_scope", "verification_state"
        }
        assert record["source_level"] == "C"
        assert record["source"] == "synthetic"
        assert record["verification_state"] == "candidate_assumption"


def test_with_parameter_revalidates_the_immutable_candidate() -> None:
    candidate = load_stage_l_candidate(CANDIDATE_PATH)
    changed = candidate.with_parameter("operating_level", "low_load_gain_db", 0.0)
    assert changed is not candidate
    assert changed.parameter("operating_level", "low_load_gain_db") == 0.0
    assert candidate.parameter("operating_level", "low_load_gain_db") != 0.0
    with pytest.raises(ValueError, match="unknown Stage-L parameter"):
        candidate.with_parameter("combustion_and_blowdown", "not_public", 1.0)


@pytest.mark.parametrize(
    "name,value",
    [
        ("engine_displacement_l", 6.4),
        ("engine_configuration", "V8"),
        ("supercharger_type", "roots"),
        ("supercharger_drive_ratio", 2.35),
        ("published_max_supercharger_rpm", 14599),
        ("published_max_boost_psi", 11.5),
        ("provenance_note", "drifted boundary"),
    ],
)
def test_every_official_fact_value_is_exact(tmp_path: Path, name: str, value: object) -> None:
    payload = _payload()
    payload["provenance"]["official_facts"][name] = value  # type: ignore[index]
    with pytest.raises(ValueError, match="official_facts"):
        load_stage_l_candidate(_write(tmp_path, payload))


def test_candidate_load_fails_if_repository_l0_evidence_receipt_bytes_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-l-hellcat-calibration-v1" / "stage_l_stage_k_evidence_receipt.json"
    drifted = tmp_path / source.name
    drifted.write_bytes(source.read_bytes() + b"\n")
    monkeypatch.setattr(module, "_L0_EVIDENCE_RECEIPT_PATH", drifted, raising=False)
    with pytest.raises(ValueError, match="L0|receipt|SHA-256"):
        load_stage_l_candidate(CANDIDATE_PATH)


def test_candidate_load_binds_component_values_to_repository_l0_feedback_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-l-hellcat-calibration-v1" / "stage_l_jovi_feedback_intake.json"
    receipt = json.loads(source.read_text(encoding="utf-8"))
    receipt["csv_inputs"]["formal_stage_k_csv"]["sha256"] = "0" * 64
    drifted = tmp_path / source.name
    drifted.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(module, "_L0_FEEDBACK_RECEIPT_PATH", drifted, raising=False)
    with pytest.raises(ValueError, match="L0|receipt|SHA-256"):
        load_stage_l_candidate(CANDIDATE_PATH)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value["reference_target"].update({"unknown": True}),
        lambda value: value["feedback_receipt"].pop("formal_template_status"),
        lambda value: value["crank_clock"].update({"unknown": True}),
        lambda value: value["combustion_and_blowdown"].pop("cylinder_strength_variation"),
        lambda value: value["supercharger_intake"].update({"unknown": value["supercharger_intake"]["gear_to_aero_ratio"]}),
        lambda value: value["loudness"].update({"unknown": True}),
        lambda value: value["locked_layers"]["rumble"].update({"unknown": True}),
        lambda value: value["provenance"]["official_facts"].update({"unknown": True}),
    ],
)
def test_json_schema_fails_closed_for_every_nested_contract(mutator) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    payload = _payload()
    mutator(payload)
    with pytest.raises(ValidationError):
        jsonschema.Draft202012Validator(schema).validate(payload)
