"""Stage AE: canonical physical-acoustic convergence.

Stage AE keeps PersistentEventDomainEngine as the single authoritative source renderer.
Experimental EngineAcoustics remains a teacher/diagnostic reference only.
"""

from .canonical_renderer import CanonicalStageAERenderer, apply_package_monitor_gain
from .ir_assets import IrAssetSpec, load_ir_asset
from .partitioned_convolver import UniformPartitionedConvolver, convolve_stereo
from .vehicle_profiles import VEHICLES, build_standard_trace

__all__ = [
    "CanonicalStageAERenderer",
    "IrAssetSpec",
    "UniformPartitionedConvolver",
    "VEHICLES",
    "apply_package_monitor_gain",
    "build_standard_trace",
    "convolve_stereo",
    "load_ir_asset",
]
