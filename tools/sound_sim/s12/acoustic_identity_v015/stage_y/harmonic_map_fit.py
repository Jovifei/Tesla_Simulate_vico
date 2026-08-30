"""Fit a fixture HarmonicTimbreMap from synthetic Hellcat cycles."""
from __future__ import annotations

import hashlib

import numpy as np

MAP_SCHEMA = "s12.stage_y.harmonic_timbre_map.v1"


def fit_harmonic_map(bank: dict, vehicle_id: str = "hellcat") -> dict:
    sample_rate = int(bank["sample_rate_hz"])
    rpm_axis = np.array(sorted(bank["cycles"].keys()), dtype=np.float64)
    load_axis = np.array([0.2, 0.6, 1.0], dtype=np.float64)
    boost_axis = np.array([0.0, 0.5, 1.0], dtype=np.float64)
    order_axis = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
    amplitude = np.zeros((rpm_axis.size, load_axis.size, boost_axis.size, order_axis.size), dtype=np.float64)
    for rpm_index, rpm in enumerate(rpm_axis):
        cycle = np.asarray(bank["cycles"][float(rpm)], dtype=np.float64)
        mono = cycle.mean(axis=1)
        spectrum = np.abs(np.fft.rfft(mono))
        freqs = np.fft.rfftfreq(mono.size, 1.0 / sample_rate)
        firing_hz = float(rpm) / 60.0 * 4.0
        for order_index, order in enumerate(order_axis):
            target = firing_hz * float(order)
            bin_index = int(np.argmin(np.abs(freqs - target)))
            base = float(spectrum[bin_index])
            for load_index, load in enumerate(load_axis):
                for boost_index, boost in enumerate(boost_axis):
                    amplitude[rpm_index, load_index, boost_index, order_index] = base * (0.4 + 0.6 * load) * (0.5 + 0.5 * boost)
    fixture_sha = hashlib.sha256(b"".join(np.asarray(bank["cycles"][float(rpm)]).tobytes() for rpm in rpm_axis)).hexdigest()
    return {
        "schema": MAP_SCHEMA,
        "vehicle_id": vehicle_id,
        "source": "synthetic_fixture",
        "rpm_axis": rpm_axis.tolist(),
        "load_axis": load_axis.tolist(),
        "boost_axis": boost_axis.tolist(),
        "order_axis": order_axis.tolist(),
        "amplitude": amplitude.tolist(),
        "fixture_sha256": fixture_sha,
    }
