"""Exact phase-domain event scheduling for piston and rotary configurations."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .config_schema import unwrap


def cycle_degrees(config: dict) -> float:
    """Return the declared mechanical cycle length in crank/eccentric degrees."""
    definition = str(unwrap(config, "cycle_definition"))
    if definition.startswith("four_stroke_"):
        return float(definition.rsplit("_", 1)[1])
    if definition == "rotary_360":
        return 360.0
    if definition == "rotary_1080":
        return 1080.0
    raise ValueError(f"unsupported cycle_definition: {definition}")


def derive_event_path_schedule(config: dict) -> list[dict[str, object]]:
    """Derive routing slots from bank assignment and collector topology."""
    banks = [int(value) for value in unwrap(config, "bank_assignment")]
    topology = str(unwrap(config, "collector_assignment")) if "collector_assignment" in config else "identity_default"
    return [{"entity": index, "bank_id": bank, "collector_slot": ("central" if topology == "central_first" else f"bank_{bank}"), "path_id": f"{topology}:entity_{index}"} for index, bank in enumerate(banks)]

@dataclass(frozen=True)
class EventTrace:
    sample_index: np.ndarray
    phase_rad: np.ndarray
    entity_index: np.ndarray
    bank_index: np.ndarray
    count: int


def derive_event_phase_deg(config: dict) -> list[float]:
    """Derive entity phase from firing order and cycle slots.

    Rotary configurations keep their explicit eccentric-shaft event phases;
    piston configurations use the declared firing sequence as the phase
    authority and retain the old phase list only as cycle-slot geometry.
    """

    if config["architecture"] == "rotary_wankel":
        geometry = [float(value) for value in unwrap(config, "rotor_geometry")]
        cycle = cycle_degrees(config)
        return [value % cycle for value in geometry]
    order = [int(value) for value in unwrap(config, "firing_order_evidence")]
    count = len(order)
    if sorted(order) != list(range(1, count + 1)):
        raise ValueError("firing order must be a complete permutation before phase derivation")
    geometry = unwrap(config, "crankpin_geometry")
    if isinstance(geometry, dict):
        geometry = geometry.get("entity_offsets_deg", geometry.get("offsets_deg", [0.0] * count))
    geometry = [float(value) for value in geometry]
    if len(geometry) != count:
        raise ValueError("crankpin geometry must cover every entity")
    bank_assignment = [int(value) for value in unwrap(config, "bank_assignment")]
    bank_offsets = [float(value) for value in unwrap(config, "bank_phase_offsets_deg")]
    if len(bank_offsets) != int(unwrap(config, "bank_count")) or not np.all(np.isfinite(bank_offsets)):
        raise ValueError("bank_phase_offsets_deg must be finite and cover every bank")
    cycle = cycle_degrees(config)
    derived = [0.0] * len(order)
    for slot_index, entity_number in enumerate(order):
        entity = entity_number - 1
        base = slot_index * cycle / count
        derived[entity] = (base + geometry[entity] + bank_offsets[bank_assignment[entity]]) % cycle
    return derived

def schedule_events(phase_rad: np.ndarray, config: dict, sample_rate_hz: int) -> EventTrace:
    phase_rad = np.asarray(phase_rad, dtype=np.float64)
    if phase_rad.ndim != 1 or phase_rad.size == 0 or not np.all(np.isfinite(phase_rad)):
        raise ValueError("phase_rad must be a finite nonempty vector")
    cycle_deg = cycle_degrees(config)
    phases_deg = np.asarray(derive_event_phase_deg(config), dtype=np.float64)
    banks = np.asarray(unwrap(config, "bank_assignment"), dtype=np.int64)
    crank_deg = phase_rad * 180.0 / np.pi
    sample_indices: list[int] = []
    entity_indices: list[int] = []
    exact_phases: list[float] = []
    for entity, offset in enumerate(phases_deg):
        first = int(np.floor((crank_deg[0] - offset) / cycle_deg))
        last = int(np.floor((crank_deg[-1] - offset) / cycle_deg))
        for cycle in range(first, last + 1):
            target_deg = cycle * cycle_deg + float(offset)
            if target_deg < crank_deg[0] or target_deg > crank_deg[-1]:
                continue
            sample = int(np.searchsorted(crank_deg, target_deg, side="left"))
            if 0 <= sample < phase_rad.size:
                sample_indices.append(sample)
                entity_indices.append(entity)
                exact_phases.append(target_deg * np.pi / 180.0)
    order = np.argsort(np.asarray(sample_indices), kind="stable")
    samples = np.asarray(sample_indices, dtype=np.int64)[order]
    entities = np.asarray(entity_indices, dtype=np.int64)[order]
    exact = np.asarray(exact_phases, dtype=np.float64)[order]
    return EventTrace(samples, exact, entities, banks[entities], int(samples.size))
