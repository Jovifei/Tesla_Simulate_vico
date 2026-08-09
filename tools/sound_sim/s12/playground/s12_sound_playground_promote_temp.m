function promotion = s12_sound_playground_promote_temp(artifact, manifest, plan)
%S12_SOUND_PLAYGROUND_PROMOTE_TEMP Future-only, rollback-safe promotion.

workspace = plan.artifacts.workspace_unvalidated_intermediate;
workspacePath = s12_sound_playground_require_text_scalar(workspace.path, "workspace model path");
if strcmp(s12_sound_playground_require_text_scalar(artifact.model_path, "temporary model path"), workspacePath) || ...
        strcmp(s12_sound_playground_require_text_scalar(plan.formal.path, "formal model path"), workspacePath)
    error("S12:Playground:EvidenceOverwrite", "Promotion must not target workspace unvalidated intermediate.");
end
if ~strcmp(manifest.status, "COMPILED_DIMENSIONS_INSPECTED")
    error("S12:Playground:PromotionGate", "Compile and dimension inspection are required before promotion.");
end
if ~isfile(artifact.model_path)
    error("S12:Playground:TemporaryArtifactMissing", "Temporary candidate is missing.");
end
assertPromotionModelsClosed(artifact.model_name, plan.formal.model_name);
assertWorkspaceIntermediateUnchanged(workspace);
if strcmp(s12_sound_playground_require_text_scalar(fileparts(artifact.model_path), "temporary model directory"), ...
        s12_sound_playground_require_text_scalar(fileparts(plan.formal.path), "formal model directory")) || ...
        ~sameVolume(artifact.model_path, plan.formal.path)
    error("S12:Playground:PromotionVolume", "Temporary and formal candidate paths require separate directories on one volume.");
end

formalExisted = isfile(plan.formal.path);
temporaryBefore = s12_sound_playground_sha256(artifact.model_path);
formalBefore = "";
if formalExisted, formalBefore = s12_sound_playground_sha256(plan.formal.path); end
transactionRoot = fullfile(plan.temporary.root, "promotion");
if ~isfolder(transactionRoot), mkdir(transactionRoot); end
backup = "";
quarantine = "";
promotion = struct( ...
    "run_id", string(plan.run_id), "temporary_before_sha256", temporaryBefore, ...
    "formal_before_existed", formalExisted, "formal_before_sha256", formalBefore, ...
    "evidence_sha256_before", evidenceHashes(workspace), ...
    "workspace_intermediate_sha256_before", workspace.sha256, ...
    "manifest_sha256", manifestSha(manifest), "backup_path", backup, "quarantine_path", quarantine, ...
    "transaction_root", string(transactionRoot), "status", "PROMOTION_STARTED_AUDIT_ONLY");
try
    if formalExisted
        backup = uniquePath(plan.formal.path + ".audit_only." + string(plan.run_id) + "." + formalBefore + ".backup");
        System.IO.File.Replace(char(artifact.model_path), char(plan.formal.path), char(backup));
        promotion.method = "ATOMIC_REPLACE";
    else
        System.IO.File.Move(char(artifact.model_path), char(plan.formal.path));
        promotion.method = "ATOMIC_FIRST_CREATE";
    end
    rehash;
    promotion.backup_path = backup;
    promotion.formal_after_sha256 = s12_sound_playground_sha256(plan.formal.path);
    promotion.workspace_intermediate_sha256_after = s12_sound_playground_sha256(workspace.path);
    promotion.evidence_sha256_after = evidenceHashes(workspace);
    if ~s12_sound_playground_sha256_equal(promotion.formal_after_sha256, temporaryBefore) || ...
            ~s12_sound_playground_sha256_equal(promotion.workspace_intermediate_sha256_after, workspace.sha256)
        error("S12:Playground:PromotionVerification", "Post-promotion SHA verification failed.");
    end
    promotion.status = "PROMOTED_UNQUALIFIED_CANDIDATE";
    promotion.qualification_state = "UNQUALIFIED";
    promotion.canonical_migration = "PROHIBITED";
    promotion.daily_open = "PROHIBITED";
    promotion.app_package = "PROHIBITED";
    persistPromotionManifest(transactionRoot, promotion);
catch cause
    promotion.status = "PROMOTION_FAILED";
    promotion.error = struct("identifier", string(cause.identifier), "message", string(cause.message), ...
        "report", string(getReport(cause, "extended", "hyperlinks", "off")));
    promotion = rollbackPromotion(plan, promotion, formalExisted, formalBefore, backup);
    persistPromotionManifest(transactionRoot, promotion);
    writePromotionError(transactionRoot, promotion);
    rethrow(cause);
end
end

function promotion = rollbackPromotion(plan, promotion, formalExisted, formalBefore, backup)
formalPath = plan.formal.path;
if formalExisted
    failedPath = uniquePath(formalPath + ".quarantine.audit_only." + string(plan.run_id));
    if ~isfile(backup) || ~isfile(formalPath)
        error("S12:Playground:PromotionRollback", "Existing-formal rollback requires backup and formal candidate.");
    end
    System.IO.File.Replace(char(backup), char(formalPath), char(failedPath));
    s12_sound_playground_require_sha256_equal(s12_sound_playground_sha256(formalPath), formalBefore, ...
        "Existing-formal rollback SHA verification failed");
    promotion.rollback = struct("mode", "existing_formal_backup", "result", "RESTORED", ...
        "backup_path", string(backup), "quarantine_path", string(failedPath));
else
    quarantine = "";
    if isfile(formalPath)
        quarantine = uniquePath(formalPath + ".quarantine.audit_only.first_create." + string(plan.run_id));
        System.IO.File.Move(char(formalPath), char(quarantine));
    end
    if isfile(formalPath)
        error("S12:Playground:PromotionRollback", "First-create formal path remained after rollback.");
    end
    promotion.rollback = struct("mode", "first_create", "result", "QUARANTINED", ...
        "quarantine_path", string(quarantine), "formal_path_absent_after_rollback", true);
end
promotion.formal_after_sha256 = "";
if isfile(formalPath), promotion.formal_after_sha256 = s12_sound_playground_sha256(formalPath); end
end

function assertWorkspaceIntermediateUnchanged(workspace)
s12_sound_playground_require_sha256_equal(s12_sound_playground_sha256(workspace.path), workspace.sha256, ...
    "Workspace unvalidated intermediate changed");
end

function hashes = evidenceHashes(workspace)
historical = s12_sound_playground_port_contract().artifacts.historical_pre_repair_invalid;
hashes = struct("historical_pre_repair_invalid", historical.sha256, ...
    "workspace_unvalidated_intermediate", s12_sound_playground_sha256(workspace.path));
end

function assertPromotionModelsClosed(temporaryName, formalName)
if bdIsLoaded(char(temporaryName)) || bdIsLoaded(char(formalName))
    error("S12:Playground:ModelLoaded", "Close temporary and formal candidate models before promotion.");
end
end

function path = uniquePath(base)
path = string(base);
index = 1;
while isfile(path) || isfolder(path)
    path = string(base) + "." + string(index);
    index = index + 1;
end
end

function persistPromotionManifest(transactionRoot, promotion)
s12_sound_playground_atomic_write_json(fullfile(transactionRoot, "promotion_manifest.json"), promotion);
end

function writePromotionError(transactionRoot, promotion)
s12_sound_playground_atomic_write_json(fullfile(transactionRoot, "promotion_failure.json"), promotion);
end

function value = manifestSha(manifest)
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(uint8(jsonencode(manifest)));
value = upper(string(reshape(dec2hex(typecast(digest.digest, "uint8"), 2).', 1, [])));
end

function result = sameVolume(left, right)
leftRoot = char(java.io.File(left).toPath().getRoot().toString());
rightRoot = char(java.io.File(right).toPath().getRoot().toString());
result = strcmpi(leftRoot, rightRoot);
end
