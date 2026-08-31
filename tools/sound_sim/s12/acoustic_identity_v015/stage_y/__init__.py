"""Stage Y source-layer, calibration, and hybrid-source utilities.

The package combines clean-room synthetic source layers with rights-gated
calibration tooling. It does not embed third-party audio and does not
modify frozen PTR/FVM/Radiation mathematics.
"""

from .cycle_residual_bank import CycleResidualBank, CycleResidualRecord
from .harmonic_map_fit import load_committed_fixture_timbre_map
from .harmonic_timbre_extractor import (
    HarmonicTimbreMap,
    extract_harmonic_timbre_map,
)
from .transfer_response_id import FirIdentificationResult, identify_fir_response

__all__ = [
    "CycleResidualBank",
    "CycleResidualRecord",
    "FirIdentificationResult",
    "HarmonicTimbreMap",
    "extract_harmonic_timbre_map",
    "identify_fir_response",
    "load_committed_fixture_timbre_map",
]
