"""Round-2 Hellcat afterfire source contracts."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import build_hellcat_crank_clock
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.hellcat_afterfire_v1 import (
    render_hellcat_afterfire_v1,
)


SAMPLE_RATE_HZ = 8_000
PARAMETERS = {
    "minimum_rpm": 3_300.0,
    "residual_energy_gain": 0.85,
    "event_energy_threshold": 0.35,
    "body_mix": 0.68,
    "bright_mix": 0.20,
    "decay_90_10_s": 0.045,
}
PRIMITIVES = (
    "hemi_exhaust_left",
    "hemi_exhaust_right",
    "hemi_blowdown_body",
    "hemi_structure_shock",
    "hemi_mechanical_torque_ripple",
)


def _fixture(
    *,
    rpm: float = 3_900.0,
    hot: bool = True,
    close_throttle: bool = True,
    residual: bool = True,
    body_hz: float = 233.0,
    bright_hz: float = 911.0,
) -> tuple[SourceRender, VehicleStateTrace, int]:
    count = 3 * SAMPLE_RATE_HZ + 1
    time_s = np.arange(count, dtype=np.float64) / SAMPLE_RATE_HZ
    close_sample = int(1.50 * SAMPLE_RATE_HZ)
    load = np.full(count, 0.12)
    throttle = np.full(count, 0.08)
    if hot:
        load[:close_sample] = 0.92
    if close_throttle:
        throttle[:close_sample] = 0.94
    else:
        throttle[:] = 0.94
        load[:] = 0.92 if hot else 0.12
    trace = VehicleStateTrace(
        time_s=time_s,
        rpm=np.full(count, rpm),
        load=load,
        throttle=throttle,
        acceleration_mps2=np.zeros(count),
    ).validate()

    body = 0.24 * np.sin(2.0 * np.pi * body_hz * time_s)
    bright = 0.12 * np.sin(2.0 * np.pi * bright_hz * time_s + 0.37)
    if not residual:
        body[:] = 0.0
        bright[:] = 0.0
    stereo_body = np.column_stack((1.04 * body, 0.96 * body))
    stereo_bright = np.column_stack((0.92 * bright, 1.08 * bright))
    stems = {
        "hemi_exhaust_left": np.column_stack((0.45 * body, 0.06 * body)),
        "hemi_exhaust_right": np.column_stack((0.06 * body, 0.45 * body)),
        "hemi_blowdown_body": stereo_body,
        "hemi_structure_shock": stereo_bright,
        "hemi_mechanical_torque_ripple": 0.18 * stereo_bright,
    }
    pressure = sum((stems[name] for name in PRIMITIVES), np.zeros_like(stereo_body))
    render = SourceRender(
        pressure=pressure,
        stems=stems,
        diagnostics={
            "pressure_stem_contract": {
                "contributors": list(PRIMITIVES),
                "diagnostic_aggregates": [],
            }
        },
    ).validate()
    return render, trace, close_sample


def _band_energy(audio: np.ndarray, low_hz: float, high_hz: float) -> float:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(mono.size))) ** 2
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / SAMPLE_RATE_HZ)
    return float(np.sum(spectrum[(frequencies >= low_hz) & (frequencies < high_hz)]))


def test_afterfire_qualifies_on_hot_lift_and_uses_next_shared_bank_event() -> None:
    render, trace, close_sample = _fixture()
    clock = build_hellcat_crank_clock(trace, SAMPLE_RATE_HZ)

    result = render_hellcat_afterfire_v1(
        render, trace, clock, PARAMETERS, sample_rate_hz=SAMPLE_RATE_HZ,
    )

    expected_position = int(np.searchsorted(clock.event_sample_indices, close_sample, side="left"))
    expected_sample = clock.event_sample_indices[expected_position]
    expected_bank = clock.bank_labels[expected_position]
    assert result.diagnostics["afterfire_event_sample_indices"] == (expected_sample,)
    assert result.diagnostics["afterfire_bank_labels"] == (expected_bank,)
    qualification = result.diagnostics["afterfire_qualification"]
    assert qualification[0]["hot_history"] is True
    assert qualification[0]["rpm"] is True
    assert qualification[0]["throttle_close"] is True
    assert qualification[0]["residual_energy"] is True
    assert qualification[0]["oxygen_proxy"] is True
    channel_rms = np.sqrt(np.mean(np.square(result.stems["afterfire"]), axis=0))
    assert int(np.argmax(channel_rms)) == (0 if expected_bank == "left" else 1)


def test_afterfire_is_real_hemi_template_content_and_one_pressure_contributor() -> None:
    render, trace, _ = _fixture(body_hz=233.0, bright_hz=911.0)
    clock = build_hellcat_crank_clock(trace, SAMPLE_RATE_HZ)
    result = render_hellcat_afterfire_v1(
        render, trace, clock, PARAMETERS, sample_rate_hz=SAMPLE_RATE_HZ,
    )
    shifted_render, shifted_trace, _ = _fixture(body_hz=317.0, bright_hz=1_207.0)
    shifted = render_hellcat_afterfire_v1(
        shifted_render,
        shifted_trace,
        build_hellcat_crank_clock(shifted_trace, SAMPLE_RATE_HZ),
        PARAMETERS,
        sample_rate_hz=SAMPLE_RATE_HZ,
    )

    afterfire = result.stems["afterfire"]
    assert not np.array_equal(afterfire, shifted.stems["afterfire"])
    assert _band_energy(afterfire, 215.0, 250.0) > _band_energy(afterfire, 72.0, 88.0)
    assert _band_energy(afterfire, 880.0, 945.0) > _band_energy(afterfire, 680.0, 720.0)
    provenance = result.diagnostics["afterfire_template_provenance"]
    assert provenance["kind"] == "actual_pre_lift_hemi_arrays"
    assert set(provenance["source_stems"]) == {
        "hemi_blowdown_body", "hemi_structure_shock", "hemi_mechanical_torque_ripple",
    }
    assert result.diagnostics["fixed_80_700_hz_oscillators_used"] is False

    contract = result.diagnostics["pressure_stem_contract"]
    assert contract["contributors"].count("afterfire") == 1
    rebuilt = sum(
        (result.stems[name] for name in contract["contributors"]),
        np.zeros_like(result.pressure),
    )
    np.testing.assert_allclose(result.pressure, rebuilt, rtol=0.0, atol=2.0e-15)
    np.testing.assert_allclose(result.pressure - render.pressure, afterfire, rtol=0.0, atol=2.0e-15)


@pytest.mark.parametrize(
    ("case", "fixture_kwargs", "oxygen"),
    (
        ("cold", {"hot": False}, None),
        ("idle", {"rpm": 900.0}, None),
        ("steady", {"close_throttle": False}, None),
        ("no_residual", {"residual": False}, None),
        ("no_oxygen", {}, "zero"),
    ),
)
def test_afterfire_wrong_operating_conditions_have_zero_events(
    case: str, fixture_kwargs: dict[str, object], oxygen: str | None,
) -> None:
    render, trace, _ = _fixture(**fixture_kwargs)
    oxygen_proxy = np.zeros(render.pressure.shape[0]) if oxygen == "zero" else None
    result = render_hellcat_afterfire_v1(
        render,
        trace,
        build_hellcat_crank_clock(trace, SAMPLE_RATE_HZ),
        PARAMETERS,
        sample_rate_hz=SAMPLE_RATE_HZ,
        oxygen_proxy=oxygen_proxy,
    )

    assert result.diagnostics["afterfire_event_count"] == 0, case
    assert result.diagnostics["afterfire_event_sample_indices"] == (), case
    np.testing.assert_array_equal(result.stems["afterfire"], np.zeros_like(render.pressure))
    np.testing.assert_array_equal(result.pressure, render.pressure)


def test_afterfire_rejects_a_second_application_or_clock_from_another_trace() -> None:
    render, trace, _ = _fixture()
    clock = build_hellcat_crank_clock(trace, SAMPLE_RATE_HZ)
    first = render_hellcat_afterfire_v1(
        render, trace, clock, PARAMETERS, sample_rate_hz=SAMPLE_RATE_HZ,
    )
    with pytest.raises(ValueError, match="only be applied once"):
        render_hellcat_afterfire_v1(
            first, trace, clock, PARAMETERS, sample_rate_hz=SAMPLE_RATE_HZ,
        )

    other_render, other_trace, _ = _fixture(rpm=4_500.0)
    with pytest.raises(ValueError, match="clock.*trace|shared crank clock"):
        render_hellcat_afterfire_v1(
            other_render, other_trace, clock, PARAMETERS, sample_rate_hz=SAMPLE_RATE_HZ,
        )
