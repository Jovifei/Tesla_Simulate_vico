"""Governed impulse-response asset loading for Stage AE.

No third-party IR bytes are committed here. A manifest must declare provenance,
SHA-256 and an explicit use policy. Public/downloadable does not imply product use.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

_PRODUCT_RIGHTS = {"PROJECT_OWNED", "VERIFIED_REDISTRIBUTABLE"}
_DIAGNOSTIC_RIGHTS = _PRODUCT_RIGHTS | {"RESEARCH_DIAGNOSTIC_ONLY", "R3_PRIVATE_DIAGNOSTIC_ONLY"}


@dataclass(frozen=True)
class IrAssetSpec:
    asset_id: str
    path: Path
    sha256: str
    source_url: str
    rights_status: str
    intended_use: str
    attribution: str
    gain_db: float = 0.0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any], base_dir: Path) -> "IrAssetSpec":
        required = {"asset_id", "path", "sha256", "source_url", "rights_status", "intended_use", "attribution"}
        missing = required - set(payload)
        if missing:
            raise ValueError(f"IR manifest missing fields: {sorted(missing)}")
        raw_path = Path(str(payload["path"]))
        path = raw_path if raw_path.is_absolute() else base_dir / raw_path
        return cls(
            asset_id=str(payload["asset_id"]),
            path=path,
            sha256=str(payload["sha256"]).lower(),
            source_url=str(payload["source_url"]),
            rights_status=str(payload["rights_status"]),
            intended_use=str(payload["intended_use"]),
            attribution=str(payload["attribution"]),
            gain_db=float(payload.get("gain_db", 0.0)),
        )


def load_ir_manifest(path: str | Path) -> IrAssetSpec:
    manifest = Path(path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return IrAssetSpec.from_mapping(payload, manifest.parent)


def _pcm_to_float(data: np.ndarray) -> np.ndarray:
    if np.issubdtype(data.dtype, np.floating):
        result = data.astype(np.float64)
    elif np.issubdtype(data.dtype, np.signedinteger):
        info = np.iinfo(data.dtype)
        scale = float(max(abs(info.min), info.max))
        result = data.astype(np.float64) / scale
    elif np.issubdtype(data.dtype, np.unsignedinteger):
        info = np.iinfo(data.dtype)
        midpoint = (info.max + 1) / 2.0
        result = (data.astype(np.float64) - midpoint) / midpoint
    else:
        raise ValueError(f"unsupported IR WAV dtype: {data.dtype}")
    return result


def load_ir_asset(spec: IrAssetSpec, target_sample_rate_hz: int = 48000, use: str = "diagnostic") -> np.ndarray:
    allowed = _PRODUCT_RIGHTS if use == "product" else _DIAGNOSTIC_RIGHTS
    if spec.rights_status not in allowed:
        raise PermissionError(f"IR asset {spec.asset_id} not authorized for {use}: {spec.rights_status}")
    if not spec.path.is_file():
        raise FileNotFoundError(spec.path)
    digest = hashlib.sha256(spec.path.read_bytes()).hexdigest()
    if digest != spec.sha256:
        raise ValueError(f"IR SHA mismatch for {spec.asset_id}")
    sample_rate, raw = wavfile.read(spec.path)
    data = _pcm_to_float(np.asarray(raw))
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    if int(sample_rate) != int(target_sample_rate_hz):
        from math import gcd
        factor = gcd(int(sample_rate), int(target_sample_rate_hz))
        data = resample_poly(data, int(target_sample_rate_hz) // factor, int(sample_rate) // factor)
    data *= 10.0 ** (spec.gain_db / 20.0)
    if data.size == 0 or not np.all(np.isfinite(data)):
        raise ValueError("IR asset decoded to empty/non-finite data")
    return data
