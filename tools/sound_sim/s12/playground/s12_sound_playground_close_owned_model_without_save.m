function result = s12_sound_playground_close_owned_model_without_save(lease)
%S12_SOUND_PLAYGROUND_CLOSE_OWNED_MODEL_WITHOUT_SAVE Preserve caller ownership.

if ~lease.owned
    result = struct("status", "ALREADY_CALLER_OWNED", "model_name", lease.model_name, "error", struct());
    return;
end
try
    if bdIsLoaded(char(lease.model_name))
        close_system(char(lease.model_name), 0);
    end
    if bdIsLoaded(char(lease.model_name))
        error("S12:Playground:ModelClose", "Owned model %s remained loaded.", lease.model_name);
    end
    result = struct("status", "CLOSED", "model_name", lease.model_name, "error", struct());
catch cause
    persisted = writeCleanupFailure(lease.cleanup_error_path, cause);
    if persisted
        status = "CLEANUP_FAILED";
    else
        status = "CLEANUP_FAILURE_EVIDENCE_WRITE_FAILED";
    end
    result = struct("status", status, "model_name", lease.model_name, ...
        "error", struct("identifier", string(cause.identifier), "message", string(cause.message), ...
        "report", string(getReport(cause, "extended", "hyperlinks", "off"))));
end
end

function persisted = writeCleanupFailure(path, cause)
persisted = false;
if strlength(string(path)) == 0, return; end
folder = fileparts(path);
if ~isfolder(folder), return; end
report = getReport(cause, "extended", "hyperlinks", "off");
try
    s12_sound_playground_atomic_write_json(path, struct("identifier", cause.identifier, "message", cause.message, ...
        "report", report));
    persisted = true;
catch
    persisted = false;
end
end
