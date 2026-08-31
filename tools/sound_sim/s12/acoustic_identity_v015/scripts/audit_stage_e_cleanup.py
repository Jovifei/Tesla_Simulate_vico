"""Create a review-only cleanup inventory; never deletes files."""
from __future__ import annotations
import hashlib, json, os
from pathlib import Path
import subprocess

ROOT = Path(r"E:\Tesla_speed")
TARGETS = [
    (ROOT / "prj" / "build", "rebuildable compiler/build output", "A"),
    (ROOT / "prj" / "tools/sound_sim/s12/benchmark/out", "benchmark working output", "A"),
    (ROOT / ".codegraph", "rebuildable code index", "A"),
    (ROOT / ".workbuddy/tmp_s12", "old non-authoritative audition scratch", "A"),
    (ROOT / "node_modules", "reinstallable dependency tree", "A"),
    (ROOT / "review_packages/_incomplete_stage_c_identity_v10", "interrupted package", "A"),
    (ROOT / "review_packages/_incomplete_stage_d_human_audition_v1", "interrupted package", "A"),
    (ROOT / "review_packages/_incomplete_stage_d_human_audition_v1_commit1", "interrupted package", "A"),
    (ROOT / "worktrees/s12-v11", "orphan worktree candidate", "B"),
    (ROOT / "audit-worktrees/s12-pp-source-2d8c58a", "orphan worktree candidate", "B"),
    (ROOT / "worktrees/_task-3-0-backup-s12-v12", "orphan backup candidate", "B"),
    (ROOT / "tasks/reports/runtime/S12_Acoustic_Realism_Phase_Review_2026-08-04.zip", "historical tracked report", "B"),
]

def digest(path: Path):
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    rows=[]
    for child in sorted(path.rglob("*")):
        if child.is_file():
            rows.append(f"{child.relative_to(path).as_posix()}|{child.stat().st_size}|{hashlib.sha256(child.read_bytes()).hexdigest()}")
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()

def main():
    out = ROOT / "review_packages/s12-cleanup-audit-stage-e"
    out.mkdir(parents=True, exist_ok=True)
    records=[]
    for path, reason, level in TARGETS:
        if not path.exists(): continue
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
        tracked=[]
        for file in files:
            try:
                tracked.append(bool(subprocess.run(["git", "-C", str(ROOT/"prj"), "ls-files", "--error-unmatch", str(file.relative_to(ROOT/"prj"))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0))
            except ValueError: tracked.append(False)
        records.append({"absolute_path":str(path),"bytes":sum(f.stat().st_size for f in files),"file_count":len(files),"tracked_any":any(tracked),"reason":reason,"recovery":"git history/reinstall/rebuild or restore backup","recommended_level":level,"approved":False,"tree_sha256":digest(path)})
    (out/"cleanup_inventory.json").write_text(json.dumps({"scope":"review only; approved=false; no deletion performed","items":records},indent=2),encoding="utf-8")
    (out/"cleanup_tree_sha256.json").write_text(json.dumps({r["absolute_path"]:r["tree_sha256"] for r in records},indent=2),encoding="utf-8")
    lines=["# Stage E Cleanup Inventory (review only)","","No files were deleted. Every item is `approved=false`; review each path before a separate deletion action.",""]
    for r in records: lines += [f"- `{r['absolute_path']}` — {r['bytes']/1024/1024:.2f} MiB, {r['file_count']} files, level {r['recommended_level']}; {r['reason']}; tree SHA-256 `{r['tree_sha256']}`."]
    (out/"cleanup_inventory.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"items":len(records),"output":str(out)},ensure_ascii=False))
if __name__ == "__main__": main()
