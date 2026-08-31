"""Stage-G automatic qualification and blind-audition tooling."""

from .candidate_profiles import StageGCandidateProfile, load_stage_g_candidate
from .render_candidate import render_stage_g_candidate

__all__ = ("StageGCandidateProfile", "load_stage_g_candidate", "render_stage_g_candidate")
