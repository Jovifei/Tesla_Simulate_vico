"""Thin AH adapter over the ORIGINAL rich AG/AF-R package builder.

Identity mode still names the unchanged AG-R1 identity layer. The new, separate
source_remediation field names the intervention. No blind-mode aliasing, new UI,
server, fitted profile, downloaded Reference, or old-package overwrite.
The legacy builder has module-global factory injection; serialize and restore it
in finally, including failure paths. Do not call other builders concurrently.
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import threading
from pathlib import Path

from ..stage_af.package_integrity import (
    REPOSITORY_ROOT, seal_contract, seal_payload, sha256_file,
)
from ..stage_ag import build_identity_dashboards as ag
from ..stage_ag.build_identity_dashboards_r1 import _extend_source_receipt
from ..stage_ag.vehicle_identity_r1 import IDENTITY_MODE_V1R1, vehicle_identity_r1_signature
from .engine import RemediationEngine
from .output_guard import (
    LEGACY_CLIP_V1,
    LINKED_SOFT_CEILING_V1,
    OUTPUT_GUARD_RECEIPT_SCHEMA,
)
from .source_policy import OUTPUT_POLICIES, VARIANTS, signature

_LOCK = threading.RLock()


def _add_manifest_metadata(package: Path, metadata: dict) -> None:
    if not metadata:
        return
    path = package / "audition_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(copy.deepcopy(metadata))
    sealed = seal_payload(manifest, manifest["schema"])
    path.write_text(json.dumps(sealed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_fingerprint():
    paths = [*Path(__file__).parent.glob("*.py"),
             Path(__file__).parents[1] / "stage_ag" / "vehicle_identity.py",
             Path(__file__).parents[1] / "stage_ag" / "vehicle_identity_r1.py"]
    return [{"path": p.relative_to(REPOSITORY_ROOT).as_posix(), "sha256": sha256_file(p)}
            for p in sorted(paths)]


def build_package(args: argparse.Namespace, variant: str, render_records: list,
                  output_policy: str | None = None) -> Path:
    output_policy = output_policy or getattr(args, "output_policy", LEGACY_CLIP_V1)
    if variant not in VARIANTS or args.identity_mode != IDENTITY_MODE_V1R1:
        raise ValueError("AH package requires AG-R1 and a supported source variant")
    if output_policy not in OUTPUT_POLICIES:
        raise ValueError(f"unsupported AH output policy: {output_policy}")
    with _LOCK:
        directory = Path(__file__).parents[1] / "stage_ad"
        # Compatibility with the unchanged legacy absolute-import entry point.
        sys.path.insert(0, str(directory))
        try:
            from ..stage_ad import build_unified_dashboards as dashboards
        finally:
            sys.path.pop(0)
        names = ("IDENTITY_MODE_V1", "IDENTITY_MODES", "VehicleIdentityEngine",
                 "vehicle_identity_signature", "identity_runtime_fingerprint",
                 "stage_ag_source_receipt", "_contract", "dependency_fingerprint",
                 "publish_staged_package")
        saved = {key: getattr(ag, key) for key in names}
        old_configs = dashboards.VEHICLE_CONFIGS

        class Factory(RemediationEngine):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw, variant=variant, output_policy=output_policy)
                self.index = 0

            def render_track(self, *a, **kw):
                pcm = super().render_track(*a, **kw)
                scenes = old_configs[self.vehicle_type]["scenes"]
                if self.index >= len(scenes):
                    raise RuntimeError("unexpected extra render in dashboard builder")
                report = dict(self.last_report)
                report["scene"] = scenes[self.index]["id"]
                self.index += 1
                render_records.append(report)
                return pcm

        def full_signature(vehicle):
            payload = vehicle_identity_r1_signature(vehicle)
            payload["source_remediation"] = signature(vehicle, variant, output_policy)
            payload["source_variant"] = variant
            payload["output_policy"] = output_policy
            return payload

        def dependency_fingerprint():
            result = saved["dependency_fingerprint"]()
            if output_policy == LINKED_SOFT_CEILING_V1:
                extra = [
                    {"path": path.relative_to(REPOSITORY_ROOT).as_posix(),
                     "sha256": sha256_file(path)}
                    for path in [Path(__file__).with_name(name) for name in
                                 ("engine.py", "source_policy.py", "output_guard.py")]
                ]
                result["audio_runtime_fingerprint"] = sorted(
                    [*result["audio_runtime_fingerprint"], *extra],
                    key=lambda item: item["path"],
                )
            return result

        def publish_staged_package(staging_root, published_root):
            _add_manifest_metadata(staging_root, getattr(args, "package_metadata", {}))
            return saved["publish_staged_package"](staging_root, published_root)

        def receipt(*, allow_dirty_dev=False):
            result = _extend_source_receipt(saved["stage_ag_source_receipt"],
                                             allow_dirty_dev=allow_dirty_dev)
            paths = [entry["path"] for entry in source_fingerprint()]
            dirty = subprocess.check_output(["git", "status", "--porcelain",
                                            "--untracked-files=all", "--", *paths],
                                           cwd=REPOSITORY_ROOT, text=True)
            if dirty.strip():
                # AH does not publish a new experiment from uncommitted code.
                raise ValueError("AH source dependencies are dirty/untracked")
            return result

        def contract(**kw):
            result = saved["_contract"](**kw)
            result["experiment_stage"] = "AH"
            result["source_variant"] = variant
            result["source_remediation_variant"] = variant
            result["output_policy"] = output_policy
            result["output_policy_config"] = {
                "policy_id": output_policy,
                "knee_linear": .90 if output_policy == LINKED_SOFT_CEILING_V1 else None,
                "ceiling_linear": .94,
                "stereo_link": (
                    "instantaneous_frame_peak_common_gain"
                    if output_policy == LINKED_SOFT_CEILING_V1 else "legacy_renderer_path"
                ),
                "parent_denominator_policy": "fixed_parent_peak",
            }
            result["output_guard_receipt_schema"] = (
                OUTPUT_GUARD_RECEIPT_SCHEMA
                if output_policy == LINKED_SOFT_CEILING_V1 else "s12.stage_ah.output_guard_receipt.v1"
            )
            result["source_remediation"] = signature(kw["vehicle"], variant, output_policy)
            return seal_contract(result)

        ag.IDENTITY_MODE_V1 = IDENTITY_MODE_V1R1
        ag.IDENTITY_MODES = frozenset({IDENTITY_MODE_V1R1})
        ag.VehicleIdentityEngine = Factory
        ag.vehicle_identity_signature = full_signature
        ag.identity_runtime_fingerprint = source_fingerprint
        ag.stage_ag_source_receipt = receipt
        ag._contract = contract
        ag.dependency_fingerprint = dependency_fingerprint
        ag.publish_staged_package = publish_staged_package
        dashboards.VEHICLE_CONFIGS = copy.deepcopy(old_configs)
        c1 = bool(getattr(args, "c1_experiment", False))
        group_label = str(getattr(args, "group_label", variant))
        for cfg in dashboards.VEHICLE_CONFIGS.values():
            prefix = (f"[AH-C1 · {group_label} · {output_policy}] "
                      if c1 else f"[AH · {variant}] ")
            cfg["title"] = prefix + cfg["title"]
            cfg["subtitle"] = (f"AG-R1 底模 / {group_label if c1 else 'AH ' + variant} / "
                               f"output_policy={output_policy} / 原始真车参考 / "
                               "诊断候选，未经人耳验收 · " + cfg["subtitle"])
        try:
            return ag.build_identity_package(args)
        finally:
            dashboards.VEHICLE_CONFIGS = old_configs
            for key, value in saved.items():
                setattr(ag, key, value)
