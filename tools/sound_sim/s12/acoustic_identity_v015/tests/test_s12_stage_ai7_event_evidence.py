"""Stage AI-7 continuous-drive observed-event evidence contracts."""

from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import continuous_drive as cycle


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
