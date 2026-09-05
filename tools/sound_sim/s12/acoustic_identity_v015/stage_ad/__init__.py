"""Stage AD closed-loop reference calibration infrastructure."""

from .aa_c3_search import AA_C3_PARAMETER_FAMILIES, AA_C3_SOURCE_CAUSAL_PARAMETERS, run_aa_c3_search
from .closed_loop import ClosedLoopPolicy, reference_audio_from_caseset, run_closed_loop
from .package_audition import build_audition_package

__all__ = [
    "AA_C3_PARAMETER_FAMILIES",
    "AA_C3_SOURCE_CAUSAL_PARAMETERS",
    "ClosedLoopPolicy",
    "build_audition_package",
    "reference_audio_from_caseset",
    "run_aa_c3_search",
    "run_closed_loop",
]
