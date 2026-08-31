"""Stage-H Hellcat-focused candidate and named audition tooling."""

from .candidate_profiles import StageHCandidateProfile, load_stage_h_candidate
from .named_review import build_stage_h_named_review
from .perceptual_metrics import compute_hellcat_perceptual_metrics
from .reference_distance import compute_stage_h_reference_distance
from .render_candidate import render_stage_h_candidate

__all__ = ("StageHCandidateProfile", "load_stage_h_candidate", "render_stage_h_candidate", "build_stage_h_named_review", "compute_hellcat_perceptual_metrics", "compute_stage_h_reference_distance")
