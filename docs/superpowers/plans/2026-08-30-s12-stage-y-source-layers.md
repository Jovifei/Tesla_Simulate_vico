# S12 Stage Y Source Layers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Hellcat Stage Y on the existing persistent event-domain engine: make the 16 unreachable parameters actually move post-PTR PCM, then add fixture HarmonicTimbreMap, a real cycle-sync P4 renderer, state transients, and a clean-room DC/dP/warmup chain, ending in a listen package.

**Architecture:** Keep `PersistentEventDomainEngine` and frozen PTR. Sequence Y1→Y6. Synthetic cycle fixtures only. Do not copy Engine-Sim/ignis C++, GTA audio, or CC BY-NC PTR weights.

**Tech Stack:** Python 3, numpy, scipy (`RegularGridInterpolator` already used), pytest, existing S12 `acoustic_identity_v015` packages.

**Spec:** `docs/superpowers/specs/2026-08-30-s12-stage-y-source-layers-design.md`\
**Baseline branch HEAD (includes spec):** `eda461e` on `agent/s12-stage-x-r2-engineering-selection`

---

## File map

Create:

- `tools/sound_sim/s12/acoustic_identity_v015/stage_y/__init__.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_y/fixture_cycles.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_y/harmonic_map_fit.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_y/cycle_sync_resynth.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_y/state_transients.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_y/audio_chain_dp.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_y/package.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_harmonic_map.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_cycle_sync.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_transients.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_dp_chain.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_package.py`
- `tasks/reports/runtime/s12-stage-y/execution_state.json`
- `tasks/reports/runtime/s12-stage-y/EXECUTION_RESUME.md`

Modify:

- `tools/sound_sim/s12/acoustic_identity_v015/event_domain/crank_phase_pll.py` — Y1 inertia/governor audible
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py` — mix omega ripple, afterfire trigger, monitor, Y3–Y5 hooks
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/timbre_map.py` — load fitted JSON; mix scales must change SHA
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py` — real P4 renderer
- `tools/sound_sim/s12/acoustic_identity_v015/stage_x/search_parameters.py` — only if a target metric is identically zero (e.g. roughness); prefer PCM-side fixes first
- `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/` — Stage Y hosted blocks

Do not modify FVM/HLLC/PTR math, Track-P, Android, ESP32, `legacy_v015` defaults, or real R1/R2/R3 files.

Working directory after Task 0:

`E:\Tesla_speed\worktrees\s12-stage-y-source-layers`

Pytest prefix (from that worktree):

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_<name>.py -q
```

---

### Task 0: Worktree and execution ledger

**Files:**

- Create: `E:\Tesla_speed\worktrees\s12-stage-y-source-layers` (git worktree)
- Create: `tasks/reports/runtime/s12-stage-y/execution_state.json`
- Create: `tasks/reports/runtime/s12-stage-y/EXECUTION_RESUME.md`

- [ ] **Step 1: Create the Stage Y worktree from the spec commit**

```
cd E:\Tesla_speed\worktrees\s12-stage-x-r2-engineering-selection
git fetch --all --prune
git worktree add -b agent/s12-stage-y-source-layers-and-reachability E:\Tesla_speed\worktrees\s12-stage-y-source-layers eda461e
```

Expected: new branch at `eda461e`, worktree path exists, `git log -1 --oneline` shows `docs(s12): add Stage Y source-layers design spec`.

- [ ] **Step 2: Write the execution ledger**

In the new worktree, write `tasks/reports/runtime/s12-stage-y/execution_state.json`:

```json
{
  "schema": "s12.stage_y.continuous_execution.v1",
  "base_stage_x_sha": "eda461e",
  "current_branch": "agent/s12-stage-y-source-layers-and-reachability",
  "worktree": "E:/Tesla_speed/worktrees/s12-stage-y-source-layers",
  "phase_order": ["Y0_SETUP", "Y1_REACHABILITY", "Y2_HARMONIC_MAP", "Y3_CYCLE_SYNC_P4", "Y4_TRANSIENTS", "Y5_DP_CHAIN", "Y6_AUDITION"],
  "current_phase": "Y0_SETUP",
  "phases": {
    "Y0_SETUP": {"status": "IN_PROGRESS"}
  },
  "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction"
}
```

Write `EXECUTION_RESUME.md` with HEAD, current phase, next command, and “do not restart Stage V”.

- [ ] **Step 3: Commit**

```
git add tasks/reports/runtime/s12-stage-y/execution_state.json tasks/reports/runtime/s12-stage-y/EXECUTION_RESUME.md
git commit -m "chore(s12): start stage y execution ledger"
```

---

### Task 1: Y1 failing tests — inertia, governor, attenuation spread

**Files:**

- Create: `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py`
- Modify later: `event_domain/crank_phase_pll.py`, `stage_w/persistent_engine.py`

Root cause to encode in tests: `CrankPhasePLL` uses `tracking_torque = 96.0 * sync_error` in `measured_rpm`, which glues omega to the trace so `crank_inertia` and `idle_governor` do not move post-PTR metrics. `_scale_spread` on equal `per_path_attenuation` is a no-op.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import hashlib
import copy

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.search_parameters import (
    PARAMETER_REACHABLE,
    apply_parameters,
    hellcat_search_parameters,
    run_parameter_reachability,
)


def _sha(pcm: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(pcm, dtype=np.float64).tobytes()).hexdigest()


def _render(config, architecture: str, scene: str, duration_s: float = 2.0):
    trace = build_hellcat_bakeoff_trace(scene, duration_s)
    settings = {
        "P2H": {"path_model": "waveguide_v1", "forced_induction_model": "harmonic_v1"},
        "P3": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"},
    }[architecture]
    engine = PersistentEventDomainEngine(copy.deepcopy(config), 48000, 960, ptr_enabled=True, **settings)
    return engine.process_with_trace(
        {"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2}
    )


def test_crank_inertia_changes_post_ptr_sha_on_idle() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"crank_inertia": 0.24}, parameters)
    high = apply_parameters(base, {"crank_inertia": 0.44}, parameters)
    a = _render(low, "P2H", "hot_idle_20s", 2.0)
    b = _render(high, "P2H", "hot_idle_20s", 2.0)
    assert a.post_ptr_raw is not None and b.post_ptr_raw is not None
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_idle_governor_changes_post_ptr_sha_on_idle() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"idle_governor": 0.15}, parameters)
    high = apply_parameters(base, {"idle_governor": 0.29}, parameters)
    a = _render(low, "P2H", "hot_idle_20s", 2.0)
    b = _render(high, "P2H", "hot_idle_20s", 2.0)
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_primary_attenuation_spread_changes_post_ptr_sha() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"primary_attenuation_spread": 0.75}, parameters)
    high = apply_parameters(base, {"primary_attenuation_spread": 1.25}, parameters)
    a = _render(low, "P2H", "full_load_acceleration", 2.0)
    b = _render(high, "P2H", "full_load_acceleration", 2.0)
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_crank_inertia_changes_post_ptr_sha_on_idle tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_idle_governor_changes_post_ptr_sha_on_idle tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_primary_attenuation_spread_changes_post_ptr_sha -q
```

Expected: FAIL, SHA equal (or assertion on None).

- [ ] **Step 3: Implement the minimal PLL and mix fixes**

In `crank_phase_pll.py`, keep `measured_rpm` but scale tracking by inertia so it cannot hide governor/inertia. Replace the tracking line:

```python
tracking_gain = 12.0 / max(inertia, 0.05)
tracking_torque = tracking_gain * sync_error if self.mode == "measured_rpm" else 0.0
governor_torque = governor * 0.35 * max(target, 1.0)
```

Do not remove measured-RPM soft tracking. Do not change frozen PTR.

In `persistent_engine.py` `_process_frame`, replace the tiny mechanical line so omega ripple is audible:

```python
mechanical = (
    0.010 * np.sin(phase * 6.0 + 0.2) * (0.35 + 0.65 * load)
    + 0.003 * phase_block.torque_ripple
    + 0.045 * omega_ripple / max(float(np.mean(np.abs(rpm)) * 2.0 * np.pi / 60.0), 1.0)
)
```

In `search_parameters.py` `_scale_spread`, if `np.allclose(values, mean)`, apply an alternating spread so equal arrays still change:

```python
def _scale_spread(config: dict[str, Any], key: str, spread: float) -> None:
    values = np.asarray(unwrap(config, key), dtype=np.float64)
    mean = float(np.mean(values))
    if np.allclose(values, mean):
        pattern = np.array([1.0 if index % 2 == 0 else -1.0 for index in range(values.size)], dtype=np.float64)
        values = mean * (1.0 + 0.08 * pattern)
    _set_parameter(config, key, list(mean + (values - mean) * spread))
```

- [ ] **Step 4: Re-run the three tests**

Same pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```
git add tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py tools/sound_sim/s12/acoustic_identity_v015/event_domain/crank_phase_pll.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py tools/sound_sim/s12/acoustic_identity_v015/stage_x/search_parameters.py
git commit -m "fix(s12): make inertia governor and header spread move hellcat pcm"
```

---

### Task 2: Y1 failing tests — blower, boost, afterfire, monitor

**Files:**

- Modify: `tests/test_s12_stage_y_reachability.py`
- Modify: `stage_w/timbre_map.py`, `stage_w/persistent_engine.py` (`_schedule_afterfire`, `_monitor`)

- [ ] **Step 1: Append failing tests**

```python
def test_blower_sideband_mix_changes_p3_post_ptr_sha() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"blower_sideband_mix": 0.70}, parameters)
    high = apply_parameters(base, {"blower_sideband_mix": 1.30}, parameters)
    a = _render(low, "P3", "full_load_acceleration", 2.0)
    b = _render(high, "P3", "full_load_acceleration", 2.0)
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_afterfire_energy_changes_sha_on_eligible_scene() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"afterfire_energy": 0.04}, parameters)
    high = apply_parameters(base, {"afterfire_energy": 0.08}, parameters)
    a = _render(low, "P3", "afterfire_eligible", 2.5)
    b = _render(high, "P3", "afterfire_eligible", 2.5)
    assert int(a.diagnostics["afterfire_event_count"]) >= 1
    assert int(b.diagnostics["afterfire_event_count"]) >= 1
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_afterfire_ineligible_stays_zero() -> None:
    base = load_config("hellcat_v1")
    block = _render(base, "P3", "afterfire_ineligible", 2.5)
    assert int(block.diagnostics["afterfire_event_count"]) == 0


def test_monitor_max_makeup_changes_monitor_sha() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"monitor_max_makeup": 6.0}, parameters)
    high = apply_parameters(base, {"monitor_max_makeup": 12.0}, parameters)
    a = _render(low, "P2H", "hot_idle_20s", 2.0)
    b = _render(high, "P2H", "hot_idle_20s", 2.0)
    assert _sha(a.monitor_pcm) != _sha(b.monitor_pcm)
```

- [ ] **Step 2: Run to verify fail**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_blower_sideband_mix_changes_p3_post_ptr_sha tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_afterfire_energy_changes_sha_on_eligible_scene tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_monitor_max_makeup_changes_monitor_sha -q
```

Expected: FAIL until wiring is fixed. Afterfire may show `afterfire_event_count == 0` because `_schedule_afterfire` requires `d_throttle < -0.8` computed from last-block vs this-block; a 2.5 s eligible trace must actually cross that threshold inside `process_with_trace`.

- [ ] **Step 3: Implement afterfire, mix, and monitor consumption**

In `timbre_map.py`, apply mixes to the harmonic stem as well as the extra stems so SHA cannot stay identical:

```python
harmonic = harmonic * (0.65 + 0.35 * sideband_mix)
```

Keep existing sideband/broadband/casing scaling.

In `_schedule_afterfire`, compute `d_throttle` from the incoming block’s throttle versus `_last_throttle` **and** from in-block throttle gradient if the bakeoff scene encodes lift inside one `process_with_trace`. If `scene` throttle already drops across frames, `process_with_trace` must pass per-frame state (it already does). Confirm `build_hellcat_bakeoff_trace("afterfire_eligible")` produces a frame-to-frame d_throttle below -0.8; if not, increase the trace drop in `bakeoff.py` for `afterfire_eligible` only, without changing `afterfire_ineligible`.

In `_monitor`, apply `max_makeup_db` as a hard ceiling on `_monitor_gain_db` **before** the RMS servo, and initialize `_monitor_gain_db` to 0 so idle scenes with makeup 6 vs 12 differ on the first blocks:

```python
self._monitor_gain_db = float(np.clip(self._monitor_gain_db, self._monitor_max_attenuation_db, self._monitor_max_makeup_db))
```

For boost_attack/boost_release: `_advance_boost` must consume `timbre_mixes.boost_attack_s` / `boost_release_s`. If those keys only affect `render_timbre_map`’s inner smoother, also pass them into `_advance_boost` so a varying boost_target on `throttle_tip_in` changes SHA.

- [ ] **Step 4: Re-run Task 2 tests**

Expected: PASS, and `test_afterfire_ineligible_stays_zero` still PASS.

- [ ] **Step 5: Commit**

```
git add tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/timbre_map.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py
git commit -m "fix(s12): consume blower afterfire and monitor parameters in hellcat pcm"
```

---

### Task 3: Y1 full 16-parameter reachability receipt

**Files:**

- Modify: `tests/test_s12_stage_y_reachability.py`
- Create: `tasks/reports/runtime/s12-stage-y/y1_reachability/parameter_reachability.json` (generated)

- [ ] **Step 1: Write the suite gate test**

```python
def test_y1_named_parameters_are_reachable(tmp_path) -> None:
    required = {
        "crank_inertia", "idle_governor", "primary_attenuation_spread",
        "blower_sideband_mix", "blower_broadband_mix", "blower_casing_mix",
        "boost_attack", "boost_release", "bypass_threshold",
        "afterfire_reservoir_rate", "afterfire_ignition_delay", "afterfire_location_mix",
        "afterfire_energy", "monitor_attack", "monitor_release", "monitor_max_makeup",
    }
    summary = run_parameter_reachability(tmp_path, traces=[], architecture="P2H")
    by_name = {row["parameter"]: row for row in summary["results"]}
    deferred = []
    for name in required:
        row = by_name[name]
        if row["status"] != PARAMETER_REACHABLE:
            if name in {"blower_sideband_mix", "blower_broadband_mix", "blower_casing_mix", "boost_attack", "boost_release", "bypass_threshold"} and row.get("probe_architecture") == "P3":
                deferred.append(name)
            else:
                raise AssertionError(f"{name} not reachable: {row['reason']}")
    assert deferred == [] or all(by_name[name]["status"] == PARAMETER_REACHABLE for name in deferred)
```

The spec allows `DEFERRED_TO_Y2` only when the unique consumer is the fitted map. After Task 2, blower mixes must already be reachable on P3 with the current table. This test must require all 16 `PARAMETER_REACHABLE`. Do not weaken it.

- [ ] **Step 2: Run it**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_y1_named_parameters_are_reachable -q
```

Expected: PASS after Tasks 1–2. If a name still fails, fix that consumer in the same task; do not skip.

- [ ] **Step 3: Copy the generated JSON into the runtime ledger and mark Y1 PASS**

Update `execution_state.json` `current_phase` to `Y2_HARMONIC_MAP`, Y1 status PASS, commit SHA.

- [ ] **Step 4: Commit**

```
git add tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py tasks/reports/runtime/s12-stage-y
git commit -m "test(s12): prove sixteen hellcat search parameters reachable"
```

---

### Task 4: Y2 fixture cycles and HarmonicTimbreMap fit

**Files:**

- Create: `stage_y/__init__.py`, `stage_y/fixture_cycles.py`, `stage_y/harmonic_map_fit.py`
- Create: `tests/test_s12_stage_y_harmonic_map.py`
- Modify: `stage_w/timbre_map.py`, `persistent_engine.py` load path

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path
import json
import hashlib
import copy
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.fixture_cycles import synthesize_hellcat_cycle_bank
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.harmonic_map_fit import fit_harmonic_map, MAP_SCHEMA
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.timbre_map import TimbreMap4D


def test_fixture_bank_is_deterministic_and_not_pcm_in_map(tmp_path) -> None:
    bank = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    assert set(bank["rpm_hz"].keys()) >= {1200.0, 2000.0, 3000.0}
    again = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    assert hashlib.sha256(bank["cycles"][1200.0].tobytes()).hexdigest() == hashlib.sha256(again["cycles"][1200.0].tobytes()).hexdigest()
    mapped = fit_harmonic_map(bank, vehicle_id="hellcat")
    assert mapped["schema"] == MAP_SCHEMA
    assert mapped["source"] == "synthetic_fixture"
    assert "pcm" not in mapped
    text = json.dumps(mapped)
    assert "int16" not in text
    path = tmp_path / "hellcat_timbre_map.json"
    path.write_text(json.dumps(mapped), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["vehicle_id"] == "hellcat"


def test_hellcat_runtime_rejects_formula_default_when_map_required() -> None:
    config = load_config("hellcat_v1")
    config["require_fitted_timbre_map"] = True
    try:
        PersistentEventDomainEngine(config, 48000, 960, ptr_enabled=True, path_model="waveguide_v1", forced_induction_model="timbre_map_v1")
        raised = False
    except ValueError as error:
        raised = "fitted" in str(error).lower() or "timbre" in str(error).lower()
    assert raised is True


def test_fitted_map_changes_sha_versus_formula(tmp_path) -> None:
    bank = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    mapped = fit_harmonic_map(bank, vehicle_id="hellcat")
    formula = load_config("hellcat_v1")
    fitted = copy.deepcopy(formula)
    fitted["timbre_map"] = {
        "rpm_axis": mapped["rpm_axis"],
        "load_axis": mapped["load_axis"],
        "boost_axis": mapped["boost_axis"],
        "order_axis": mapped["order_axis"],
        "values": mapped["amplitude"],
    }
    trace = build_hellcat_bakeoff_trace("steady_2000rpm", 1.5)
    a = PersistentEventDomainEngine(formula, 48000, 960, ptr_enabled=True, path_model="waveguide_v1", forced_induction_model="timbre_map_v1").process_with_trace({"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2})
    b = PersistentEventDomainEngine(fitted, 48000, 960, ptr_enabled=True, path_model="waveguide_v1", forced_induction_model="timbre_map_v1").process_with_trace({"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2})
    assert hashlib.sha256(a.post_ptr_raw.tobytes()).hexdigest() != hashlib.sha256(b.post_ptr_raw.tobytes()).hexdigest()
```

- [ ] **Step 2: Run to verify fail**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_harmonic_map.py -q
```

Expected: FAIL, `stage_y` import missing.

- [ ] **Step 3: Implement fixture + fit + engine guard**

`fixture_cycles.py`: deterministic stereo cycles. For each RPM in `{1200, 2000, 3000, 4500}`, build one engine cycle at 48000 Hz using firing order from `load_config("hellcat_v1")` — pulse train of raised-cosine bursts at cylinder events plus low-level noise with `np.random.default_rng(20260830)`. Return `{"rpm_hz": ..., "cycles": {rpm: ndarray(n,2)}, "sample_rate_hz": 48000}`.

`harmonic_map_fit.py`:

```python
MAP_SCHEMA = "s12.stage_y.harmonic_timbre_map.v1"

def fit_harmonic_map(bank: dict, vehicle_id: str = "hellcat") -> dict:
    sample_rate = int(bank["sample_rate_hz"])
    rpm_axis = np.array(sorted(bank["cycles"].keys()), dtype=np.float64)
    load_axis = np.array([0.2, 0.6, 1.0], dtype=np.float64)
    boost_axis = np.array([0.0, 0.5, 1.0], dtype=np.float64)
    order_axis = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
    amplitude = np.zeros((rpm_axis.size, load_axis.size, boost_axis.size, order_axis.size), dtype=np.float64)
    for rpm_index, rpm in enumerate(rpm_axis):
        cycle = np.asarray(bank["cycles"][float(rpm)], dtype=np.float64)
        mono = cycle.mean(axis=1)
        spectrum = np.abs(np.fft.rfft(mono))
        freqs = np.fft.rfftfreq(mono.size, 1.0 / sample_rate)
        firing_hz = float(rpm) / 60.0 * 4.0
        for order_index, order in enumerate(order_axis):
            target = firing_hz * float(order)
            bin_index = int(np.argmin(np.abs(freqs - target)))
            base = float(spectrum[bin_index])
            for load_index, load in enumerate(load_axis):
                for boost_index, boost in enumerate(boost_axis):
                    amplitude[rpm_index, load_index, boost_index, order_index] = base * (0.4 + 0.6 * load) * (0.5 + 0.5 * boost)
    fixture_sha = hashlib.sha256(b"".join(np.asarray(bank["cycles"][float(rpm)]).tobytes() for rpm in rpm_axis)).hexdigest()
    return {
        "schema": MAP_SCHEMA,
        "vehicle_id": vehicle_id,
        "source": "synthetic_fixture",
        "rpm_axis": rpm_axis.tolist(),
        "load_axis": load_axis.tolist(),
        "boost_axis": boost_axis.tolist(),
        "order_axis": order_axis.tolist(),
        "amplitude": amplitude.tolist(),
        "fixture_sha256": fixture_sha,
    }
```

Need `import hashlib` in that module.

For each RPM cycle, FFT, collect magnitudes at orders 1..5 of firing frequency (`rpm/60 * 4` for Hellcat V8). Fill `amplitude` with shape `(n_rpm, n_load, n_boost, n_order)`. Use three load points `[0.2, 0.6, 1.0]` and boost `[0.0, 0.5, 1.0]` by scaling the same cycle (fixture-only). Include `fixture_sha256`, `source="synthetic_fixture"`. No PCM field.

`persistent_engine.py` `__init__`: if `config.get("require_fitted_timbre_map")` and (`timbre_map` missing or equals `TimbreMap4D.default()` axes/values), raise `ValueError("fitted HarmonicTimbreMap required")`. Hellcat bake-off P3 must set `require_fitted_timbre_map` after Y2.

Store a generated map at `tools/sound_sim/s12/acoustic_identity_v015/stage_y/data/hellcat_fixture_timbre_map.json` (JSON only).

- [ ] **Step 4: Re-run harmonic map tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add tools/sound_sim/s12/acoustic_identity_v015/stage_y tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_harmonic_map.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py
git commit -m "feat(s12): fit hellcat harmonic timbre map from synthetic cycles"
```

---

### Task 5: Y3 cycle-sync P4 renderer

**Files:**

- Create: `stage_y/cycle_sync_resynth.py`
- Create: `tests/test_s12_stage_y_cycle_sync.py`
- Modify: `stage_w/bakeoff.py` P4 placeholder, `persistent_engine.py` mix hook

- [ ] **Step 1: Write failing tests**

```python
import hashlib
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.fixture_cycles import synthesize_hellcat_cycle_bank
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.cycle_sync_resynth import CycleSyncResampler
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import PLACEHOLDER_RECORDS, RENDERABLE_ARCHITECTURES, _render_architecture
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace


def test_p4_is_not_a_placeholder() -> None:
    assert "P4" not in PLACEHOLDER_RECORDS
    assert "P4" in RENDERABLE_ARCHITECTURES


def test_cycle_sync_shares_phase_and_has_no_block_click() -> None:
    bank = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    resampler = CycleSyncResampler(bank, sample_rate_hz=48000)
    phase = np.linspace(0.0, 40.0 * np.pi, 9600)
    rpm = np.full(9600, 2000.0)
    audio = resampler.render(phase, rpm)
    assert audio.shape == (9600, 2)
    assert np.all(np.isfinite(audio))
    metrics = block_boundary_click_metrics(audio, 960)
    assert metrics["max_abs_jump"] < 0.35
    resampler2 = CycleSyncResampler(bank, sample_rate_hz=48000)
    assert hashlib.sha256(resampler2.render(phase, rpm).tobytes()).hexdigest() == hashlib.sha256(audio.tobytes()).hexdigest()


def test_p4_bakeoff_render_differs_from_p2h() -> None:
    trace = build_hellcat_bakeoff_trace("steady_2000rpm", 1.5)
    p2h_raw, p2h_post, _p2h_mon, _p2h_diag = _render_architecture("P2H", trace)
    p4_raw, p4_post, _p4_mon, _p4_diag = _render_architecture("P4", trace)
    assert hashlib.sha256(p4_post.tobytes()).hexdigest() != hashlib.sha256(p2h_post.tobytes()).hexdigest()
```

If `_render_architecture` is not public, call the same helper bakeoff uses. Adjust the test to the real function name in `bakeoff.py` (`_render_architecture` exists).

- [ ] **Step 2: Run to verify fail**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_cycle_sync.py -q
```

Expected: FAIL, P4 still in `PLACEHOLDER_RECORDS`.

- [ ] **Step 3: Implement CycleSyncResampler and bakeoff P4**

```python
class CycleSyncResampler:
    def __init__(self, bank: dict, sample_rate_hz: int = 48000) -> None:
        self.sample_rate_hz = int(sample_rate_hz)
        self.rpms = np.array(sorted(bank["cycles"].keys()), dtype=np.float64)
        self.cycles = [np.asarray(bank["cycles"][float(rpm)], dtype=np.float64) for rpm in self.rpms]
        self.phase_index = 0.0

    def render(self, phase: np.ndarray, rpm: np.ndarray) -> np.ndarray:
        phase = np.asarray(phase, dtype=np.float64)
        rpm = np.asarray(rpm, dtype=np.float64)
        out = np.zeros((phase.size, 2), dtype=np.float64)
        for index, (phase_value, rpm_value) in enumerate(zip(phase, rpm)):
            lo = int(np.searchsorted(self.rpms, rpm_value, side="right") - 1)
            lo = int(np.clip(lo, 0, self.rpms.size - 1))
            hi = int(np.clip(lo + 1, 0, self.rpms.size - 1))
            mix = 0.0 if lo == hi else float(np.clip((rpm_value - self.rpms[lo]) / max(self.rpms[hi] - self.rpms[lo], 1e-9), 0.0, 1.0))
            gain_lo = np.cos(mix * np.pi / 2.0)
            gain_hi = np.sin(mix * np.pi / 2.0)
            sample_lo = self._sample(self.cycles[lo], phase_value)
            sample_hi = self._sample(self.cycles[hi], phase_value)
            out[index] = gain_lo * sample_lo + gain_hi * sample_hi
        return out

    def _sample(self, cycle: np.ndarray, phase_rad: float) -> np.ndarray:
        position = (phase_rad / (2.0 * np.pi)) * cycle.shape[0]
        wrapped = position % cycle.shape[0]
        left = int(np.floor(wrapped)) % cycle.shape[0]
        right = (left + 1) % cycle.shape[0]
        fraction = wrapped - np.floor(wrapped)
        return (1.0 - fraction) * cycle[left] + fraction * cycle[right]
```

In `persistent_engine.py`, add `cycle_sync_model: str = "off"` constructor flag. When `"fixture_v1"`, mix `0.35 * CycleSyncResampler.render(...)` into `raw` after combustion and before PTR. P4 bakeoff settings: `path_model="waveguide_v1"`, `forced_induction_model="timbre_map_v1"`, `cycle_sync_model="fixture_v1"`.

Remove P4 from `PLACEHOLDER_RECORDS`. Add `"P4"` to `RENDERABLE_ARCHITECTURES`. Update `_render_architecture` `settings` dict to include P4 and P3DP.

- [ ] **Step 4: Re-run cycle-sync tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add tools/sound_sim/s12/acoustic_identity_v015/stage_y/cycle_sync_resynth.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_cycle_sync.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py
git commit -m "feat(s12): render hellcat p4 from fixture cycle-synchronous grains"
```

---

### Task 6: Y4 state transients

**Files:**

- Create: `stage_y/state_transients.py`
- Create: `tests/test_s12_stage_y_transients.py`
- Modify: `persistent_engine.py`

- [ ] **Step 1: Write failing tests**

```python
import hashlib
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.state_transients import StateTransientMixer
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace, _render_architecture


def test_equal_power_crossfade_preserves_power() -> None:
    mixer = StateTransientMixer(sample_rate_hz=48000)
    a = np.ones((960, 2))
    b = np.ones((960, 2)) * 2.0
    out = mixer.equal_power_crossfade(a, b, mix=0.5)
    power = float(np.mean(np.square(out)))
    assert abs(power - 0.5 * (1.0 + 4.0)) < 0.15


def test_tip_in_and_shift_stems_change_sha() -> None:
    tip = build_hellcat_bakeoff_trace("throttle_tip_in", 2.0)
    shift = build_hellcat_bakeoff_trace("gear_shift", 2.0)
    _raw_off, post_off, _mon_off, _diag_off = _render_architecture("P3", tip)
    _raw_on, post_on, _mon_on, diag_on = _render_architecture("P5", tip)
    assert hashlib.sha256(post_on.tobytes()).hexdigest() != hashlib.sha256(post_off.tobytes()).hexdigest()
    _sraw, spost, _smon, sdiag = _render_architecture("P5", shift)
    _p3s, p3spost, _p3sm, _ = _render_architecture("P3", shift)
    assert int(sdiag.get("transient_shift_count", 0)) >= 1 or hashlib.sha256(spost.tobytes()).hexdigest() != hashlib.sha256(p3spost.tobytes()).hexdigest()
```

- [ ] **Step 2: Run to verify fail**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_transients.py -q
```

If `_render_architecture("P3", tip)` already differs from P5 because of today's `_synthetic_transient_residual`, still replace that helper with `StateTransientMixer` and require `diagnostics["transient_model"] == "state_v1"`. Do not keep the old one-shot residual as the Y4 implementation.

- [ ] **Step 3: Implement mixer**

`StateTransientMixer`: hysteresis on throttle (enter tip-in when d_throttle > 0.4 and stay until d_throttle < 0.1). One-shot raised-cosine burst for shift when rpm drops > 800 rpm in < 80 ms. BOV when boost falls while throttle < 0.2. Mix after collector, before PTR, via `external_transient` already on `process_with_trace` or a new engine flag `transient_model="state_v1"` used by P5.

`equal_power_crossfade`:

```python
def equal_power_crossfade(self, a, b, mix: float) -> np.ndarray:
    mix = float(np.clip(mix, 0.0, 1.0))
    gain_a = np.cos(mix * np.pi / 2.0)
    gain_b = np.sin(mix * np.pi / 2.0)
    return gain_a * a + gain_b * b
```

Do not add pops onto post-PTR PCM.

- [ ] **Step 4: Re-run**

Expected: PASS. Re-run `test_afterfire_ineligible_stays_zero`.

- [ ] **Step 5: Commit**

```
git add tools/sound_sim/s12/acoustic_identity_v015/stage_y/state_transients.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_transients.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py
git commit -m "feat(s12): add hellcat state transients with equal-power crossfade"
```

---

### Task 7: Y5 DC / dP / warmup chain

**Files:**

- Create: `stage_y/audio_chain_dp.py`
- Create: `tests/test_s12_stage_y_dp_chain.py`
- Modify: `persistent_engine.py`

- [ ] **Step 1: Write failing tests**

```python
import hashlib
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.audio_chain_dp import PressureAudioChain
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace, _render_architecture


def test_warmup_then_stream_matches_oneshot_within_tolerance() -> None:
    chain = PressureAudioChain(sample_rate_hz=48000, delay_samples=64.0)
    noise = np.random.default_rng(0).standard_normal((48000, 2)) * 0.01
    chain.warmup(noise[: 4800])
    streamed = []
    for index in range(0, 9600, 960):
        streamed.append(chain.process(noise[index : index + 960]))
    streamed = np.concatenate(streamed, axis=0)
    oneshot = PressureAudioChain(sample_rate_hz=48000, delay_samples=64.0)
    oneshot.warmup(noise[: 4800])
    full = oneshot.process(noise[: 9600])
    assert np.max(np.abs(streamed - full)) < 1e-9
    metrics = block_boundary_click_metrics(streamed, 960)
    assert metrics["max_abs_jump"] < 0.35


def test_dp_chain_ablation_changes_sha() -> None:
    trace = build_hellcat_bakeoff_trace("steady_2000rpm", 1.5)
    _off_raw, off_post, _off_mon, _off_d = _render_architecture("P3", trace)
    _on_raw, on_post, _on_mon, _on_d = _render_architecture("P3DP", trace)
    assert hashlib.sha256(on_post.tobytes()).hexdigest() != hashlib.sha256(off_post.tobytes()).hexdigest()
```

If adding architecture name `P3DP` is too wide, use a boolean `audio_chain="dp_v1"` on P3 via bakeoff settings instead, and compare two `_render_architecture` calls with that flag. Pick one name and use it in bakeoff and this test. Recommended: keep P3 default off; Y6 candidate F uses `audio_chain="dp_v1"`.

- [ ] **Step 2: Run to verify fail**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_dp_chain.py -q
```

Expected: FAIL, missing `PressureAudioChain`.

- [ ] **Step 3: Implement clean-room chain**

```python
class PressureAudioChain:
    def __init__(self, sample_rate_hz: int, delay_samples: float) -> None:
        self.dc = 0.0
        self.prev = np.zeros(2)
        self.delay_samples = float(delay_samples)
        self.history_length = max(int(np.ceil(delay_samples)) + 1, 2)
        self.history = np.zeros((self.history_length, 2), dtype=np.float64)
        self.warm = False

    def _filter(self, block: np.ndarray) -> np.ndarray:
        x = np.asarray(block, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != 2:
            raise ValueError("PressureAudioChain expects stereo")
        self.dc = 0.995 * self.dc + 0.005 * float(np.mean(x))
        y = x - self.dc
        dp = np.diff(y, axis=0, prepend=self.prev.reshape(1, 2))
        self.prev = y[-1].copy()
        mixed = y + 0.35 * dp
        joined = np.concatenate((self.history, mixed), axis=0)
        positions = self.history_length + np.arange(mixed.shape[0], dtype=np.float64) - self.delay_samples
        left = np.floor(positions).astype(np.int64)
        fraction = (positions - left).reshape(-1, 1)
        left_clipped = np.clip(left, 0, joined.shape[0] - 1)
        right_clipped = np.clip(left + 1, 0, joined.shape[0] - 1)
        delayed = joined[left_clipped] * (1.0 - fraction) + joined[right_clipped] * fraction
        self.history = joined[-self.history_length :].copy()
        return 0.65 * mixed + 0.35 * delayed

    def warmup(self, block: np.ndarray) -> None:
        self._filter(np.asarray(block, dtype=np.float64))
        self.warm = True

    def process(self, block: np.ndarray) -> np.ndarray:
        if not self.warm:
            self.warmup(np.zeros((max(int(0.1 * 48000), 1), 2), dtype=np.float64))
        return self._filter(np.asarray(block, dtype=np.float64))
```

Do not copy Engine-Sim or ignis source. Apply the chain to collector stereo **before** PTR when `audio_chain == "dp_v1"`. If `warm` is False at first audible block, run 100 ms of zeros through `process` internally (warmup) then process the real block.

- [ ] **Step 4: Re-run dp tests plus Stage W click test if present**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_dp_chain.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py -q --ignore-glob=*slow*
```

Expected: PASS. If the persistent engine file has a 3000×20 ms test marked slow, do not skip the click contract tests.

- [ ] **Step 5: Commit**

```
git add tools/sound_sim/s12/acoustic_identity_v015/stage_y/audio_chain_dp.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_dp_chain.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py
git commit -m "feat(s12): add clean-room dc dp warmup chain before frozen ptr"
```

---

### Task 8: Y6 Hellcat listen package

**Files:**

- Create: `stage_y/package.py`
- Create: `tests/test_s12_stage_y_package.py`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path
import json
import wave

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.package import build_hellcat_layer_package, validate_layer_package

SCENES = (
    "hot_idle_20s", "steady_1200rpm", "steady_2000rpm", "steady_3000rpm",
    "throttle_tip_in", "full_load_acceleration", "gear_shift", "high_rpm_lift",
    "afterfire_eligible", "afterfire_ineligible", "idle_return",
)
STEMS = ("parent", "y1_event", "y2_map", "y3_p4", "y4_transients", "y5_dp", "monitor")


def test_package_writes_required_wavs_and_distinct_parent_candidate(tmp_path) -> None:
    root = tmp_path / "pkg"
    manifest = build_hellcat_layer_package(root, long_window=False, duration_s=0.8)
    errors = validate_layer_package(root)
    assert errors == []
    for scene in SCENES:
        for stem in STEMS:
            wav = root / scene / f"{stem}.wav"
            assert wav.is_file(), wav
            with wave.open(str(wav), "rb") as handle:
                assert handle.getnframes() > 0
    assert manifest["parent_sha256"] != manifest["candidate_sha256"]
    assert "OEM" not in json.dumps(manifest)
    assert manifest["formal_status"] == "FORMAL_R1_REFERENCE_MISSING"
```

Use `duration_s=0.8` in tests so CI stays short. The real package driver uses full scene lengths from the spec.

- [ ] **Step 2: Run to verify fail**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_package.py -q
```

Expected: FAIL, missing `build_hellcat_layer_package`.

- [ ] **Step 3: Implement package builder**

Write PCM24 wavs with existing `stage_v.io.write_pcm24_wav`. Map stems to bakeoff architectures: parent=`P1`, y1_event=`P2H`, y2_map=`P3` with fitted map, y3_p4=`P4`, y4_transients=`P5`, y5_dp=`P5` plus `audio_chain="dp_v1"`, monitor=monitor of y5. Chinese `AUDITION_GUIDE_ZH.md` in the package with Timbre vs Dynamic instructions. Validator checks duration, SHA manifest, parent≠candidate, no files named like gta/fivem.

Production output path: `E:\Tesla_speed\review_packages\s12-stage-y-hellcat-layers-v1\` (outside Git). Tests use `tmp_path`.

- [ ] **Step 4: Re-run package tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add tools/sound_sim/s12/acoustic_identity_v015/stage_y/package.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_package.py
git commit -m "feat(s12): build hellcat stage y layer audition package"
```

---

### Task 9: Knowledge notes, ignis/markeasting registry, final qualification

**Files:**

- Modify: `docs/research/engine-audio-ecosystem/source_registry.json`
- Create: `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/15-Stage-Y-Status.md`
- Modify: `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/00-MOC.md`
- Create: `tasks/reports/runtime/s12-stage-y/y9_final_qualification_receipt.json` (generated)

- [ ] **Step 1: Checkout research clones outside Git**

```
cd E:\Tesla_speed\research\engine-audio-ecosystem
git clone --depth 1 https://github.com/xevrion/ignis.git
git clone --depth 1 https://github.com/markeasting/engine-audio.git
```

Read each LICENSE. Pin HEAD in `source_registry.json`. Do not add those clones to S12 Git.

- [ ] **Step 2: Write hosted Stage Y status note**

`15-Stage-Y-Status.md` with branch, HEAD, Y1–Y6 receipts, `FORMAL_R1_REFERENCE_MISSING`, `NOT_PROFILE_FREEZE_READY`. Link method-to-file mapping. Update MOC.

- [ ] **Step 3: Focused Stage Y tests then one full S12 on exact HEAD**

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_harmonic_map.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_cycle_sync.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_transients.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_dp_chain.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_package.py -q
```

Expected: all PASS.

Then once:

```
python -m pytest tools/sound_sim/s12/tests tools/sound_sim/s12/acoustic_identity_v015/tests -q
```

Record command, times, exit code, log SHA, HEAD in `y9_final_qualification_receipt.json`. Do not paste 1015 or 1205. Also `python -m compileall tools/sound_sim/s12/acoustic_identity_v015/stage_y tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py` and `git diff --check`.

If Track-P guard is in the suite, it must stay green (no frozen-file edits).

- [ ] **Step 4: Commit docs and receipts**

```
git add docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem docs/research/engine-audio-ecosystem/source_registry.json tasks/reports/runtime/s12-stage-y
git commit -m "docs(s12): record stage y layer landing and qualification receipts"
```

Default: do not push. Do not merge main. Do not open a PR.

---

## Spec coverage

| Spec section | Task |
|---|---|
| 2.1 reachability | 1–3 |
| 2.1 harmonic map | 4 |
| 2.1 P4 | 5 |
| 2.1 transients | 6 |
| 2.1 dP chain | 7 |
| 2.1 listen package | 8 |
| 4.2 worktree | 0 |
| 8 non-blocking R1 | 8 manifest `FORMAL_R1_REFERENCE_MISSING` |
| 9 final pytest | 9 |
| 10 knowledge | 9 |
| Frozen PTR/FVM | never in file map |

## Type names used throughout

`CycleSyncResampler.render(phase, rpm)`\
`fit_harmonic_map(bank, vehicle_id="hellcat")`\
`MAP_SCHEMA = "s12.stage_y.harmonic_timbre_map.v1"`\
`StateTransientMixer.equal_power_crossfade`\
`PressureAudioChain.warmup` / `process`\
`build_hellcat_layer_package` / `validate_layer_package`
