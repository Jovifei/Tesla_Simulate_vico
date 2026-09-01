"""Stage Z method-level open-source absorption evidence."""

from .method_ablation import (
    METHOD_CATALOG,
    build_method_adoption_matrix,
    build_teacher_vs_reduced_response,
    render_ablation_case,
)

__all__ = [
    "METHOD_CATALOG",
    "build_method_adoption_matrix",
    "build_teacher_vs_reduced_response",
    "render_ablation_case",
]
