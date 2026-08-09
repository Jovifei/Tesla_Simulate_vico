function result = s12_sound_playground_repeatability_gate(plan, outputRoot)
%S12_SOUND_PLAYGROUND_REPEATABILITY_GATE Run one frozen qualification case twice in independent roots.

firstRoot = fullfile(outputRoot, "repeatability_a");
secondRoot = fullfile(outputRoot, "repeatability_b");
if isfolder(firstRoot) || isfolder(secondRoot)
    error("S12:Playground:RepeatabilityReuse", "Repeatability roots must be new and independent.");
end
first = s12_sound_playground_run_simulink_case("idle", plan, true, firstRoot);
second = s12_sound_playground_run_simulink_case("idle", plan, true, secondRoot);
fields = ["pcm_sha256", "wav_sha256", "parameter_snapshot_sha256", "scenario_sha256", ...
    "metrics_json_sha256", "model_sha256_before", "model_sha256_after"];
for index = 1:numel(fields)
    field = fields(index);
    if ~isfield(first.evidence, char(field)) || ~isfield(second.evidence, char(field))
        error("S12:Playground:Repeatability", "Repeatability evidence is missing %s.", field);
    end
    s12_sound_playground_require_sha256_equal(first.evidence.(char(field)), second.evidence.(char(field)), ...
        "Repeatability mismatch for " + field);
end
if first.expected_frame_count ~= second.expected_frame_count || ~isequal(first.metrics, second.metrics)
    error("S12:Playground:Repeatability", "Frame count or metrics mismatch.");
end
result = struct("status", "REPEATABILITY_PASSED_RUNTIME_EVIDENCE", "repeatability_a", first.evidence, ...
    "repeatability_b", second.evidence, "frame_count", first.expected_frame_count, ...
    "model_sha256", first.model_sha256_after, "metrics", first.metrics);
end
