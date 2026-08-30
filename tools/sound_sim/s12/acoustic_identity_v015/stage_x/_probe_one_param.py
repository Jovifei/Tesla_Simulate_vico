"""One-parameter reachability probe (not part of the shipped test surface)."""
from __future__ import annotations

import hashlib
import sys

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.search_parameters import (
    _pcm_metrics,
    _render_config_pcm,
    hellcat_search_parameters,
)


def main(name: str) -> int:
    item = next(parameter for parameter in hellcat_search_parameters() if parameter.name == name)
    base = load_config("hellcat_v1")
    traces = [build_hellcat_bakeoff_trace(scene, duration) for scene, duration in item.scenes]
    baseline_blocks = [block[{"raw": 0, "post_ptr": 1, "monitor": 2}[item.stem]] for block in _render_config_pcm(base, item.architecture, traces)]
    baseline_bytes = b"".join(block.tobytes() for block in baseline_blocks)
    baseline_metrics = _pcm_metrics(baseline_blocks)
    movement: dict[str, float] = {}
    sha_changed = False
    for sign in (-1.0, 1.0):
        config = __import__("copy").deepcopy(base)
        item.apply(config, item.baseline + sign * item.delta)
        blocks = [block[{"raw": 0, "post_ptr": 1, "monitor": 2}[item.stem]] for block in _render_config_pcm(config, item.architecture, traces)]
        if hashlib.sha256(b"".join(block.tobytes() for block in blocks)).hexdigest() != hashlib.sha256(baseline_bytes).hexdigest():
            sha_changed = True
        variant = _pcm_metrics(blocks)
        for metric, value in variant.items():
            base_value = baseline_metrics[metric]
            change = abs(value - base_value) / max(abs(base_value), 1e-9)
            movement[metric] = max(movement.get(metric, 0.0), change)
    target = max((movement.get(metric, 0.0) for metric in item.target_metrics), default=0.0)
    print(f"name={item.name} arch={item.architecture} scenes={item.scenes} stem={item.stem}")
    print(f"sha_changed={sha_changed} target_movement={target:.4f} targets={item.target_metrics}")
    print("movement", {k: round(v, 4) for k, v in sorted(movement.items(), key=lambda kv: -kv[1])[:12]})
    return 0 if sha_changed and target > 0.02 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "primary_attenuation_spread"))
