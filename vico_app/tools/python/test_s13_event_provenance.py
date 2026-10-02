import export_s12_android_sound_banks as exporter
import pytest


def test_s13_event_binding_records_absolute_frame_and_crop_offset():
    make_binding = getattr(exporter, "_s13_event_binding", None)
    assert callable(make_binding), "S13 exporter must emit frame-bound event provenance"

    binding = make_binding(
        event_id="shift_event_01",
        kind="shift",
        asset_file="shift_event_01_s12.wav",
        asset_sha256="a" * 64,
        trace_sha256="b" * 64,
        source_domain="TRACE_EVENT",
        source_time_s=1000 / 48000,
        source_frame=1000,
        crop_start_frame=959,
        sample_count=64,
    )
    assert binding["source_frame"] == 1000
    assert binding["crop_start_frame"] == 959
    assert binding["trigger_offset_frames"] == 41
    assert binding["source_time_s"] == 1000 / 48000

    with pytest.raises(ValueError, match="outside the decoded clip"):
        make_binding(
            event_id="shift_event_bad",
            kind="shift",
            asset_file="shift.wav",
            asset_sha256="a" * 64,
            trace_sha256="b" * 64,
            source_domain="TRACE_EVENT",
            source_time_s=1000 / 48000,
            source_frame=1000,
            crop_start_frame=959,
            sample_count=3,
        )


def test_s13_afterfire_crop_origin_comes_from_measured_active_sample():
    crop = getattr(exporter, "_afterfire_source_frames", None)
    assert callable(crop), "S13 exporter must preserve the afterfire crop calculation"
    assert crop(window_start_frame=864000, active_first_frame=3000, pre_roll_frames=1200) == (
        867000,
        865800,
        1200,
    )
    assert crop(window_start_frame=864000, active_first_frame=500, pre_roll_frames=1200) == (
        864500,
        864000,
        500,
    )


def test_s13_sidecar_records_event_extraction_rules():
    rules = getattr(exporter, "_s13_event_extraction_contract", None)
    assert callable(rules), "S13 sidecar must preserve the exact source crop rules"
    contract = rules()
    assert contract["shift"]["pre_roll_frames"] == 1920
    assert contract["shift"]["post_roll_frames"] == 10560
    assert contract["afterfire"]["window_start_frame"] == 864000
    assert contract["afterfire"]["threshold_relative_peak"] == 0.015
    assert contract["afterfire"]["pre_roll_frames"] == 1200
