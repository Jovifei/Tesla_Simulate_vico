"""
Audition Reference Audio Extractor
===================================
Downloads and extracts real-vehicle reference audio clips from YouTube / Bilibili
for use in the Stage AD human-audition dashboard A/B comparison.

Usage
-----
  python extract_reference_audio.py \\
      --youtube-cookies cookies/youtube_cookies.txt \\
      --bilibili-cookies cookies/bilibili_cookies.txt \\
      --output-dir path/to/web_audio

Dependencies: yt-dlp, ffmpeg (both on PATH), numpy

Reference sources used for Hellcat v1 package
----------------------------------------------
  Bilibili BV14mwHeMEJU — "地狱猫国道暴力加速" by Trojx
    hot_idle    : 58.8s – 67.8s
    steady_low  : 125.3s – 134.3s
    steady_mid  : 31.4s – 40.4s
    full_pull   : 17.2s – 26.2s
    afterfire   : 6.9s  – 15.9s   (burst+lift-off transient at ~9s)

  YouTube ZzzkrRazdJo — "DODGE HELLCAT XR 888HP | AUTOBAHN POV" by AutoTopNL
    steady_high : 270.0s – 282.0s  (4:30 – 4:42, Autobahn high-speed cruise)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Scene definitions — (source, identifier, t_start, t_end, scene_name)
# ---------------------------------------------------------------------------

@dataclass
class ReferenceClip:
    source: str            # 'bilibili' | 'youtube'
    video_id: str          # bvid or yt id
    t_start: float         # seconds into original video
    t_end: float           # seconds into original video
    scene: str             # output filename stem
    url: str = field(default="")

    def __post_init__(self):
        if not self.url:
            if self.source == "bilibili":
                self.url = f"https://www.bilibili.com/video/{self.video_id}"
            else:
                self.url = f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def duration(self) -> float:
        return self.t_end - self.t_start


HELLCAT_V1_CLIPS: list[ReferenceClip] = [
    ReferenceClip("bilibili", "BV14mwHeMEJU",  58.8,  67.8, "ref_hot_idle"),
    ReferenceClip("bilibili", "BV14mwHeMEJU", 125.3, 134.3, "ref_steady_low"),
    ReferenceClip("bilibili", "BV14mwHeMEJU",  31.4,  40.4, "ref_steady_mid"),
    ReferenceClip("bilibili", "BV14mwHeMEJU",  17.2,  26.2, "ref_full_pull"),
    ReferenceClip("bilibili", "BV14mwHeMEJU",   6.9,  15.9, "ref_afterfire"),
    ReferenceClip("youtube",  "ZzzkrRazdJo",  270.0, 282.0, "ref_steady_high"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TARGET_SR = 48000
TARGET_CHANNELS = 2
TARGET_FMT = "s16"


def _yt_dlp_section(url: str, t_start: float, dur: float,
                    out_mp4: Path, cookies: str | None,
                    proxy: str | None, js_runtime: str = "node") -> bool:
    """Download a time-ranged mp4 via yt-dlp."""
    section = f"*{t_start:.3f}-{t_start + dur:.3f}"
    cmd = ["yt-dlp", "--no-playlist", "--download-sections", section,
           "-o", str(out_mp4), url]
    if cookies:
        cmd += ["--cookies", cookies]
    if proxy:
        cmd += ["--proxy", proxy]
    cmd += ["--js-runtimes", js_runtime]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [yt-dlp ERROR] {result.stderr[-400:]}", file=sys.stderr)
        return False
    return True


def _ffmpeg_extract(src: Path, t_start: float, dur: float, out_wav: Path) -> bool:
    """Re-encode to target WAV format."""
    cmd = ["ffmpeg", "-y", "-ss", f"{t_start:.3f}", "-i", str(src),
           "-t", f"{dur:.3f}", "-ar", str(TARGET_SR),
           "-ac", str(TARGET_CHANNELS), "-sample_fmt", TARGET_FMT, str(out_wav)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ffmpeg ERROR] {result.stderr[-400:]}", file=sys.stderr)
        return False
    return True


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Auto-detection using energy profiling (fallback when timestamps unknown)
# ---------------------------------------------------------------------------

def rms_profile(wav_path: Path, hop_ms: int = 100) -> tuple[np.ndarray, float]:
    """Compute hop-based RMS from a 16-bit PCM WAV file."""
    import wave
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    dtype = np.int16 if sw == 2 else np.int32
    audio = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if ch == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)
    audio /= np.iinfo(dtype).max
    hop = int(sr * hop_ms / 1000)
    n = len(audio) // hop
    rms = np.array([np.sqrt(np.mean(audio[i*hop:(i+1)*hop]**2)) for i in range(n)])
    return rms, hop_ms / 1000.0


def auto_select_window(rms: np.ndarray, hop_s: float, target_rms: float,
                       dur_s: float = 9.0) -> float:
    """Return the best start time (seconds) whose window RMS is closest to target."""
    n = int(dur_s / hop_s)
    best_score, best_i = 1e9, 0
    for i in range(len(rms) - n):
        score = abs(rms[i:i+n].mean() - target_rms)
        if score < best_score:
            best_score, best_i = score, i
    return best_i * hop_s


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def extract_clips(clips: list[ReferenceClip], output_dir: Path,
                  yt_cookies: str | None, bili_cookies: str | None,
                  proxy: str | None, tmp_dir: Path) -> list[dict]:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for clip in clips:
        print(f"\n→ {clip.scene}  [{clip.source}]  {clip.t_start:.1f}s–{clip.t_end:.1f}s")
        out_wav = output_dir / f"{clip.scene}.wav"
        tmp_mp4 = tmp_dir / f"{clip.scene}_raw.mp4"

        cookies = yt_cookies if clip.source == "youtube" else bili_cookies
        ok = _yt_dlp_section(clip.url, clip.t_start, clip.duration, tmp_mp4, cookies, proxy)
        if not ok:
            print(f"  [SKIP] Download failed for {clip.scene}")
            continue

        # ffmpeg: extract from the downloaded section (offset 0, full duration)
        ok = _ffmpeg_extract(tmp_mp4, 0, clip.duration, out_wav)
        if not ok:
            print(f"  [SKIP] Re-encode failed for {clip.scene}")
            continue

        size_kb = out_wav.stat().st_size // 1024
        sha = _sha256(out_wav)
        print(f"  [OK] {out_wav.name}  {size_kb} KB  sha256={sha[:16]}...")
        results.append({
            "scene": clip.scene,
            "source": clip.source,
            "video_id": clip.video_id,
            "url": clip.url,
            "clip_start_s": clip.t_start,
            "clip_end_s": clip.t_end,
            "format": f"{TARGET_SR}Hz stereo 16-bit PCM WAV",
            "size_bytes": out_wav.stat().st_size,
            "sha256": sha,
        })
    return results


def main():
    p = argparse.ArgumentParser(description="Extract Hellcat reference audio clips")
    p.add_argument("--output-dir", default="web_audio", type=Path)
    p.add_argument("--youtube-cookies", type=str, default=None)
    p.add_argument("--bilibili-cookies", type=str, default=None)
    p.add_argument("--proxy", type=str, default=None,
                   help="e.g. http://127.0.0.1:7890")
    p.add_argument("--tmp-dir", type=Path, default=Path("_ref_tmp"))
    p.add_argument("--manifest-out", type=Path, default=None)
    args = p.parse_args()

    results = extract_clips(
        HELLCAT_V1_CLIPS,
        output_dir=args.output_dir,
        yt_cookies=args.youtube_cookies,
        bili_cookies=args.bilibili_cookies,
        proxy=args.proxy,
        tmp_dir=args.tmp_dir,
    )

    manifest = {
        "schema": "s12.stage_ad.reference_audio.v2",
        "vehicle": "Dodge Challenger SRT Hellcat (6.2L Supercharged V8)",
        "note": "Real vehicle audio for human audition A/B comparison. Not an R1/R2 optimization target.",
        "references": results,
    }
    out_path = args.manifest_out or (args.output_dir / "reference_audio_manifest.json")
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[DONE] Manifest written to {out_path}")
    print(f"       Extracted {len(results)}/{len(HELLCAT_V1_CLIPS)} clips.")


if __name__ == "__main__":
    main()
