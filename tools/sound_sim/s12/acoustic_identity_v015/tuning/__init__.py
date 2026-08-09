"""Track-S 逐状态调音层：ratio-invariant 的 deep realism 注入。"""

from .deep_realism import STATE_KEYS, apply_deep_realism, classify_state, load_tuning_manifest

__all__ = (
    "STATE_KEYS",
    "apply_deep_realism",
    "classify_state",
    "load_tuning_manifest",
)
