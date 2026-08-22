"""Stage Q real-reference inventory and fail-closed evidence contracts."""

from .inventory import (
    CATALOG,
    ANCHOR_VEHICLES,
    build_inventory,
    build_evidence_matrix,
    write_stage_q_outputs,
)
from .qualification import ReferenceQualificationError, qualify_r1_reference, require_r1_reference

__all__ = [
    "ANCHOR_VEHICLES",
    "CATALOG",
    "build_evidence_matrix",
    "build_inventory",
    "write_stage_q_outputs",
    "ReferenceQualificationError",
    "qualify_r1_reference",
    "require_r1_reference",
]
