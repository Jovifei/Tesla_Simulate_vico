"""Fail-closed importer and bounded diagnostics for the anchor Chinese A/B export."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from .anchor_ab_validate import AnchorABValidationError, validate_anchor_ab_package


class FeedbackImportError(ValueError):
    """Raised when a Jovi feedback export is incomplete or not package-bound."""


_PREFERENCES = {"参考声音更好", "候选声音更好", "两者接近", "无法判断"}
_PARAMETER_GROUPS = {
    "车型身份": "vehicle_identity_voicing",
    "真实感": "broadband_realism_balance",
    "低频重量": "low_frequency_weight",
    "机械感": "mechanical_texture",
    "怠速生命感": "idle_dynamics",
    "加速攻击性": "acceleration_aggression",
    "换挡真实感": "shift_transient",
    "回火自然度": "afterfire_transient",
    "合成器感/伪影": "synthetic_artifact_suppression",
}
_COMMENT_KEYWORDS = {
    "低频": "低频重量",
    "低频偏": "低频重量",
    "机械": "机械感",
    "怠速": "怠速生命感",
    "加速": "加速攻击性",
    "换挡": "换挡真实感",
    "回火": "回火自然度",
    "伪影": "合成器感/伪影",
    "合成器": "合成器感/伪影",
    "车型": "车型身份",
    "身份": "车型身份",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FeedbackImportError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise FeedbackImportError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FeedbackImportError(f"missing feedback field: {label}")
    return value.strip()


def _sha(value: object, label: str) -> str:
    text = _text(value, label).lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise FeedbackImportError(f"invalid SHA-256: {label}")
    return text


def _score(value: object, label: str) -> int | str:
    if isinstance(value, str) and value.strip() in {"不确定", "uncertain"}:
        return "不确定"
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FeedbackImportError(f"invalid score: {label}") from exc
    if number < 1 or number > 5 or not number.is_integer():
        raise FeedbackImportError(f"score outside integer 1..5: {label}")
    return int(number)


def _manifest_trial_map(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for trial in manifest.get("trials", []):
        if isinstance(trial, Mapping):
            result[_text(trial.get("trial_id"), "manifest.trial_id")] = trial
    return result


def classify_feedback_problems(trials: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Classify low/uncertain dimensions without inferring numeric tuning values."""

    evidence: dict[str, dict[str, Any]] = {}
    for trial in trials:
        trial_id = str(trial.get("trial_id"))
        scores = trial.get("scores") if isinstance(trial.get("scores"), Mapping) else {}
        for dimension, value in scores.items():
            is_problem = value == "不确定" or (isinstance(value, int) and value <= 2)
            if not is_problem or dimension == "偏好":
                continue
            item = evidence.setdefault(dimension, {"category": dimension, "trial_ids": [], "signals": []})
            item["trial_ids"].append(trial_id)
            item["signals"].append("uncertain" if value == "不确定" else f"score_{value}")
        comment = trial.get("comment")
        if isinstance(comment, str):
            for keyword, category in _COMMENT_KEYWORDS.items():
                if keyword in comment:
                    item = evidence.setdefault(category, {"category": category, "trial_ids": [], "signals": []})
                    if trial_id not in item["trial_ids"]:
                        item["trial_ids"].append(trial_id)
                    item["signals"].append(f"comment:{keyword}")
        if trial.get("preference") == "参考声音更好":
            item = evidence.setdefault("候选整体偏好落后", {"category": "候选整体偏好落后", "trial_ids": [], "signals": []})
            item["trial_ids"].append(trial_id)
            item["signals"].append("reference_preferred")
    return [evidence[key] for key in sorted(evidence)]


def validate_anchor_feedback(feedback_path: Path, package_root: Path) -> dict[str, Any]:
    """Validate a complete anchor page export and return a canonical receipt."""

    try:
        package_receipt = validate_anchor_ab_package(package_root)
    except AnchorABValidationError as exc:
        raise FeedbackImportError(str(exc)) from exc
    package_root = Path(package_root).resolve()
    feedback = _read_json(Path(feedback_path), "feedback JSON")
    if feedback.get("schema_version") != "s12-stage-s-human-feedback-zh.v1":
        raise FeedbackImportError("unexpected feedback schema")
    if feedback.get("test_id") != package_receipt.get("package_status") and feedback.get("test_id") != _read_json(package_root / "anchor_ab_zh_manifest.json", "manifest").get("test_id"):
        raise FeedbackImportError("feedback test_id does not match package")
    if feedback.get("package_status") != "READY_FOR_REVIEW":
        raise FeedbackImportError("feedback package must be READY_FOR_REVIEW")
    if feedback.get("automatic_tuning_eligible") is not False:
        raise FeedbackImportError("feedback cannot grant automatic tuning")
    if feedback.get("profile_update") != "FORBIDDEN":
        raise FeedbackImportError("feedback cannot grant profile update")
    listener_id = _text(feedback.get("listener_id"), "listener_id")
    supplied_package_sha = _sha(feedback.get("package_manifest_sha256"), "package_manifest_sha256")
    if supplied_package_sha != package_receipt["manifest_sha256"].lower():
        raise FeedbackImportError("feedback package SHA does not match anchor manifest")
    evidence_level = _text(feedback.get("evidence_level"), "evidence_level").upper()
    if evidence_level not in {"R2", "R3"}:
        raise FeedbackImportError("only R2/R3 human feedback is accepted")
    manifest = _read_json(package_root / "anchor_ab_zh_manifest.json", "anchor manifest")
    manifest_trials = _manifest_trial_map(manifest)
    dimensions = manifest.get("scoring_dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise FeedbackImportError("manifest scoring_dimensions is missing")
    raw_trials = feedback.get("trials")
    if not isinstance(raw_trials, list) or len(raw_trials) != len(manifest_trials):
        raise FeedbackImportError("feedback must cover every package trial")
    canonical: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_trials:
        if not isinstance(raw, Mapping):
            raise FeedbackImportError("feedback trial is malformed")
        trial_id = _text(raw.get("trial_id"), "trial_id")
        if trial_id in seen or trial_id not in manifest_trials:
            raise FeedbackImportError(f"unknown or duplicate feedback trial: {trial_id}")
        seen.add(trial_id)
        source = manifest_trials[trial_id]
        if _text(raw.get("vehicle_id"), f"{trial_id}.vehicle_id") != _text(source.get("vehicle_id"), "manifest.vehicle_id"):
            raise FeedbackImportError(f"vehicle mismatch: {trial_id}")
        reference_audio = raw.get("reference_audio")
        candidate_audio = raw.get("candidate_audio")
        if not isinstance(reference_audio, Mapping) or not isinstance(candidate_audio, Mapping):
            raise FeedbackImportError(f"audio SHA fields missing: {trial_id}")
        if _sha(reference_audio.get("audition_sha256"), f"{trial_id}.reference_sha256") != _sha(source.get("reference_audition_sha256"), f"{trial_id}.manifest_reference_sha256"):
            raise FeedbackImportError(f"reference audition SHA mismatch: {trial_id}")
        if _sha(candidate_audio.get("audition_sha256"), f"{trial_id}.candidate_sha256") != _sha(source.get("candidate_audition_sha256"), f"{trial_id}.manifest_candidate_sha256"):
            raise FeedbackImportError(f"candidate audition SHA mismatch: {trial_id}")
        scores = raw.get("scores")
        if not isinstance(scores, Mapping):
            raise FeedbackImportError(f"scores missing: {trial_id}")
        canonical_scores = {str(dimension): _score(scores.get(dimension), f"{trial_id}.{dimension}") for dimension in dimensions}
        preference = _text(raw.get("preference"), f"{trial_id}.preference")
        if preference not in _PREFERENCES:
            raise FeedbackImportError(f"invalid preference: {trial_id}")
        comment = raw.get("comment")
        if comment is not None and not isinstance(comment, str):
            raise FeedbackImportError(f"comment must be text or null: {trial_id}")
        canonical.append({
            "trial_id": trial_id,
            "vehicle_id": _text(raw.get("vehicle_id"), f"{trial_id}.vehicle_id"),
            "file_id": _text(raw.get("file_id"), f"{trial_id}.file_id"),
            "scores": canonical_scores,
            "preference": preference,
            "comment": comment.strip() if isinstance(comment, str) and comment.strip() else None,
            "reference_audition_sha256": _sha(source.get("reference_audition_sha256"), "manifest reference"),
            "candidate_audition_sha256": _sha(source.get("candidate_audition_sha256"), "manifest candidate"),
        })
    if seen != set(manifest_trials):
        raise FeedbackImportError("feedback trial set does not match package")
    problems = classify_feedback_problems(canonical)
    return {
        "schema_version": "s12-stage-s-r2-r3-human-feedback-receipt-v1",
        "status": f"VALIDATED_{evidence_level}_HUMAN_FEEDBACK",
        "evidence_level": evidence_level,
        "package_manifest_sha256": package_receipt["manifest_sha256"],
        "feedback_sha256": _sha256(Path(feedback_path)),
        "test_id": manifest["test_id"],
        "listener_id": listener_id,
        "feedback_rows": len(canonical),
        "trials": canonical,
        "problem_categories": problems,
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "parameter_changes": 0,
        "profile_candidate_ready": False,
    }


def build_limited_parameter_recommendations(receipt: Mapping[str, Any]) -> dict[str, Any]:
    evidence_level = str(receipt.get("evidence_level") or "R3")
    recommendations: list[dict[str, Any]] = []
    for problem in receipt.get("problem_categories", []):
        if not isinstance(problem, Mapping):
            continue
        category = str(problem.get("category") or "")
        parameter_group = _PARAMETER_GROUPS.get(category, "manual_problem_review")
        recommendations.append({
            "category": category,
            "parameter_group": parameter_group,
            "direction": "REVIEW_ONLY_NO_NUMERIC_VALUE",
            "evidence_trial_ids": list(problem.get("trial_ids") or []),
            "signals": list(problem.get("signals") or []),
            "uncertainty": "R2/R3 feedback cannot establish RPM-synchronous target or a numeric parameter delta.",
            "allowed_scope": "R2_LIMITED_MANUAL_REVIEW" if evidence_level == "R2" else "R3_DIRECTIONAL_ONLY",
        })
    return {
        "schema_version": "s12-stage-s-r2-r3-limited-parameter-recommendations-v1",
        "status": "LIMITED_R2_R3_FEEDBACK_ONLY" if recommendations else "NO_PROBLEM_CATEGORIES",
        "evidence_level": evidence_level,
        "recommendations": recommendations,
        "parameter_changes": 0,
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "profile_candidate_ready": False,
    }


def _waiting_recommendations() -> dict[str, Any]:
    return {
        "schema_version": "s12-stage-s-r2-r3-limited-parameter-recommendations-v1",
        "status": "WITHHELD_NO_JOVI_FEEDBACK",
        "evidence_level": "R2_R3_ONLY",
        "recommendations": [],
        "parameter_changes": 0,
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "profile_candidate_ready": False,
    }


def _render_report(package_result: Mapping[str, Any], receipt: Mapping[str, Any] | None, recommendations: Mapping[str, Any]) -> str:
    if receipt is None:
        return "\n".join([
            "# S12 R2/R3 中文人耳反馈报告",
            "",
            "状态：`WAITING_FOR_JOVI_HUMAN_FEEDBACK`",
            "",
            f"A/B 包校验：`{package_result.get('status')}`；试次：`{package_result.get('trial_count')}`；试听片段：`{package_result.get('clip_count')}`。",
            "",
            "等待 Jovi 真实反馈 JSON；当前不生成评分、问题分类或参数建议，不修改声源，不启动 Stage S。",
            "",
            "R2/R3 边界：未来即使导入反馈，也只允许有限诊断建议，不开放 Order hard gate、自动阶次调参或 Profile Freeze。",
            "",
        ])
    lines = [
        "# S12 R2/R3 中文人耳反馈报告",
        "",
        f"状态：`{receipt.get('status')}`；证据等级：`{receipt.get('evidence_level')}`；听者：`{receipt.get('listener_id')}`。",
        "",
        "| 试次 | 车型 | 评分 | 偏好 | 问题分类 | 备注 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for trial in receipt.get("trials", []):
        categories = [item.get("category") for item in receipt.get("problem_categories", []) if trial.get("trial_id") in item.get("trial_ids", [])]
        lines.append(f"| `{trial.get('trial_id')}` | `{trial.get('vehicle_id')}` | `{json.dumps(trial.get('scores'), ensure_ascii=False, sort_keys=True)}` | {trial.get('preference')} | {'、'.join(categories) or '无'} | {trial.get('comment') or '—'} |")
    lines.extend([
        "",
        "## 有限建议",
        "",
        f"生成 `{len(recommendations.get('recommendations', []))}` 条参数组方向；`parameter_changes=0`，不写入声源、不授予自动调参或 Profile 权限。",
        "",
    ])
    return "\n".join(lines)


def write_feedback_outputs(package_root: Path, output_dir: Path, feedback_path: Path | None = None) -> dict[str, Path]:
    package_result = validate_anchor_ab_package(package_root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if feedback_path is None:
        receipt = None
        recommendations = _waiting_recommendations()
    else:
        receipt = validate_anchor_feedback(feedback_path, package_root)
        recommendations = build_limited_parameter_recommendations(receipt)
        (output_dir / "feedback_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report = output_dir / "S12_R2_Human_Feedback_Report.md"
    recommendation_path = output_dir / "parameter_recommendations.json"
    gate_path = output_dir / "feedback_gate.json"
    report.write_text(_render_report(package_result, receipt, recommendations), encoding="utf-8", newline="\n")
    recommendation_path.write_text(json.dumps(recommendations, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    gate_path.write_text(json.dumps({
        "schema_version": "s12-stage-s-r2-r3-feedback-gate-v1",
        "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK" if receipt is None else "FEEDBACK_VALIDATED_LIMITED_ONLY",
        "feedback_rows": 0 if receipt is None else receipt["feedback_rows"],
        "evidence_level": None if receipt is None else receipt["evidence_level"],
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "parameter_changes": 0,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"report": report, "recommendations": recommendation_path, "gate": gate_path, "receipt": output_dir / "feedback_receipt.json"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入 S12 anchor 中文 R2/R3 人耳反馈并生成有限诊断建议")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        paths = write_feedback_outputs(args.package_root, args.output_dir, args.feedback)
    except (AnchorABValidationError, FeedbackImportError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FeedbackImportError",
    "build_limited_parameter_recommendations",
    "classify_feedback_problems",
    "validate_anchor_feedback",
    "write_feedback_outputs",
    "main",
]
