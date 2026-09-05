"""Single-authority Stage AE renderer.

The authoritative source remains PersistentEventDomainEngine.  Optional governed IR
convolution is inserted after the S12 source/path/audio-chain output and before the
unchanged Frozen PTR boundary.  Monitor gain is a separate package-level operation
and is never fed back into reference-distance optimization.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import copy
import numpy as np

from ..event_domain.config_schema import load_config
from ..stage_w.boundary_adapter import FrozenPtrStereo
from ..stage_w.persistent_engine import PersistentEventDomainEngine
from .ir_assets import IrAssetSpec, load_ir_asset
from .partitioned_convolver import convolve_stereo


@dataclass(frozen=True)
class CanonicalRenderResult:
    pre_ptr_pcm: np.ndarray
    post_ptr_pcm: np.ndarray
    diagnostics: dict


class CanonicalStageAERenderer:
    def __init__(self, vehicle_config_id: str, sample_rate_hz: int = 48000, block_size: int = 960, random_seed: int = 20260905, ir_spec: IrAssetSpec | None = None) -> None:
        self.vehicle_config_id = vehicle_config_id
        self.sample_rate_hz = int(sample_rate_hz)
        self.block_size = int(block_size)
        self.random_seed = int(random_seed)
        self.ir_spec = ir_spec

    def render(self, trace: Mapping[str, np.ndarray]) -> CanonicalRenderResult:
        cfg = load_config(self.vehicle_config_id)
        engine = PersistentEventDomainEngine(
            copy.deepcopy(cfg), self.sample_rate_hz, self.block_size,
            ptr_enabled=False, path_model="waveguide_v1", forced_induction_model="harmonic_v1",
            random_seed=self.random_seed, jitter_fraction=0.0,
            transient_model="state_v1", audio_chain="dp_v1",
        )
        source = engine.process_with_trace(trace)
        pre_ptr = np.asarray(source.raw_pcm, dtype=np.float64)
        ir_meta = None
        if self.ir_spec is not None:
            ir = load_ir_asset(self.ir_spec, self.sample_rate_hz, use="diagnostic")
            pre_ptr = convolve_stereo(pre_ptr, ir, self.block_size)
            ir_meta = {"asset_id": self.ir_spec.asset_id, "sha256": self.ir_spec.sha256, "rights_status": self.ir_spec.rights_status}
        ptr = FrozenPtrStereo(self.sample_rate_hz)
        blocks = []
        for start in range(0, pre_ptr.shape[0], self.block_size):
            chunk = pre_ptr[start:start+self.block_size]
            valid = chunk.shape[0]
            if valid < self.block_size:
                chunk = np.pad(chunk, ((0,self.block_size-valid),(0,0)))
            blocks.append(ptr.process(chunk)[:valid])
        post_ptr = np.vstack(blocks) if blocks else np.empty((0,2), dtype=np.float64)
        diagnostics = dict(source.diagnostics)
        diagnostics["stage_ae"] = {
            "canonical_source": "PersistentEventDomainEngine",
            "external_ir": ir_meta,
            "random_seed": self.random_seed,
            "monitor_gain_applied": False,
            "teacher_renderer_used": False,
        }
        return CanonicalRenderResult(pre_ptr, post_ptr, diagnostics)


def package_gain_db(scene_pcm: Mapping[str, np.ndarray], ceiling: float = 0.94) -> float:
    """Return one attenuation-only gain for the entire package."""
    if not 0.0 < ceiling < 1.0:
        raise ValueError("ceiling must be in (0,1)")
    peak = max((float(np.max(np.abs(np.asarray(v,float)))) for v in scene_pcm.values() if np.asarray(v).size), default=0.0)
    if peak <= ceiling or peak == 0.0:
        return 0.0
    return float(20.0*np.log10(ceiling/peak))


def apply_package_monitor_gain(scene_pcm: Mapping[str, np.ndarray], ceiling: float = 0.94) -> tuple[dict[str,np.ndarray], float]:
    gain_db = package_gain_db(scene_pcm, ceiling)
    gain = 10.0 ** (gain_db/20.0)
    return {name: np.asarray(pcm,dtype=np.float64)*gain for name,pcm in scene_pcm.items()}, gain_db
