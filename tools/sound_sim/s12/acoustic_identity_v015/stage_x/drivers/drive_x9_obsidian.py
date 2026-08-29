"""Drive X9: generate Stage X Obsidian notes, sync repo mirror + personal vault."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO_ROOT))

RUNTIME = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-x"
MIRROR = REPO_ROOT / "docs" / "knowledge" / "obsidian" / "S12" / "Engine-Audio-Ecosystem"
VAULT_CUSTOM = Path("E:/AI_Tools/Obsidian/data/notes-personal/codex_memory/03-项目记忆/tesla-speed/09-S12-Engine-Audio-Ecosystem")
VAULT_MIRROR = Path("E:/AI_Tools/Obsidian/data/notes-personal/codex_memory/03-项目记忆/tesla-speed/05-工程文档/docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem")
BRANCH = "agent/s12-stage-x-r2-engineering-selection"
SCOPE = "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction"

NOTES = ("07-Stage-X-Remote-Reconciliation", "08-Engineering-Selection-Contract", "09-Hellcat-R2-Engineering-Selection", "10-Ferrari-RX7-Diagnostic-Migration", "11-R1-Formal-Gate-Readiness", "12-Stage-X-Final-Status")


def _git_head() -> str:
    import subprocess

    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()


def _load(name: str) -> dict | None:
    path = RUNTIME / name
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _frontmatter(title: str, head: str) -> str:
    return (
        "---\n"
        f"title: {title}\n"
        "project: Tesla-Speed-Sound\n"
        "subproject: S12\n"
        "stage: Stage-X\n"
        "document_type: experiment_note\n"
        "status: partial_engineering_preselection\n"
        "source_url: https://github.com/Jovifei/Tesla_Simulate_vico\n"
        f"s12_git_branch: {BRANCH}\n"
        f"s12_git_commit: {head}\n"
        "created: 2026-08-29\n"
        "updated: 2026-08-29\n"
        "tags:\n  - S12\n  - Stage-X\n---\n\n"
    )


def _block(body: str) -> str:
    return f"<!-- S12-STAGE-X:AUTO:BEGIN -->\n{body}\n<!-- S12-STAGE-X:AUTO:END -->\n"


def build_notes(head: str) -> dict[str, str]:
    reconciliation = (RUNTIME / "S12_Stage_X_Remote_Local_Reconciliation.md").read_text(encoding="utf-8")
    reachability = _load("x4_reachability/parameter_reachability.json") or {}
    preselection = _load("x5_hellcat_preselection_summary.json") or {}
    migration = _load("x6_migration/x6_summary.json") or {}
    package = _load("x7_package_summary.json") or {}
    formal = _load("x8_formal_gate_fixture/x8_summary.json") or {}
    notes: dict[str, str] = {}

    notes["07-Stage-X-Remote-Reconciliation"] = _frontmatter("Stage X Remote Reconciliation", head) + _block(
        f"""X0 reconciliation (2026-08-29): remote Stage W branch remains at `7d4e49b`
(cached origin ref; live fetch blocked by network egress and re-checked before
push). Local Stage W `8637e62` carries 116 unpushed commits with the complete
v26→v27 arc and final qualification closure; remote is its ancestor, so
recovery rule B applies: Stage X branches directly from `8637e62`, nothing
discarded. Worktree `E:/Tesla_speed/worktrees/s12-stage-x-r2-engineering-selection`.
Track-P baseline v3 / `ea586bc` unchanged (180 files / 2 symbols). Full detail
in `tasks/reports/runtime/s12-stage-x/S12_Stage_X_Remote_Local_Reconciliation.md`.
Scope: {SCOPE}."""
    )

    notes["08-Engineering-Selection-Contract"] = _frontmatter("Engineering Selection Contract", head) + _block(
        f"""Stage X splits the single selection gate into two layers
(`tools/sound_sim/s12/acoustic_identity_v015/stage_x/selection_contract.py`):

1. **engineering_preselection** — inputs: R2 audio, clean R3, Jovi feedback,
   Parent/Candidate metrics, ablation, runtime hard gates. May emit
   `R2_ENGINEERING_PRESELECTION`; never APPROVED_PROFILE / PROFILE_FREEZE /
   OEM_MATCH.
2. **formal_selection** — R1 only (rights + synchronized RPM/load/gear +
   scenario binding + human confirmation). Stays
   `FORMAL_R1_REFERENCE_MISSING` with `architecture=null` until real R1.

`selection_eligible` is now computed from data (hard gates, valid reference
count ≥2, median improvement ≥15%, evidence level) — the unconditional
`false` is gone. Scenario-bound `ReferenceCaseSet`
(`stage_x/reference_caseset.py`) binds each bake-off scenario to an
independent SHA-verified R2 segment with a deterministic speech-band detector;
speech-contaminated windows are rejected fail-closed (RX-7 is rejected by
Jovi receipt + detector). Multi-reference comparator
(`stage_x/multi_reference_comparator.py`) separates raw-dynamic metrics from
loudness-matched timbre metrics and outputs the 12 contract dimensions plus a
multi-reference median objective; order metrics stay NOT_QUALIFIED without
RPM traces. Scope: {SCOPE}."""
    )

    reach_line = f"Reachability probe: {reachability.get('reachable_count', '?')}/{reachability.get('parameter_count', '?')} parameters reachable under the per-parameter targeted protocol (architecture + scenes + stem)." if reachability else "Reachability scan pending."
    if preselection:
        arch_lines = "\n".join(
            f"- {arch}: status `{gate['status']}`, objective {gate.get('best_objective')}"
            for arch, gate in preselection.get("preselections", {}).items()
        )
        selected = preselection.get("selected_engineering_architecture") or "none (NO_R2_ENGINEERING_CANDIDATE_IMPROVED)"
        hellcat_body = f"""Hellcat engineering search (X5): deterministic Sobol two-stage search
(64 coarse + 32 refine per architecture, seed-bound), every candidate
rendered, reopened, hashed and compared against the scenario-bound R2
references (bound scenarios: {', '.join(preselection.get('reference_scenarios', []))}).
{reach_line}

{arch_lines}

Selected engineering architecture: **{selected}**. Scope: {SCOPE}."""
    else:
        hellcat_body = f"Hellcat engineering search pending. {reach_line} Scope: {SCOPE}."
    notes["09-Hellcat-R2-Engineering-Selection"] = _frontmatter("Hellcat R2 Engineering Selection", head) + _block(hellcat_body)

    if migration:
        vehicle_lines = []
        for vehicle_id, record in migration.get("vehicles", {}).items():
            best = record.get("best_architecture") or "none"
            vehicle_lines.append(f"- {vehicle_id}: valid references {record['valid_reference_count']}, best architecture `{best}` ({', '.join(record['reference_scenarios']) or 'no bound scenarios'})")
        migration_body = ("Ferrari/RX-7 diagnostic migration (X6): bounded search (64 coarse + 24 refine per architecture) over the reachability-verified parameter box.\n"
                          + "\n".join(vehicle_lines)
                          + f"\nRX-7 references stay speech-contaminated (Jovi receipt), so its result is diagnostic-only; no reference-supported preselection and no formal migration or OEM likeness claim. Scope: {SCOPE}.")
    else:
        migration_body = f"Ferrari/RX-7 diagnostic migration pending. Scope: {SCOPE}."
    notes["10-Ferrari-RX7-Diagnostic-Migration"] = _frontmatter("Ferrari RX7 Diagnostic Migration", head) + _block(migration_body)

    if formal:
        formal_body = f"""R1 formal gate readiness (X8): the formal pipeline is complete and exercised
on a synthetic fixture — multi-scenario binding, SHA receipts, rights fields,
synchronized RPM/load/gear traces, time coverage, microphone/AGC declaration,
MATLAB order-input export, multi-reference median, formal selection and the
profile-candidate gate. Fixture result: all pipeline checks
{'PASS' if formal.get('all_checks_pass') else 'FAIL'}, formal selection
`{formal.get('formal_selection_status')}`, selected architecture
`{formal.get('selected_architecture')}`, profile candidate gate
{'opened' if formal.get('profile_candidate_opened') else 'closed (fail-closed)'}.
The fixture carries FIXTURE_ONLY / NOT_REAL_R1 / NOT_TUNING_AUTHORITY markers
and can never produce a real formal selection; real status remains
`{formal.get('real_status')}`. When real R1 data arrives it is imported into
this same pipeline with no new selection algorithm. Scope: {SCOPE}."""
    else:
        formal_body = f"R1 formal gate fixture pending. Scope: {SCOPE}."
    notes["11-R1-Formal-Gate-Readiness"] = _frontmatter("R1 Formal Gate Readiness", head) + _block(formal_body)

    package_line = f"Review package `{package.get('package_root')}` (validator errors: {len(package.get('validator_errors', []))}) is ready for Jovi's guided + blind audition." if package else "Review package pending."
    notes["12-Stage-X-Final-Status"] = _frontmatter("Stage X Final Status", head) + _block(
        f"""Stage X final status (2026-08-29): engineering/formal selection split
implemented and validated; scenario-bound R2 references bound for Hellcat
({', '.join(preselection.get('reference_scenarios', [])) if preselection else 'pending'}) and Ferrari; RX-7 excluded fail-closed for speech
contamination; parameter reachability, two-stage search, engineering gate,
R1-ready formal pipeline and the guided audition package are all in place.
{package_line}

Remaining external gates (fail-closed): real R1 intake
(`R1_PILOT_PREFLIGHT_FAILED` template at
`E:/Claude_allow/Download/s12-stage-w-r1-capture-v1`), Jovi blind feedback on
the Stage X package, W10 multi-reference selection, human confirmation and
Profile Freeze. No Human PASS, Approved Profile, OEM reproduction, calibration
or productization claim. Scope: {SCOPE}."""
    )
    return notes


def main() -> int:
    started = time.perf_counter()
    head = _git_head()
    notes = build_notes(head)
    MIRROR.mkdir(parents=True, exist_ok=True)
    for name, body in notes.items():
        (MIRROR / f"{name}.md").write_text(body, encoding="utf-8", newline="\n")
    index = MIRROR / "00-MOC.md"
    if index.is_file():
        text = index.read_text(encoding="utf-8")
        links = "\n".join(f"- [[{name}]]" for name in NOTES if f"[[{name}]]" not in text)
        if links:
            text = text.rstrip("\n") + "\n\n" + links + "\n"
            index.write_text(text, encoding="utf-8", newline="\n")
    vault_status: dict[str, str] = {}
    if VAULT_CUSTOM.is_dir():
        for name, body in notes.items():
            target = VAULT_CUSTOM / f"{name}.md"
            if target.exists():
                existing = target.read_text(encoding="utf-8")
                if "<!-- S12-STAGE-X:AUTO:BEGIN -->" in existing:
                    start = existing.index("<!-- S12-STAGE-X:AUTO:BEGIN -->")
                    end = existing.index("<!-- S12-STAGE-X:AUTO:END -->") + len("<!-- S12-STAGE-X:AUTO:END -->")
                    existing = existing[:start] + body.rstrip("\n") + existing[end:]
                    target.write_text(existing, encoding="utf-8", newline="\n")
                    vault_status[name] = "UPDATED_MANAGED_BLOCK"
                    continue
            target.write_text(body, encoding="utf-8", newline="\n")
            vault_status[name] = "CREATED"
        if VAULT_MIRROR.is_dir():
            import shutil

            for name in notes:
                shutil.copyfile(MIRROR / f"{name}.md", VAULT_MIRROR / f"{name}.md")
    manifest = {
        "schema": "s12.stage_x.obsidian_sync.v1",
        "branch": BRANCH,
        "head_at_capture": head,
        "notes": [
            {"name": f"{name}.md", "repo_mirror_sha256": hashlib.sha256((MIRROR / f"{name}.md").read_bytes()).hexdigest(), "vault_custom_sha256": hashlib.sha256((VAULT_CUSTOM / f"{name}.md").read_bytes()).hexdigest() if (VAULT_CUSTOM / f"{name}.md").is_file() else None}
            for name in notes
        ],
        "vault_custom_status": vault_status,
        "mirror_status": "REPO_MIRROR_UPDATED",
        "vault_mirror_status": "VAULT_MIRROR_SYNCED" if VAULT_MIRROR.is_dir() else "VAULT_MIRROR_UNAVAILABLE",
        "managed_block": "S12-STAGE-X:AUTO",
        "wall_seconds": round(time.perf_counter() - started, 1),
    }
    (RUNTIME / "obsidian_sync_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"notes": len(notes), "vault": vault_status, "seconds": manifest["wall_seconds"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
