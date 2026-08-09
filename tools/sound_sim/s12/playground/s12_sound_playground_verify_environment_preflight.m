function evidence = s12_sound_playground_verify_environment_preflight(evidencePath, authorization)
%S12_SOUND_PLAYGROUND_VERIFY_ENVIRONMENT_PREFLIGHT Consume fresh read-only host evidence.

if nargin ~= 2 || ~isfile(evidencePath)
    environmentFail("preflight evidence file is absent");
end
try
    evidence = jsondecode(fileread(evidencePath));
catch cause
    environmentFail("preflight evidence cannot be decoded: " + string(cause.message));
end
required = ["desktop_root_count", "desktop_pid", "desktop_command_line", "desktop_responding", ...
    "catapult_child_count", "catapult_child_pids", "catapult_parent_pid", ...
    "other_matlab_process_count", "other_matlab_pids", ...
    "mcp_root_count", "watchdog_count", "batch_process_count", "engine_process_count", ...
    "crash_dump_latest_time", "new_crash_detected", "active_run_lock", "captured_at", "expires_at"];
for index = 1:numel(required)
    if ~isfield(evidence, required(index))
        environmentFail("missing field " + required(index));
    end
end
if ~isfield(authorization, "allowed_mcp_root_count") || ~isfield(authorization, "allowed_watchdog_count")
    environmentFail("authorization does not declare allowed MCP/watchdog counts");
end
capturedAt = readTime(evidence.captured_at, "captured_at");
expiresAt = readTime(evidence.expires_at, "expires_at");
if capturedAt > datetime("now", "TimeZone", "local") || expiresAt <= datetime("now", "TimeZone", "local") || expiresAt <= capturedAt
    environmentFail("preflight evidence is stale or has invalid freshness bounds");
end
if strlength(string(evidence.crash_dump_latest_time)) > 0
    crashDumpAt = readTime(evidence.crash_dump_latest_time, "crash_dump_latest_time");
    if crashDumpAt > capturedAt
        environmentFail("crash dump timestamp is newer than preflight capture");
    end
end
if double(evidence.desktop_root_count) ~= 1 || double(evidence.desktop_pid) <= 0 || ~logical(evidence.desktop_responding)
    environmentFail("exactly one responsive visible Desktop is required");
end
commandLine = lower(s12_sound_playground_require_text_scalar(evidence.desktop_command_line, "desktop_command_line"));
if any(contains(commandLine, ["-batch", "-r", "-nodesktop"]))
    environmentFail("Desktop command line contains a prohibited headless launch option");
end
if double(evidence.other_matlab_process_count) ~= 0 || ~isempty(evidence.other_matlab_pids)
    environmentFail("rogue MATLAB process outside the Desktop tree detected");
end
catapultPids = double(reshape(evidence.catapult_child_pids, 1, []));
if double(evidence.catapult_child_count) ~= numel(catapultPids)
    environmentFail("Catapult child count does not match the captured process list");
end
if ~isempty(catapultPids) && double(evidence.catapult_parent_pid) ~= double(evidence.desktop_pid)
    environmentFail("Catapult children are not owned by the responsive Desktop process tree");
end
if double(evidence.batch_process_count) ~= 0 || double(evidence.engine_process_count) ~= 0
    environmentFail("batch or MATLAB Engine process detected");
end
if double(evidence.mcp_root_count) > double(authorization.allowed_mcp_root_count) || ...
        double(evidence.watchdog_count) > double(authorization.allowed_watchdog_count)
    environmentFail("MCP root or watchdog count exceeds the authorized limit");
end
if logical(evidence.active_run_lock) || logical(evidence.new_crash_detected)
    environmentFail("active run lock or new crash evidence detected");
end
evidence.path = string(evidencePath);
evidence.sha256 = s12_sound_playground_sha256(evidencePath);
evidence.status = "ENVIRONMENT_GATE_PASSED_READ_ONLY_EVIDENCE";
end

function value = readTime(raw, field)
try
    value = datetime(string(raw), "InputFormat", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", "TimeZone", "local");
catch
    environmentFail("invalid timestamp " + string(field));
end
end

function environmentFail(message)
error("S12:Playground:ENVIRONMENT_GATE_FAIL", "%s", string(message));
end
