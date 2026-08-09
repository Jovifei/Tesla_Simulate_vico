function paths = s12_sound_playground_runtime_paths(runId, scope)
%S12_SOUND_PLAYGROUND_RUNTIME_PATHS Derive mutable paths outside source scope.

if nargin < 2
    scope = "controlled_rebuild";
end
runId = string(runId);
if isempty(regexp(char(runId), "^[A-Za-z][A-Za-z0-9_]{0,47}$", "once"))
    error("S12:Playground:RunId", "Run ID must be an identifier of at most 48 characters.");
end
sourceRoot = string(fileparts(mfilename("fullpath")));
projectRoot = fileparts(fileparts(fileparts(fileparts(fileparts(sourceRoot)))));
scope = s12_sound_playground_require_text_scalar(scope, "runtime scope");
if strcmp(scope, "runtime_proof")
    runtimeBase = fullfile(projectRoot, "tasks", "reports", "runtime", "s12-playground-runtime-proof");
elseif strcmp(scope, "controlled_rebuild")
    runtimeBase = fullfile(projectRoot, "tasks", "reports", "runtime", "s12-simulink-playground-v09");
else
    error("S12:Playground:RuntimeScope", "Unknown runtime path scope.");
end
runtimeRoot = fullfile(runtimeBase, runId);
if strcmp(scope, "runtime_proof")
    transactionRoot = runtimeRoot;
    temporaryRoot = runtimeRoot;
    caseOutputRoot = fullfile(runtimeRoot, "case_outputs");
else
    transactionRoot = fullfile(runtimeRoot, "transaction");
    temporaryRoot = fullfile(runtimeRoot, "temporary");
    caseOutputRoot = fullfile(runtimeRoot, "transaction", "case_outputs");
end
if is_subpath(runtimeRoot, sourceRoot)
    error("S12:Playground:RuntimeInsideSource", "Runtime root must be outside the immutable source tree.");
end
paths = struct( ...
    "source_root", sourceRoot, ...
    "project_root", string(projectRoot), ...
    "runtime_base", string(runtimeBase), ...
    "runtime_root", string(runtimeRoot), ...
    "transaction_root", string(transactionRoot), ...
    "temporary_root", string(temporaryRoot), ...
    "case_output_root", string(caseOutputRoot), ...
    "authorization_registry_root", string(fullfile(runtimeBase, "authorization_registry")), ...
    "active_run_lock_path", string(fullfile(runtimeBase, "ACTIVE_RUN_LOCK.json")), ...
    "active_run_lock_audit_root", string(fullfile(runtimeBase, "active_run_lock_audit")), ...
    "formal_status_root", string(fullfile(runtimeRoot, "formal_candidate_status")));
end

function result = is_subpath(candidate, parent)
candidatePath = char(java.io.File(candidate).getCanonicalPath());
parentPath = char(java.io.File(parent).getCanonicalPath());
result = strcmpi(candidatePath, parentPath) || startsWith(candidatePath, [parentPath filesep], "IgnoreCase", true);
end
