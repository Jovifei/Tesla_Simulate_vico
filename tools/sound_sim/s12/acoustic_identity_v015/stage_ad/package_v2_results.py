"""
Packages the newly calibrated Stage AD v2 results (calibrated on authentic YouTube & Bilibili videos):
- Copies newly rendered candidate WAVs into review_packages/.../web_audio
- Updates audition_manifest.json
- Updates PARAMETERS in make_audition_dashboard
- Rebuilds index.html (fast lightweight streaming mode) and index_standalone.html
"""
import shutil
import json
import hashlib
from pathlib import Path

RUN_DIR = Path(r"E:\Tesla_speed\stage_ad_runs\hellcat_closed_loop_v2\02_blower")
PACKAGE_DIR = Path(r"E:\Tesla_speed\review_packages\s12-stage-ad-hellcat-closed-loop-v1")
WEB_AUDIO = PACKAGE_DIR / "web_audio"
MANIFEST_PATH = PACKAGE_DIR / "audition_manifest.json"

def main():
    print("=== Packaging Stage AD v2 Closed-Loop Results ===")
    
    # 1. Read final summary
    summary_path = RUN_DIR / "closed_loop_summary.json"
    if not summary_path.exists():
        print(f"ERROR: {summary_path} does not exist!")
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    
    final_distance = summary["final_absolute_reference_distance"]
    final_overrides = summary["final_overrides"]
    final_config_sha = summary["final_config_sha256"]
    
    print(f"Final Absolute Reference Distance: {final_distance:.4f}")
    print(f"Final Config SHA256: {final_config_sha[:16]}...")
    
    # 2. Locate the best iteration directory
    iter_count = summary.get("iteration_count", 2)
    last_iter_dir = RUN_DIR / f"iteration_{iter_count-1:02d}"
    if not last_iter_dir.exists():
        last_iter_dir = RUN_DIR / "iteration_00"
    print(f"Source candidate directory: {last_iter_dir}")
    
    # Copy candidate WAVs
    wav_files = list(last_iter_dir.glob("*.wav"))
    print(f"Found {len(wav_files)} candidate WAV files to copy:")
    for src in sorted(wav_files):
        dst = WEB_AUDIO / src.name
        shutil.copy2(src, dst)
        sha = hashlib.sha256(dst.read_bytes()).hexdigest()
        print(f"  ✓ {src.name} -> web_audio/ ({dst.stat().st_size // 1024} KB, sha: {sha[:12]})")
        
        # Also copy to package root (historical compatibility)
        shutil.copy2(src, PACKAGE_DIR / src.name)

    # 3. Update audition_manifest.json
    manifest_files = []
    for idx, fname in enumerate([
        "01_afterfire.wav", "02_full_pull.wav", "03_hot_idle.wav", "04_idle_return.wav",
        "05_lift.wav", "06_shift.wav", "07_steady_high.wav", "08_steady_low.wav",
        "09_steady_mid.wav", "10_tip_in.wav"
    ], 1):
        p = WEB_AUDIO / fname
        scene_name = fname.replace(".wav", "")[3:]
        manifest_files.append({
            "index": idx,
            "scene": scene_name,
            "file": fname,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()
        })
        
    audition_manifest = {
        "schema": "s12.stage_ad.audition_package.v2",
        "calibration_target": "authentic_youtube_and_bilibili_hellcat_v8",
        "source_loop_root": str(RUN_DIR),
        "source_summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "final_iteration": iter_count - 1,
        "final_objective": -final_distance,
        "final_absolute_reference_distance": final_distance,
        "final_config_sha256": final_config_sha,
        "files": manifest_files,
        "blind": False,
        "official_v3_modified": False,
        "instruction": "Listen to monitor WAVs calibrated directly on authentic Hellcat videos."
    }
    MANIFEST_PATH.write_text(json.dumps(audition_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated: {MANIFEST_PATH}")
    
    # 4. Extract updated 18 parameters
    # Read body summary for full 18 parameters
    body_summary_path = Path(r"E:\Tesla_speed\stage_ad_runs\hellcat_closed_loop_v2\01_body\closed_loop_summary.json")
    body_summary = json.loads(body_summary_path.read_text(encoding="utf-8"))
    
    all_overrides = {**body_summary["final_overrides"], **final_overrides}
    print("\nAll 18 calibrated parameters:")
    for k, v in all_overrides.items():
        print(f"  {k:30s} = {v:.6f}")
        
    # 5. Rebuild HTML dashboard
    template_path = Path(r"E:\Tesla_speed\worktrees\s12-stage-ad-closed-loop-calibration\tools\sound_sim\s12\acoustic_identity_v015\stage_ad\audition_dashboard_template.html")
    template = template_path.read_text(encoding="utf-8")
    
    # Rebuild PARAMETERS list with new values and deltas
    base_values = {
        "combustion_rise_time": 0.0035, "combustion_event_energy": 0.600, "combustion_decay_time": 0.030,
        "cycle_variation": 0.080, "collector_loss": 0.920, "primary_length_spread": 1.000,
        "primary_attenuation_spread": 1.000, "crank_inertia": 0.340, "idle_governor": 0.220,
        "waveguide_loss": 0.080, "waveguide_reflection": 1.000,
        "blower_sideband_mix": 1.000, "blower_casing_mix": 1.000, "blower_broadband_mix": 1.000,
        "boost_attack": 0.080, "boost_release": 0.250, "bypass_threshold": 0.200, "intake_mix": 0.180,
    }
    
    # Descriptions and Chinese names
    meta_info = {
        "combustion_rise_time": ("排气管路 (Body)", "燃烧升压时间", "缩短使爆燃打击感清脆有力"),
        "combustion_event_energy": ("排气管路 (Body)", "单次点火爆发能量", "提升做功压强，赋予V8深沉低频"),
        "combustion_decay_time": ("排气管路 (Body)", "燃烧脉冲衰减时间", "缩短泄压尾音，避免声波浑浊"),
        "cycle_variation": ("排气管路 (Body)", "工作循环不均度", "重塑美式十字曲轴怠速粗暴的煮水声"),
        "collector_loss": ("排气管路 (Body)", "汇流排声学阻尼", "保留更多高频排气声能"),
        "primary_length_spread": ("排气管路 (Body)", "歧管分支长度离散度", "增强排气声脉冲交错复合立体感"),
        "primary_attenuation_spread": ("排气管路 (Body)", "歧管分支衰减离散度", "增强不对称声场真实度"),
        "crank_inertia": ("排气管路 (Body)", "曲轴旋转等效惯量", "匹配美式重型V8曲轴真实迟滞感"),
        "idle_governor": ("排气管路 (Body)", "怠速调速环闭环增益", "允许自然的转速呼吸式微浮动"),
        "waveguide_loss": ("排气管路 (Body)", "排气波导传输损耗", "排气管壁高频粘滞摩擦损耗"),
        "waveguide_reflection": ("排气管路 (Body)", "管口端部声反射系数", "保持全反射物理模型"),
        "blower_sideband_mix": ("机械增压 (Blower)", "增压器啮合侧频混合比", "强化标志性'猫叫'啸叫辨识度"),
        "blower_casing_mix": ("机械增压 (Blower)", "增压器机壳辐射混合比", "增强机壳中高频机械声"),
        "blower_broadband_mix": ("机械增压 (Blower)", "增压器宽带气流声", "保持自然气流声基准"),
        "boost_attack": ("机械增压 (Blower)", "增压起音响应时间", "模拟增压腔充气压强建立过程"),
        "boost_release": ("机械增压 (Blower)", "增压泄压释放时间", "松油截流干脆利落，不拖泥带水"),
        "bypass_threshold": ("机械增压 (Blower)", "旁通阀开启压力阈值", "让轻负荷松油也能激发轻微泄压声"),
        "intake_mix": ("机械增压 (Blower)", "进气总管声学混合比", "进气冬菇头/歧管气流声混音比例"),
    }
    
    new_params = []
    for k, (grp, name, desc) in meta_info.items():
        base = base_values[k]
        final = all_overrides.get(k, base)
        delta = ((final - base) / base) * 100.0 if base != 0 else 0.0
        new_params.append({
            "group": grp,
            "key": k,
            "name": name,
            "base": round(base, 4),
            "final": round(final, 6),
            "delta": round(delta, 1),
            "desc": desc
        })

    import sys
    sys.path.insert(0, str(template_path.parent))
    from make_audition_dashboard import SCENES

    scenes_json = json.dumps(SCENES, ensure_ascii=False)
    params_json = json.dumps(new_params, ensure_ascii=False)
    
    html = template.replace("__SCENES_JSON__", scenes_json).replace("__PARAMS_JSON__", params_json).replace("__AUDIOS_JSON__", "{}")
    (PACKAGE_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"\n[OK] Rebuilt index.html: {(PACKAGE_DIR / 'index.html').stat().st_size} bytes")

if __name__ == "__main__":
    main()
