# S12 Stage W v26 Checkpointed Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed, test-covered single-architecture resume API, then complete the interrupted v26 Hellcat bake-off root without rerendering verified cases.

**Architecture:** `run_hellcat_bakeoff()` keeps its current all-or-nothing behavior. New `resume_hellcat_bakeoff()` inspects a root one architecture at a time, accepts only no-reference synthetic recovery, records an external canonical-root-bound checkpoint, uses verified P1 post-PTR PCM for candidates, stages new cases outside the strict evidence root, and emits the existing five summaries/manifest only when all five executable architectures are complete.

**Tech Stack:** Python 3.14, NumPy, pytest, existing Stage W PCM/JSON/SHA helpers.

## Global Constraints

- Worktree: `E:/Tesla_speed/worktrees/s12-stage-w-ecosystem-bakeoff`; source baseline before Task 1 is `da27914`.
- Preserve `run_hellcat_bakeoff()` signature and its non-empty-root refusal exactly.
- Preserve v25 and current v26 bytes; do not delete, copy, move or overwrite any verified v26 case.
- Resume is limited to `reference=None`; all result/checkpoint/summary selection fields are null and statuses remain `REFERENCE_TARGET_MISSING` / `REFERENCE_POINTER_ONLY`.
- `validate_bakeoff_manifest()` must remain strict: no partial root manifest and no checkpoint/staging file inside the final evidence root.
- No change to PTR/radiation, Track-P, Stage V behavior, migrations, external media, Vault, push, merge or PR.
- Each live long-window architecture render is a single bounded worker action; do not launch a second architecture or a second process while it runs.

---

### Task 1: Add fail-closed resume API with RED/GREEN tests

**Files:**

- Modify: `tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py`
- Modify: `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff.py`
- Modify: `tasks/reports/runtime/s12-stage-w/checkpoints/README.md`

**Interfaces:**

- Produces `resume_hellcat_bakeoff(output_root: str | Path, architecture: str, duration_s: float = 8.0, *, long_window: bool = False) -> dict[str, Any]`.
- Uses executable architectures `("P1", "P2", "P2H", "P3", "P5")`; `architecture` is exactly one member.
- Uses sidecar checkpoint `root.parent / "checkpoints" / f"{root.name}-{sha256(str(root.resolve()))[:16]}.resume.json"`.

- [ ] **Step 1: Write the failing tests**

Add these focused tests, importing `resume_hellcat_bakeoff` from the bakeoff module:

```python
def test_resume_bakeoff_defers_manifest_and_preserves_verified_cases(tmp_path) -> None:
    root = tmp_path / "bakeoff"
    first = resume_hellcat_bakeoff(root, "P1", duration_s=0.20)
    preserved = (root / "P1" / "hot_idle_20s" / "raw_source.wav").read_bytes()
    shutil.rmtree(root / "P1" / "complete_cycle_60s")
    (root / "P1" / "complete_cycle_60s").mkdir()
    again = resume_hellcat_bakeoff(root, "P1", duration_s=0.20)
    assert first["status"] == again["status"] == "IN_PROGRESS"
    assert (root / "P1" / "hot_idle_20s" / "raw_source.wav").read_bytes() == preserved
    assert (root / "P1" / "complete_cycle_60s" / "sha256_manifest.json").is_file()
    assert not (root / "bakeoff_manifest.json").exists()


def test_resume_bakeoff_finalizes_only_after_all_architectures(tmp_path) -> None:
    root = tmp_path / "bakeoff"
    for architecture in ("P1", "P2", "P2H", "P3"):
        result = resume_hellcat_bakeoff(root, architecture, duration_s=0.20)
        assert result["status"] == "IN_PROGRESS"
        assert not (root / "bakeoff_manifest.json").exists()
    final = resume_hellcat_bakeoff(root, "P5", duration_s=0.20)
    assert final["status"] == "REFERENCE_TARGET_MISSING"
    assert final["selected_architecture"] is None
    assert validate_bakeoff_manifest(root) == []


@pytest.mark.parametrize("mutator", ("incomplete_case", "duration", "long_window"))
def test_resume_bakeoff_rejects_bad_state_without_overwrite(tmp_path, mutator) -> None:
    root = tmp_path / "bakeoff"
    if mutator == "incomplete_case":
        case = root / "P1" / "hot_idle_20s"; case.mkdir(parents=True)
        target = case / "raw_source.wav"; target.write_bytes(b"partial")
        before = target.read_bytes()
        with pytest.raises(ValueError, match="incomplete"):
            resume_hellcat_bakeoff(root, "P1", duration_s=0.20)
        assert target.read_bytes() == before
        return
    resume_hellcat_bakeoff(root, "P1", duration_s=0.20, long_window=False)
    with pytest.raises(ValueError, match=mutator):
        resume_hellcat_bakeoff(root, "P2", duration_s=0.25 if mutator == "duration" else 0.20, long_window=mutator == "long_window")


def test_resume_candidate_uses_verified_p1_parent_without_rerender(tmp_path, monkeypatch) -> None:
    root = tmp_path / "bakeoff"
    resume_hellcat_bakeoff(root, "P1", duration_s=0.20)
    original = bakeoff_module._render_architecture
    def no_parent_rerender(architecture, trace):
        if architecture == "P1":
            raise AssertionError("candidate resume must use verified P1 PCM")
        return original(architecture, trace)
    monkeypatch.setattr(bakeoff_module, "_render_architecture", no_parent_rerender)
    result = resume_hellcat_bakeoff(root, "P2", duration_s=0.20)
    assert result["status"] == "IN_PROGRESS"
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff.py -q
```

Expected: the three added tests fail because `resume_hellcat_bakeoff` does not exist.

- [ ] **Step 3: Implement the minimal resume path**

Implement these exact responsibilities:

```python
def resume_hellcat_bakeoff(output_root, architecture, duration_s=8.0, *, long_window=False):
    root = Path(output_root).resolve()
    checkpoint = _load_or_initialize_resume_checkpoint(root, duration_s, long_window)
    verified_p1 = _inspect_architecture(root, "P1", checkpoint, allow_missing=True)
    result = _resume_one_architecture(root, architecture, duration_s, long_window, verified_p1)
    _write_resume_checkpoint_atomic(checkpoint)
    return _finalize_bakeoff_from_verified_cases(root, checkpoint) if _all_architectures_complete(root) else result
```

- `_load_or_initialize_resume_checkpoint` binds resolved root path/root id, `duration_s`, `long_window`, `reference_status="REFERENCE_POINTER_ONLY"`, `selected_architecture=None`; mismatches raise `ValueError` containing `root`, `duration`, or `long_window`.
- `_load_verified_case` requires exactly the normal eleven artifacts, exact ten-entry inner SHA inventory and recomputed hashes. It returns raw/post/monitor SHA, stored comparison, render seconds and reopened post-PTR PCM.
- `_inspect_architecture` treats no directory or an empty directory as renderable, verified-complete cases as reusable, and any other non-empty directory as `ValueError("incomplete")` without write.
- `_write_case_atomic` calls existing rendering into root-external checkpoint staging, then replaces only an absent/empty target. `_write_case` gains an optional verified P1 post-PTR argument; existing default callers retain its prior internal P1 render behavior.
- Candidate resume calls require fully verified P1 and pass its scene-matched PCM to `_write_case_atomic`.
- `_finalize_bakeoff_from_verified_cases` reconstructs the original `architectures` records from verified metrics/inner manifests, writes the same five summary JSONs and standard `bakeoff_manifest.json`, then raises if `validate_bakeoff_manifest(root)` is nonempty.
- Export the new public API from `__all__`. Document checkpoint semantics in the existing checkpoint README.

- [ ] **Step 4: Run GREEN and focused regression**

Run:

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py -q
python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015/stage_w
git diff --check
```

Expected: all tests pass, compileall exit 0, diff check exit 0.

- [ ] **Step 5: Commit source/test/documentation only**

Stage only the three Task 1 files and commit:

```text
feat(s12): add checkpointed bakeoff recovery
```

### Task 2: Complete v26 P1 only

**Files:**

- Create/modify runtime evidence only: v26 P1 empty long-cycle case and external v26 checkpoint.
- Create: `tasks/reports/runtime/s12-stage-w/logs/task6l_v26_p1_resume.*.log`

- [ ] **Step 1:** Record v25/v26 file counts and SHA of each verified P1 scene before execution.
- [ ] **Step 2:** Invoke only `resume_hellcat_bakeoff(v26_root, "P1", duration_s=0.20, long_window=True)` in one foreground monitored worker; do not start another worker.
- [ ] **Step 3:** Require `IN_PROGRESS`, P1 all 12 verified cases, no root manifest, checkpoint completed architectures `["P1"]`, and unchanged hashes for the previous eleven P1 cases.
- [ ] **Step 4:** Run the focused strict validator only to confirm it reports missing final manifest (not a false success); record result without altering evidence.

### Task 3: Complete one candidate architecture per worker

**Files:**

- Create/modify runtime evidence only: v26 P2, then P2H, then P3, then P5 case trees and external checkpoint.
- Create: `tasks/reports/runtime/s12-stage-w/logs/task6l_v26_<architecture>_resume.*.log`

- [ ] **Step 1:** For each architecture in exact order `P2`, `P2H`, `P3`, `P5`, use a separate worker and invoke exactly one resume API call with `duration_s=0.20, long_window=True`.
- [ ] **Step 2:** After P2/P2H/P3, require `IN_PROGRESS`, no root summary/manifest, and checkpoint advancement only.
- [ ] **Step 3:** After P5, require the five standard summaries, strict root manifest, `selected_architecture=null`, and `validate_bakeoff_manifest(root) == []`.
- [ ] **Step 4:** Record one command/PID/start/end/exit per architecture and never retry a failed architecture without a new recovery diagnosis.

### Task 4: Generate migration evidence and validate current v26 set

**Files:**

- Create runtime evidence only: RX-7/Ferrari v26 roots and manifests.
- Create logs: `tasks/reports/runtime/s12-stage-w/logs/task6l_v26_migrations.*.log`

- [ ] **Step 1:** Generate RX-7 and Ferrari each once with the existing migration public API at `duration_s=0.20`.
- [ ] **Step 2:** Require all three strict validators return `[]`, JSON finite, PCM reopen/format/clipping, nested SHA, click/afterfire/parameter gates, null selection, and exact 20s/60s Hellcat duration map.
- [ ] **Step 3:** Record v25 preservation, v26 manifests/hashes, command timing/PID/exit and non-R1 boundary in a compact evidence receipt.

### Task 5: Close current metadata and review gates

**Files:**

- Modify: Stage W current receipt/state/resume/W9/artifact/usage/package/Obsidian repo-mirror metadata identified by Task 6D.
- Create: current validator/Stage-W/Stage-V/slow/Track-P/compileall logs.

- [ ] **Step 1:** Run the Task5A/Task5B/Task6A/Task6B/Task6C focused suites, remediation, strict validators, slow 3000, Stage W focused, Stage V focused, compileall, Track-P and diff gates.
- [ ] **Step 2:** Update only metadata pointers to the completed v26 evidence and current source head; leave Vault `PENDING_PARENT_CODEX_MEMORY`, R1/W10/Profile Freeze unqualified and selection null.
- [ ] **Step 3:** Commit evidence/metadata separately, rerun Stage W on metadata head, and obtain task/whole-branch reviews before parent full S12 and Vault synchronization.

## Plan Review

- Spec coverage: all user-authorized resume safety boundaries, partial-root handling, parent PCM binding, external checkpoint, atomic publishing, v26 continuation and final governed checks are covered.
- Placeholder scan: no TODO/TBD or unbounded recovery behavior remains.
- Interface consistency: existing full API is unchanged; new API is explicitly single-architecture and only returns standard final summaries after strict validation can succeed.
