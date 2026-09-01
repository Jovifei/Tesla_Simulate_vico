from __future__ import annotations

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.energy_budget import (
    ENERGY_LAYERS,
    build_energy_budget,
)


def test_energy_budget_contains_required_layers_and_gain_ratios() -> None:
    payload = build_energy_budget(duration_s=0.25, scenes=("hot_idle",))
    assert payload["schema"] == "s12.stage_aa.energy_budget_trace.v1"
    scene = payload["scenes"]["hot_idle"]
    assert tuple(scene["layers"]) == ENERGY_LAYERS
    for index, layer in enumerate(scene["layers"]):
        metrics = scene["layers"][layer]
        assert metrics["signal_kind"] in {"audio", "control_proxy"}
        assert metrics["rms_dbfs"] is not None
        assert metrics["bands"]
        assert metrics["spectral_centroid_hz"] is not None
        assert metrics["transient_energy"] >= 0
        if layer in {"vehicle_state", "combustion_event", "forced_induction", "central_collector", "pre_transients"}:
            assert metrics["gain_ratio_vs_previous"] is None
        else:
            assert metrics["gain_ratio_vs_previous"] is not None
