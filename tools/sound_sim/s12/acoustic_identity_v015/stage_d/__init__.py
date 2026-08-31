"""Stage-D candidate overlays and human audition tooling for Track-S."""

from .blind_audition import build_blind_package, score_blind_responses
from .candidate_profiles import BASE_COMMIT, StageDCandidateProfile, load_stage_d_candidate
from .reference_distance import band_distance, summarize_reference_distance
from .render_candidate import render_stage_d_candidate

__all__ = (
    "BASE_COMMIT",
    "StageDCandidateProfile",
    "band_distance",
    "build_blind_package",
    "load_stage_d_candidate",
    "render_stage_d_candidate",
    "score_blind_responses",
    "summarize_reference_distance",
)
