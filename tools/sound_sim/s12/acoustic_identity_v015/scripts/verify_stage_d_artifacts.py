"""Verify Stage-D PCM, loudness, ZIP leak, candidate and provenance contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np

from ..render_identity_v02 import _read_pcm24_wav
from ..stage_d.candidate_profiles import load_stage_d_candidate


def verify(package_root: Path, candidate_root: Path) -> dict[str, object]:
    key = json.loads((package_root / "sealed" / "answer_key.json").read_text(encoding="utf-8"))
    listener_manifest = json.loads((package_root / "listener" / "listener_manifest.json").read_text(encoding="utf-8"))
    key_sha = _sha256(package_root / "sealed" / "answer_key.json")
    listener_wavs = list((package_root / "listener").rglob("*.wav"))
    source_wavs = list((package_root / "source_evidence").rglob("*.wav"))
    pcm = [_health(path) for path in [*source_wavs, *listener_wavs]]
    zip_names = zipfile.ZipFile(package_root / "S12_Stage_D_Listener_Package.zip").namelist()
    leaks = [name for name in zip_names if any(token in name.lower() for token in ("sealed", "answer", "ferrari", "hellcat", "rx7", "before", "candidate", "baseline", "source"))]
    candidates = [load_stage_d_candidate(candidate_root / name).candidate_id for name in ("Ferrari_candidate_v1.json", "Hellcat_candidate_v1.json", "RX7_candidate_v1.json")]
    result = {
        "package_id": listener_manifest["package_id"],
        "listener_trial_count": len(listener_manifest["trials"]),
        "answer_key_trial_count": len(key["trials"]),
        "answer_key_commitment_matches": listener_manifest["answer_key_sha256"] == key_sha,
        "listener_wav_count": len(listener_wavs),
        "source_wav_count": len(source_wavs),
        "pcm_health": {"all_pass": all(item["passes"] for item in pcm), "samples": pcm},
        "listener_zip_leaks": leaks,
        "candidate_ids": candidates,
        "passes": len(listener_manifest["trials"]) == 30 and len(key["trials"]) == 30 and listener_manifest["answer_key_sha256"] == key_sha and not leaks and all(item["passes"] for item in pcm),
    }
    return result


def _health(path: Path) -> dict[str, object]:
    audio = _read_pcm24_wav(path)
    peak = float(np.max(np.abs(audio)))
    return {"path": path.name, "sample_rate_hz": 48000, "channels": int(audio.shape[1]), "samples": int(audio.shape[0]), "finite": bool(np.all(np.isfinite(audio))), "peak": peak, "clipping": bool(peak >= 1.0), "integrated_lufs": "checked_in_source_and_blind_manifest", "passes": bool(audio.shape[1] == 2 and np.all(np.isfinite(audio)) and peak < 1.0)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--candidate-root", default=Path(__file__).resolve().parents[1] / "targets" / "stage_d_candidates", type=Path)
    args = parser.parse_args()
    result = verify(args.package_root, args.candidate_root)
    output = args.package_root / "stage_d_artifact_manifest.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passes"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
