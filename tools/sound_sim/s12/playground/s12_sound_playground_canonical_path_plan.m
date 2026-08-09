function plan = s12_sound_playground_canonical_path_plan()
%S12_SOUND_PLAYGROUND_CANONICAL_PATH_PLAN Future-only canonical migration.
% This function plans; it does not load, create, move, or overwrite an SLX.

root = fileparts(mfilename("fullpath"));
artifacts = s12_sound_playground_port_contract().artifacts;
plan.status = "FUTURE_SEPARATELY_AUTHORIZED_CANONICAL_MIGRATION_REQUIRED";
plan.artifact_roles = artifacts;
plan.current_workspace_path = artifacts.workspace_unvalidated_intermediate.path;
plan.current_workspace_state = artifacts.workspace_unvalidated_intermediate.role;
plan.pre_repair_invalid_evidence_sha256 = artifacts.historical_pre_repair_invalid.sha256;
plan.pre_repair_invalid_evidence_location = "EXISTING_AUDIT_PACKAGE_ONLY";
plan.future_evidence_archive_path = fullfile(root, "S12_Sound_Playground_PRE_REPAIR_INVALID.slx");
plan.future_canonical_candidate_path = artifacts.future_canonical.path;
plan.qualification_manifest_required = "external formal candidate qualification manifest with matching SHA and all required gates";
plan.unqualified_candidate_policy = "canonical migration, daily open, and App packaging are prohibited";
plan.required_sequence = [ ...
    "retain_or_archive_invalid_audit_evidence_with_sha", ...
    "verify qualification manifest and exact candidate SHA before canonical migration", ...
    "independently_review_verified_candidate", ...
    "obtain_explicit_canonical_migration_authorization", ...
    "move_evidence_to_pre_repair_invalid_name", ...
    "move_verified_candidate_to_canonical_name", ...
    "verify_both_sha256_values_and_write_migration_record"];
plan.offline_repair_action = "NO_FILE_OPERATION";
end
