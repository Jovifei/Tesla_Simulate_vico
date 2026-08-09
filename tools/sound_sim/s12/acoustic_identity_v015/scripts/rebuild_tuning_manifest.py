# tools/sound_sim/s12/acoustic_identity_v015/scripts/rebuild_tuning_manifest.py
"""重建 `targets/deep_realism_tuning_manifest.json` 的 per-state band 目标。

用法::

    python acoustic_identity_v015/scripts/rebuild_tuning_manifest.py [--check]

`--check` 只比对不写盘，退出码非 0 表示磁盘上的 manifest 与重建结果不一致。

保留不动的部分
--------------
`schema_version` / `scope` / `reproducibility` / 每车 `uniform_ratio_scale`、
`reference_id`，以及每个状态的 `order_couplings`、`level_scale` —— 这些是渲染
链直接消费的字段，Task 3.0 只重建"目标数据"，不碰渲染行为。

重建的部分
----------
- 每个状态的 `band_shares_target` 与逐态 `provenance`，来自
  `tuning/reference_reconstruction.py` 的正演物理模型（必要时与通过自洽性检验
  的补偿参考做几何混合）。
- 顶层新增 `recording_chain_compensation`（滚降拟合参数 + 内/外样本残差 +
  是否通过单链假设检验）与 `physics_prior`（各车阶次先验及其依据），使目标值
  可追溯、可复现、可被后续任务审计。

确定性：全流程无随机数，拟合走固定栅格搜索；重复运行输出逐字节一致。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_V015 = Path(__file__).resolve().parents[1]
if str(_V015.parent) not in sys.path:
    sys.path.insert(0, str(_V015.parent))

from acoustic_identity_v015.tuning.deep_realism import STATE_KEYS, STATE_OPERATING_POINTS
from acoustic_identity_v015.tuning.reference_reconstruction import (
    ENGINE_PRIORS,
    REFERENCE_SEGMENT_OPERATING_POINTS,
    VEHICLE_IDS,
    _BIAS_TRANSPORT_MIN_SEGMENTS,
    _BIAS_TRANSPORT_RESIDUAL_MAX,
    _EXHAUST_RESONANCE_Q,
    _PULSE_LOAD_EXPONENT,
    _REFERENCE_BLEND_WEIGHT,
    fit_recording_chain,
    firing_frequency_hz,
    model_bias_correction,
    registry_corroborated_segments,
    state_targets,
)

MANIFEST_PATH = _V015 / "targets" / "deep_realism_tuning_manifest.json"

_REFERENCE_PROVENANCE = (
    "band targets are derived, not measured: a forward physics model of the firing-order "
    "series supplies every state, blended with a roll-off compensated reference segment only "
    "where the single recording-chain assumption survives out-of-sample validation; the "
    "underlying clips remain relative recording features, not calibration"
)
_CHAIN_ASSUMPTION = (
    "each vehicle's reference clip passes through one linear time-invariant high-pass "
    "(fc, n) fitted on the idle segment; the fit is then evaluated on every available "
    "segment of the same clip and rejected when it fails to generalise"
)


def build_manifest(existing: dict) -> dict:
    """由现有 manifest + 物理重建结果产出新 manifest（纯函数，无副作用）。"""
    fits = {vehicle: fit_recording_chain(vehicle) for vehicle in VEHICLE_IDS}
    rebuilt = {
        "schema_version": existing["schema_version"],
        "scope": existing["scope"],
        "reference_provenance": _REFERENCE_PROVENANCE,
        "vehicles": {
            vehicle: _rebuild_vehicle(vehicle, existing["vehicles"][vehicle])
            for vehicle in existing["vehicles"]
        },
        "recording_chain_compensation": {
            "assumption": _CHAIN_ASSUMPTION,
            "acceptance": {
                "out_of_sample_over_in_sample_max": 3.0,
                "out_of_sample_residual_max": 0.35,
                "residual_metric": "band-share weighted RMS of log10 error",
            },
            "segment_operating_points": {
                segment: {"rpm": rpm, "load": load}
                for segment, (rpm, load) in REFERENCE_SEGMENT_OPERATING_POINTS.items()
            },
            "vehicles": {vehicle: _chain_block(fits[vehicle]) for vehicle in VEHICLE_IDS},
        },
        "physics_prior_bias_correction": {
            "method": (
                "the compensated reference is compared against the physics prior AT THE "
                "REFERENCE SEGMENT'S OWN OPERATING POINT, yielding a per-band ratio that "
                "measures how far the prior is systematically off. That ratio is a property "
                "of the model, not of an operating point, so it is applied to all six states "
                "at once -- unlike the segment spectrum itself, which belongs to its own rpm "
                "and load and cannot be transplanted onto a different state"
            ),
            "acceptance": {
                "min_corroborated_segments": _BIAS_TRANSPORT_MIN_SEGMENTS,
                "transport_residual_max": _BIAS_TRANSPORT_RESIDUAL_MAX,
                "residual_metric": (
                    "band-share weighted RMS of the log10 spread of the per-segment ratios "
                    "about their geometric mean"
                ),
                "rationale": (
                    "a single segment cannot falsify the claim that the ratio is "
                    "operating-point independent, so one segment is never enough"
                ),
            },
            "reference_blend_weight": _REFERENCE_BLEND_WEIGHT,
            "vehicles": {vehicle: _bias_block(vehicle) for vehicle in VEHICLE_IDS},
        },
        "physics_prior": {
            "model": (
                "discrete order series (f = rpm/60 * order) with a flat envelope below the "
                "firing frequency and a dB/oct roll-off above it, plus an exhaust blowdown "
                "pulse term shaped by the exhaust pipe's fundamental standing-wave mode "
                "(second-order band-pass resonator at c/(2L), Q = 2.5, energy scaling as "
                "load^2 because cylinder pressure at exhaust-valve-open scales with charge "
                "mass), a Strouhal-scaled broadband exhaust-flow term and an optional turbo "
                "narrowband term, integrated over "
                "acoustic_analysis/spectral_targets.py::BAND_EDGES"
            ),
            "exhaust_pulse_term": {
                "shape": "x^2 / ((1 - x^2)^2 + (x/Q)^2), x = f / exhaust_resonance_hz",
                "resonance_q": _EXHAUST_RESONANCE_Q,
                "load_exponent": _PULSE_LOAD_EXPONENT,
                "hot_gas_speed_of_sound_m_per_s": 557.0,
                "basis": (
                    "each exhaust-valve-opening blowdown injects a broadband pressure pulse "
                    "into the exhaust; the pipe's open-open fundamental c/(2L) amplifies it "
                    "and the tailpipe orifice radiates it with a monopole f^2 efficiency, so "
                    "the term is a band-pass resonator that is silent at DC, peaks near "
                    "100 Hz and decays as f^-2 above it. Hot-gas c = sqrt(1.35*287*800) "
                    "= 557 m/s, far above the 343 m/s of ambient air. Q = 2.5 sits mid-range "
                    "of the 2-4 measured for lossy exhaust ducts (open-end radiation loss, "
                    "hot-gas viscous loss, muffler absorption). The load^2 exponent is the "
                    "same acoustic-energy-proportional-to-pressure-squared argument already "
                    "used by the flow-noise term, not an independently fitted exponent"
                ),
            },
            "calibration_status": "prior estimates only; no measured calibration",
            "state_operating_points": {
                state: {"rpm": rpm, "load": load, "throttle": throttle}
                for state, (rpm, load, throttle) in STATE_OPERATING_POINTS.items()
            },
            "vehicles": {vehicle: _prior_block(vehicle) for vehicle in VEHICLE_IDS},
        },
        "reproducibility": dict(existing["reproducibility"]),
    }
    rebuilt["reproducibility"].update(
        {
            "rebuilt_by": "acoustic_identity_v015/scripts/rebuild_tuning_manifest.py",
            "deterministic": True,
        }
    )
    return rebuilt


def _rebuild_vehicle(vehicle_id: str, existing_vehicle: dict) -> dict:
    targets = state_targets(vehicle_id)
    states = {}
    for state in STATE_KEYS:
        previous = existing_vehicle["states"][state]
        entry = targets[state]
        states[state] = {
            "band_shares_target": entry["band_shares_target"],
            "provenance": entry["provenance"],
            "reference_segment": entry["reference_segment"],
            "basis": entry["basis"],
            "operating_point": entry["operating_point"],
            "order_couplings": previous["order_couplings"],
            "level_scale": previous["level_scale"],
        }
    return {
        "uniform_ratio_scale": existing_vehicle["uniform_ratio_scale"],
        "reference_id": existing_vehicle["reference_id"],
        "states": states,
    }


def _chain_block(fit) -> dict:
    return {
        "fc_hz": round(fit.fc_hz, 4),
        "order_n": round(fit.order_n, 4),
        "in_sample_residual": round(fit.in_sample_residual, 6),
        "out_of_sample_residual": round(fit.out_of_sample_residual, 6),
        "single_chain_consistent": fit.single_chain_consistent,
        "fitted_on": fit.fitted_on,
        "validated_on": list(fit.validated_on),
        "registry_corroborated_segments": list(registry_corroborated_segments(fit.vehicle_id)),
        "applied": fit.single_chain_consistent,
    }


def _bias_block(vehicle_id: str) -> dict:
    bias = model_bias_correction(vehicle_id)
    finite = bias.transportable or bias.segments
    return {
        "segments": list(bias.segments),
        "correction": [round(value, 6) for value in bias.correction],
        "transport_residual": round(bias.transport_residual, 6) if finite else None,
        "per_band_dispersion": (
            [round(value, 6) for value in bias.per_band_dispersion] if finite else None
        ),
        "transportable": bias.transportable,
        "applied": bias.transportable,
        "reason": bias.reason,
    }


def _prior_block(vehicle_id: str) -> dict:
    prior = ENGINE_PRIORS[vehicle_id]
    return {
        "firing_order": prior.firing_order,
        "sub_order_weight": prior.sub_order_weight,
        "half_order_weight": prior.half_order_weight,
        "harmonic_rolloff_db_per_octave": prior.harmonic_rolloff_db_per_octave,
        "flow_noise_fraction": prior.flow_noise_fraction,
        "pulse_fraction": prior.pulse_fraction,
        "exhaust_resonance_hz": prior.exhaust_resonance_hz,
        "turbo_weight": prior.turbo_weight,
        "firing_frequency_hz_at_3000_rpm": round(firing_frequency_hz(vehicle_id, 3000.0), 4),
        "basis": prior.basis,
    }


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只比对，不写盘")
    args = parser.parse_args(argv)

    existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload = render(build_manifest(existing))

    # 按字节比对/写入，强制 LF 行尾（write_text 在 Windows 会把 \n 转成 \r\n，
    # read_text 的 universal newlines 又会把 \r\n 读回 \n，两者叠加会掩盖行尾偏差）
    encoded = payload.encode("utf-8")

    if args.check:
        if MANIFEST_PATH.read_bytes() == encoded:
            print(f"OK   {MANIFEST_PATH.name} 与重建结果一致")
            return 0
        print(f"DIFF {MANIFEST_PATH.name} 与重建结果不一致；请重新运行本脚本", file=sys.stderr)
        return 1

    MANIFEST_PATH.write_bytes(encoded)
    for vehicle in VEHICLE_IDS:
        fit = fit_recording_chain(vehicle)
        verdict = "applied" if fit.single_chain_consistent else "REJECTED"
        print(
            f"{vehicle:<12} fc={fit.fc_hz:7.2f} Hz  n={fit.order_n:.3f}  "
            f"in={fit.in_sample_residual:.4f}  out={fit.out_of_sample_residual:.4f}  "
            f"chain={verdict}"
        )
    print(f"written: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
