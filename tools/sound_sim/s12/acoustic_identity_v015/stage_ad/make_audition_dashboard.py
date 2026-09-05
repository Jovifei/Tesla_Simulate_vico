"""
Audition Dashboard Generator
==============================
Builds the self-contained human-audition HTML dashboard for Stage AD review
packages by embedding all WAV files as base64 Data URIs.

Usage
-----
  python make_audition_dashboard.py \\
      --package-dir path/to/s12-stage-ad-hellcat-closed-loop-v1 \\
      --output index.html

The resulting HTML is completely standalone — open directly in any browser,
no server or network required.

Dependencies: Python 3.10+, no third-party packages needed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

# ── Scene metadata ────────────────────────────────────────────────────────────

SCENES = [
    {"id": "01_afterfire",  "index": 1,  "category": "afterfire",    "candidate_file": "01_afterfire.wav",  "ref_file": "ref_afterfire.wav",    "title": "01 减速回火与爆音 (Afterfire / Pops & Bangs)",          "desc": "高速轰油后急剧松油，未燃混合气进入红热排气管爆燃产生的放炮与劈啪回火。",     "focus": "关注回火瞬态的打击感、空气爆炸张力及尾音消散的自然度。"},
    {"id": "02_full_pull",  "index": 2,  "category": "acceleration", "candidate_file": "02_full_pull.wav",  "ref_file": "ref_full_pull.wav",    "title": "02 全负荷加速狂飙 (Full Pull / WOT)",                   "desc": "节气门100%全开冲刺。机械增压器双螺杆高速气流啸叫与V8排气深沉咆哮交织。", "focus": "关注4000+ RPM标志性机械增压'猫叫'啸叫声与大排量排气低频的平衡度。"},
    {"id": "03_hot_idle",   "index": 3,  "category": "idle",         "candidate_file": "03_hot_idle.wav",   "ref_file": "ref_hot_idle.wav",     "title": "03 热态怠速稳态 (Hot Idle ~700 RPM)",                   "desc": "发动机热机700转怠速。十字曲轴90度点火间隙造成的非对称脉动，经典美式'煮水声'。", "focus": "关注气缸做功间歇的不均匀律动感，是否有足够的低频胸腔共振。"},
    {"id": "04_idle_return","index": 4,  "category": "idle",         "candidate_file": "04_idle_return.wav","ref_file": "ref_hot_idle.wav",     "title": "04 轰油回落怠速 (Idle Return)",                         "desc": "转速从高位滑行快速回落到怠速，闭环调速器介入稳定。",                        "focus": "关注回落过程的音量衰减曲线与怠速接管平顺度。"},
    {"id": "05_lift",       "index": 5,  "category": "dynamics",     "candidate_file": "05_lift.wav",       "ref_file": "ref_afterfire.wav",    "title": "05 大负荷急松油 (Throttle Lift)",                       "desc": "全负荷加速途中突然丢掉油门，旁通阀快速泄压，进气与排气压力急骤卸载。",       "focus": "关注泄压瞬间气流声的干脆利落程度，有无突兀爆音或拖沓截断。"},
    {"id": "06_shift",      "index": 6,  "category": "dynamics",     "candidate_file": "06_shift.wav",      "ref_file": None,                   "title": "06 升挡转速跌落瞬态 (Upshift Transient)",               "desc": "8速自动变速箱极速升挡瞬间，ECU点火推迟并切断扭矩，排气管发出沉闷低频冲击。", "focus": "关注换挡切扭矩时的低频冲击力（Shift Fart）及接挡后的转速连贯性。"},
    {"id": "07_steady_high","index": 7,  "category": "cruising",     "candidate_file": "07_steady_high.wav","ref_file": "ref_steady_high.wav",  "title": "07 高速稳态巡航 (~4500 RPM)",                           "desc": "中高转速连续巡航，消音器谐振腔充分受激，高频机械声与气流啸叫稳定平齐。",   "focus": "关注高频谐波是否刺耳，是否有持续的单调机械声疲劳感。"},
    {"id": "08_steady_low", "index": 8,  "category": "cruising",     "candidate_file": "08_steady_low.wav", "ref_file": "ref_steady_low.wav",   "title": "08 低速稳态巡航 (~1200 RPM)",                           "desc": "城市跟车工况，转速约1200转，负荷低，排气沉稳厚实，低频轰鸣感温和舒适。",   "focus": "关注100Hz以下低频是否纯净，无箱体共振塑料杂音。"},
    {"id": "09_steady_mid", "index": 9,  "category": "cruising",     "candidate_file": "09_steady_mid.wav", "ref_file": "ref_steady_mid.wav",   "title": "09 中速稳态巡航 (~2400 RPM)",                           "desc": "高速公路巡航典型工况，排气主谐波处于人耳敏感区间。",                         "focus": "关注音色层次感：排气管声、增压器机械声、机壳辐射声的声场分布。"},
    {"id": "10_tip_in",     "index": 10, "category": "acceleration", "candidate_file": "10_tip_in.wav",     "ref_file": None,                   "title": "10 急踩油门瞬态响应 (Tip-in)",                          "desc": "稳态行驶中油门突然下探到底，节气门瞬态全开，燃烧室内爆发能量跃迁。",         "focus": "关注音量与音色的建立延迟（Attack Time），瞬态响应是否凌厉逼真。"},
]

PARAMETERS = [
    {"group": "排气管路 (Body)",    "key": "combustion_rise_time",      "name": "燃烧升压时间",     "base": 0.0035,  "final": 0.001465,  "delta": -58.1, "desc": "缩短使爆燃打击感清脆有力"},
    {"group": "排气管路 (Body)",    "key": "combustion_event_energy",   "name": "单次点火爆发能量", "base": 0.600,   "final": 0.8105,    "delta": +35.1, "desc": "提升做功压强，赋予V8深沉低频"},
    {"group": "排气管路 (Body)",    "key": "combustion_decay_time",     "name": "燃烧脉冲衰减时间","base": 0.030,   "final": 0.0239,    "delta": -20.3, "desc": "缩短泄压尾音，避免声波浑浊"},
    {"group": "排气管路 (Body)",    "key": "cycle_variation",           "name": "工作循环不均度",   "base": 0.080,   "final": 0.1222,    "delta": +52.8, "desc": "重塑美式十字曲轴怠速粗暴的煮水声"},
    {"group": "排气管路 (Body)",    "key": "collector_loss",            "name": "汇流排声学阻尼",   "base": 0.920,   "final": 0.9837,    "delta": +6.9,  "desc": "保留更多高频排气声能"},
    {"group": "排气管路 (Body)",    "key": "primary_length_spread",     "name": "歧管分支长度离散度","base": 1.000,  "final": 1.1499,    "delta": +15.0, "desc": "增强排气声脉冲交错复合立体感"},
    {"group": "排气管路 (Body)",    "key": "primary_attenuation_spread","name": "歧管分支衰减离散度","base": 1.000,  "final": 1.1621,    "delta": +16.2, "desc": "增强不对称声场真实度"},
    {"group": "排气管路 (Body)",    "key": "crank_inertia",             "name": "曲轴旋转等效惯量", "base": 0.340,   "final": 0.3791,    "delta": +11.5, "desc": "匹配美式重型V8曲轴真实迟滞感"},
    {"group": "排气管路 (Body)",    "key": "idle_governor",             "name": "怠速调速环闭环增益","base": 0.220,  "final": 0.2092,    "delta": -4.9,  "desc": "允许自然的转速呼吸式微浮动"},
    {"group": "排气管路 (Body)",    "key": "waveguide_loss",            "name": "排气波导传输损耗", "base": 0.080,   "final": 0.0933,    "delta": +16.6, "desc": "排气管壁高频粘滞摩擦损耗"},
    {"group": "排气管路 (Body)",    "key": "waveguide_reflection",      "name": "管口端部声反射系数","base": 1.000,  "final": 1.000,     "delta": 0.0,   "desc": "保持全反射物理模型"},
    {"group": "机械增压 (Blower)",  "key": "blower_sideband_mix",       "name": "增压器啮合侧频混合比","base": 1.000,"final": 1.3213,    "delta": +32.1, "desc": "强化标志性'猫叫'啸叫辨识度"},
    {"group": "机械增压 (Blower)",  "key": "blower_casing_mix",         "name": "增压器机壳辐射混合比","base": 1.000,"final": 1.1385,   "delta": +13.9, "desc": "增强机壳中高频机械声"},
    {"group": "机械增压 (Blower)",  "key": "blower_broadband_mix",      "name": "增压器宽带气流声",  "base": 1.000,"final": 0.9972,    "delta": -0.3,  "desc": "保持自然气流声基准"},
    {"group": "机械增压 (Blower)",  "key": "boost_attack",              "name": "增压起音响应时间", "base": 0.080,   "final": 0.1057,    "delta": +32.1, "desc": "模拟增压腔充气压强建立过程"},
    {"group": "机械增压 (Blower)",  "key": "boost_release",             "name": "增压泄压释放时间", "base": 0.250,   "final": 0.0702,    "delta": -71.9, "desc": "松油截流干脆利落，不拖泥带水"},
    {"group": "机械增压 (Blower)",  "key": "bypass_threshold",          "name": "旁通阀开启压力阈值","base": 0.200,  "final": 0.1473,    "delta": -26.3, "desc": "让轻负荷松油也能激发轻微泄压声"},
    {"group": "机械增压 (Blower)",  "key": "intake_mix",                "name": "进气总管声学混合比","base": 0.180,  "final": 0.2187,    "delta": +21.5, "desc": "进气冬菇头/歧管气流声混音比例"},
]

# ── Template (same JS logic as before, injected via str.replace) ──────────────

HTML_TEMPLATE = open(Path(__file__).parent / "audition_dashboard_template.html", encoding="utf-8").read() \
    if (Path(__file__).parent / "audition_dashboard_template.html").exists() else None


def load_audio_b64(path: Path) -> str:
    if path.exists():
        return "data:audio/wav;base64," + base64.b64encode(path.read_bytes()).decode()
    return ""


def build_dashboard(package_dir: Path, output_path: Path) -> None:
    web_audio = package_dir / "web_audio"
    print(f"Packing audio from {web_audio}…")

    audio_store: dict[str, str] = {}
    for scene in SCENES:
        key_c = scene["id"] + "_candidate"
        audio_store[key_c] = load_audio_b64(web_audio / scene["candidate_file"])
        print(f"  {'OK' if audio_store[key_c] else 'MISSING':6s} candidate: {scene['candidate_file']}")
        if scene.get("ref_file"):
            key_r = scene["id"] + "_ref"
            audio_store[key_r] = load_audio_b64(web_audio / scene["ref_file"])
            print(f"  {'OK' if audio_store[key_r] else 'MISSING':6s} reference: {scene['ref_file']}")

    scenes_json = json.dumps(SCENES, ensure_ascii=False)
    params_json = json.dumps(PARAMETERS, ensure_ascii=False)
    audios_json = json.dumps(audio_store)

    # Read the template from the same directory as this script
    template_path = Path(__file__).parent / "audition_dashboard_template.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    template = template_path.read_text(encoding="utf-8")

    html = (template
            .replace("__SCENES_JSON__", scenes_json)
            .replace("__PARAMS_JSON__", params_json)
            .replace("__AUDIOS_JSON__", audios_json))

    output_path.write_text(html, encoding="utf-8")
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"[OK] Dashboard → {output_path}  ({size_mb:.1f} MB)")


def main():
    ap = argparse.ArgumentParser(description="Build Stage AD audition dashboard HTML")
    ap.add_argument("--package-dir", type=Path,
                    default=Path(r"E:\Tesla_speed\review_packages\s12-stage-ad-hellcat-closed-loop-v1"))
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    out = args.output or (args.package_dir / "index.html")
    build_dashboard(args.package_dir, out)


if __name__ == "__main__":
    main()
