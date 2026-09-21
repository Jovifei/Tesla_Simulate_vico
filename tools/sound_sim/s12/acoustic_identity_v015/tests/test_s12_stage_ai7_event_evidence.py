"""Stage AI-7 continuous-drive observed-event evidence contracts."""

from __future__ import annotations

import hashlib
import json
import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import continuous_drive as cycle
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import remaining_vehicle_pipeline as pipeline
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import qualified_three_way as qualified
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.feedback_evidence import SCENES
from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender


def _report(*, observed_onset_s=18.043, observed_frame=866064,
            domain="SOURCE_STEM_PRE_IR"):
    return {
        "candidate_source_diagnostics": {
            "shift_event_count": 3,
            "afterfire_event_count": 1,
            "afterfire_stem_energy_after_lift": 1.0,
            "afterfire_requested_event_times_s": [18.0],
            "afterfire_onset_s": observed_onset_s,
            "afterfire_observed_onset_s": observed_onset_s,
            "afterfire_observed_onset_frame": observed_frame,
            "afterfire_observation_domain": domain,
        }
    }


def test_event_evidence_separates_requested_from_observed_onset():
    observed = cycle._validate_event_diagnostics(_report(), cycle.continuous_events())

    assert observed["requested_event_times_s"] == [18.0]
    assert observed["observed_onset_frame"] == 866064
    assert observed["observed_onset_s"] == pytest.approx(18.043)
    assert observed["observation_domain"] == "SOURCE_STEM_PRE_IR"


@pytest.mark.parametrize(
    ("observed_onset_s", "observed_frame", "domain"),
    [
        (None, 866064, "SOURCE_STEM_PRE_IR"),
        (float("nan"), 866064, "SOURCE_STEM_PRE_IR"),
        (17.999, 863952, "SOURCE_STEM_PRE_IR"),
        (18.043, 866064, "FINAL_PCM"),
    ],
)
def test_event_evidence_rejects_missing_early_or_wrong_domain_observation(
    observed_onset_s, observed_frame, domain
):
    with pytest.raises(ValueError, match="afterfire"):
        cycle._validate_event_diagnostics(
            _report(
                observed_onset_s=observed_onset_s,
                observed_frame=observed_frame,
                domain=domain,
            ),
            cycle.continuous_events(),
        )


def test_observation_frame_must_match_onset_within_one_sample():
    report = _report(observed_onset_s=18.043, observed_frame=866100)

    with pytest.raises(ValueError, match="afterfire"):
        cycle._validate_event_diagnostics(report, cycle.continuous_events())


def test_remaining_engine_records_source_stem_observation(monkeypatch):
    sample_rate = 48_000
    duration = 1.0
    count = int(sample_rate * duration)
    onset_frame = 10_000
    stem = np.zeros((count, 2), dtype=np.float64)
    stem[onset_frame:, 0] = 0.2
    stem[onset_frame:, 1] = 0.1
    source = SourceRender(
        pressure=stem.copy(),
        stems={"afterfire": stem.copy(), "base": np.zeros_like(stem)},
        diagnostics={
            "afterfire_event_count": 1,
            "afterfire_onset_s": onset_frame / sample_rate,
        },
    ).validate()
    monkeypatch.setattr(
        pipeline, "_feedback_source", lambda vehicle, trace, feedback: source
    )
    engine = pipeline.RemainingVehicleEngine(
        "rx7_fd", sample_rate, output_policy=pipeline.LINKED_SOFT_CEILING_V1,
        ir=np.array([1.0]), scene_ids=("continuous_drive",),
        boundary_policy=pipeline.RX7_BOUNDARY_POLICY_V1,
    )
    engine.render_track(
        np.full(count, 2500.0), np.full(count, 0.5), duration,
        afterfire_events=[{"time_s": 0.2}], shift_events=[], bov_events=[],
    )
    diagnostics = engine.reports[-1]["candidate_source_diagnostics"]
    assert diagnostics["afterfire_requested_event_times_s"] == [0.2]
    assert diagnostics["afterfire_observed_onset_frame"] == onset_frame
    assert diagnostics["afterfire_observed_onset_s"] == pytest.approx(onset_frame / sample_rate)
    assert diagnostics["afterfire_observation_domain"] == "SOURCE_STEM_PRE_IR"


def test_legacy_continuous_role_hash_uses_continuous_receipt(tmp_path):
    folder = tmp_path / "rx7_fd"
    audio = folder / "web_audio" / "A_continuous_drive.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"continuous-audio")
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    (folder / "continuous_drive_receipt.json").write_text(
        json.dumps({"wav": {"A": {"wav_file_sha256": digest}}}),
        encoding="utf-8",
    )
    contract = {"source_sha256": {"original": {}}}
    scene = {"id": "continuous_drive", "candidate_file": "A_continuous_drive.wav"}

    assert qualified._legacy_role_sha(folder, contract, scene, "original") == digest


def test_legacy_scene_loader_filters_ai6_continuous_scene(tmp_path):
    page = tmp_path / "index.html"
    scenes = [{"id": scene} for scene in SCENES] + [{"id": "continuous_drive"}]
    page.write_text("const SCENES=" + json.dumps(scenes) + ";", encoding="utf-8")

    assert [row["id"] for row in qualified._load_legacy_scenes(page)] == list(SCENES)
