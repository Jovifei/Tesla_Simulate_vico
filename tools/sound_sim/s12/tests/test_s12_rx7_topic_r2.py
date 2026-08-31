from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference import rx7_topic_r2
from tools.sound_sim.s12.real_reference.rx7_topic_r2 import (
    CANDIDATE_PROFILE_NAME,
    PARAMETER_GROUP,
    PARAMETER_OVERRIDES,
    SOURCE_MANIFEST_NAME,
    Rx7TopicR2Error,
    build_rx7_topic_package,
    load_rx7_source_manifest,
)


SOURCE_ROOT = Path(
    os.environ.get(
        "S12_RX7_SOURCE_ROOT",
        r"E:\Claude_allow\Download\s12-rx7sim-source-audit-20260823",
    )
)
CANDIDATE_ROOT = Path(
    os.environ.get(
        "S12_RX7_CANDIDATE_ROOT",
        r"E:\Claude_allow\Download\s12-professional-long-window-candidate-v1",
    )
)
SOURCE_AVAILABLE = (SOURCE_ROOT / SOURCE_MANIFEST_NAME).is_file()
CANDIDATE_AVAILABLE = (
    CANDIDATE_ROOT / "candidates" / CANDIDATE_PROFILE_NAME
).is_file()


@pytest.mark.skipif(
    not SOURCE_AVAILABLE,
    reason=(
        "external authorized RX-7 R2 source package is unavailable; "
        "set S12_RX7_SOURCE_ROOT to run the source-audit integration contract"
    ),
)
def test_rx7_source_manifest_has_five_audited_native_recordings() -> None:
    records = load_rx7_source_manifest(SOURCE_ROOT)
    assert len(records) == 5
    assert {record["scenario"] for record in records} == {
        "idle",
        "steady_low",
        "steady_mid",
        "full_pull",
        "full_pull_interior",
    }
    assert all(record["reference_class"] == "R2" for record in records)
    assert all(record["native_duration_s"] > 0 for record in records)


def test_rx7_candidate_overrides_are_one_bounded_parameter_group() -> None:
    assert PARAMETER_GROUP == "rotary_housing_turbo_distribution"
    assert set(PARAMETER_OVERRIDES) == {
        "rotary_pulse_width_scale",
        "primary_spool_tau_s",
        "secondary_spool_tau_s",
        "boost_attack_s",
        "boost_release_s",
        "blow_off_gain_scale",
        "blow_off_release_s",
    }
    assert PARAMETER_OVERRIDES["rotary_pulse_width_scale"] == 1.08
    assert PARAMETER_OVERRIDES["primary_spool_tau_s"] == 0.14


def test_rx7_builder_rejects_output_outside_approved_download_root(
    tmp_path: Path,
) -> None:
    with pytest.raises(Rx7TopicR2Error, match="allowed root"):
        build_rx7_topic_package(tmp_path / "rx7", SOURCE_ROOT, CANDIDATE_ROOT)


def test_rx7_builder_rejects_non_empty_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed_root = tmp_path / "approved-download-root"
    output = allowed_root / "s12-rx7-topic-r2-test-nonempty"
    source = allowed_root / "source"
    candidate = allowed_root / "candidate"
    output.mkdir(parents=True)
    source.mkdir(parents=True)
    candidate.mkdir(parents=True)
    (output / "sentinel.json").write_text(
        json.dumps({"owned_by_test": True}),
        encoding="utf-8",
    )
    monkeypatch.setattr(rx7_topic_r2, "ALLOWED_ROOT", allowed_root)

    with pytest.raises(Rx7TopicR2Error, match="non-empty"):
        build_rx7_topic_package(output, source, candidate)


@pytest.mark.skipif(
    not (SOURCE_AVAILABLE and CANDIDATE_AVAILABLE),
    reason=(
        "external RX-7 source/candidate packages are unavailable; set "
        "S12_RX7_SOURCE_ROOT and S12_RX7_CANDIDATE_ROOT to run package integration"
    ),
)
def test_rx7_external_package_inputs_are_explicitly_available() -> None:
    assert SOURCE_AVAILABLE
    assert CANDIDATE_AVAILABLE
