function result = s12_sound_playground_release_global_run_lock(lock, runId, authorizationId)
%S12_SOUND_PLAYGROUND_RELEASE_GLOBAL_RUN_LOCK Release only after an owner-verified blocking intent exists.

lockPath = string(lock.lock_path);
intentPath = sentinelPath(lockPath, "RELEASE_IN_PROGRESS", runId, authorizationId);
if ~isfile(lockPath)
    if isfile(intentPath) || isfile(sentinelPath(lockPath, "RELEASE_FAILED", runId, authorizationId))
        error("S12:Playground:LockReleaseIncomplete", "Release remains blocked by a run-specific sentinel.");
    end
    result = struct("status", "ALREADY_RELEASED", "lock_path", lockPath);
    return;
end
record = readLock(lockPath);
assertOwner(record, runId, authorizationId);
writeReleaseIntent(intentPath, lockPath, runId, authorizationId);
try
    delete(char(lockPath));
catch cause
    writeReleaseFailure(lockPath, runId, authorizationId, cause, "PRIMARY_LOCK_DELETE_FAILED");
    error("S12:Playground:LockReleaseCleanupFailed", "Active-run lock deletion failed: %s", cause.message);
end
if isfile(lockPath)
    cause = MException("S12:Playground:LockReleaseCleanupFailed", "Primary active-run lock remains after deletion.");
    writeReleaseFailure(lockPath, runId, authorizationId, cause, "PRIMARY_LOCK_REMAINS");
    throw(cause);
end
try
    receipt = writeReleaseReceipt(lockPath, runId, authorizationId, intentPath);
catch cause
    writeReleaseFailure(lockPath, runId, authorizationId, cause, "RELEASE_RECEIPT_WRITE_FAILED");
    error("S12:Playground:LockReleaseCleanupFailed", "Release receipt write failed after primary lock deletion: %s", cause.message);
end
try
    delete(char(intentPath));
catch cause
    writeReleaseFailure(lockPath, runId, authorizationId, cause, "RELEASE_SENTINEL_DELETE_FAILED");
    error("S12:Playground:LockReleaseCleanupFailed", "Release intent could not be cleared: %s", cause.message);
end
result = struct("status", "RELEASED", "lock_path", lockPath, "release_receipt_path", receipt.path, ...
    "release_receipt_sha256", receipt.sha256);
end

function record = readLock(path)
try
    record = jsondecode(fileread(path));
catch cause
    error("S12:Playground:LockRead", "Cannot read active-run lock: %s", cause.message);
end
end

function assertOwner(record, runId, authorizationId)
if ~isfield(record, "run_id") || ~isfield(record, "authorization_id") || ...
        ~strcmp(s12_sound_playground_require_text_scalar(record.run_id, "lock run_id"), ...
            s12_sound_playground_require_text_scalar(runId, "requested run_id")) || ...
        ~strcmp(s12_sound_playground_require_text_scalar(record.authorization_id, "lock authorization_id"), ...
            s12_sound_playground_require_text_scalar(authorizationId, "requested authorization_id"))
    error("S12:Playground:LockOwnerMismatch", "Active-run lock belongs to another run or authorization.");
end
end

function writeReleaseIntent(path, lockPath, runId, authorizationId)
if isfile(path)
    error("S12:Playground:LockReleaseCollision", "Owner release intent path already exists.");
end
intent = struct("status", "RELEASE_IN_PROGRESS", "run_id", string(runId), ...
    "authorization_id", string(authorizationId), "lock_path", string(lockPath), ...
    "created_at", nowString());
s12_sound_playground_atomic_write_json(path, intent, false);
end

function receipt = writeReleaseReceipt(lockPath, runId, authorizationId, intentPath)
path = sentinelPath(lockPath, "RELEASE_RECEIPT", runId, authorizationId);
receipt = struct("status", "RELEASED", "run_id", string(runId), ...
    "authorization_id", string(authorizationId), "lock_path", string(lockPath), ...
    "release_intent_path", string(intentPath), "released_at", nowString());
s12_sound_playground_atomic_write_json(path, receipt, false);
receipt.path = string(path);
receipt.sha256 = s12_sound_playground_sha256(path);
end

function writeReleaseFailure(lockPath, runId, authorizationId, cause, status)
path = sentinelPath(lockPath, "RELEASE_FAILED", runId, authorizationId);
failure = struct("status", string(status), "run_id", string(runId), ...
    "authorization_id", string(authorizationId), "lock_path", string(lockPath), ...
    "error_identifier", string(cause.identifier), "error_message", string(cause.message), ...
    "recorded_at", nowString());
try
    s12_sound_playground_atomic_write_json(path, failure, true);
catch
    % A retained RELEASE_IN_PROGRESS sentinel still blocks any subsequent acquire.
end
end

function path = sentinelPath(lockPath, status, runId, authorizationId)
path = fullfile(fileparts(lockPath), string(status) + "." + string(runId) + "." + string(authorizationId) + ".json");
end

function value = nowString()
value = string(datetime("now", "Format", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"));
end
