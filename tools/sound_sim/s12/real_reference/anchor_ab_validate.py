"""Validate the external Chinese anchor A/B package without importing raw media."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


class AnchorABValidationError(ValueError):
    """Raised when an anchor A/B package is incomplete or tampered with."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnchorABValidationError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise AnchorABValidationError(f"{label} must be a JSON object: {path}")
    return value


def _inside(root: Path, candidate: Path, label: str) -> Path:
    root = root.resolve()
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise AnchorABValidationError(f"{label} escapes A/B package root: {candidate}") from exc
    return resolved


def _package_path(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise AnchorABValidationError(f"missing {label}")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return _inside(root, candidate, label)


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnchorABValidationError(f"missing {label}")
    return value.strip()


def _lower_sha(value: object, label: str) -> str:
    text = _required_text(value, label).lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise AnchorABValidationError(f"invalid SHA-256 in {label}")
    return text


def _validate_page(page: Path, manifest_sha: str, trial_ids: list[str]) -> dict[str, Any]:
    if not page.is_file():
        raise AnchorABValidationError("index.html is missing")
    text = page.read_text(encoding="utf-8")
    required = {
        "manifest_sha": manifest_sha,
        "feedback_schema": "s12-stage-s-human-feedback-zh.v1",
        "export_button": "生成并下载反馈 JSON",
    }
    missing = [label for label, token in required.items() if token not in text]
    missing_trials = [trial_id for trial_id in trial_ids if trial_id not in text]
    if missing or missing_trials:
        detail = []
        if missing:
            detail.append("missing=" + ",".join(missing))
        if missing_trials:
            detail.append("trial_ids=" + ",".join(missing_trials))
        raise AnchorABValidationError("index.html content check failed: " + "; ".join(detail))
    return {
        "status": "PASS",
        "sha256": _sha256(page),
        "required_tokens": list(required),
        "trial_ids_embedded": len(trial_ids),
    }


def validate_anchor_ab_package(package_root: Path) -> dict[str, Any]:
    """Validate manifest, page, receipt and all 18 audition clip hashes."""

    root = Path(package_root).resolve()
    if not root.is_dir():
        raise AnchorABValidationError(f"A/B package directory does not exist: {root}")
    manifest_path = root / "anchor_ab_zh_manifest.json"
    receipt_path = root / "anchor_ab_zh_receipt.json"
    readme_path = root / "README_中文.md"
    manifest = _json(manifest_path, "anchor_ab_zh_manifest.json")
    receipt = _json(receipt_path, "anchor_ab_zh_receipt.json")
    if manifest.get("schema_version") != "s12-stage-s-anchor-ab-zh.v1":
        raise AnchorABValidationError("unexpected anchor A/B manifest schema")
    if manifest.get("language") != "zh-CN":
        raise AnchorABValidationError("anchor A/B package is not zh-CN")
    policy = manifest.get("package_policy")
    if not isinstance(policy, Mapping):
        raise AnchorABValidationError("anchor A/B package_policy is missing")
    if policy.get("automatic_tuning_eligible") is not False:
        raise AnchorABValidationError("anchor A/B package grants automatic tuning")
    if policy.get("profile_update") != "FORBIDDEN":
        raise AnchorABValidationError("anchor A/B package grants profile update")
    raw_trials = manifest.get("trials")
    if not isinstance(raw_trials, list) or len(raw_trials) != 9:
        raise AnchorABValidationError("anchor A/B manifest must contain exactly 9 trials")
    trial_ids: list[str] = []
    vehicle_counts: Counter[str] = Counter()
    clip_hashes: dict[str, str] = {}
    clip_paths: set[Path] = set()
    for trial in raw_trials:
        if not isinstance(trial, Mapping):
            raise AnchorABValidationError("anchor A/B trial is malformed")
        trial_id = _required_text(trial.get("trial_id"), "trial_id")
        if trial_id in trial_ids:
            raise AnchorABValidationError(f"duplicate trial: {trial_id}")
        vehicle_id = _required_text(trial.get("vehicle_id"), f"{trial_id}.vehicle_id")
        if vehicle_id not in {"ferrari_458", "hellcat", "rx7_fd"}:
            raise AnchorABValidationError(f"unsupported anchor vehicle: {vehicle_id}")
        trial_ids.append(trial_id)
        vehicle_counts[vehicle_id] += 1
        for side, sha_key in (("reference_audition_path", "reference_audition_sha256"), ("candidate_audition_path", "candidate_audition_sha256")):
            path = _package_path(root, trial.get(side), f"{trial_id}.{side}")
            if path in clip_paths:
                raise AnchorABValidationError(f"duplicate audition clip path: {path}")
            clip_paths.add(path)
            if path.suffix.lower() not in {".wav", ".flac"}:
                raise AnchorABValidationError(f"audition clip must be WAV/FLAC: {path}")
            if not path.is_file():
                raise AnchorABValidationError(f"audition clip is missing: {path}")
            declared = _lower_sha(trial.get(sha_key), f"{trial_id}.{sha_key}")
            actual = _sha256(path)
            if actual != declared:
                raise AnchorABValidationError(f"SHA-256 mismatch for {trial_id}.{side}: {actual} != {declared}")
            clip_hashes[f"{trial_id}:{side}"] = actual
    if vehicle_counts != Counter({"ferrari_458": 3, "hellcat": 3, "rx7_fd": 3}):
        raise AnchorABValidationError(f"anchor vehicle trial counts are wrong: {dict(vehicle_counts)}")
    manifest_sha = _sha256(manifest_path)
    receipt_manifest_sha = _lower_sha(receipt.get("manifest_sha256"), "receipt.manifest_sha256")
    if receipt_manifest_sha != manifest_sha:
        raise AnchorABValidationError("receipt manifest SHA-256 does not match manifest")
    if not readme_path.is_file():
        raise AnchorABValidationError("README_中文.md is missing")
    readme_sha = _sha256(readme_path)
    if _lower_sha(receipt.get("readme_sha256"), "receipt.readme_sha256") != readme_sha:
        raise AnchorABValidationError("receipt README SHA-256 does not match README_中文.md")
    receipt_trials = receipt.get("trials")
    if not isinstance(receipt_trials, list) or len(receipt_trials) != len(raw_trials):
        raise AnchorABValidationError("receipt trial count does not match manifest")
    receipt_by_id = {str(item.get("trial_id")): item for item in receipt_trials if isinstance(item, Mapping)}
    if set(receipt_by_id) != set(trial_ids):
        raise AnchorABValidationError("receipt trial IDs do not match manifest")
    for trial_id in trial_ids:
        receipt_trial = receipt_by_id[trial_id]
        manifest_trial = next(item for item in raw_trials if item.get("trial_id") == trial_id)
        for key in ("reference_audition_sha256", "candidate_audition_sha256"):
            if _lower_sha(receipt_trial.get(key), f"receipt.{trial_id}.{key}") != _lower_sha(manifest_trial.get(key), f"manifest.{trial_id}.{key}"):
                raise AnchorABValidationError(f"receipt SHA mismatch: {trial_id}.{key}")
    page_checks = _validate_page(root / "index.html", manifest_sha, trial_ids)
    return {
        "schema_version": "s12-stage-s-anchor-ab-validation.v1",
        "status": "VALIDATION_PASS",
        "package_root": str(root),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "receipt_path": str(receipt_path),
        "receipt_sha256": _sha256(receipt_path),
        "readme_sha256": readme_sha,
        "trial_count": len(raw_trials),
        "clip_count": len(clip_paths),
        "vehicle_counts": dict(sorted(vehicle_counts.items())),
        "package_status": manifest.get("package_status"),
        "evidence_level": manifest.get("evidence_level"),
        "page_checks": page_checks,
        "sha_checks": {"checked": len(clip_hashes) + 2, "failed": [], "clips": clip_hashes},
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "feedback_status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 S12 中文 anchor A/B 包的 manifest、页面和 18 个试听片段 SHA")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = validate_anchor_ab_package(args.package_root)
    except AnchorABValidationError as exc:
        result = {
            "schema_version": "s12-stage-s-anchor-ab-validation.v1",
            "status": "VALIDATION_FAILED",
            "package_root": str(Path(args.package_root).resolve()),
            "errors": [str(exc)],
        }
        exit_code = 2
    else:
        exit_code = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["AnchorABValidationError", "validate_anchor_ab_package", "main"]
