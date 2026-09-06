"""
build_unified_dashboards.py
Builds physics audio tracks and self-contained side-by-side audition dashboards for:
1. Dodge Challenger SRT Hellcat (6.2L SC V8) -> port 8088
2. Ferrari 458 Italia (4.5L NA Flat-plane V8) -> port 8089
3. Lexus LFA (4.8L NA 72° V10) -> port 8090
4. Nissan GT-R R35 (3.8L Twin-Turbo 60° V6) -> port 8091

Every dashboard follows the exact Ferrari-style side-by-side layout:
- Both Candidate (仿真声音) and Reference (真车原声) placed side-by-side in the same card!
- Top master dock with instant seamless A/B switching and real-time FFT visualizer!
- Global 4-car navigation bar at the top of every page!
"""

import os
import json
import base64
from pathlib import Path
import numpy as np
import scipy.io.wavfile as wavfile
from engine_sim_acoustics import EngineAcoustics

TEMPLATE_PATH = Path(r"E:\Tesla_speed\worktrees\s12-stage-ad-closed-loop-calibration\tools\sound_sim\s12\acoustic_identity_v015\stage_ad\audition_dashboard_template.html")

VEHICLE_CONFIGS = {
    "hellcat": {
        "dir": Path(r"E:\Tesla_speed\review_packages\s12-stage-ad-hellcat-closed-loop-v1"),
        "port": 8088,
        "name": "Dodge Challenger SRT Hellcat",
        "title": "DODGE HELLCAT V8 声音仿真人耳试听",
        "subtitle": "声学闭环校准与真车A/B对比评审控制台 · Dodge Challenger SRT Hellcat 6.2L Supercharged (6500 RPM)",
        "badge": "⚡ Dodge Hellcat 6.2L (机械增压 V8)",
        "icon": "⚡",
        "color": "amber",
        "idle_rpm": 720.0,
        "redline_rpm": 6500.0,
        "pull_start": 1500.0,
        "pull_end": 6200.0,
        "shift_cut": 0.12,
        "ref_source": "YouTube (AutoTopNL) / B站实录",
        "scenes": [
            {
                "id": "01_afterfire", "index": 1, "category": "afterfire",
                "candidate_file": "01_afterfire.wav", "ref_file": "ref_afterfire.wav",
                "title": "01 减速回火与爆音 (Afterfire / Pops & Bangs)",
                "desc": "高速轰油后急剧松油，未燃混合气进入红热排气管爆燃产生的放炮与劈啪回火。美式大V8特征性点火截断爆音。",
                "focus": "关注回火瞬态的打击感、空气爆炸张力及尾音消散的自然度。"
            },
            {
                "id": "02_full_pull", "index": 2, "category": "acceleration",
                "candidate_file": "02_full_pull.wav", "ref_file": "ref_full_pull.wav",
                "title": "02 全负荷加速狂飙 (Full Pull / WOT Acceleration)",
                "desc": "节气门100%全开冲刺。机械增压器双螺杆高速气流啸叫（Supercharger Whine）与十字曲轴HEMI低沉咆哮交织，声浪极具压迫感。",
                "focus": "关注4000+ RPM时标志性机械增压“猫叫”啸叫声与十字曲轴大排量排气低频的完美平衡。"
            },
            {
                "id": "03_hot_idle", "index": 3, "category": "idle",
                "candidate_file": "03_hot_idle.wav", "ref_file": "ref_hot_idle.wav",
                "title": "03 热态怠速稳态 (Hot Idle ~720 RPM)",
                "desc": "发动机热机720转怠速。十字曲轴90度点火间隙造成的非对称脉动，呈现标志性的美式‘煮水声’（Chop），低频松散而有力。",
                "focus": "关注气缸做功间歇的不均匀律动感，是否有足够的24/48 Hz低频胸腔共振。"
            },
            {
                "id": "04_idle_return", "index": 4, "category": "idle",
                "candidate_file": "04_idle_return.wav", "ref_file": "ref_hot_idle.wav",
                "title": "04 轰油回落怠速 (Idle Return / Rev Drop)",
                "desc": "转速从高位滑行快速回落到怠速，闭环调速器介入稳定，没有失速抖动，声波平稳回落至基底轰鸣。",
                "focus": "关注回落过程的音量衰减曲线与怠速接管平顺度。"
            },
            {
                "id": "05_lift", "index": 5, "category": "dynamics",
                "candidate_file": "05_lift.wav", "ref_file": "ref_afterfire.wav",
                "title": "05 大负荷突然松油 (Lift-off Deceleration)",
                "desc": "高负荷加速时瞬间收油门，节气门关闭，发动机进入发动机制动减速工况，伴随排气管低沉反吐轰鸣与零星脆爆。",
                "focus": "关注松油瞬间声压骤降的瞬态响应与持续滑行时的排气管共鸣。"
            },
            {
                "id": "06_shift", "index": 6, "category": "dynamics",
                "candidate_file": "06_shift.wav", "ref_file": "",
                "title": "06 升挡扭矩截断 (Shift Interruption & Crack)",
                "desc": "全油门加速过程中快速升挡，8AT变速箱换挡时触发短暂点火推迟与切油，随后在齿轮啮合瞬间产生沉重的排气回压爆破声。",
                "focus": "关注换挡瞬间120ms能量凹陷的干脆程度与动力重新接合时的排气管冲击力。"
            },
            {
                "id": "07_steady_high", "index": 7, "category": "cruise",
                "candidate_file": "07_steady_high.wav", "ref_file": "ref_steady_high.wav",
                "title": "07 高转速巡航 (Steady High 5000 RPM)",
                "desc": "高挡位5000转中高负荷高速巡航，HEMI V8燃烧脉冲密集，机械增压器轻微啸叫，气流声与机械轰鸣交融。",
                "focus": "关注高转速下燃烧谐波的层次感与机舱内增压器微弱高频哨音。"
            },
            {
                "id": "08_steady_low", "index": 8, "category": "cruise",
                "candidate_file": "08_steady_low.wav", "ref_file": "ref_steady_low.wav",
                "title": "08 低转速平稳巡航 (Steady Low 1500 RPM)",
                "desc": "平顺道路1500转轻负荷跟车巡航，排气声浪低沉内敛，低频隆隆声稳定可控，无恼人共振轰头感。",
                "focus": "关注低转巡航时低频能量的厚实度与平顺性。"
            },
            {
                "id": "09_steady_mid", "index": 9, "category": "cruise",
                "candidate_file": "09_steady_mid.wav", "ref_file": "ref_steady_mid.wav",
                "title": "09 中转速动力巡航 (Steady Mid 3000 RPM)",
                "desc": "中速道路3000转稳定巡航，V8四阶点火基频位于200Hz黄金爆发区，动力响应随叫随到，声浪富有张力。",
                "focus": "关注中转速段声浪的饱满感与声压级线性度。"
            },
            {
                "id": "10_tip_in", "index": 10, "category": "dynamics",
                "candidate_file": "10_tip_in.wav", "ref_file": "",
                "title": "10 突然急踩油门瞬态 (Tip-in Transient)",
                "desc": "低负荷巡航时瞬间地板油深踩，节气门瞬间完全开大，进气歧管负压骤变为正压，机械增压器气流瞬间喷涌，排气声浪瞬间撕裂爆发。",
                "focus": "关注油门踩下第0.1秒的进气吸吮爆发感与排气音量的瞬间阶跃阶度。"
            }
        ]
    },
    "ferrari_458": {
        "dir": Path(r"E:\Tesla_speed\review_packages\s12-stage-ad-ferrari-458-closed-loop-v1"),
        "port": 8089,
        "name": "Ferrari 458 Italia",
        "title": "FERRARI 458 ITALIA V8 声音仿真人耳试听",
        "subtitle": "声学闭环校准与真车A/B对比评审控制台 · Ferrari 458 Italia 4.5L Flat-Plane V8 (9000 RPM)",
        "badge": "🏎️ Ferrari 458 Italia (自吸平面曲轴 V8)",
        "icon": "🏎️",
        "color": "red",
        "idle_rpm": 1000.0,
        "redline_rpm": 9000.0,
        "pull_start": 2200.0,
        "pull_end": 8800.0,
        "shift_cut": 0.08,
        "ref_source": "YouTube (AutoTopNL 0-310km/h)",
        "scenes": [
            {
                "id": "01_afterfire", "index": 1, "category": "afterfire",
                "candidate_file": "01_afterfire.wav", "ref_file": "ref_afterfire.wav",
                "title": "01 减速回火与排气脆爆 (Afterfire / Pops & Bangs)",
                "desc": "9000转高速轰油后急松油门，未燃混合气在高温排气管爆燃。平面曲轴产生极其清脆干脆的金属枪击爆音，无美式浑浊拖沓。",
                "focus": "关注高转速丢油瞬态排气管爆音的清脆打击感、金属高频张力及回火收尾的干脆程度。"
            },
            {
                "id": "02_full_pull", "index": 2, "category": "acceleration",
                "candidate_file": "02_full_pull.wav", "ref_file": "ref_full_pull.wav",
                "title": "02 全负荷红线嘶吼 (Full Pull / WOT 3000-9000 RPM)",
                "desc": "油门全开从3000转直冲9000转红线。180度平面曲轴每转均匀4次排气脉冲（E4阶次），随着转速攀升演化为法拉利标志性的高亢撕裂歌喉。",
                "focus": "关注中高转速（6000-9000 RPM）纯粹的自然吸气平面曲轴尖啸，高阶谐波穿透力强且无稀碎杂散噪音。"
            },
            {
                "id": "03_hot_idle", "index": 3, "category": "idle",
                "candidate_file": "03_hot_idle.wav", "ref_file": "ref_hot_idle.wav",
                "title": "03 热态怠速稳态 (Hot Idle ~1050 RPM)",
                "desc": "4.5L V8发动机热态1050转平稳怠速。平面曲轴对称敲击声，不同于十字曲轴的咕噜煮水声，呈现出紧凑、清脆、赛车化的机械呼吸感。",
                "focus": "关注1050转怠速气缸做功敲击的均匀节奏感与排气尾段轻微的声压微颤，无粗暴失步感。"
            },
            {
                "id": "04_idle_return", "index": 4, "category": "idle",
                "candidate_file": "04_idle_return.wav", "ref_file": "ref_hot_idle.wav",
                "title": "04 轰油回落怠速 (Idle Return)",
                "desc": "高转速轰油后完全松开油门，转速平滑滑行回落至1050转怠速，闭环调速器无缝接管。",
                "focus": "关注回落过程中的能量衰减包络与落回怠速瞬间的转速稳定性，过渡平顺自然。"
            },
            {
                "id": "05_lift", "index": 5, "category": "dynamics",
                "candidate_file": "05_lift.wav", "ref_file": "ref_afterfire.wav",
                "title": "05 高负荷急收油 (Lift-off Overrun)",
                "desc": "高转速高负荷轰鸣中骤然松油，气门正时与回压突变，产生极其动感的自然吸气赛车减速滑行音。",
                "focus": "关注收油瞬间高频衰减与排气管尾段共振的自然消退。"
            },
            {
                "id": "06_shift", "index": 6, "category": "dynamics",
                "candidate_file": "06_shift.wav", "ref_file": "",
                "title": "06 DCT闪电换挡 (Dual-Clutch Shift Crack)",
                "desc": "7速双离合变速箱全油门升挡，80毫秒瞬间完成扭矩交接与点火截断，伴随清脆激昂的换挡爆音。",
                "focus": "关注双离合换挡的闪电切断感与下一挡位无缝接合的爆破力度。"
            },
            {
                "id": "07_steady_high", "index": 7, "category": "cruise",
                "candidate_file": "07_steady_high.wav", "ref_file": "ref_steady_high.wav",
                "title": "07 高转巡航狂欢 (Steady High 7000 RPM)",
                "desc": "7000转高速轰鸣巡航，平面曲轴进入高谐波共鸣区间，声浪如同意式赛道级乐器般高亢纯粹。",
                "focus": "关注高转速下纯粹的自吸歌喉，声音紧绷激昂无杂散失真。"
            },
            {
                "id": "08_steady_low", "index": 8, "category": "cruise",
                "candidate_file": "08_steady_low.wav", "ref_file": "ref_steady_low.wav",
                "title": "08 低转城市巡航 (Steady Low 2200 RPM)",
                "desc": "2200转城市巡航，排气阀门半开状态下的低沉磁性排气声，低调而不失性能锋芒。",
                "focus": "关注低转速下排气管共振的饱满度与排气脉冲质感。"
            },
            {
                "id": "09_steady_mid", "index": 9, "category": "cruise",
                "candidate_file": "09_steady_mid.wav", "ref_file": "ref_steady_mid.wav",
                "title": "09 中转激情巡航 (Steady Mid 4500 RPM)",
                "desc": "4500转排气旁通阀全开，声浪从沉稳瞬间转变为亢奋，意式跑车的灵魂音色开始完全展现。",
                "focus": "关注排气阀门开启前后的音质跃迁与中频穿透力。"
            },
            {
                "id": "10_tip_in", "index": 10, "category": "dynamics",
                "candidate_file": "10_tip_in.wav", "ref_file": "",
                "title": "10 急踩油门瞬态响应 (Tip-in Transient)",
                "desc": "巡航时瞬间油门到底，8个独立节气门瞬间全开，声浪毫无迟滞地如惊雷般炸裂而出。",
                "focus": "关注大自吸瞬间响应的无延迟感与爆发冲击力。"
            }
        ]
    },
    "lfa": {
        "dir": Path(r"E:\Tesla_speed\review_packages\s12-stage-ad-lfa-closed-loop-v1"),
        "port": 8090,
        "name": "Lexus LFA",
        "title": "LEXUS LFA V10 声音仿真人耳试听",
        "subtitle": "声学闭环校准与真车A/B对比评审控制台 · Lexus LFA 1LR-GUE 4.8L 72° V10 (9500 RPM)",
        "badge": "🇯🇵 Lexus LFA (雅马哈声学调校 V10)",
        "icon": "🇯🇵",
        "color": "cyan",
        "idle_rpm": 950.0,
        "redline_rpm": 9500.0,
        "pull_start": 2500.0,
        "pull_end": 9400.0,
        "shift_cut": 0.06,
        "ref_source": "YouTube (Toyota Times / LFA POV)",
        "scenes": [
            {
                "id": "01_afterfire", "index": 1, "category": "afterfire",
                "candidate_file": "01_afterfire.wav", "ref_file": "ref_afterfire.wav",
                "title": "01 减速回火与天籁收尾 (Afterfire & Overrun)",
                "desc": "9500转天籁之音收油，未燃气体在三出排气钛合金腔体爆鸣，清脆、高贵而富有金属质感的天使咆哮。",
                "focus": "关注高转速收油瞬态的清脆金属爆音与雅马哈声学腔体共振。"
            },
            {
                "id": "02_full_pull", "index": 2, "category": "acceleration",
                "candidate_file": "02_full_pull.wav", "ref_file": "ref_full_pull.wav",
                "title": "02 天使之吼 (Angel's Cry / 9500 RPM WOT)",
                "desc": "4.8L 72度夹角V10，均匀72度点火（5阶与10阶高亢谐波），油门全开直达9500转，F1赛车般的极致天籁尖啸。",
                "focus": "关注7000-9500 RPM纯粹无杂质的超高阶次共鸣，音调平滑如丝般高亢，零杂音。"
            },
            {
                "id": "03_hot_idle", "index": 3, "category": "idle",
                "candidate_file": "03_hot_idle.wav", "ref_file": "ref_hot_idle.wav",
                "title": "03 热车怠速韵律 (Hot Idle ~950 RPM)",
                "desc": "72度等间隔点火V10在950转怠速下的极度平稳机械做功律动，伴随钛合金排气管的微弱回响。",
                "focus": "关注十缸做功的极度细腻均匀感与钛合金消音腔体的微颤声压。"
            },
            {
                "id": "04_idle_return", "index": 4, "category": "idle",
                "candidate_file": "04_idle_return.wav", "ref_file": "ref_hot_idle.wav",
                "title": "04 极速轰油落回怠速 (Ultra-Fast Rev Drop)",
                "desc": "LFA发动机转速攀升与跌落极快（0.6秒直达红线），松油瞬间转速如同自由落体般轻盈滑回950转怠速。",
                "focus": "关注转速跌落的超轻飞轮轻盈感与怠速接管瞬间的绝对平稳。"
            },
            {
                "id": "05_lift", "index": 5, "category": "dynamics",
                "candidate_file": "05_lift.wav", "ref_file": "ref_afterfire.wav",
                "title": "05 高负荷急收油 (High-Load Lift Overrun)",
                "desc": "高速狂飙中收油门，雅马哈声学进气管道与钛合金排气腔体共鸣逐渐消散，留下迷人的滑行声。",
                "focus": "关注进排气高频消退时的空间空气感与金属尾音。"
            },
            {
                "id": "06_shift", "index": 6, "category": "dynamics",
                "candidate_file": "06_shift.wav", "ref_file": "",
                "title": "06 单离合ASG极速切挡 (ASG Rapid Shift)",
                "desc": "6速序列式单离合ASG变速箱全速切挡，60毫秒极速换挡中断，伴随赛车般凶狠的排气管冲击声。",
                "focus": "关注序列式单离合换挡的直接打击感与下一挡位瞬间狂暴介入。"
            },
            {
                "id": "07_steady_high", "index": 7, "category": "cruise",
                "candidate_file": "07_steady_high.wav", "ref_file": "ref_steady_high.wav",
                "title": "07 高转乐器级巡航 (Steady High 7500 RPM)",
                "desc": "7500转稳定高音巡航，十缸高阶谐波如同管弦乐合奏，完全超越普通燃油车音质。",
                "focus": "关注V10独有的五阶次与十阶次和弦感，纯正透明。"
            },
            {
                "id": "08_steady_low", "index": 8, "category": "cruise",
                "candidate_file": "08_steady_low.wav", "ref_file": "ref_steady_low.wav",
                "title": "08 低转静谧巡航 (Steady Low 2000 RPM)",
                "desc": "2000转低转速巡航，排气声音内敛平顺，展现丰田顶级工艺的静谧平衡。",
                "focus": "关注低转速下的纯净底噪与微弱排气脉冲。"
            },
            {
                "id": "09_steady_mid", "index": 9, "category": "cruise",
                "candidate_file": "09_steady_mid.wav", "ref_file": "ref_steady_mid.wav",
                "title": "09 中转渐进鸣唱 (Steady Mid 5000 RPM)",
                "desc": "5000转雅马哈进气调音阀开启，声音从沉稳瞬间转变为高亢昂扬的天籁。",
                "focus": "关注进气调谐腔启动时音色的层次感变化。"
            },
            {
                "id": "10_tip_in", "index": 10, "category": "dynamics",
                "candidate_file": "10_tip_in.wav", "ref_file": "",
                "title": "10 地板油瞬间爆发 (Tip-in Surge)",
                "desc": "轻负荷瞬间地板油，10组节气门同步暴风吸入，高转速V10瞬间爆发出摧枯拉朽的声学冲击。",
                "focus": "关注瞬间深踩油门时进排气声浪毫无迟滞的阶跃响应。"
            }
        ]
    },
    "gtr_r35": {
        "dir": Path(r"E:\Tesla_speed\review_packages\s12-stage-ad-gtr-r35-closed-loop-v1"),
        "port": 8091,
        "name": "Nissan GT-R R35",
        "title": "NISSAN GT-R R35 V6 声音仿真人耳试听",
        "subtitle": "声学闭环校准与真车A/B对比评审控制台 · Nissan GT-R R35 3.8L Twin-Turbo VR38DETT (7200 RPM)",
        "badge": "🚗 Nissan GT-R R35 (双涡轮增压 V6)",
        "icon": "🚗",
        "color": "emerald",
        "idle_rpm": 800.0,
        "redline_rpm": 7200.0,
        "pull_start": 2000.0,
        "pull_end": 7000.0,
        "shift_cut": 0.08,
        "ref_source": "YouTube (POV Nismo Autobahn)",
        "scenes": [
            {
                "id": "01_afterfire", "index": 1, "category": "afterfire",
                "candidate_file": "01_afterfire.wav", "ref_file": "ref_afterfire.wav",
                "title": "01 涡轮收油泄压与回火 (BOV Hiss & Crackles)",
                "desc": "大负荷收油，双进气泄压阀（BOV）瞬间喷薄出清脆高频气流泄压哨音，伴随排气管沉重回火爆鸣。",
                "focus": "关注泄压阀（BOV）急速泄压的扑哧气流声与排气管回火的打击力。"
            },
            {
                "id": "02_full_pull", "index": 2, "category": "acceleration",
                "candidate_file": "02_full_pull.wav", "ref_file": "ref_full_pull.wav",
                "title": "02 双涡轮狂暴起压加速 (Full Pull / Twin Turbo Spool)",
                "desc": "油门全开，双并联IHI涡轮瞬间起压，高频涡轮叶片旋转气流啸叫与VR38DETT沉厚喉音交织。",
                "focus": "关注涡轮起压过程中的叶片高频气流哨音与V6排气低频的浑厚推动力。"
            },
            {
                "id": "03_hot_idle", "index": 3, "category": "idle",
                "candidate_file": "03_hot_idle.wav", "ref_file": "ref_hot_idle.wav",
                "title": "03 战神怠速低吼 (Hot Idle ~800 RPM)",
                "desc": "3.8L V6双涡轮热机800转怠速，大口径钛合金中尾段排气管传递出低沉、沉稳、充满力量感的低频脉冲。",
                "focus": "关注6缸等间隔120度做功脉冲的沉重低频感与排气尾段回响。"
            },
            {
                "id": "04_idle_return", "index": 4, "category": "idle",
                "candidate_file": "04_idle_return.wav", "ref_file": "ref_hot_idle.wav",
                "title": "04 轰油回落稳态 (Idle Return)",
                "desc": "空挡轰油后转速迅速平稳滑落回800转怠速，双涡轮转速缓缓回落，声浪平滑收缩。",
                "focus": "关注转速回落曲线的顺滑度与怠速接管稳定性。"
            },
            {
                "id": "05_lift", "index": 5, "category": "dynamics",
                "candidate_file": "05_lift.wav", "ref_file": "ref_afterfire.wav",
                "title": "05 收油滑行泄压 (Lift-off Deceleration)",
                "desc": "高转速高负荷骤然松油，进气管路正压经双旁通阀排泄，产生标志性的东瀛战神泄压空气回响。",
                "focus": "关注涡轮泄压阀高频气流消散与排气管低频的平稳过渡。"
            },
            {
                "id": "06_shift", "index": 6, "category": "dynamics",
                "candidate_file": "06_shift.wav", "ref_file": "",
                "title": "06 GR6双离合强力换挡 (DCT Snap Shift)",
                "desc": "BorgWarner双离合变速箱80毫秒强力换挡，涡轮保压切火，产生清脆而猛烈的换挡排气爆裂声。",
                "focus": "关注双离合换挡切火瞬间的清脆能量凹陷与重咬瞬间的推背感声学冲击。"
            },
            {
                "id": "07_steady_high", "index": 7, "category": "cruise",
                "candidate_file": "07_steady_high.wav", "ref_file": "ref_steady_high.wav",
                "title": "07 高转速动力巡航 (Steady High 5500 RPM)",
                "desc": "5500转高转速巡航，双涡轮处于持续微正压状态，进排气声音高度饱满，张力十足。",
                "focus": "关注高转速下双涡轮啸叫与V6排气声浪的高频穿透力。"
            },
            {
                "id": "08_steady_low", "index": 8, "category": "cruise",
                "candidate_file": "08_steady_low.wav", "ref_file": "ref_steady_low.wav",
                "title": "08 低转速平稳跟车 (Steady Low 1800 RPM)",
                "desc": "1800转低速跟车，涡轮未起压，排气声音内敛低沉，呈现大排量V6的厚重底气。",
                "focus": "关注低转巡航时低频能量的紧致度，无多余空腔共鸣。"
            },
            {
                "id": "09_steady_mid", "index": 9, "category": "cruise",
                "candidate_file": "09_steady_mid.wav", "ref_file": "ref_steady_mid.wav",
                "title": "09 中转速蓄力巡航 (Steady Mid 3500 RPM)",
                "desc": "3500转正值涡轮扭矩平台起点，随时准备爆发，声浪逐渐从深沉向高亢过渡。",
                "focus": "关注中转速段声浪的层次感与涡轮微弱哨音。"
            },
            {
                "id": "10_tip_in", "index": 10, "category": "dynamics",
                "candidate_file": "10_tip_in.wav", "ref_file": "",
                "title": "10 弹射起步油门全开 (Tip-in & Boost Attack)",
                "desc": "瞬间地板油，双涡轮从真空极速起压至1.4bar，产生雷霆万钧的加速声浪爆发。",
                "focus": "关注涡轮起压时的声音爬升梯度与发动机做功密度的瞬间暴增。"
            }
        ]
    }
}

def load_audio_b64(path: Path) -> str:
    if path.exists():
        return "data:audio/wav;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    return ""

def render_vehicle_audio(v_key: str, cfg: dict):
    print(f"\n=======================================================")
    print(f"--> Rendering 10 Physics Tracks for {cfg['name']} ({v_key})")
    print(f"=======================================================")
    
    sim = EngineAcoustics(vehicle_type=v_key, sr=48000)
    sr = sim.sr
    web_dir = cfg["dir"] / "web_audio"
    web_dir.mkdir(parents=True, exist_ok=True)
    
    idle_rpm = cfg["idle_rpm"]
    redline_rpm = cfg["redline_rpm"]
    pull_start = cfg["pull_start"]
    pull_end = cfg["pull_end"]
    shift_cut = cfg["shift_cut"]
    
    cases = {}
    
    # 01_afterfire (7.0s)
    dur = 7.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.zeros(N)
    t_cut = 2.2
    m_acc = t < t_cut
    rpm[m_acc] = idle_rpm + (0.75 * redline_rpm - idle_rpm) * (t[m_acc] / t_cut) ** 1.3
    thr[m_acc] = 0.85
    m_dec = t >= t_cut
    tau = (t[m_dec] - t_cut) / (dur - t_cut)
    rpm[m_dec] = idle_rpm + (0.75 * redline_rpm - idle_rpm) * np.exp(-tau * 3.5)
    thr[m_dec] = 0.0
    af_events = [(2.5, 0.9), (2.8, 0.7), (3.2, 1.0), (3.6, 0.8), (4.2, 0.6), (4.9, 0.5), (5.5, 0.4)]
    bov_events = [(2.25, 0.35)] if cfg.get("has_turbo") or v_key == "gtr_r35" else None
    cases["01_afterfire"] = (rpm, thr, dur, None, af_events, bov_events)
    
    # 02_full_pull (7.0s)
    dur = 7.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = pull_start + (pull_end - pull_start) * ((t / dur) ** 1.15)
    thr = np.ones(N) * 1.0
    cases["02_full_pull"] = (rpm, thr, dur, None, None, None)
    
    # 03_hot_idle (6.0s)
    dur = 6.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = idle_rpm + 10.0 * np.sin(2.0 * np.pi * 0.4 * t) + 6.0 * np.sin(2.0 * np.pi * 0.85 * t)
    thr = np.zeros(N)
    cases["03_hot_idle"] = (rpm, thr, dur, None, None, None)
    
    # 04_idle_return (6.0s)
    dur = 6.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.zeros(N)
    t1, t2 = 1.0, 2.2
    m1 = t < t1
    rpm[m1] = idle_rpm
    thr[m1] = 0.0
    m2 = (t >= t1) & (t < t2)
    blip_peak = 0.55 * redline_rpm
    rpm[m2] = idle_rpm + (blip_peak - idle_rpm) * np.sin(np.pi * (t[m2] - t1) / (t2 - t1))
    thr[m2] = 0.70 * np.sin(np.pi * (t[m2] - t1) / (t2 - t1))
    m3 = t >= t2
    tau = (t[m3] - t2) / (dur - t2)
    rpm[m3] = idle_rpm + (blip_peak - idle_rpm) * 0.2 * np.exp(-tau * 4.0)
    thr[m3] = 0.0
    bov_ret = [(2.22, 0.25)] if v_key == "gtr_r35" else None
    cases["04_idle_return"] = (rpm, thr, dur, None, None, bov_ret)
    
    # 05_lift (7.0s)
    dur = 7.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.zeros(N)
    t_lift = 2.0
    m_hold = t < t_lift
    rpm[m_hold] = 0.65 * redline_rpm
    thr[m_hold] = 0.60
    m_lift = t >= t_lift
    tau_lift = (t[m_lift] - t_lift) / (dur - t_lift)
    rpm[m_lift] = idle_rpm + (0.65 * redline_rpm - idle_rpm) * np.exp(-tau_lift * 2.5)
    thr[m_lift] = 0.0
    af_events_lift = [(2.2, 0.6), (2.6, 0.8), (3.1, 0.5), (3.7, 0.4)]
    bov_lift = [(2.05, 0.35)] if v_key == "gtr_r35" else None
    cases["05_lift"] = (rpm, thr, dur, None, af_events_lift, bov_lift)
    
    # 06_shift (6.0s)
    dur = 6.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.ones(N) * 0.95
    t_shift = 2.8
    m_g1 = t < t_shift
    rpm[m_g1] = 3000.0 + (0.85 * redline_rpm - 3000.0) * (t[m_g1] / t_shift)
    m_g2 = t >= t_shift
    rpm_after = 0.55 * redline_rpm
    rpm[m_g2] = rpm_after + (0.80 * redline_rpm - rpm_after) * ((t[m_g2] - t_shift) / (dur - t_shift))
    shift_events = [(t_shift, shift_cut)]
    bov_shift = [(t_shift + 0.02, 0.18)] if v_key == "gtr_r35" else None
    cases["06_shift"] = (rpm, thr, dur, shift_events, None, bov_shift)
    
    # 07_steady_high (6.0s)
    dur = 6.0
    N = int(sr * dur)
    rpm = np.ones(N) * (0.75 * redline_rpm)
    thr = np.ones(N) * 0.45
    cases["07_steady_high"] = (rpm, thr, dur, None, None, None)
    
    # 08_steady_low (6.0s)
    dur = 6.0
    N = int(sr * dur)
    rpm = np.ones(N) * (idle_rpm + 800.0)
    thr = np.ones(N) * 0.20
    cases["08_steady_low"] = (rpm, thr, dur, None, None, None)
    
    # 09_steady_mid (6.0s)
    dur = 6.0
    N = int(sr * dur)
    rpm = np.ones(N) * (0.45 * redline_rpm)
    thr = np.ones(N) * 0.35
    cases["09_steady_mid"] = (rpm, thr, dur, None, None, None)
    
    # 10_tip_in (6.0s)
    dur = 6.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.zeros(N)
    t_snap = 2.0
    m_pre = t < t_snap
    rpm[m_pre] = idle_rpm + 1200.0
    thr[m_pre] = 0.15
    m_post = t >= t_snap
    r_start = idle_rpm + 1200.0
    rpm[m_post] = r_start + (0.85 * redline_rpm - r_start) * (((t[m_post] - t_snap) / (dur - t_snap)) ** 1.2)
    thr[m_post] = 1.0
    cases["10_tip_in"] = (rpm, thr, dur, None, None, None)
    
    for name, (r_curve, t_curve, d, s_ev, a_ev, b_ev) in cases.items():
        print(f"  Rendering {name}.wav ...")
        audio = sim.render_track(r_curve, t_curve, d, shift_events=s_ev, afterfire_events=a_ev, bov_events=b_ev)
        wavfile.write(str(web_dir / f"{name}.wav"), sr, audio)
        wavfile.write(str(cfg["dir"] / f"{name}.wav"), sr, audio)
        
    print(f"Done rendering all 10 tracks for {v_key}.")

def build_dashboard(v_key: str, cfg: dict):
    print(f"\n--> Building Side-by-Side Audition Dashboard for {cfg['name']} (Port {cfg['port']})")
    
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    
    # Replace header info
    html = template
    html = html.replace(
        "<title>Dodge Challenger SRT Hellcat V8 - 声音算法人耳试听评审系统</title>",
        f"<title>{cfg['name']} - 声音算法人耳试听评审系统</title>"
    )
    html = html.replace(
        '<h1 class="font-bold text-lg text-white tracking-wide">DODGE HELLCAT V8 声音仿真人耳试听</h1>',
        f'<h1 class="font-bold text-lg text-white tracking-wide">{cfg["title"]}</h1>'
    )
    html = html.replace(
        '<p class="text-xs text-slate-400">声学闭环校准与真车A/B对比评审控制台 · Dodge Challenger SRT Hellcat 6.2L Supercharged</p>',
        f'<p class="text-xs text-slate-400">{cfg["subtitle"]}</p>'
    )
    
    # Global 4-Vehicle Top Switcher Navigation Bar
    nav_links = []
    for vk, other_cfg in VEHICLE_CONFIGS.items():
        is_current = (vk == v_key)
        if is_current:
            nav_links.append(f'''
              <a href="http://localhost:{other_cfg['port']}" class="text-xs px-3 py-1 rounded-md bg-red-950/90 text-red-400 border border-red-700/80 font-bold flex items-center gap-1 pointer-events-none">
                {other_cfg['icon']} {other_cfg['name']} (当前)
              </a>
            ''')
        else:
            nav_links.append(f'''
              <a href="http://localhost:{other_cfg['port']}" class="text-xs px-3 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors flex items-center gap-1 font-medium">
                {other_cfg['icon']} {other_cfg['name']}
              </a>
            ''')
            
    vehicle_nav = f'''
  <!-- GLOBAL 4-VEHICLE SELECTION SWITCHER -->
  <div class="bg-[#131b2e] border-b border-slate-700/80 px-4 py-2 sticky top-[65px] z-30 shadow-md">
    <div class="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
      <div class="flex items-center gap-2 text-xs">
        <span class="text-slate-400 font-medium">当前评测车型:</span>
        <span class="px-2.5 py-1 rounded-md bg-red-600/30 text-red-300 border border-red-500/50 font-bold flex items-center gap-1">
          {cfg['badge']}
        </span>
      </div>
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="text-xs text-slate-400 hidden md:inline mr-1">切换车型:</span>
        {''.join(nav_links)}
      </div>
    </div>
  </div>
    '''
    html = html.replace("</header>", "</header>\n" + vehicle_nav)
    
    scenes_json = json.dumps(cfg["scenes"], ensure_ascii=False)
    params_json = "[]"
    
    # Pack Base64 audio store
    web_dir = cfg["dir"] / "web_audio"
    audio_store = {}
    print("  Packing Base64 Audio data for all scenes...")
    for scene in cfg["scenes"]:
        cand_key = scene["id"] + "_candidate"
        cand_path = web_dir / scene["candidate_file"]
        audio_store[cand_key] = load_audio_b64(cand_path)
        
        if scene.get("ref_file"):
            ref_key = scene["id"] + "_ref"
            ref_path = web_dir / scene["ref_file"]
            audio_store[ref_key] = load_audio_b64(ref_path)
            print(f"    Scene {scene['id']}: Candidate OK, Reference OK ({scene['ref_file']})")
        else:
            print(f"    Scene {scene['id']}: Candidate OK, Reference NONE")
            
    audios_json = json.dumps(audio_store)
    
    full_html = (html
                 .replace("__SCENES_JSON__", scenes_json)
                 .replace("__PARAMS_JSON__", params_json)
                 .replace("__AUDIOS_JSON__", audios_json))
                 
    out_index = cfg["dir"] / "index.html"
    out_standalone = cfg["dir"] / "index_standalone.html"
    
    out_index.write_text(full_html, encoding="utf-8")
    out_standalone.write_text(full_html, encoding="utf-8")
    print(f"  ✓ Written {out_index} ({out_index.stat().st_size // 1024 // 1024} MB embedded Base64)")
    print(f"  ✓ Written {out_standalone}")

def main():
    for v_key, cfg in VEHICLE_CONFIGS.items():
        render_vehicle_audio(v_key, cfg)
        build_dashboard(v_key, cfg)
        
    print("\n=======================================================")
    print("All 4 Vehicle Physics Packages & Dashboards Completed!")
    print("=======================================================")

if __name__ == "__main__":
    main()
