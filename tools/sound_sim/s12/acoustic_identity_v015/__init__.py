"""Synthetic, uncalibrated S12 acoustic-identity v0.15 sources and contracts."""

from .acoustic_layers import (
    ShiftEvent,
    apply_afterfire,
    apply_exhaust_rumble,
    apply_idle_dynamics,
    apply_low_frequency_body,
    apply_pre_ptr_equalization,
    apply_shift_dynamics,
    detect_shift_events,
)
from .acoustic_layers.realism_profiles import (
    REALISM_PROFILES,
    SUPPORTED_REALISM_VEHICLE_IDS,
    get_realism_profile,
    validate_realism_profiles,
)
from .acoustic_analysis import OrderMap, compare_identity_renders, compute_engine_identity_metrics, compute_order_map, compute_realism_metrics, write_order_map, write_spectrogram
from .contracts import ResearchDatabase, SourceRender, VehicleStateTrace, load_research_database
from .loudness_manager import LoudnessManagedBundle, LoudnessMetrics, manage_bundle_loudness, measure_loudness
from .render_identity_v02 import publish_identity_v02
from .render_drive_cycle_v10 import build_drive_cycle_trace, publish_drive_cycle_v10, render_drive_cycle_source
from .render_realism_v10 import publish_realism_v10
from .sources.flat_plane_v8_source import render_ferrari_458
from .sources.lamborghini_v12_source import render_aventador_lp700
from .sources.lexus_v10_source import render_lfa
from .sources.mercedes_v8_source import render_c63_w204
from .sources.nissan_v6_turbo_source import render_gtr_r35
from .sources.rotary_turbo_source import render_rx7_fd
from .sources.supercharged_hemi_source import render_hellcat
from .sources.toyota_i6_turbo_source import render_supra_jza80

__all__ = (
    "ResearchDatabase",
    "SourceRender",
    "VehicleStateTrace",
    "ShiftEvent",
    "LoudnessManagedBundle",
    "LoudnessMetrics",
    "OrderMap",
    "apply_afterfire",
    "apply_exhaust_rumble",
    "apply_idle_dynamics",
    "apply_low_frequency_body",
    "apply_pre_ptr_equalization",
    "apply_shift_dynamics",
    "detect_shift_events",
    "build_drive_cycle_trace",
    "compare_identity_renders",
    "compute_engine_identity_metrics",
    "compute_order_map",
    "compute_realism_metrics",
    "load_research_database",
    "manage_bundle_loudness",
    "measure_loudness",
    "REALISM_PROFILES",
    "SUPPORTED_REALISM_VEHICLE_IDS",
    "get_realism_profile",
    "validate_realism_profiles",
    "publish_identity_v02",
    "publish_drive_cycle_v10",
    "publish_realism_v10",
    "render_ferrari_458",
    "render_aventador_lp700",
    "render_c63_w204",
    "render_drive_cycle_source",
    "render_hellcat",
    "render_gtr_r35",
    "render_lfa",
    "render_rx7_fd",
    "render_supra_jza80",
    "write_order_map",
    "write_spectrogram",
)
