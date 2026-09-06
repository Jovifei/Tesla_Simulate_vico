"""
Generates the Ferrari 458 Italia Audition Dashboard.
Builds both index.html (streaming mode) and index_standalone.html (embedded base64 audio).
"""
import base64
import hashlib
import json
from pathlib import Path

PACKAGE_DIR = Path(r"E:\Tesla_speed\review_packages\s12-stage-ad-ferrari-458-closed-loop-v1")
WEB_AUDIO_DIR = PACKAGE_DIR / "web_audio"
TEMPLATE_PATH = Path(r"E:\Tesla_speed\worktrees\s12-stage-ad-closed-loop-calibration\tools\sound_sim\s12\acoustic_identity_v015\stage_ad\audition_dashboard_template.html")

SCENES = [
    {
        "id": "01_afterfire",
        "index": 1,
        "category": "afterfire",
        "candidate_file": "01_afterfire.wav",
        "ref_file": "ref_afterfire.wav",
        "title": "01 减速回火与排气脆爆 (Afterfire / Pops & Bangs)",
        "desc": "9000转高速轰油后急松油门，未燃混合气在高温排气管爆燃。平面曲轴产生极其清脆干脆的金属枪击爆音，无美式浑浊拖沓。",
        "focus": "关注高转速丢油瞬态排气管爆音的清脆打击感、金属高频张力及回火收尾的干脆程度。",
        "origin_tag": "YouTube 德国高速 (AutoTopNL 0-310km/h)"
    },
    {
        "id": "02_full_pull",
        "index": 2,
        "category": "acceleration",
        "candidate_file": "02_full_pull.wav",
        "ref_file": "ref_full_pull.wav",
        "title": "02 全负荷红线嘶吼 (Full Pull / WOT 3000-9000 RPM)",
        "desc": "油门全开从3000转直冲9000转红线。180度平面曲轴每转均匀4次排气脉冲（E4阶次），随着转速攀升演化为法拉利标志性的高亢撕裂歌喉。",
        "focus": "关注中高转速（6000-9000 RPM）纯粹的自然吸气平面曲轴尖啸，零机械增压杂音，高阶谐波穿透力强且无稀碎杂散噪音。",
        "origin_tag": "YouTube 德国高速 (AutoTopNL 0-310km/h)"
    },
    {
        "id": "03_hot_idle",
        "index": 3,
        "category": "idle",
        "candidate_file": "03_hot_idle.wav",
        "ref_file": "ref_hot_idle.wav",
        "title": "03 热态怠速稳态 (Hot Idle ~1050 RPM)",
        "desc": "4.5L V8发动机热态1050转平稳怠速。平面曲轴对称敲击声，不同于十字曲轴的咕噜煮水声，呈现出紧凑、清脆、赛车化的机械呼吸感。",
        "focus": "关注1050转怠速气缸做功敲击的均匀节奏感与排气尾段轻微的声压微颤，无粗暴失步感。",
        "origin_tag": "YouTube 德国高速 (AutoTopNL 0-310km/h)"
    },
    {
        "id": "04_idle_return",
        "index": 4,
        "category": "idle",
        "candidate_file": "04_idle_return.wav",
        "ref_file": "ref_hot_idle.wav",
        "title": "04 轰油回落怠速 (Idle Return)",
        "desc": "高转速轰油后完全松开油门，转速平滑滑行回落至1050转怠速，闭环调速器无缝接管。",
        "focus": "关注回落过程中的能量衰减包络与落回怠速瞬间的转速稳定性，过渡平顺自然。",
        "origin_tag": "YouTube 德国高速 (AutoTopNL 0-310km/h)"
    },
    {
        "id": "05_lift",
        "index": 5,
        "category": "dynamics",
        "candidate_file": "05_lift.wav",
        "ref_file": "ref_afterfire.wav",
        "title": "05 高转速急松油门 (Throttle Lift)",
        "desc": "高转速高负荷行驶中突然全松油门，进气歧管骤呈真空，排气管声压瞬态泄落并伴随金属气流回鸣。",
        "focus": "关注声压截断的瞬态反应速度（Attack/Decay），有无突兀杂音，收油瞬间金属质感是否纯正。",
        "origin_tag": "YouTube 德国高速 (AutoTopNL 0-310km/h)"
    },
    {
        "id": "06_shift",
        "index": 6,
        "category": "dynamics",
        "candidate_file": "06_shift.wav",
        "ref_file": None,
        "title": "06 双离合极速升挡 (Dual-Clutch Shift Transient)",
        "desc": "7速F1双离合变速箱在7000转瞬态升挡。毫秒级微切点火降扭矩，转速闪电跌落后瞬间咬合下一挡位。",
        "focus": "关注换挡瞬间微切扭矩的干脆利落程度，转速跌落瞬间的声学连贯性与冲刺推背感。",
        "origin_tag": "物理模型高保真仿真"
    },
    {
        "id": "07_steady_high",
        "index": 7,
        "category": "cruising",
        "candidate_file": "07_steady_high.wav",
        "ref_file": "ref_steady_high.wav",
        "title": "07 超高速稳态巡航 (~7000 RPM)",
        "desc": "德国无限速高速公路280+ km/h极限巡航。排气旁通阀门彻底敞开，消音器短路直通，高频金属共振贯穿整个声场。",
        "focus": "关注极速巡航下高频能量的纯净度与穿透力，是否有声压压迫感，同时避免刺耳疲劳失真。",
        "origin_tag": "YouTube 德国高速 (AutoTopNL 0-310km/h)"
    },
    {
        "id": "08_steady_low",
        "index": 8,
        "category": "cruising",
        "candidate_file": "08_steady_low.wav",
        "ref_file": "ref_steady_low.wav",
        "title": "08 低速城市巡航 (~1500 RPM)",
        "desc": "城市轻负荷跟车工况，转速约1500转。排气阀门关闭，声浪深沉内敛，展现日常驾驶的舒适质感。",
        "focus": "关注低转速下的排气纯净度，低频饱满而不发闷，无塑料箱体共鸣。",
        "origin_tag": "YouTube 德国高速 (AutoTopNL 0-310km/h)"
    },
    {
        "id": "09_steady_mid",
        "index": 9,
        "category": "cruising",
        "candidate_file": "09_steady_mid.wav",
        "ref_file": "ref_steady_mid.wav",
        "title": "09 中速公路巡航 (~3500 RPM)",
        "desc": "3500转常规巡航工况，正处于排气旁通阀开启的临界转速区间。自吸V8声浪从中速向高音阶过渡。",
        "focus": "关注声场纵深与层次感，机体机械做功声与排气共鸣的协调融合。",
        "origin_tag": "YouTube 德国高速 (AutoTopNL 0-310km/h)"
    },
    {
        "id": "10_tip_in",
        "index": 10,
        "category": "acceleration",
        "candidate_file": "10_tip_in.wav",
        "ref_file": None,
        "title": "10 急踩油门瞬态响应 (Throttle Tip-In)",
        "desc": "巡航中节气门瞬间从轻负荷踏板踩至到底。大口径独立节气门瞬间涌入海量空气，高转自吸声浪零迟滞爆发。",
        "focus": "关注油门踏下瞬间进气咆哮建立时间（Attack Time），爆发力是否凌厉敏捷，有无迟滞软拖。",
        "origin_tag": "物理模型高保真仿真"
    },
]

# Read summary overrides
summary_path = Path(r"E:\Tesla_speed\stage_ad_runs\ferrari_458_closed_loop_v1\closed_loop_summary.json")
summary = json.loads(summary_path.read_text(encoding="utf-8"))
final_overrides = summary["final_overrides"]

PARAMETERS = [
    {"group": "燃烧与机体 (Combustion)", "key": "combustion_rise_time",    "name": "燃烧升压时间 (Rise Time)",  "base": 0.0022,  "final": round(final_overrides.get("combustion_rise_time", 0.0025), 6), "delta": round((final_overrides.get("combustion_rise_time", 0.0025)/0.0022 - 1)*100, 1), "desc": "优化燃烧爆发上升沿，消除稀碎杂刺，使脉冲饱满清脆"},
    {"group": "燃烧与机体 (Combustion)", "key": "combustion_event_energy", "name": "单缸爆发能量 (Event Energy)", "base": 0.480,   "final": round(final_overrides.get("combustion_event_energy", 0.352), 4), "delta": round((final_overrides.get("combustion_event_energy", 0.352)/0.480 - 1)*100, 1), "desc": "校准做功压强，与实车4.5L自吸缸压动态严密对齐"},
    {"group": "燃烧与机体 (Combustion)", "key": "combustion_decay_time",   "name": "脉冲衰减时间 (Decay Time)",  "base": 0.018,   "final": round(final_overrides.get("combustion_decay_time", 0.0189), 4), "delta": round((final_overrides.get("combustion_decay_time", 0.0189)/0.018 - 1)*100, 1), "desc": "精细控制排气门开启泄压尾部形态，保持高转通透"},
    {"group": "燃烧与机体 (Combustion)", "key": "load_exponent",           "name": "负荷耦合指数 (Load Exponent)","base": 0.720,   "final": round(final_overrides.get("load_exponent", 0.798), 4), "delta": round((final_overrides.get("load_exponent", 0.798)/0.720 - 1)*100, 1), "desc": "高负荷全开时声量呈指数级激增，小负荷轻盈内敛"},
    {"group": "燃烧与机体 (Combustion)", "key": "blowdown_event",          "name": "排气吹扫能量 (Blowdown)",    "base": 0.380,   "final": round(final_overrides.get("blowdown_event", 0.247), 4), "delta": round((final_overrides.get("blowdown_event", 0.247)/0.380 - 1)*100, 1), "desc": "高速气流扫气声压，消除人工粗糙度"},
    {"group": "燃烧与机体 (Combustion)", "key": "cycle_variation",         "name": "工作循环离散度 (Cycle Var)",  "base": 0.035,   "final": round(final_overrides.get("cycle_variation", 0.061), 4), "delta": round((final_overrides.get("cycle_variation", 0.061)/0.035 - 1)*100, 1), "desc": "重塑平面曲轴对称脉冲中的自然微幅生理呼吸律动"},
    {"group": "排气与谐振 (Exhaust)",    "key": "collector_loss",          "name": "三出中置尾段汇流阻尼",       "base": 0.950,   "final": 0.950, "delta": 0.0, "desc": "精准再现法拉利专利3出中央排气管背压与谐振特性"},
    {"group": "排气与谐振 (Exhaust)",    "key": "gas_temperature",        "name": "排气燃气温度 (Gas Temp)",    "base": 830.0,   "final": 830.0, "delta": 0.0, "desc": "影响排气管道声速（~660m/s），精确锁定声学谐振腔峰值频率"},
    {"group": "排气与谐振 (Exhaust)",    "key": "intake_mix",              "name": "多喉直吸进气混合比",         "base": 0.220,   "final": 0.220, "delta": 0.0, "desc": "自然吸气高转速进气风箱共鸣咆哮"},
    {"group": "回火与瞬态 (Afterfire)",  "key": "afterfire_gain",          "name": "减速回火强度 (Afterfire Gain)","base": 0.035,  "final": 0.035, "delta": 0.0, "desc": "松油未燃燃油爆燃枪击爆音强度"},
    {"group": "回火与瞬态 (Afterfire)",  "key": "afterfire_cooldown",      "name": "回火冷却间隔 (Cooldown)",    "base": 0.070,   "final": 0.070, "delta": 0.0, "desc": "连续回火爆音触发最小时间间隔"},
]

def load_audio_b64(path: Path) -> str:
    if path.exists():
        return "data:audio/wav;base64," + base64.b64encode(path.read_bytes()).decode()
    return ""

def main():
    print("=== Generating Ferrari 458 Italia Audition Dashboard ===")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    
    # 1. Prepare JSONs
    scenes_json = json.dumps(SCENES, ensure_ascii=False)
    params_json = json.dumps(PARAMETERS, ensure_ascii=False)
    
    # Customize template header & texts for Ferrari 458
    html = template
    html = html.replace(
        "<title>Dodge Challenger SRT Hellcat V8 - 声音算法人耳试听评审系统</title>",
        "<title>Ferrari 458 Italia 4.5L V8 - 声音算法人耳试听评审系统</title>"
    )
    html = html.replace(
        '<h1 class="font-bold text-lg text-white tracking-wide">DODGE HELLCAT V8 声音仿真人耳试听</h1>',
        '<h1 class="font-bold text-lg text-white tracking-wide">FERRARI 458 ITALIA V8 声音仿真人耳试听</h1>'
    )
    html = html.replace(
        '<p class="text-xs text-slate-400">声学闭环校准与真车A/B对比评审控制台 · Dodge Challenger SRT Hellcat 6.2L Supercharged</p>',
        '<p class="text-xs text-slate-400">声学闭环校准与真车A/B对比评审控制台 · Ferrari 458 Italia 4.5L Flat-Plane V8 (9000 RPM)</p>'
    )
    html = html.replace(
        '<span class="font-mono font-bold text-amber-400 line-through">0.880</span>',
        '<span class="font-mono font-bold text-amber-400 line-through">0.601</span>'
    )
    html = html.replace(
        '<span class="font-mono font-bold text-emerald-400">0.648</span>',
        '<span class="font-mono font-bold text-emerald-400">0.449</span>'
    )
    html = html.replace(
        '<span class="text-[10px] bg-emerald-950/80 text-emerald-300 border border-emerald-800 px-1 py-0.2 rounded font-semibold">-26.3%</span>',
        '<span class="text-[10px] bg-emerald-950/80 text-emerald-300 border border-emerald-800 px-1 py-0.2 rounded font-semibold">-25.3%</span>'
    )
    html = html.replace(
        '<span class="font-mono font-bold text-purple-400">AA-C3 (P3)</span>',
        '<span class="font-mono font-bold text-purple-400">Stage AD (P3 Flat-Plane)</span>'
    )
    html = html.replace(
        '<span class="font-mono font-bold text-sky-400">18 项</span>',
        '<span class="font-mono font-bold text-sky-400">11 项</span>'
    )
    
    # Inject Vehicle Switcher Navigation Bar directly at top of body!
    vehicle_nav = '''
  <!-- VEHICLE SELECTION SWITCHER -->
  <div class="bg-[#131b2e] border-b border-slate-700/80 px-4 py-2 sticky top-[65px] z-30 shadow-md">
    <div class="max-w-7xl mx-auto flex items-center justify-between">
      <div class="flex items-center gap-2 text-xs">
        <span class="text-slate-400 font-medium">当前评测车型:</span>
        <span class="px-2.5 py-1 rounded-md bg-red-600/30 text-red-300 border border-red-500/50 font-bold flex items-center gap-1">
          🏎️ Ferrari 458 Italia (4.5L 自吸平面曲轴 V8 · 9000 RPM)
        </span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-slate-400 hidden sm:inline">切换车型:</span>
        <a href="http://localhost:8088" class="text-xs px-3 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-amber-300 border border-amber-500/40 transition-colors flex items-center gap-1 font-medium">
          ⚡ Dodge Hellcat 6.2L (机械增压 V8)
        </a>
        <a href="http://localhost:8089" class="text-xs px-3 py-1 rounded-md bg-red-950/90 text-red-400 border border-red-700/80 font-bold flex items-center gap-1 pointer-events-none">
          🏎️ Ferrari 458 Italia (当前)
        </a>
      </div>
    </div>
  </div>
    '''
    html = html.replace("</header>", "</header>\n" + vehicle_nav)

    # 2. Build streaming mode (fast, lightweight index.html)
    print("Building streaming index.html...")
    streaming_html = (html
                      .replace("__SCENES_JSON__", scenes_json)
                      .replace("__PARAMS_JSON__", params_json)
                      .replace("__AUDIOS_JSON__", "{}"))
    
    out_streaming = PACKAGE_DIR / "index.html"
    out_streaming.write_text(streaming_html, encoding="utf-8")
    print(f"  ✓ Written {out_streaming} ({out_streaming.stat().st_size // 1024} KB)")

    # 3. Build standalone mode (embedded base64 index_standalone.html)
    print("Building embedded standalone index_standalone.html...")
    audio_store = {}
    for scene in SCENES:
        key_c = scene["id"] + "_candidate"
        cand_path = WEB_AUDIO_DIR / scene["candidate_file"]
        audio_store[key_c] = load_audio_b64(cand_path)
        print(f"  {'OK' if audio_store[key_c] else 'MISSING':7s} candidate: {scene['candidate_file']}")
        if scene.get("ref_file"):
            key_r = scene["id"] + "_ref"
            ref_path = WEB_AUDIO_DIR / scene["ref_file"]
            audio_store[key_r] = load_audio_b64(ref_path)
            print(f"  {'OK' if audio_store[key_r] else 'MISSING':7s} reference: {scene['ref_file']}")

    audios_json = json.dumps(audio_store)
    standalone_html = (html
                       .replace("__SCENES_JSON__", scenes_json)
                       .replace("__PARAMS_JSON__", params_json)
                       .replace("__AUDIOS_JSON__", audios_json))
    
    out_standalone = PACKAGE_DIR / "index_standalone.html"
    out_standalone.write_text(standalone_html, encoding="utf-8")
    print(f"  ✓ Written {out_standalone} ({out_standalone.stat().st_size // 1024 // 1024} MB)")
    print("Dashboard generation complete!")

if __name__ == "__main__":
    main()
