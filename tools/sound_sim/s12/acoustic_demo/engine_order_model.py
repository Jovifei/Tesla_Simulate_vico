"""Synthetic engine-order frequency contract for the v0.3 vertical slice."""

from __future__ import annotations

import math


def order_frequencies_hz(rpm: float, profile: dict) -> dict[str, float]:
    if not math.isfinite(rpm) or rpm <= 0.0:
        raise ValueError("RPM must be finite and positive")
    if profile.get("source") != "synthetic" or not isinstance(profile.get("orders"), list):
        raise ValueError("order model requires a synthetic order profile")
    frequencies = {}
    for entry in profile["orders"]:
        if not isinstance(entry, dict) or entry.get("source") != "synthetic":
            raise ValueError("order entries must be synthetic")
        name = entry.get("name")
        order = float(entry.get("order"))
        if not isinstance(name, str) or not name or not math.isfinite(order) or order <= 0.0:
            raise ValueError("order entries require positive finite orders")
        frequencies[name] = order * rpm / 60.0
    return frequencies
