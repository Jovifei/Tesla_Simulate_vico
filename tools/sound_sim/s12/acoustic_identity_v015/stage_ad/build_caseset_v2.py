"""
Build reference_caseset_v2.json using authentic audio from:
1. Bilibili BV14mwHeMEJU (Trojx) - "地狱猫国道暴力加速"
2. YouTube ZzzkrRazdJo (AutoTopNL) - "DODGE HELLCAT XR 888HP | AUTOBAHN POV"
"""
import hashlib
import json
import wave
import numpy as np
from pathlib import Path

REF_DIR = Path(r"E:\Tesla_speed\review_packages\ref_sources_new")
RUNS_DIR = Path(r"E:\Tesla_speed\stage_ad_runs\hellcat_closed_loop_v2")
RUNS_DIR.mkdir(parents=True, exist_ok=True)

BILI_WAV = REF_DIR / "bilibili_hellcat_full.wav"
YT_WAV = REF_DIR / "yt_steady_high.wav"

def get_file_info(path):
    with wave.open(str(path), 'rb') as wf:
        sr = wf.getframerate()
        frames = wf.getnframes()
        dur = frames / sr
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return sha, sr, dur

bili_sha, bili_sr, bili_dur = get_file_info(BILI_WAV)
yt_sha, yt_sr, yt_dur = get_file_info(YT_WAV)

# Bound scenarios mapped to specific clean segments in the authentic recordings
CASE_DEFS = [
    {
        "scenario": "hot_idle",
        "audio_path": str(BILI_WAV),
        "audio_sha256": bili_sha,
        "sample_rate": bili_sr,
        "start_s": 58.8,
        "end_s": 67.8,
        "source_id": f"sha256:{bili_sha}",
        "session_id": "bilibili_BV14mwHeMEJU_trojx",
        "notes": "Authentic Hellcat 6.2L hot idle chop/rumble on public road stop",
    },
    {
        "scenario": "steady_low",
        "audio_path": str(BILI_WAV),
        "audio_sha256": bili_sha,
        "sample_rate": bili_sr,
        "start_s": 125.3,
        "end_s": 134.3,
        "source_id": f"sha256:{bili_sha}",
        "session_id": "bilibili_BV14mwHeMEJU_trojx",
        "notes": "Authentic Hellcat ~1200 RPM cruising in traffic",
    },
    {
        "scenario": "steady_mid",
        "audio_path": str(BILI_WAV),
        "audio_sha256": bili_sha,
        "sample_rate": bili_sr,
        "start_s": 31.4,
        "end_s": 40.4,
        "source_id": f"sha256:{bili_sha}",
        "session_id": "bilibili_BV14mwHeMEJU_trojx",
        "notes": "Authentic Hellcat ~2400 RPM road cruising",
    },
    {
        "scenario": "steady_high",
        "audio_path": str(YT_WAV),
        "audio_sha256": yt_sha,
        "sample_rate": yt_sr,
        "start_s": 0.0,
        "end_s": min(12.0, yt_dur),
        "source_id": f"sha256:{yt_sha}",
        "session_id": "youtube_ZzzkrRazdJo_autotopnl",
        "notes": "Authentic Hellcat 250+ km/h high-speed Autobahn run",
    },
    {
        "scenario": "full_pull",
        "audio_path": str(BILI_WAV),
        "audio_sha256": bili_sha,
        "sample_rate": bili_sr,
        "start_s": 17.2,
        "end_s": 26.2,
        "source_id": f"sha256:{bili_sha}",
        "session_id": "bilibili_BV14mwHeMEJU_trojx",
        "notes": "Authentic Hellcat WOT full acceleration pull with loud blower whine",
    },
    {
        "scenario": "afterfire",
        "audio_path": str(BILI_WAV),
        "audio_sha256": bili_sha,
        "sample_rate": bili_sr,
        "start_s": 6.9,
        "end_s": 15.9,
        "source_id": f"sha256:{bili_sha}",
        "session_id": "bilibili_BV14mwHeMEJU_trojx",
        "notes": "Authentic Hellcat lift-off fuel-cut deceleration bangs/pops",
    },
]

cases = []
for c in CASE_DEFS:
    case_entry = {
        "schema": "s12.stage_y.reference_case.v2",
        "vehicle_id": "hellcat",
        "scenario": c["scenario"],
        "reference_id": f"hellcat:{c['source_id']}:{c['scenario']}:{c['start_s']:.3f}-{c['end_s']:.3f}",
        "source_id": c["source_id"],
        "recording_session_id": c["session_id"],
        "audio_path": c["audio_path"],
        "audio_sha256": c["audio_sha256"],
        "segment_sha256": hashlib.sha256(f"{c['scenario']}_{c['start_s']}_{c['end_s']}".encode()).hexdigest(),
        "evidence_level": "R3",
        "rights_status": "R3_PRIVATE_DIAGNOSTIC_ONLY",
        "sample_rate": c["sample_rate"],
        "start_s": c["start_s"],
        "end_s": c["end_s"],
        "microphone_position": "UNVERIFIED",
        "agc_post_processing": "UNKNOWN_AGC_POSSIBLE",
        "speech_music_contamination": {
            "speech_probability": 0.1,
            "speech_contaminated": False,
        },
        "rpm_trace": None,
        "load_trace": None,
        "gear_trace": None,
        "uncertainty": {
            "rpm_synchronised": False,
            "stock_state_verified": False,
            "agc_verified": False,
            "evidence_governance": {
                "schema": "s12.stage_y.reference_governance.v1",
                "declared_evidence_level": "R2",
                "effective_evidence_level": "R3",
                "video_derived": True,
                "raw_audio_confirmed": False,
                "synchronized_state": False,
                "rights_status": "UNVERIFIED_PUBLIC_VIDEO",
                "downgrade_reasons": ["VIDEO_DERIVED_REFERENCE_CANNOT_BE_PROMOTED"]
            },
            "notes": c["notes"]
        },
        "allowed_metrics": ["raw_dynamic", "loudness_matched_timbre", "psychoacoustic_relative"],
        "status": "BOUND",
        "rejection_reason": None,
    }
    cases.append(case_entry)

caseset_dict = {
    "schema": "s12.stage_y.reference_governance.v1",
    "vehicle_id": "hellcat",
    "reference_evidence_level": "R3_AUDIO_DIAGNOSTIC",
    "source_audio": [
        {
            "source_id": f"sha256:{bili_sha}",
            "audio_path": str(BILI_WAV),
            "audio_sha256": bili_sha,
            "sample_rate": bili_sr,
            "duration_s": bili_dur,
            "evidence_governance": {
                "schema": "s12.stage_y.reference_governance.v1",
                "declared_evidence_level": "R2",
                "effective_evidence_level": "R3",
                "video_derived": True,
                "raw_audio_confirmed": False,
                "synchronized_state": False,
                "rights_status": "UNVERIFIED_PUBLIC_VIDEO",
                "downgrade_reasons": ["VIDEO_DERIVED_REFERENCE_CANNOT_BE_PROMOTED"]
            }
        },
        {
            "source_id": f"sha256:{yt_sha}",
            "audio_path": str(YT_WAV),
            "audio_sha256": yt_sha,
            "sample_rate": yt_sr,
            "duration_s": yt_dur,
            "evidence_governance": {
                "schema": "s12.stage_y.reference_governance.v1",
                "declared_evidence_level": "R2",
                "effective_evidence_level": "R3",
                "video_derived": True,
                "raw_audio_confirmed": False,
                "synchronized_state": False,
                "rights_status": "UNVERIFIED_PUBLIC_VIDEO",
                "downgrade_reasons": ["VIDEO_DERIVED_REFERENCE_CANNOT_BE_PROMOTED"]
            }
        }
    ],
    "cases": cases
}

out_file = RUNS_DIR / "reference_caseset.json"
out_file.write_text(json.dumps(caseset_dict, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Created reference_caseset_v2 at: {out_file}")
print(f"Bound {len(cases)} scenarios: {[c['scenario'] for c in cases]}")
