"""Stage Y data-driven calibration and hybrid-source utilities.

These modules are tooling only until authorized synchronized recordings or
pressure-response data are supplied. They never embed third-party audio and
do not modify the frozen PTR/FVM/Radiation implementation.
"""

from .cycle_residual_bank import CycleResidualBank, CycleResidualRecord
from .harmonic_timbre_extractor import HarmonicTimbreMap, extract_harmonic_timbre_map
from .transfer_response_id import FirIdentificationResult, identify_fir_response

__all__ = [
    "CycleResidualBank",
    "CycleResidualRecord",
    "FirIdentificationResult",
    "HarmonicTimbreMap",
    "extract_harmonic_timbre_map",
    "identify_fir_response",
]
