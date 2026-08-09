# tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_deep_realism_separation_eval.py
"""S12 深度真实感：三锚点身份分离评估。

验证三锚点在共享 trace 下的 pairwise 谱距大于最小分离阈值，
确认分离评估 harness 可用（初始目标下不应崩溃且能产出报告）。
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

# 让 tests/ 能够 import acoustic_identity_v015 包（父目录的父目录）。
_V015 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_V015.parent))

from acoustic_identity_v015.render_identity_v02 import _scenario_trace  # noqa: E402
from acoustic_identity_v015.sources.flat_plane_v8_source import render_ferrari_458  # noqa: E402
from acoustic_identity_v015.sources.supercharged_hemi_source import render_hellcat  # noqa: E402
from acoustic_identity_v015.sources.rotary_turbo_source import render_rx7_fd  # noqa: E402
from acoustic_identity_v015.acoustic_analysis.spectral_targets import spectral_distance  # noqa: E402
from acoustic_identity_v015.acoustic_layers.afterfire_model import apply_afterfire  # noqa: E402
from acoustic_identity_v015.acoustic_layers.idle_dynamics import apply_idle_dynamics  # noqa: E402
from acoustic_identity_v015.acoustic_layers.low_frequency_body import apply_low_frequency_body  # noqa: E402

RENDERERS = {"ferrari_458": render_ferrari_458, "hellcat": render_hellcat, "rx7_fd": render_rx7_fd}
_MANIFEST = json.loads((_V015 / "reference_database" / "realism_reference_manifest.json").read_text(encoding="utf-8"))
_MIN_DIST = float(_MANIFEST["deep_realism_thresholds"]["identity_separation_min_distance"])


def _full_render(vid: str):
    """对每个车辆渲染一次，保留其 trace 供谱距比较复用。"""
    trace = _scenario_trace(vid, "full_pull", 3.0)
    src = RENDERERS[vid](trace)
    src = apply_idle_dynamics(src, vid, trace)
    src = apply_afterfire(src, vid, trace)
    return apply_low_frequency_body(src, vid, trace), trace


class SeparationEvalTests(unittest.TestCase):
    def test_three_anchors_are_pairwise_separated(self) -> None:
        # 每个车辆只渲染一次，保留各自的 render 与 trace。
        renders: dict[str, object] = {}
        traces: dict[str, object] = {}
        for vid in RENDERERS:
            render, trace = _full_render(vid)
            renders[vid] = render
            traces[vid] = trace
        for i, a in enumerate(RENDERERS):
            for b in list(RENDERERS)[i + 1:]:
                with self.subTest(a=a, b=b):
                    # 使用相同 trace（render_a 的 trace）比较以保证可比性。
                    trace_a = traces[a]
                    d = spectral_distance(renders[a], renders[b], trace_a)
                    self.assertGreater(d, _MIN_DIST)


if __name__ == "__main__":
    unittest.main(verbosity=2)
