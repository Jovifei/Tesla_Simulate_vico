function result = s12_sound_playground_run_simulink_case(name, plan, execute, outputDirectory, scenarioOverride)
%S12_SOUND_PLAYGROUND_RUN_SIMULINK_CASE Controlled future qualification runner.
% execute=false is the only permitted offline use.

if nargin < 3, execute = false; end
if nargin < 4, outputDirectory = ""; end
if nargin < 5, scenarioOverride = struct(); end
if isempty(fieldnames(scenarioOverride))
    scenario = s12_sound_playground_scenario_source(name);
else
    scenario = scenarioOverride;
end
assertScenarioWorkspaceRoundTrip(scenario);
result = struct( ...
    "source", "simulink_model", ...
    "execution_policy", "REQUIRES_CONTROLLED_RUNTIME_CONFIRMATION", ...
    "scenario", scenario.name, ...
    "expected_frame_count", scenario.frame_count, ...
    "expected_stop_time_s", scenario.stop_time_s, ...
    "operations", ["load_repaired_candidate", "apply_scenario_frames", "qualification_mode", ...
        "sim", "normalize_logged_pcm", "validate_metrics", "write_pcm_wav_json_after_validation"], ...
    "status", "NOT_EXECUTED");
if ~execute
    return;
end
assertControlledOutputDirectory(outputDirectory, plan.runtime.transaction_root);
executionPolicy = s12_sound_playground_require_text_scalar(plan.execution_policy, "execution_policy");
if ~any(strcmp(executionPolicy, ["EXISTING_SESSION_RUNTIME_PROOF", "REQUIRES_CONTROLLED_RUNTIME_CONFIRMATION"]))
    error("S12:Playground:ExecutionPolicy", "Unexpected runtime execution policy.");
end
candidate = selectedCandidate(plan);
if ~isfile(candidate.path)
    error("S12:Playground:CandidateMissing", "The Runtime Proof temporary candidate is required before sim(...).");
end
try
    model = string(candidate.model_name);
    lease = s12_sound_playground_open_owned_model(model, candidate.path, ...
        fullfile(plan.runtime.transaction_root, "runner_cleanup_failure.json"));
    if ~lease.owned
        error("S12:Playground:CandidateCallerOwned", "Controlled runner refuses a caller-owned candidate model.");
    end
    cleanup = onCleanup(@() s12_sound_playground_close_owned_model_without_save(lease));
    modelShaBefore = s12_sound_playground_sha256(candidate.path);
    set_param(model, "SimulationMode", "normal", "FastRestart", "off", "StartTime", "0", ...
        "StopTime", num2str(scenario.stop_time_s, 17));
    s12_sound_playground_apply_mode(model, "qualification");
    workspace = get_param(model, "ModelWorkspace");
    assignin(workspace, "s12_playground_scenario_frames", scenario.workspace_signal);
    simulation = sim(char(model));
    rawPcm = simulation.playground_pcm;
    pcm = s12_sound_playground_normalize_logged_pcm(rawPcm, scenario.frame_count);
    metrics = s12_sound_playground_measure_pcm(pcm, scenario.frame_count);
    s12_sound_playground_validate_pcm_metrics(metrics, scenario.frame_count);
    closeResult = s12_sound_playground_close_owned_model_without_save(lease);
    clear cleanup
    if ~strcmp(s12_sound_playground_require_text_scalar(closeResult.status, "model close status"), "CLOSED") || bdIsLoaded(char(model))
        error("S12:Playground:ModelClose", "Owned model did not close cleanly after qualification.");
    end
    result.status = "SIMULATION_COMPLETED_AND_VALIDATED";
    result.metrics = metrics;
    result.model_sha256_before = modelShaBefore;
    result.model_sha256_after = s12_sound_playground_sha256(candidate.path);
    s12_sound_playground_require_sha256_equal(result.model_sha256_before, result.model_sha256_after, ...
        "Candidate changed during unsaved simulation");
    parameters = s12_sound_playground_parameters();
    result.evidence = s12_sound_playground_write_case_evidence(pcm, result, scenario, parameters, outputDirectory);
catch cause
    result.status = "SIMULATION_FAILED_VALIDATION";
    result.error = struct("identifier", string(cause.identifier), "message", string(cause.message), ...
        "report", string(getReport(cause, "extended", "hyperlinks", "off")));
    if exist("metrics", "var")
        result.metrics = metrics;
    end
    writeFailure(result, outputDirectory);
    rethrow(cause);
end
end

function candidate = selectedCandidate(plan)
if isfield(plan, "candidate")
    candidate = plan.candidate;
elseif isfield(plan, "formal")
    candidate = struct("path", string(plan.formal.path), "model_name", string(plan.formal.model_name));
else
    error("S12:Playground:CandidateMissing", "Plan does not declare a candidate.");
end
end

function assertControlledOutputDirectory(outputDirectory, transactionRoot)
if strlength(string(outputDirectory)) == 0
    error("S12:Playground:OutputRootRequired", "A controlled output directory is required.");
end
outputPath = char(java.io.File(outputDirectory).getCanonicalPath());
transactionPath = char(java.io.File(transactionRoot).getCanonicalPath());
if strcmpi(outputPath, transactionPath) || ~startsWith(outputPath, [transactionPath filesep], "IgnoreCase", true)
    error("S12:Playground:OutputRoot", "Case output must be a strict child of the controlled transaction root.");
end
end

function writeFailure(result, outputDirectory)
if strlength(string(outputDirectory)) == 0
    return;
end
if ~isfolder(outputDirectory), mkdir(outputDirectory); end
 s12_sound_playground_atomic_write_json(fullfile(outputDirectory, "simulink_failure.json"), result);
end

function assertScenarioWorkspaceRoundTrip(scenario)
if ~isfield(scenario, "workspace_signal") || ~isfield(scenario.workspace_signal, "signals") || ...
        ~isfield(scenario.workspace_signal.signals, "values") || ~isfield(scenario.workspace_signal.signals, "dimensions")
    error("S12:Playground:ScenarioWorkspaceMismatch", "Scenario workspace_signal is incomplete.");
end
if ~isequal(scenario.workspace_signal.signals.dimensions, [18, 1])
    error("S12:Playground:ScenarioWorkspaceMismatch", "Scenario workspace dimensions must be [18 1].");
end
values = scenario.workspace_signal.signals.values;
if numel(values) ~= 18 * scenario.frame_count || ...
        ~isequal(reshape(values, 18, scenario.frame_count), scenario.configuration_frames)
    error("S12:Playground:ScenarioWorkspaceMismatch", ...
        "Scenario workspace signal does not round-trip to configuration_frames.");
end
end
