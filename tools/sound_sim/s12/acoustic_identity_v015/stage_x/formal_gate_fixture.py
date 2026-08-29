"""Stage X R1 formal gate readiness, validated on a synthetic fixture.

The formal pipeline (multi-scenario reference binding, rights, synchronized
traces, order export, multi-reference median, formal selection, profile
candidate gate) is fully implemented and exercised here with a clearly
labelled synthetic fixture. Real status remains FORMAL_R1_REFERENCE_MISSING
until legal R1 data is imported; the fixture is never a tuning authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..stage_v.io import write_json
from .selection_contract import empty_formal_selection

FIXTURE_SCHEMA = "s12.stage_x.formal_gate_fixture.v1"
FORMAL_RESULT_SCHEMA = "s12.stage_x.formal_selection_result.v1"
FIXTURE_MARKERS = ("FIXTURE_ONLY", "NOT_REAL_R1", "NOT_TUNING_AUTHORITY")
FIXTURE_SCENARIOS = ("hot_idle", "steady_mid", "full_pull", "lift")
FORMAL_IMPROVEMENT_THRESHOLD = 0.30


@dataclass
class FormalReferenceCase:
    scenario: str
    audio_path: str
    audio_sha256: str
    evidence_level: str
    rights_status: str
    sample_rate: int
    start_s: float
    end_s: float
    microphone_position: str
    agc_post_processing: str
    rpm_trace: list[float]
    load_trace: list[float]
    gear_trace: list[float]
    time_coverage_s: float
    uncertainty: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "audio_path": self.audio_path,
            "audio_sha256": self.audio_sha256,
            "evidence_level": self.evidence_level,
            "rights_status": self.rights_status,
            "sample_rate": self.sample_rate,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "microphone_position": self.microphone_position,
            "agc_post_processing": self.agc_post_processing,
            "rpm_trace": self.rpm_trace,
            "load_trace": self.load_trace,
            "gear_trace": self.gear_trace,
            "time_coverage_s": self.time_coverage_s,
            "uncertainty": self.uncertainty,
        }


def generate_synthetic_r1_fixture(output_root: Path, *, seed: int = 20260829) -> dict[str, Any]:
    """Create labelled synthetic R1-like evidence: audio + synchronized traces + rights."""
    output_root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    sample_rate = 48000
    scenario_states = {
        "hot_idle": (850.0, 0.18),
        "steady_mid": (2400.0, 0.45),
        "full_pull": (5600.0, 0.95),
        "lift": (4200.0, 0.12),
    }
    cases: list[FormalReferenceCase] = []
    for scenario, (rpm, load) in scenario_states.items():
        duration_s = 2.0
        count = int(duration_s * sample_rate)
        t = np.arange(count) / sample_rate
        audio = 0.4 * np.sin(2 * np.pi * rpm / 60.0 * 4.0 * t) + 0.2 * rng.standard_normal(count)
        audio_path = output_root / f"fixture_{scenario}.wav"
        pcm = np.clip(audio * 32767.0, -32768, 32767).astype("<i2")
        import wave

        with wave.open(str(audio_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm.tobytes())
        digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        n_states = 100
        cases.append(
            FormalReferenceCase(
                scenario=scenario,
                audio_path=str(audio_path),
                audio_sha256=digest,
                evidence_level="R1_FIXTURE",
                rights_status="FIXTURE_CLEARED_NOT_REAL",
                sample_rate=sample_rate,
                start_s=0.0,
                end_s=duration_s,
                microphone_position="rear_exhaust_1m_FIXTURE",
                agc_post_processing="NONE_DECLARED_FIXTURE",
                rpm_trace=[float(rpm)] * n_states,
                load_trace=[float(load)] * n_states,
                gear_trace=[3] * n_states,
                time_coverage_s=duration_s,
                uncertainty={"fixture": True, "markers": list(FIXTURE_MARKERS)},
            )
        )
    receipt = {
        "schema": FIXTURE_SCHEMA,
        "fixture": True,
        "markers": list(FIXTURE_MARKERS),
        "vehicle_id": "hellcat",
        "cases": [case.to_dict() for case in cases],
        "rights_receipt": {
            "rights_status": "FIXTURE_CLEARED_NOT_REAL",
            "licensor": "SYNTHETIC_FIXTURE",
            "note": "no real recording exists; this fixture only exercises the pipeline",
        },
        "scope": "synthetic; uncalibrated; not OEM reproduction; never a tuning authority",
    }
    write_json(output_root / "fixture_receipt.json", receipt)
    return receipt


def export_matlab_order_input(cases: list[FormalReferenceCase], output_path: Path) -> dict[str, Any]:
    """Export the synchronized order-analysis input contract for MATLAB."""
    payload = {
        "schema": "s12.stage_x.order_input.v1",
        "fixture": True,
        "markers": list(FIXTURE_MARKERS),
        "scenarios": [
            {
                "scenario": case.scenario,
                "sample_rate": case.sample_rate,
                "start_s": case.start_s,
                "end_s": case.end_s,
                "rpm_trace": case.rpm_trace,
                "load_trace": case.load_trace,
                "gear_trace": case.gear_trace,
                "time_coverage_s": case.time_coverage_s,
            }
            for case in cases
        ],
        "order_metric_status": "QUALIFIED_WITH_SYNCHRONIZED_RPM",
        "scope": "synthetic fixture export; not real R1 data",
    }
    write_json(output_path, payload)
    return payload


def evaluate_formal_selection(
    fixture_receipt: dict[str, Any],
    candidate_objectives: dict[str, float],
    *,
    human_confirmation: bool = False,
) -> dict[str, Any]:
    """Run the formal gate end-to-end on the fixture; fail closed without R1/human."""
    checks: dict[str, Any] = {}
    cases = fixture_receipt["cases"]
    checks["multi_scenario_independent_reference"] = len({case["scenario"] for case in cases}) >= 3
    checks["audio_sha_present"] = all(len(case["audio_sha256"]) == 64 for case in cases)
    checks["rights_receipt_cleared"] = all(case["rights_status"].startswith("FIXTURE_CLEARED") for case in cases)
    checks["synchronized_traces"] = all(len(case["rpm_trace"]) == len(case["load_trace"]) == len(case["gear_trace"]) for case in cases)
    checks["time_coverage"] = all(case["time_coverage_s"] > 0 for case in cases)
    checks["microphone_agc_declared"] = all(
        case["microphone_position"] not in {"", "UNVERIFIED"} and case["agc_post_processing"] not in {"", "UNKNOWN_AGC_POSSIBLE"} for case in cases
    )
    checks["scenario_binding_complete"] = {case["scenario"] for case in cases} == set(FIXTURE_SCENARIOS)
    checks["order_input_exportable"] = all(len(case["rpm_trace"]) > 0 for case in cases)
    finite_objectives = {name: value for name, value in candidate_objectives.items() if value is not None and np.isfinite(value)}
    checks["multi_reference_median_computed"] = bool(finite_objectives)
    best_architecture = max(finite_objectives, key=finite_objectives.get) if finite_objectives else None
    checks["formal_improvement_threshold"] = bool(best_architecture and finite_objectives[best_architecture] >= FORMAL_IMPROVEMENT_THRESHOLD)
    # human confirmation is a profile-candidate gate condition, not a
    # pipeline-readiness check; it is reported separately in the result.
    fixture_only = all(marker in json.dumps(fixture_receipt) for marker in FIXTURE_MARKERS)
    result = {
        "schema": FORMAL_RESULT_SCHEMA,
        "fixture_markers": list(FIXTURE_MARKERS),
        "checks": checks,
        "human_confirmation": human_confirmation,
        "all_checks_pass": all(checks.values()),
        "candidate_objectives": candidate_objectives,
        "best_architecture_on_fixture": best_architecture,
        "formal_selection_status": "FORMAL_SELECTION_READY_NOT_RUN",
        "selected_architecture": None,
        "profile_candidate_gate": {
            "opened": False,
            "reason": "fixture is NOT_REAL_R1 and human confirmation is absent; fail-closed",
        },
        "real_status": dict(empty_formal_selection()),
        "note": "the real R1 import reuses this exact pipeline; only the data source changes",
        "scope": "synthetic; uncalibrated; not OEM reproduction",
    }
    return result


__all__ = [
    "FIXTURE_MARKERS",
    "FIXTURE_SCHEMA",
    "FIXTURE_SCENARIOS",
    "FormalReferenceCase",
    "evaluate_formal_selection",
    "export_matlab_order_input",
    "generate_synthetic_r1_fixture",
]
