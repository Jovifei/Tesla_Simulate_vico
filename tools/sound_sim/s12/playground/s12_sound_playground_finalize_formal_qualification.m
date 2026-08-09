function manifest = s12_sound_playground_finalize_formal_qualification(plan, promotion, result, qualificationCases)
%S12_SOUND_PLAYGROUND_FINALIZE_FORMAL_QUALIFICATION Persist formal state using freshly recomputed evidence.

if nargin < 4
    qualificationCases = struct([]);
end
root = plan.runtime.formal_status_root;
if ~isfolder(root)
    mkdir(root);
end
evidence = s12_sound_playground_recompute_final_evidence(plan, promotion, qualificationCases);
if strcmp(s12_sound_playground_require_text_scalar(result.status, "controlled flow status"), "CONTROLLED_FLOW_PASSED")
    status = "PCM_QUALIFIED_DIRECT_LISTENING_INCOMPLETE";
else
    status = "FAILED_QUALIFICATION";
end
manifestPath = fullfile(root, "qualification_manifest.json");
manifest = struct( ...
    "stage", "formal_qualification", "run_id", plan.run_id, ...
    "formal_candidate_sha256", evidence.formal_candidate_sha256, ...
    "qualification_status", status, "failed_stage", stringOrEmpty(result, "failed_stage"), ...
    "canonical_migration", "PROHIBITED", "daily_open", "PROHIBITED", "app_package", "PROHIBITED", ...
    "direct_listening_gate", stringOrEmpty(result, "direct_listening_gate"), ...
    "manifest_path", string(manifestPath), "final_evidence", evidence, ...
    "reason", "formal candidate remains unqualified until all separately authorized gates are complete");
s12_sound_playground_atomic_write_json(manifestPath, manifest);
end

function value = stringOrEmpty(record, field)
if isfield(record, field)
    value = string(record.(field));
else
    value = "";
end
end
