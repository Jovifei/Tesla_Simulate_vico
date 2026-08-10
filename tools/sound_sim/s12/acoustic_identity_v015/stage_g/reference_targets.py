"""State-specific B/R2 reference targets for Stage G qualification.

The four audited bands remain fractions of the *entire* measured spectrum.
They are therefore validated, but never renormalised to sum to one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


REFERENCE_STATE_IDS = ("idle", "acceleration", "afterfire")


@dataclass(frozen=True)
class ReferenceStateTarget:
    vehicle_id: str
    state_id: str
    band_shares: tuple[float, float, float, float]
    spectral_centroid_hz: float
    provenance: Mapping[str, object]
    source_sha256: str


def load_reference_state_target(
    path: str | Path,
    vehicle_id: str,
    state_id: str,
    expected_sha256: str,
) -> ReferenceStateTarget | None:
    """Load one exact state target, returning ``None`` when it is unavailable.

    Missing state data is deliberately not filled from another state.  File
    identity and vehicle identity are checked before any metric is accepted.
    """
    target_path = Path(path)
    digest = hashlib.sha256(target_path.read_bytes()).hexdigest()
    if digest != str(expected_sha256).lower():
        raise ValueError(
            f"reference target SHA-256 mismatch: expected {expected_sha256}, got {digest}"
        )
    if state_id not in REFERENCE_STATE_IDS:
        raise ValueError(f"unsupported reference state_id: {state_id!r}")

    payload = json.loads(target_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("reference target root must be an object")
    if payload.get("vehicle") != vehicle_id:
        raise ValueError(
            f"reference target vehicle mismatch: expected {vehicle_id!r}, "
            f"got {payload.get('vehicle')!r}"
        )
    stock_median = payload.get("stock_median")
    if not isinstance(stock_median, Mapping):
        return None

    shares_value = stock_median.get(f"{state_id}_band_shares")
    centroid_value = stock_median.get(f"{state_id}_spectral_centroid_hz")
    if shares_value is None and centroid_value is None:
        return None
    if not isinstance(shares_value, (list, tuple)) or len(shares_value) != 4:
        raise ValueError(f"{state_id} band shares must contain four values")
    try:
        shares = tuple(float(value) for value in shares_value)
        centroid = float(centroid_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{state_id} target metrics must be numeric") from exc
    if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in shares):
        raise ValueError(f"{state_id} band shares must be finite values in [0, 1]")
    total = math.fsum(shares)
    if not 0.0 < total <= 1.000001:
        raise ValueError(
            f"{state_id} band shares must retain the full-spectrum denominator; "
            f"sum must be in (0, 1.000001], got {total}"
        )
    if not math.isfinite(centroid) or centroid < 0.0:
        raise ValueError(f"{state_id} spectral centroid must be finite and non-negative")

    provenance = {
        "level": "B/R2 relative features",
        "recording_note": payload.get("provenance", ""),
        "boundary": payload.get("boundary", "uncalibrated; not OEM reproduction"),
        "schema": payload.get("schema", ""),
        "source_file": target_path.name,
    }
    return ReferenceStateTarget(
        vehicle_id=vehicle_id,
        state_id=state_id,
        band_shares=shares,  # type: ignore[arg-type]
        spectral_centroid_hz=centroid,
        provenance=provenance,
        source_sha256=digest,
    )
