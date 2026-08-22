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
from .stage_r_execute import (
    MATLAB_R1_FUNCTIONS,
    R1_INPUT_SCHEMA_VERSION,
    StageRExecutionContractError,
    build_r1_execution_plan,
    prepare_r1_matlab_inputs,
    read_unaltered_pcm_wav,
    run_r2_limited_comparison,
    write_r2_outputs,
)
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
    "MATLAB_R1_FUNCTIONS",
    "R1_INPUT_SCHEMA_VERSION",
    "StageRExecutionContractError",
    "build_r1_execution_plan",
    "prepare_r1_matlab_inputs",
    "read_unaltered_pcm_wav",
    "run_r2_limited_comparison",
    "write_r2_outputs",
    "render_waiting_final_report",
    "write_waiting_final_report",
]
