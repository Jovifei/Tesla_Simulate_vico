function lock = s12_sound_playground_acquire_global_run_lock(lockPath, lockRecord)
%S12_SOUND_PLAYGROUND_ACQUIRE_GLOBAL_RUN_LOCK Atomically create the external active-run lock.

lockPath = string(lockPath);
required = ["run_id", "authorization_id", "desktop_pid", "source_tree_sha256", ...
    "audit_zip_sha256", "start_time", "owner_process"];
for index = 1:numel(required)
    if ~isfield(lockRecord, required(index)) || strlength(string(lockRecord.(required(index)))) == 0
        error("S12:Playground:LockRecord", "Missing active-run lock field %s.", required(index));
    end
end
root = fileparts(lockPath);
if ~isfolder(root)
    mkdir(root);
end
assertNoBlockingMarker(lockPath);
lockRecord.status = "ACTIVE";
lockRecord.lock_path = lockPath;
try
    s12_sound_playground_atomic_write_json(lockPath, lockRecord, false);
catch cause
    if contains(string(cause.message), "already exists", "IgnoreCase", true) || ...
            contains(string(cause.message), "FileAlreadyExists", "IgnoreCase", true)
        error("S12:Playground:ACTIVE_RUN_LOCKED", "ACTIVE_RUN_LOCKED: %s", lockPath);
    end
    rethrow(cause);
end
lock = lockRecord;
end

function assertNoBlockingMarker(lockPath)
root = fileparts(lockPath);
sentinels = [dir(fullfile(root, "RELEASE_IN_PROGRESS.*.json")); ...
    dir(fullfile(root, "RELEASE_FAILED.*.json"))];
if isfile(lockPath) || ~isempty(sentinels)
    error("S12:Playground:ACTIVE_RUN_LOCKED", "ACTIVE_RUN_LOCKED: active lock or release sentinel exists.");
end
end
