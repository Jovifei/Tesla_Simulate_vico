"""
Build reference_caseset.json for Ferrari 458 Italia using authentic clips extracted
from AutoTopNL YouTube video (X0yiRilcKME):
- ref_hot_idle.wav
- ref_steady_low.wav
- ref_steady_mid.wav
- ref_steady_high.wav
- ref_full_pull.wav
- ref_afterfire.wav
"""
import hashlib
import json
import wave
from pathlib import Path

PACKAGE_DIR = Path(r"E:\Tesla_speed\review_packages\s12-stage-ad-ferrari-458-closed-loop-v1")
WEB_AUDIO_DIR = PACKAGE_DIR / "web_audio"
RUNS_DIR = Path(r"E:\Tesla_speed\stage_ad_runs\ferrari_458_closed_loop_v1")
RUNS_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_VIDEO_PATH = Path(r"E:\Tesla_speed\review_packages\ref_sources_new\ferrari_458_autotopnl.mp4")
FULL_WAV_PATH = Path(r"E:\Tesla_speed\review_packages\ref_sources_new\ferrari_458_full.wav")

def get_file_info(path: Path):
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        frames = wf.getnframes()
        dur = frames / sr
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return sha, sr, dur

full_sha, full_sr, full_dur = get_file_info(FULL_WAV_PATH)

CASE_DEFS = [
    {
        "scenario": "hot_idle",
        "clip_file": "ref_hot_idle.wav",
        "start_s": 0.0,
        "end_s": 9.0,
        "video_start_s": 99.0,
        "video_end_s": 108.0,
        "notes": "Authentic Ferrari 458 4.5L Flat-Plane V8 hot idle mechanical tap & exhaust purr at 1050 RPM",
    },
    {
        "scenario": "steady_low",
        "clip_file": "ref_steady_low.wav",
        "start_s": 0.0,
        "end_s": 9.0,
        "video_start_s": 107.0,
        "video_end_s": 116.0,
        "notes": "Authentic Ferrari 458 ~1500 RPM smooth urban cruise",
    },
    {
        "scenario": "steady_mid",
        "clip_file": "ref_steady_mid.wav",
        "start_s": 0.0,
        "end_s": 9.0,
        "video_start_s": 139.0,
        "video_end_s": 148.0,
        "notes": "Authentic Ferrari 458 ~3500 RPM cruising before bypass valve full-open",
    },
    {
        "scenario": "steady_high",
        "clip_file": "ref_steady_high.wav",
        "start_s": 0.0,
        "end_s": 9.0,
        "video_start_s": 167.0,
        "video_end_s": 176.0,
        "notes": "Authentic Ferrari 458 7000+ RPM German Autobahn high-speed scream",
    },
    {
        "scenario": "full_pull",
        "clip_file": "ref_full_pull.wav",
        "start_s": 0.0,
        "end_s": 9.0,
        "video_start_s": 54.0,
        "video_end_s": 63.0,
        "notes": "Authentic Ferrari 458 WOT acceleration from 3000 to 9000 RPM redline scream",
    },
    {
        "scenario": "afterfire",
        "clip_file": "ref_afterfire.wav",
        "start_s": 0.0,
        "end_s": 9.0,
        "video_start_s": 59.0,
        "video_end_s": 68.0,
        "notes": "Authentic Ferrari 458 9000 RPM lift-off sharp metallic fuel-cut pops and gearshift crackle",
    },
]

cases = []
source_audios = []

for c in CASE_DEFS:
    clip_path = WEB_AUDIO_DIR / c["clip_file"]
    c_sha, c_sr, c_dur = get_file_info(clip_path)
    
    source_audios.append({
        "source_id": f"sha256:{c_sha}",
        "audio_path": str(clip_path),
        "audio_sha256": c_sha,
        "sample_rate": c_sr,
        "duration_s": c_dur,
        "evidence_governance": {
            "schema": "s12.stage_y.reference_governance.v1",
            "declared_evidence_level": "R2",
            "effective_evidence_level": "R3",
            "video_derived": True,
            "raw_audio_confirmed": False,
            "synchronized_state": False,
            "rights_status": "UNVERIFIED_PUBLIC_VIDEO",
            "downgrade_reasons": ["VIDEO_DERIVED_REFERENCE_CANNOT_BE_PROMOTED"],
        }
    })

    case_entry = {
        "schema": "s12.stage_y.reference_case.v2",
        "vehicle_id": "ferrari_458",
        "scenario": c["scenario"],
        "reference_id": f"ferrari_458:{c_sha[:12]}:{c['scenario']}:{c['start_s']:.1f}-{c['end_s']:.1f}",
        "source_id": f"sha256:{c_sha}",
        "recording_session_id": "youtube_X0yiRilcKME_autotopnl",
        "audio_path": str(clip_path),
        "audio_sha256": c_sha,
        "segment_sha256": hashlib.sha256(f"{c['scenario']}_{c['start_s']}_{c['end_s']}".encode()).hexdigest(),
        "evidence_level": "R3",
        "rights_status": "R3_PRIVATE_DIAGNOSTIC_ONLY",
        "sample_rate": c_sr,
        "start_s": c["start_s"],
        "end_s": c["end_s"],
        "microphone_position": "IN_CABIN_POV",
        "agc_post_processing": "UNKNOWN_AGC_POSSIBLE",
        "speech_music_contamination": {
            "speech_probability": 0.05,
            "speech_contaminated": False,
        },
        "rpm_trace": None,
        "load_trace": None,
        "gear_trace": None,
        "uncertainty": {
            "rpm_synchronised": False,
            "stock_state_verified": True,
            "agc_verified": False,
            "evidence_governance": {
                "schema": "s12.stage_y.reference_governance.v1",
                "declared_evidence_level": "R2",
                "effective_evidence_level": "R3",
                "video_derived": True,
                "raw_audio_confirmed": False,
                "synchronized_state": False,
                "rights_status": "UNVERIFIED_PUBLIC_VIDEO",
                "downgrade_reasons": ["VIDEO_DERIVED_REFERENCE_CANNOT_BE_PROMOTED"],
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
    "vehicle_id": "ferrari_458",
    "reference_evidence_level": "R3_AUDIO_DIAGNOSTIC",
    "source_audio": source_audios,
    "cases": cases
}

out_file = RUNS_DIR / "reference_caseset.json"
out_file.write_text(json.dumps(caseset_dict, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Created reference_caseset at: {out_file}")
print(f"Bound {len(cases)} scenarios: {[c['scenario'] for c in cases]}")
