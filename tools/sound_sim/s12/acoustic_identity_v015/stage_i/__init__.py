"""Stage-I Hellcat whine voicing package.

The public API is loaded lazily so the source renderer can reuse
``stage_i.whine_voicing`` without creating a candidate-renderer import cycle.
"""

from __future__ import annotations

from typing import Any


_EXPORTS = {
    "StageICandidateProfile",
    "load_stage_i_candidate",
    "render_stage_i_candidate",
}


def __getattr__(name: str) -> Any:
    if name in {"StageICandidateProfile", "load_stage_i_candidate"}:
        from .candidate_profiles import StageICandidateProfile, load_stage_i_candidate

        return {
            "StageICandidateProfile": StageICandidateProfile,
            "load_stage_i_candidate": load_stage_i_candidate,
        }[name]
    if name == "render_stage_i_candidate":
        from .render_candidate import render_stage_i_candidate

        return render_stage_i_candidate
    raise AttributeError(name)


__all__ = tuple(sorted(_EXPORTS))
