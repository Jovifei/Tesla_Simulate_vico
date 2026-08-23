from __future__ import annotations

from pathlib import Path


def test_audio_feature_batch_treats_candidate_id_as_optional_for_reference_and_parent_rows() -> None:
    source = (Path(__file__).parents[1] / "real_reference" / "run_stage_u_audio_feature_batch.m").read_text(encoding="utf-8")

    assert "isfield(clip, 'candidate_id')" in source


def test_matlab_runners_hash_analyzed_audio_and_validate_manifest_sha() -> None:
    source_root = Path(__file__).parents[1] / "real_reference"
    professional = (source_root / "run_stage_u_professional_metrics.m").read_text(encoding="utf-8")
    features = (source_root / "run_stage_u_audio_features.m").read_text(encoding="utf-8")
    batch = (source_root / "run_stage_u_audio_feature_batch.m").read_text(encoding="utf-8")

    assert "actualSha256 = sha256File(inputPath)" in professional
    assert "strcmpi(actualSha256, char(clip.sha256))" in professional
    assert "row.input_sha256 = actualSha256" in professional
    assert "expectedSha256" in features
    assert "actualSha256 = sha256File(inputPath)" in features
    assert "strcmpi(actualSha256, expectedSha256)" in features
    assert "'input_sha256', actualSha256" in features
    assert "featureReceipt = run_stage_u_audio_features(char(clip.path), featurePath, char(clip.sha256))" in batch
    assert "row.input_sha256 = char(featureReceipt.input_sha256)" in batch
    assert "row.input_sha256 = char(clip.sha256)" not in batch
