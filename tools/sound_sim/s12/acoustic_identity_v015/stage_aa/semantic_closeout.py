"""Stage AA semantic closeout for Stage-Z method ablation evidence."""

from __future__ import annotations

from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from ..stage_v.io import write_json


REPO_ROOT = Path(__file__).resolve().parents[5]
V1_SCORECARD_PATH = Path("tasks/reports/runtime/s12-stage-z/method_ablation_scorecard.json")
V2_SCORECARD_PATH = Path("tasks/reports/runtime/s12-stage-aa/method_ablation_scorecard_v2.json")
CONTRACT_PATH = Path("tasks/reports/runtime/s12-stage-aa/metric_significance_contract.json")
MATRIX_V2_PATH = Path("docs/research/engine-audio-ecosystem/method_adoption_matrix_v2.json")
MATRIX_V3_PATH = Path("docs/research/engine-audio-ecosystem/method_adoption_matrix_v3.json")
RECEIPT_PATH = Path("tasks/reports/runtime/s12-stage-aa/stage_z_semantic_closeout_receipt.json")
CAUSAL_DELTA_FLOOR = 1.0e-4


_METRIC_DEFAULTS: dict[str, dict[str, Any]] = {
    "rms_dbfs": {
        "absolute_floor": 0.50,
        "relative_floor": 0.05,
        "unit": "dBFS",
        "reference_scale": 1.0,
        "reason": "A half-dB level move is above digital measurement noise and is audible in a matched diagnostic comparison.",
        "estimation_method": "max(10x PCM24 level sensitivity, repeat-render floor, 0.5 dB engineering resolution)",
    },
    "peak_dbfs": {
        "absolute_floor": 0.50,
        "relative_floor": 0.05,
        "unit": "dBFS",
        "reference_scale": 1.0,
        "reason": "Peak changes smaller than half a dB are not treated as a meaningful headroom or impact change.",
        "estimation_method": "max(10x PCM24 peak sensitivity, repeat-render floor, 0.5 dB engineering resolution)",
    },
    "crest_db": {
        "absolute_floor": 0.25,
        "relative_floor": 0.05,
        "unit": "dB",
        "reference_scale": 1.0,
        "reason": "Crest-factor changes need a quarter-dB movement to exceed numerical and windowing sensitivity.",
        "estimation_method": "max(repeat-render/quantization floor, 0.25 dB engineering resolution)",
    },
    "dynamic_range_db": {
        "absolute_floor": 0.25,
        "relative_floor": 0.05,
        "unit": "dB",
        "reference_scale": 1.0,
        "reason": "A dynamic-range effect must exceed a quarter dB and five percent of the baseline envelope range.",
        "estimation_method": "max(repeat-render/quantization floor, 5% of baseline, 0.25 dB engineering resolution)",
    },
    "transient_event_density_per_s": {
        "absolute_floor": 0.25,
        "relative_floor": 0.10,
        "unit": "events/s",
        "reference_scale": 1.0,
        "reason": "One quarter event per second is the minimum stable change for a bounded scene-level event-density claim.",
        "estimation_method": "max(one event over a four-second ablation window, 10% relative resolution)",
    },
    "spectral_centroid_hz": {
        "absolute_floor": 5.0,
        "relative_floor": 0.005,
        "unit": "Hz",
        "reference_scale": 1000.0,
        "reason": "Centroid movement must exceed small-bin/quantization sensitivity and one half percent of a kilohertz-scale baseline; 0.000359 Hz is therefore below significance.",
        "estimation_method": "max(10x PCM24 round-trip sensitivity, repeat-render floor, 0.5% of 1 kHz reference scale, 5 Hz engineering resolution)",
    },
    "spectral_flux": {
        "absolute_floor": 0.001,
        "relative_floor": 0.10,
        "unit": "normalized spectral-flux units",
        "reference_scale": 0.01,
        "reason": "Flux is a normalized proxy; a ten-percent and 0.001 absolute move is required to exceed frame-window sensitivity.",
        "estimation_method": "max(10x PCM24 round-trip sensitivity, repeat-render floor, 10% baseline resolution, 0.001 absolute resolution)",
    },
    "roughness_proxy": {
        "absolute_floor": 0.01,
        "relative_floor": 0.05,
        "unit": "normalized roughness proxy",
        "reference_scale": 0.10,
        "reason": "The proxy needs at least a 0.01 absolute and five-percent move to distinguish texture from numerical variation.",
        "estimation_method": "max(10x quantization sensitivity, repeat-render floor, 5% baseline resolution, 0.01 absolute resolution)",
    },
    "sharpness_proxy": {
        "absolute_floor": 0.01,
        "relative_floor": 0.05,
        "unit": "normalized sharpness proxy",
        "reference_scale": 0.10,
        "reason": "The proxy needs at least a 0.01 absolute and five-percent move; a SHA change alone is insufficient.",
        "estimation_method": "max(10x quantization sensitivity, repeat-render floor, 5% baseline resolution, 0.01 absolute resolution)",
    },
    "tonality_proxy": {
        "absolute_floor": 0.01,
        "relative_floor": 0.05,
        "unit": "normalized tonality proxy",
        "reference_scale": 0.10,
        "reason": "Tonality proxy movement must exceed a one-percent absolute and five-percent relative threshold.",
        "estimation_method": "max(10x quantization sensitivity, repeat-render floor, 5% baseline resolution, 0.01 absolute resolution)",
    },
    "persistent_tone_ratio": {
        "absolute_floor": 0.02,
        "relative_floor": 0.05,
        "unit": "fraction of persistent tonal energy",
        "reference_scale": 0.10,
        "reason": "A two-percentage-point move is the minimum stable change in carrier persistence.",
        "estimation_method": "max(10x quantization sensitivity, repeat-render floor, 5% baseline resolution, 0.02 absolute resolution)",
    },
    "narrowband_whine_proxy": {
        "absolute_floor": 0.01,
        "relative_floor": 0.10,
        "unit": "normalized narrowband-whine proxy",
        "reference_scale": 0.10,
        "reason": "Whine dominance needs a one-percent absolute and ten-percent relative movement to be treated as an engineering effect.",
        "estimation_method": "max(10x quantization sensitivity, repeat-render floor, 10% baseline resolution, 0.01 absolute resolution)",
    },
}


def default_metric_significance_contract() -> dict[str, Any]:
    return {
        "schema": "s12.stage_aa.metric_significance_contract.v1",
        "causal_detection": {
            "absolute_delta_floor": CAUSAL_DELTA_FLOOR,
            "rule": "PCM SHA must differ and absolute metric delta must exceed this numerical floor.",
            "purpose": "numerical causal detection only; not engineering significance",
        },
        "metrics": deepcopy(_METRIC_DEFAULTS),
        "evidence_basis": {
            "repeat_render_count": 3,
            "repeat_render_max_abs_delta": "measured per metric during AA0 audit",
            "pcm24_roundtrip": "Stage-V PCM24 rint/pack/unpack contract",
            "scenario_variance": "Stage-Z ablation baselines and AA1 scene ledger",
            "known_engineering_scale": "metric-specific absolute and relative floors above",
        },
        "status": "DIAGNOSTIC_ONLY",
    }


def load_metric_significance_contract(path: Path | None = None) -> dict[str, Any]:
    target = (REPO_ROOT / CONTRACT_PATH) if path is None else Path(path)
    if target.is_file():
        return json.loads(target.read_text(encoding="utf-8"))
    return default_metric_significance_contract()


def _relative_delta(delta: float, before: float, spec: dict[str, Any]) -> float:
    denominator = max(abs(float(before)), float(spec.get("reference_scale", 1.0e-12)))
    return abs(float(delta)) / denominator


def _classify_row(row: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    metric = row.get("target_metric")
    delta = float(row.get("delta", 0.0))
    before = float(row.get("target_metric_before", 0.0))
    off_sha = str(row.get("off_pcm_sha", ""))
    on_sha = str(row.get("on_pcm_sha", ""))
    guards_pass = bool(row.get("guard_metric_before", {}).get("passed")) and bool(row.get("guard_metric_after", {}).get("passed"))
    causal_floor = float(contract["causal_detection"]["absolute_delta_floor"])
    causal = off_sha != on_sha and abs(delta) > causal_floor and guards_pass
    if metric is None or metric not in contract["metrics"]:
        significance = "NOT_APPLICABLE"
        relative = None
        threshold = None
    else:
        threshold = contract["metrics"][metric]
        relative = _relative_delta(delta, before, threshold)
        significant = abs(delta) >= float(threshold["absolute_floor"]) and relative >= float(threshold["relative_floor"])
        significance = "MEANINGFUL_ENGINEERING_EFFECT" if significant and causal else "BELOW_ENGINEERING_SIGNIFICANCE"
    return {
        "causal_status": "CAUSAL_EFFECT_DETECTED" if causal else "NO_CAUSAL_EFFECT",
        "engineering_significance_status": significance,
        "quality_direction_status": "REFERENCE_UNAVAILABLE",
        "quality_direction_reason": "No synchronized legal R1 reference is available; this field is diagnostic only.",
        "causal_delta_floor": causal_floor,
        "engineering_absolute_floor": None if threshold is None else threshold["absolute_floor"],
        "engineering_relative_floor": None if threshold is None else threshold["relative_floor"],
        "relative_delta": relative,
        "deprecated_status": row.get("status"),
    }


def build_scorecard_v2(rows: Iterable[dict[str, Any]], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    active_contract = contract or default_metric_significance_contract()
    output_rows: list[dict[str, Any]] = []
    for original in rows:
        row = deepcopy(original)
        row.pop("status", None)
        row.update(_classify_row(original, active_contract))
        output_rows.append(row)
    return {
        "schema": "s12.stage_aa.method_ablation_scorecard.v2",
        "status": "DIAGNOSTIC_ONLY",
        "legacy_scorecard": str(V1_SCORECARD_PATH).replace("\\", "/"),
        "metric_significance_contract": str(CONTRACT_PATH).replace("\\", "/"),
        "causal_status_is_not_quality_claim": True,
        "rows": output_rows,
        "scope": "synthetic; uncalibrated; vehicle-inspired; no synchronized R1 reference",
    }


def _evidence_for_method(method_id: str, score_by_method: dict[str, dict[str, Any]]) -> dict[str, Any]:
    row = score_by_method.get(method_id)
    if row is None:
        return {
            "causal_status": "NO_CAUSAL_EFFECT",
            "engineering_significance_status": "NOT_APPLICABLE",
            "quality_direction_status": "REFERENCE_UNAVAILABLE",
            "deprecated_status": None,
            "scorecard_row": None,
        }
    return {
        "causal_status": row["causal_status"],
        "engineering_significance_status": row["engineering_significance_status"],
        "quality_direction_status": row["quality_direction_status"],
        "deprecated_status": row["deprecated_status"],
        "target_metric": row.get("target_metric"),
        "relative_delta": row.get("relative_delta"),
        "evidence_receipt": str(V2_SCORECARD_PATH).replace("\\", "/"),
        "scorecard_row": row["method_id"],
    }


def build_method_adoption_matrix_v3(matrix_v2: dict[str, Any], scorecard_v2: dict[str, Any], *, base_main_head: str) -> dict[str, Any]:
    score_by_method = {row["method_id"]: row for row in scorecard_v2["rows"]}
    rows = []
    for original in matrix_v2["rows"]:
        row = deepcopy(original)
        row["acoustic_evidence"] = _evidence_for_method(str(row["method_id"]), score_by_method)
        rows.append(row)
    return {
        "schema": "s12.stage_aa.method_adoption_matrix.v3",
        "base_matrix": str(MATRIX_V2_PATH).replace("\\", "/"),
        "base_main_head": base_main_head,
        "tested_head": matrix_v2.get("tested_head"),
        "adoption_and_acoustic_significance_are_separate": True,
        "rows": rows,
        "scope": matrix_v2.get("scope"),
    }


def enrich_method_adoption_matrix_v2(matrix_v2: dict[str, Any], scorecard_v2: dict[str, Any], *, base_main_head: str) -> dict[str, Any]:
    output = deepcopy(matrix_v2)
    output["post_merge_main_head"] = base_main_head
    output["semantic_closeout_scorecard"] = str(V2_SCORECARD_PATH).replace("\\", "/")
    output["acoustic_significance_is_separate_from_adoption"] = True
    score_by_method = {row["method_id"]: row for row in scorecard_v2["rows"]}
    for row in output["rows"]:
        row["acoustic_evidence"] = _evidence_for_method(str(row["method_id"]), score_by_method)
    return output


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_v1(repo_root: Path) -> dict[str, Any]:
    return json.loads((repo_root / V1_SCORECARD_PATH).read_text(encoding="utf-8"))


def recompute_scorecard_v2(*, duration_s: float = 4.0, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Re-run every executable Stage-Z ablation, then classify its result."""
    from ..stage_z.method_ablation import METHOD_CATALOG, score_ablation

    rows = []
    for item in METHOD_CATALOG:
        result, _ = score_ablation(item["method_id"], item["ablation_scenario"], duration_s=duration_s)
        rows.append(result)
    return build_scorecard_v2(rows, load_metric_significance_contract(repo_root / CONTRACT_PATH))


def publish_semantic_closeout(*, base_main_head: str, tested_head: str, recompute: bool = False, duration_s: float = 4.0, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    contract = default_metric_significance_contract()
    contract_path = repo_root / CONTRACT_PATH
    write_json(contract_path, contract)
    v1 = _load_v1(repo_root)
    scorecard = recompute_scorecard_v2(duration_s=duration_s, repo_root=repo_root) if recompute else build_scorecard_v2(v1["rows"], contract)
    score_path = repo_root / V2_SCORECARD_PATH
    write_json(score_path, scorecard)
    matrix_path = repo_root / MATRIX_V2_PATH
    matrix_v2 = json.loads(matrix_path.read_text(encoding="utf-8"))
    enriched_v2 = enrich_method_adoption_matrix_v2(matrix_v2, scorecard, base_main_head=base_main_head)
    write_json(matrix_path, enriched_v2)
    matrix_v3 = build_method_adoption_matrix_v3(enriched_v2, scorecard, base_main_head=base_main_head)
    matrix_v3_path = repo_root / MATRIX_V3_PATH
    write_json(matrix_v3_path, matrix_v3)
    receipt = {
        "schema": "s12.stage_aa.stage_z_semantic_closeout_receipt.v1",
        "status": "PASS",
        "base_main_head": base_main_head,
        "tested_head": tested_head,
        "recomputed_all_ablations": recompute,
        "ablation_duration_s": duration_s if recompute else None,
        "legacy_scorecard_path": str(V1_SCORECARD_PATH).replace("\\", "/"),
        "legacy_scorecard_sha256": _sha256(repo_root / V1_SCORECARD_PATH),
        "scorecard_v2_path": str(V2_SCORECARD_PATH).replace("\\", "/"),
        "scorecard_v2_sha256": _sha256(score_path),
        "metric_significance_contract_path": str(CONTRACT_PATH).replace("\\", "/"),
        "metric_significance_contract_sha256": _sha256(contract_path),
        "matrix_v2_path": str(MATRIX_V2_PATH).replace("\\", "/"),
        "matrix_v2_sha256": _sha256(matrix_path),
        "matrix_v3_path": str(MATRIX_V3_PATH).replace("\\", "/"),
        "matrix_v3_sha256": _sha256(matrix_v3_path),
        "rows": len(scorecard["rows"]),
        "boundaries": {"r1_reference": "MISSING", "quality_direction": "REFERENCE_UNAVAILABLE", "ptr_radiation_track_p": "UNCHANGED"},
    }
    receipt_path = repo_root / RECEIPT_PATH
    write_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-main-head", required=True)
    parser.add_argument("--tested-head", required=True)
    parser.add_argument("--recompute", action="store_true")
    parser.add_argument("--duration-s", type=float, default=4.0)
    args = parser.parse_args()
    receipt = publish_semantic_closeout(base_main_head=args.base_main_head, tested_head=args.tested_head, recompute=args.recompute, duration_s=args.duration_s)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_method_adoption_matrix_v3",
    "build_scorecard_v2",
    "default_metric_significance_contract",
    "enrich_method_adoption_matrix_v2",
    "load_metric_significance_contract",
    "publish_semantic_closeout",
    "recompute_scorecard_v2",
]
