"""Synthetic, uncalibrated S12 acoustic-identity v0.15 sources and contracts."""

from .acoustic_layers import apply_afterfire, apply_idle_dynamics, apply_low_frequency_body
from .acoustic_analysis import OrderMap, compare_identity_renders, compute_engine_identity_metrics, compute_order_map, compute_realism_metrics, write_order_map, write_spectrogram
from .contracts import ResearchDatabase, SourceRender, VehicleStateTrace, load_research_database
from .loudness_manager import LoudnessManagedBundle, LoudnessMetrics, manage_bundle_loudness, measure_loudness
from .render_identity_v02 import publish_identity_v02
from .render_drive_cycle_v10 import build_drive_cycle_trace, publish_drive_cycle_v10, render_drive_cycle_source
from .render_realism_v10 import publish_realism_v10
from .sources.flat_plane_v8_source import render_ferrari_458
from .sources.rotary_turbo_source import render_rx7_fd
from .sources.supercharged_hemi_source import render_hellcat

__all__ = (
    "ResearchDatabase",
    "SourceRender",
    "VehicleStateTrace",
    "LoudnessManagedBundle",
    "LoudnessMetrics",
    "OrderMap",
    "apply_afterfire",
    "apply_idle_dynamics",
    "apply_low_frequency_body",
    "build_drive_cycle_trace",
    "compare_identity_renders",
    "compute_engine_identity_metrics",
    "compute_order_map",
    "compute_realism_metrics",
    "load_research_database",
    "manage_bundle_loudness",
    "measure_loudness",
    "publish_identity_v02",
    "publish_drive_cycle_v10",
    "publish_realism_v10",
    "render_ferrari_458",
    "render_drive_cycle_source",
    "render_hellcat",
    "render_rx7_fd",
    "write_order_map",
    "write_spectrogram",
)
