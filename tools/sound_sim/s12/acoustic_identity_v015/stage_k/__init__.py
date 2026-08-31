"""Stage-K Track-S contracts for four-vehicle perceptual repair.

All outputs remain synthetic, uncalibrated, vehicle-inspired and explicitly
not an OEM reproduction.  The package does not modify the frozen PTR or
formal loudness manager.
"""

from .candidate_profiles import (
    BASE_COMMIT,
    COMMON_KEYS,
    ELIGIBLE_STATES,
    PARENT_MAPPING,
    REFERENCE_MAPPING,
    SCHEMA_VERSION,
    SOURCE_KEYS,
    STAGE_K_VEHICLES,
    StageKCandidateProfile,
    load_stage_k_candidate,
)
from .render_candidate import render_stage_k_candidate, render_stage_k_parent

__all__ = (
    "BASE_COMMIT",
    "COMMON_KEYS",
    "ELIGIBLE_STATES",
    "PARENT_MAPPING",
    "REFERENCE_MAPPING",
    "SCHEMA_VERSION",
    "SOURCE_KEYS",
    "STAGE_K_VEHICLES",
    "StageKCandidateProfile",
    "load_stage_k_candidate",
    "render_stage_k_candidate",
    "render_stage_k_parent",
)
