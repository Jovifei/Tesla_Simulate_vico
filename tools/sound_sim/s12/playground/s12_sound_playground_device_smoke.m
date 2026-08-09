function result = s12_sound_playground_device_smoke(plan, durationSeconds, outputRoot)
%S12_SOUND_PLAYGROUND_DEVICE_SMOKE Run a bounded existing-session device playback smoke.

if nargin ~= 3 || durationSeconds < 1 || durationSeconds > 3
    error("S12:Playground:DeviceSmokeDuration", "Device smoke must be between 1 and 3 seconds.");
end
if ~strcmp(s12_sound_playground_require_text_scalar(plan.execution_policy, "execution_policy"), ...
        "EXISTING_SESSION_RUNTIME_PROOF")
    error("S12:Playground:ExecutionPolicy", "Device smoke requires the existing-session Runtime Proof policy.");
end
candidate = plan.candidate;
if ~isfile(candidate.path)
    error("S12:Playground:CandidateMissing", "Runtime Proof temporary candidate is absent.");
end
if ~isfolder(outputRoot)
    mkdir(outputRoot);
end
result = struct("status", "DEVICE_AUDIO_SMOKE_RUNNING", "duration_s", double(durationSeconds), ...
    "device_playback_executed", false, "user_audible_confirmation", "pending", ...
    "audio_device_error", struct(), "candidate_sha256_before", s12_sound_playground_sha256(candidate.path), ...
    "candidate_sha256_after", "");
try
    model = string(candidate.model_name);
    lease = s12_sound_playground_open_owned_model(model, candidate.path, ...
        fullfile(outputRoot, "device_smoke_cleanup_failure.json"));
    if ~lease.owned
        error("S12:Playground:CandidateCallerOwned", "Device smoke refuses a caller-owned model.");
    end
    cleanup = onCleanup(@() s12_sound_playground_close_owned_model_without_save(lease));
    scenario = s12_sound_playground_scenario_source("idle");
    workspace = get_param(model, "ModelWorkspace");
    assignin(workspace, "s12_playground_scenario_frames", scenario.workspace_signal);
    s12_sound_playground_apply_mode(model, "qualification");
    set_param(model + "/Optional Device Output", "Commented", "off");
    signal = s12_sound_playground_signal_contract();
    expectedFrames = round(durationSeconds / signal.frame_period_s);
    stopTime = (expectedFrames - 1) * signal.frame_period_s;
    set_param(model, "SimulationMode", "normal", "FastRestart", "off", ...
        "StartTime", "0", "StopTime", num2str(stopTime, 17));
    simulation = sim(char(model));
    pcm = s12_sound_playground_normalize_logged_pcm(simulation.playground_pcm, expectedFrames);
    result.pcm_metrics = s12_sound_playground_measure_pcm(pcm, expectedFrames);
    s12_sound_playground_validate_pcm_metrics(result.pcm_metrics, expectedFrames, durationSeconds);
    closeResult = s12_sound_playground_close_owned_model_without_save(lease);
    clear cleanup
    if ~strcmp(s12_sound_playground_require_text_scalar(closeResult.status, "model close status"), "CLOSED") || bdIsLoaded(char(model))
        error("S12:Playground:ModelClose", "Device-smoke model did not close cleanly.");
    end
    result.device_playback_executed = true;
    result.status = "DEVICE_AUDIO_SMOKE_EXECUTED_NO_DEVICE_ERROR";
catch cause
    result.status = "DEVICE_AUDIO_SMOKE_FAILED";
    result.audio_device_error = struct("identifier", string(cause.identifier), ...
        "message", string(cause.message), "report", string(getReport(cause, "extended", "hyperlinks", "off")));
    s12_sound_playground_atomic_write_json(fullfile(outputRoot, "device_audio_smoke_failure.json"), result);
    rethrow(cause);
end
result.candidate_sha256_after = s12_sound_playground_sha256(candidate.path);
s12_sound_playground_require_sha256_equal(result.candidate_sha256_before, result.candidate_sha256_after, ...
    "Device smoke changed the temporary candidate on disk");
s12_sound_playground_atomic_write_json(fullfile(outputRoot, "device_audio_smoke.json"), result);
end
