from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_g.reference_targets import (
    load_reference_state_target,
)


_REFERENCE_ROOT = Path(__file__).resolve().parents[1] / "reference_database"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_each_state_loads_its_own_stock_median_without_renormalising() -> None:
    path = _REFERENCE_ROOT / "hellcat_reference_targets.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    loaded = {
        state: load_reference_state_target(path, "hellcat", state, _sha256(path))
        for state in ("idle", "acceleration", "afterfire")
    }

    for state, target in loaded.items():
        assert target is not None
        assert target.state_id == state
        assert target.vehicle_id == "hellcat"
        assert target.band_shares == tuple(payload["stock_median"][f"{state}_band_shares"])
        assert target.spectral_centroid_hz == payload["stock_median"][f"{state}_spectral_centroid_hz"]
        assert target.source_sha256 == _sha256(path)

    assert loaded["idle"].band_shares != loaded["acceleration"].band_shares
    assert loaded["acceleration"].band_shares != loaded["afterfire"].band_shares
    # The target extractor divides by the entire spectrum.  In particular the
    # four audited bands are not required to sum to one.
    assert sum(loaded["afterfire"].band_shares) == pytest.approx(0.902293161342415)


def test_missing_state_is_not_filled_from_another_state(tmp_path: Path) -> None:
    path = tmp_path / "targets.json"
    path.write_text(
        json.dumps(
            {
                "vehicle": "hellcat",
                "provenance": "B/R2 relative features",
                "boundary": "uncalibrated; not OEM reproduction",
                "stock_median": {
                    "idle_band_shares": [0.4, 0.3, 0.2, 0.05],
                    "idle_spectral_centroid_hz": 280.0,
                },
            }
        ),
        encoding="utf-8",
    )

    assert load_reference_state_target(path, "hellcat", "acceleration", _sha256(path)) is None


def test_target_loader_fails_closed_on_identity_hash_or_invalid_shares(tmp_path: Path) -> None:
    path = tmp_path / "targets.json"
    path.write_text(
        json.dumps(
            {
                "vehicle": "hellcat",
                "stock_median": {
                    "idle_band_shares": [0.6, 0.4, 0.2, 0.1],
                    "idle_spectral_centroid_hz": 280.0,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="SHA-256"):
        load_reference_state_target(path, "hellcat", "idle", "0" * 64)
    with pytest.raises(ValueError, match="vehicle"):
        load_reference_state_target(path, "ferrari_458", "idle", _sha256(path))
    with pytest.raises(ValueError, match="state_id"):
        load_reference_state_target(path, "hellcat", "cruise", _sha256(path))
    with pytest.raises(ValueError, match="band shares"):
        load_reference_state_target(path, "hellcat", "idle", _sha256(path))
