"""Stage-J three-vehicle identity candidates and named review helpers."""

from .candidate_profiles import (
    BASE_COMMIT,
    STAGE_J_VEHICLES,
    StageJCandidateProfile,
    load_stage_j_candidate,
)
from .render_candidate import render_stage_j_candidate
from .named_review import REVIEW_GAIN_DB, REVIEW_GAIN_LINEAR, build_stage_j_named_review
from .perceptual_metrics import compute_stage_j_perceptual_metrics
from .reference_distance import compute_stage_j_reference_distance

__all__ = (
    "BASE_COMMIT",
    "STAGE_J_VEHICLES",
    "StageJCandidateProfile",
    "load_stage_j_candidate",
    "render_stage_j_candidate",
    "REVIEW_GAIN_LINEAR",
    "REVIEW_GAIN_DB",
    "build_stage_j_named_review",
    "compute_stage_j_perceptual_metrics",
    "compute_stage_j_reference_distance",
)
