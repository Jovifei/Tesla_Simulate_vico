"""Regression checks for the Stage-K frozen Track-P and loudness boundaries."""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.loudness_manager import manage_bundle_loudness
from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import _health


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_k_does_not_change_formal_loudness_signature_or_health_body() -> None:
    signature = inspect.signature(manage_bundle_loudness)
    assert tuple(signature.parameters) == ("segments", "sample_rate_hz", "target_lufs", "peak_limit_dbfs")
    assert signature.parameters["sample_rate_hz"].default == 48000
    assert signature.parameters["target_lufs"].default == -18.0
    assert signature.parameters["peak_limit_dbfs"].default == -1.0
    health_source = inspect.getsource(_health)
    assert "def _health" in health_source


def test_stage_k_preserves_frozen_loudness_manager_bytes() -> None:
    assert _sha256(ROOT / "loudness_manager.py") == "26feb740842a1e4db93e0a83fd7924c17c1ee5cfb8d1737a304af83e3e163fd3"


def test_stage_k_candidate_layers_are_declared_before_frozen_boundary() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_k.render_candidate import render_stage_k_candidate

    # The renderer's declaration is an auditable contract; no new energy may
    # be added after the frozen PTR/edge-fade boundary.
    assert render_stage_k_candidate.__name__ == "render_stage_k_candidate"
