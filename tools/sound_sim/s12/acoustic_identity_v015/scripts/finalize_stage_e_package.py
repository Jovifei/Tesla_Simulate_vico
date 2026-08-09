from __future__ import annotations
import json, shutil, sys, zipfile
from pathlib import Path

def main():
    root = Path(sys.argv[1]).resolve()
    repo = Path(sys.argv[2]).resolve()
    candidates = root / "candidates"; reference = root / "reference_distance"
    candidates.mkdir(exist_ok=True); reference.mkdir(exist_ok=True)
    for name in ("Ferrari_candidate_v2.json", "Hellcat_candidate_v2.json", "RX7_candidate_v2.json"):
        shutil.copy2(repo / "tools/sound_sim/s12/acoustic_identity_v015/targets/stage_e_candidates" / name, candidates / name)
    (reference / "README.md").write_text("Final-PCM reference distance is PARTIAL until the candidate evidence is evaluated; no 30% gate is claimed.\n", encoding="utf-8")
    (root / "source_evidence" / "README.md").write_text("Stage C baseline and Stage E candidate source evidence for the anonymous two-round package.\n", encoding="utf-8")
    pairs = root / "listener" / "qualitative_full_cycle_pairs"; pairs.mkdir(exist_ok=True)
    (pairs / "README.md").write_text("Anonymous full-cycle A/B files are optional preference evidence and do not enter the confusion matrix.\n", encoding="utf-8")
    (root / "listener" / "ab_responses_template.csv").write_text("package_id,listener_id,pair_id,preferred_option,low_frequency_naturalness,afterfire_naturalness,artifact_blocker,notes\n", encoding="utf-8")
    with zipfile.ZipFile(root / "S12_Stage_E_Listener_Package.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((root / "listener").rglob("*")):
            if path.is_file(): archive.writestr(f"listener/{path.relative_to(root / 'listener').as_posix()}", path.read_bytes())
if __name__ == "__main__": main()
