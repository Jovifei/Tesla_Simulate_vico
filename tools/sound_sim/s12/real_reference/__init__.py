"""Stage Q real-reference inventory and fail-closed evidence contracts."""

from .inventory import (
    CATALOG,
    ANCHOR_VEHICLES,
    build_inventory,
    build_evidence_matrix,
    write_stage_q_outputs,
)
from .qualification import ReferenceQualificationError, qualify_r1_reference, qualify_r2_reference, require_r1_reference
from .limited import compare_r2_signals
from .closed_loop_report import render_waiting_final_report, write_waiting_final_report

__all__ = [
    "ANCHOR_VEHICLES",
    "CATALOG",
    "build_evidence_matrix",
    "build_inventory",
    "write_stage_q_outputs",
    "ReferenceQualificationError",
    "qualify_r1_reference",
    "qualify_r2_reference",
    "require_r1_reference",
    "compare_r2_signals",
    "render_waiting_final_report",
    "write_waiting_final_report",
]
