import json
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.three_way_audition import (
    build_page_html,
    render_vehicle_switcher,
)


def scene():
    return {
        "id": "01_afterfire",
        "index": 1,
        "category": "afterfire",
        "candidate_file": "A_01_afterfire.wav",
        "feedback_file": "B_01_afterfire.wav",
        "reference_file": "C_01_afterfire.wav",
        "title": "01 三路对照",
        "desc": "受控场景",
        "focus": "比较三路声音",
    }


def contract(feedback=True, reference=True):
    return {
        "schema": "s12.stage_ah.three_way.dashboard.v1",
        "vehicle": "demo",
        "package_id": "three-way-demo",
        "source_roles": {
            "original": {"label": "A: 原始算法（未加负反馈）", "available": True},
            "feedback": {"label": "B: 负反馈算法", "available": feedback,
                          "reason": "无合格 B" if not feedback else ""},
            "reference": {"label": "C: 真车原声", "available": reference},
        },
    }


def test_page_contract_exposes_distinct_three_way_sources(tmp_path):
    template = Path(
        "tools/sound_sim/s12/acoustic_identity_v015/stage_ad/audition_dashboard_template.html"
    ).read_text(encoding="utf-8")
    audio = {
        "01_afterfire_original": "data:audio/wav;base64,QQ==",
        "01_afterfire_feedback": "data:audio/wav;base64,Qg==",
        "01_afterfire_reference": "data:audio/wav;base64,Qw==",
    }
    html = build_page_html(template, "Demo", "DEMO TITLE", "DEMO SUBTITLE",
                           [scene()], contract(), audio, [])
    assert "A: 原始算法（未加负反馈）" in html
    assert "B: 负反馈算法" in html
    assert "C: 真车原声" in html
    assert "switchTriSource('original')" in html
    assert "switchTriSource('feedback')" in html
    assert "switchTriSource('reference')" in html
    assert 'const AUDIO_STORE = ' + json.dumps(audio, ensure_ascii=False) in html


def test_missing_feedback_is_explicitly_disabled():
    template = Path(
        "tools/sound_sim/s12/acoustic_identity_v015/stage_ad/audition_dashboard_template.html"
    ).read_text(encoding="utf-8")
    html = build_page_html(template, "Demo", "DEMO TITLE", "DEMO SUBTITLE",
                           [scene()], contract(feedback=False),
                           {"01_afterfire_original": "data:audio/wav;base64,QQ==",
                            "01_afterfire_reference": "data:audio/wav;base64,Qw=="}, [])
    assert "B: 负反馈算法（不可用）" in html
    assert "无合格 B" in html


def test_vehicle_switcher_uses_relative_same_port_routes():
    html = render_vehicle_switcher("demo", [
        {"key": "demo", "name": "Demo", "status": "READY"},
        {"key": "other", "name": "Other", "status": "BLOCKED"},
    ])
    assert 'id="vehicleSwitcher"' in html
    assert 'value="../demo/index.html" selected' in html
    assert 'value="../other/index.html"' in html
    assert "Other · BLOCKED" in html
