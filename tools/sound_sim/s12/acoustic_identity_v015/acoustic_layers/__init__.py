"""Causal synthetic pre-PTR acoustic layers."""

from .afterfire_model import apply_afterfire
from .exhaust_rumble import apply_exhaust_rumble
from .idle_dynamics import apply_idle_dynamics
from .low_frequency_body import apply_low_frequency_body
from .pre_equalization import apply_pre_ptr_equalization
from .shift_dynamics import ShiftEvent, apply_shift_dynamics, detect_shift_events

__all__ = (
    "ShiftEvent",
    "apply_afterfire",
    "apply_exhaust_rumble",
    "apply_idle_dynamics",
    "apply_low_frequency_body",
    "apply_pre_ptr_equalization",
    "apply_shift_dynamics",
    "detect_shift_events",
)
