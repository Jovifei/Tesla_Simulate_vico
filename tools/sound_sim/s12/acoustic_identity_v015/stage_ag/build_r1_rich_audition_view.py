"""Build a view-only rich Stage AG-R1 audition workbench from an immutable package.

This module intentionally NEVER renders audio.  It verifies the exact Stage-AG
package manifest and every candidate/reference SHA, copies the existing bytes,
and rebuilds only the HTML using the established Stage-AD rich audition template.

The output is VIEW_ONLY / NOT_EVIDENCE_PACKAGE.  The immutable source package
remains the evidence authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..stage_af.package_integrity import canonical_json_bytes, sha256_file

PACKAGE_SCHEMA = "s12.stage_ag.package_manifest.v1"
VIEW_SCHEMA = "s12.stage_ag.r1_rich_view.v1"
VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")
RICH_REQUIRED_MARKERS = (
    "声音仿真人耳试听",
    "实时动态声学分析仪",
    "主观逼真度打分",
    "导出试听评审记录 JSON",
    "GLOBAL 4-VEHICLE SELECTION SWITCHER",
)
FORBIDDEN_SIMPLE_MARKERS = (
    "package-wide gain",
    "canonical S12 renderer",
    "Stage AE · canonical",
)


def _manifest_self_hash(payload: Mapping[str, Any]) -> str:
    canonical = dict(payload)
    canonical.pop("manifest_sha256", None)
    return hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()


def _load_manifest(
    package_root: Path,
    *,
    expected_manifest_sha256: str,
    expected_identity_mode: str,
) -> dict[str, Any]:
    manifest_path = package_root / "audition_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    actual_file_sha = sha256_file(manifest_path)
    if actual_file_sha.lower() != expected_manifest_sha256.lower():
        raise ValueError(
            "source package manifest file SHA mismatch: "
            f"expected={expected_manifest_sha256} actual={actual_file_sha}"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema") != PACKAGE_SCHEMA:
        raise ValueError("source package is not a Stage AG immutable package")
    if payload.get("identity_mode") != expected_identity_mode:
        raise ValueError(
            "source package identity mode mismatch: "
            f"expected={expected_identity_mode} actual={payload.get('identity_mode')}"
        )
    recorded = str(payload.get("manifest_sha256", ""))
    calculated = _manifest_self_hash(payload)
    if not recorded or recorded != calculated:
        raise ValueError("source package manifest self-hash mismatch")
    by_vehicle = {row.get("vehicle"): row for row in payload.get("vehicles", [])}
    if set(by_vehicle) != set(VEHICLES):
        raise ValueError("source package must contain exactly the four governed vehicles")
    return payload


def _verify_audio_bytes(package_root: Path, manifest: Mapping[str, Any]) -> None:
    for entry in manifest.get("vehicles", []):
        vehicle_root = package_root / str(entry["directory"]) / "web_audio"
        for filename, expected in entry.get("candidate_pcm_sha256", {}).items():
            path = vehicle_root / str(filename)
            actual = sha256_file(path)
            if actual != str(expected):
                raise ValueError(f"candidate PCM SHA mismatch: {entry['vehicle']}/{filename}")
        for filename, expected in entry.get("reference_sha256", {}).items():
            path = vehicle_root / str(filename)
            actual = sha256_file(path)
            if actual != str(expected):
                raise ValueError(f"Reference SHA mismatch: {entry['vehicle']}/{filename}")


def _copy_audio_exact(
    source_package: Path,
    view_root: Path,
    manifest: Mapping[str, Any],
) -> None:
    for entry in manifest.get("vehicles", []):
        source_vehicle = source_package / str(entry["directory"])
        target_vehicle = view_root / str(entry["directory"])
        target_web = target_vehicle / "web_audio"
        target_web.mkdir(parents=True, exist_ok=False)

        filenames = set(entry.get("candidate_pcm_sha256", {})) | set(
            entry.get("reference_sha256", {})
        )
        for filename in sorted(filenames):
            source = source_vehicle / "web_audio" / str(filename)
            target = target_web / str(filename)
            shutil.copyfile(source, target)
            if sha256_file(source) != sha256_file(target):
                raise RuntimeError(f"audio copy changed bytes: {entry['vehicle']}/{filename}")

        for receipt_name in ("dashboard_contract.json", "stage_ag_binding.json"):
            source_receipt = source_vehicle / receipt_name
            if source_receipt.is_file():
                shutil.copyfile(source_receipt, target_vehicle / f"source_{receipt_name}")


def _rich_label(identity_mode: str) -> str:
    return (
        "Stage AG-R1 · Vehicle Identity v1r1"
        if identity_mode == "vehicle_identity_v1r1"
        else "Stage AG-R1 · Legacy Anchor"
    )


def _patch_rich_html(
    path: Path,
    *,
    package_id: str,
    identity_mode: str,
    source_manifest_sha256: str,
    source_git_head: str | None,
) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace("Stage AF-R (diagnostic)", _rich_label(identity_mode))
    text = text.replace("Stage AF-R 当前包参数台账", "Stage AG-R1 当前包参数台账")
    text = text.replace("声学闭环校准与真车A/B对比评审控制台", "Stage AG-R1 · Candidate / Reference A/B 试听控制台")
    text = text.replace("B: 真车参考实录 (R3)", "B: Reference (R3 / AUDITION_ONLY)")
    text = text.replace("真车实录:", "Reference:")
    text = text.replace("真车原声 (B)", "Reference (B)")

    receipt_banner = f'''\n  <div data-s12-rich-view-receipt="1" class="bg-cyan-950/40 border-b border-cyan-800/60 px-4 py-2 text-[11px] font-mono text-cyan-200">\n    VIEW_ONLY RICH WORKBENCH · source package: {package_id} · identity: {identity_mode} · manifest: {source_manifest_sha256} · source git: {source_git_head or 'UNKNOWN'}\n  </div>\n'''
    if "<main " not in text:
        raise ValueError("rich template main marker missing")
    text = text.replace("  <main ", receipt_banner + "\n  <main ", 1)
    path.write_text(text, encoding="utf-8")


def validate_rich_page(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in RICH_REQUIRED_MARKERS if marker not in text]
    forbidden = [marker for marker in FORBIDDEN_SIMPLE_MARKERS if marker in text]
    if missing:
        raise ValueError(f"rich workbench markers missing from {path}: {missing}")
    if forbidden:
        raise ValueError(f"old/simple dashboard markers found in {path}: {forbidden}")
    if 'data-s12-rich-view-receipt="1"' not in text:
        raise ValueError(f"rich view receipt banner missing from {path}")


def build_rich_view(
    source_package: Path,
    view_root: Path,
    *,
    expected_manifest_sha256: str,
    expected_identity_mode: str,
    port_base: int,
) -> Path:
    source_package = source_package.resolve()
    view_root = view_root.resolve()
    if view_root.exists():
        raise FileExistsError(view_root)
    if not 1024 <= int(port_base) <= 65532:
        raise ValueError("port_base must leave room for four vehicle ports")

    manifest = _load_manifest(
        source_package,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_identity_mode=expected_identity_mode,
    )
    _verify_audio_bytes(source_package, manifest)
    view_root.mkdir(parents=True, exist_ok=False)
    try:
        _copy_audio_exact(source_package, view_root, manifest)

        stage_ad_dir = Path(__file__).resolve().parents[1] / "stage_ad"
        sys.path.insert(0, str(stage_ad_dir))
        try:
            from ..stage_ad import build_unified_dashboards as dashboards
        finally:
            if sys.path and sys.path[0] == str(stage_ad_dir):
                sys.path.pop(0)

        previous_template = dashboards.TEMPLATE_PATH
        dashboards.TEMPLATE_PATH = stage_ad_dir / "audition_dashboard_template.html"
        nav_ports = {vehicle: int(port_base) + index for index, vehicle in enumerate(VEHICLES)}
        source_entries = {row["vehicle"]: row for row in manifest["vehicles"]}
        try:
            for vehicle in VEHICLES:
                entry = source_entries[vehicle]
                cfg = copy.deepcopy(dashboards.VEHICLE_CONFIGS[vehicle])
                cfg["dir"] = view_root / str(entry["directory"])
                contract_path = source_package / str(entry["directory"]) / "dashboard_contract.json"
                if not contract_path.is_file():
                    raise FileNotFoundError(contract_path)
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                if contract.get("identity_mode") != expected_identity_mode:
                    raise ValueError(f"dashboard contract identity mode mismatch: {vehicle}")
                cfg["_dashboard_contract"] = contract
                cfg["_dashboard_params"] = contract.get("parameters", [])
                cfg["_nav_ports"] = nav_ports
                cfg["_nav_vehicles"] = VEHICLES
                dashboards.build_dashboard(vehicle, cfg)

                source_git = (manifest.get("source_receipt") or {}).get("git_head")
                for html_name in ("index.html", "index_standalone.html"):
                    html_path = cfg["dir"] / html_name
                    _patch_rich_html(
                        html_path,
                        package_id=str(manifest.get("package_id", "UNKNOWN")),
                        identity_mode=expected_identity_mode,
                        source_manifest_sha256=expected_manifest_sha256,
                        source_git_head=source_git,
                    )
                    validate_rich_page(html_path)
        finally:
            dashboards.TEMPLATE_PATH = previous_template

        # Prove the view still contains the exact source audio bytes.
        view_manifest = copy.deepcopy(manifest)
        _verify_audio_bytes(view_root, view_manifest)
        receipt = {
            "schema": VIEW_SCHEMA,
            "status": "VIEW_ONLY / NOT_EVIDENCE_PACKAGE",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_package": str(source_package),
            "source_package_id": manifest.get("package_id"),
            "source_identity_mode": expected_identity_mode,
            "source_manifest_file_sha256": expected_manifest_sha256,
            "source_manifest_self_sha256": manifest.get("manifest_sha256"),
            "source_git_head": (manifest.get("source_receipt") or {}).get("git_head"),
            "port_base": int(port_base),
            "audio_policy": "EXACT_BYTE_COPY_NO_RENDER_NO_NORMALIZATION",
            "ui_policy": "STAGE_AD_RICH_WORKBENCH_REBUILT_FOR_STAGE_AG_R1",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "vehicles": [
                {
                    "vehicle": vehicle,
                    "directory": source_entries[vehicle]["directory"],
                    "url": f"http://localhost:{nav_ports[vehicle]}/",
                }
                for vehicle in VEHICLES
            ],
        }
        receipt_path = view_root / "rich_view_receipt.json"
        receipt_path.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        shutil.copyfile(source_package / "audition_manifest.json", view_root / "source_audition_manifest.json")
        return receipt_path
    except Exception:
        if view_root.exists():
            shutil.rmtree(view_root)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild screenshot-1-style rich workbench from exact immutable Stage AG-R1 audio"
    )
    parser.add_argument("--source-package", required=True, type=Path)
    parser.add_argument("--view-root", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument(
        "--expected-identity-mode",
        required=True,
        choices=("legacy", "vehicle_identity_v1r1"),
    )
    parser.add_argument("--port-base", required=True, type=int)
    args = parser.parse_args(argv)
    result = build_rich_view(
        args.source_package,
        args.view_root,
        expected_manifest_sha256=args.expected_manifest_sha256,
        expected_identity_mode=args.expected_identity_mode,
        port_base=args.port_base,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
