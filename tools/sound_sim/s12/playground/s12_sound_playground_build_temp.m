function artifact = s12_sound_playground_build_temp(plan)
%S12_SOUND_PLAYGROUND_BUILD_TEMP Build only a unique temporary candidate.
% Invoke solely inside one user-started stable Desktop session.

assertImmutableArtifacts(plan);
ensureTemporaryRoot(plan);
modelName = char(plan.temporary.model_name);
libraryWasLoaded = bdIsLoaded("dspsnks4");
modelLease = ownedLease(modelName, false, fullfile(plan.temporary.root, "model_cleanup_failure.json"));
libraryLease = ownedLease("dspsnks4", false, fullfile(plan.temporary.root, "library_cleanup_failure.json"));
fallback = onCleanup(@() fallbackOwnedCleanup(modelName, ~libraryWasLoaded, plan.temporary.root));
primaryCause = [];
try
    load_system("dspsnks4");
    libraryLease.owned = ~libraryWasLoaded;
    new_system(modelName, "Model");
    modelLease.owned = true;
    signal = s12_sound_playground_signal_contract();
    set_param(modelName, "Solver", "FixedStepDiscrete", "FixedStep", num2str(signal.frame_period_s, 17), ...
        "StopTime", num2str(signal.qualification_stop_time_s, 17), ...
        "Description", "SCRIPT_CONFIGURED_SIMULINK_AUDITION_CANDIDATE; NOT_A_VALIDATED_DASHBOARD_PLAYGROUND; APP_IMPORT_CLAIM = PROHIBITED.");
    addSubsystems(modelName);
    addTopLevelLines(modelName);
    assertSignalSpecificationReadback(modelName);
    save_system(modelName, plan.temporary.model_path);
catch cause
    primaryCause = cause;
end
cleanupResults = closeOwnedBuilderResources(modelLease, libraryLease);
if ~isempty(primaryCause)
    writeFailure(plan.temporary.failure_report_path, primaryCause, cleanupResults);
    rethrow(primaryCause);
end
cleanupStatuses = string({cleanupResults.status});
if any(~ismember(cleanupStatuses, ["CLOSED", "ALREADY_CALLER_OWNED"]))
    cleanupCause = MException("S12:Playground:BuilderCleanup", "Owned builder cleanup did not complete.");
    writeFailure(plan.temporary.failure_report_path, cleanupCause, cleanupResults);
    throw(cleanupCause);
end
artifact = struct("model_name", string(modelName), "model_path", string(plan.temporary.model_path), ...
    "failure_report_path", plan.temporary.failure_report_path, "cleanup", cleanupResults, ...
    "status", "TEMPORARY_SLX_GENERATED_NOT_VALIDATED");
end

function ensureTemporaryRoot(plan)
if ~isfolder(plan.temporary.root)
    mkdir(plan.temporary.root);
    return;
end
if isfield(plan, "execution_policy") && strcmp( ...
        s12_sound_playground_require_text_scalar(plan.execution_policy, "execution_policy"), ...
        "EXISTING_SESSION_RUNTIME_PROOF")
    entries = dir(plan.temporary.root);
    names = string({entries.name});
    entries = entries(~ismember(names, [".", ".."]));
    if isempty(entries)
        return;
    end
end
error("S12:Playground:TemporaryPathExists", "Run ID already has a non-empty temporary directory.");
end

function assertImmutableArtifacts(plan)
workspace = plan.artifacts.workspace_unvalidated_intermediate;
s12_sound_playground_require_sha256_equal(s12_sound_playground_sha256(workspace.path), workspace.sha256, ...
    "Workspace unvalidated intermediate changed");
candidatePath = selectedCandidatePath(plan);
workspacePath = s12_sound_playground_require_text_scalar(workspace.path, "workspace path");
temporaryPath = s12_sound_playground_require_text_scalar(plan.temporary.model_path, "temporary model path");
if strcmp(candidatePath, workspacePath) || strcmp(temporaryPath, workspacePath)
    error("S12:Playground:EvidenceOverwrite", "Candidate paths must not target the workspace unvalidated intermediate.");
end
end

function path = selectedCandidatePath(plan)
if isfield(plan, "candidate")
    path = string(plan.candidate.path);
elseif isfield(plan, "formal")
    path = string(plan.formal.path);
else
    error("S12:Playground:CandidateMissing", "Plan does not declare a candidate path.");
end
end

function addSubsystems(model)
names = ["Dashboard", "Vehicle State", "Engine Excitation", "PTR Radiation Tuning Adapter", "Audio Renderer"];
positions = {[30 90 200 220], [260 130 410 190], [470 90 640 230], [700 90 870 230], [930 130 1080 200]};
for index = 1:numel(names)
    path = string(model) + "/" + names(index);
    add_block("simulink/Ports & Subsystems/Subsystem", path, "Position", positions{index});
    s12_sound_playground_clear_default_subsystem_contents(path);
end
buildDashboard(string(model) + "/Dashboard");
buildVehicle(string(model) + "/Vehicle State");
buildEngine(string(model) + "/Engine Excitation");
buildPtr(string(model) + "/PTR Radiation Tuning Adapter");
buildRenderer(string(model) + "/Audio Renderer");
sink = string(model) + "/Qualification PCM Sink";
add_block("simulink/Sinks/To Workspace", sink, "Position", [1150 150 1230 180]);
s12_sound_playground_configure_pcm_sink(sink);
add_block("dspsnks4/Audio Device" + newline + "Writer", string(model) + "/Optional Device Output", ...
    "Commented", "on", "Position", [1150 90 1230 120]);
s12_sound_playground_configure_audio_device_writer(string(model) + "/Optional Device Output");
end

function buildDashboard(path)
labels = ["RPM", "Load", "Acceleration", "Throttle", "Cylinder Count", "Firing Order", "Order Gain", ...
    "Pipe Length", "Area", "Reflection", "Damping", "Gain dB"];
values = ["800", "0.10", "0", "0.10", "4", "[1 3 4 2]", "[1 .7 .4 .25]", "1.5", ".02", ".35", ".15", "-12"];
for index = 1:numel(labels)
    block = path + "/" + labels(index);
    add_block("simulink/Sources/Constant", block, "Value", values(index), "SampleTime", "0.02", ...
        "Position", [25 20 + 28 * index 145 40 + 28 * index]);
end
add_block("simulink/Signal Routing/Mux", path + "/Pack Configuration", "Inputs", "12", "Position", [190 80 215 410]);
addFixedConfigurationReshape(path + "/Interactive Configuration Reshape", [225 115 285 145]);
addFixedConfigurationSpecification(path + "/Interactive Configuration [18x1]", [300 115 360 145]);
add_block("simulink/Sources/From Workspace", path + "/Qualification Scenario Source", ...
    "VariableName", "s12_playground_scenario_frames", "OutDataTypeStr", "double", "SampleTime", "0.02", ...
    "Interpolate", "off", "OutputAfterFinalValue", "Holding final value", "ZeroCross", "off", "Position", [190 430 310 455]);
addFixedConfigurationReshape(path + "/Qualification Configuration Reshape", [330 430 390 460]);
addFixedConfigurationSpecification(path + "/Qualification Configuration [18x1]", [405 430 465 460]);
add_block("simulink/Signal Routing/Manual Switch", path + "/Mode Selector", "Position", [420 190 440 230]);
addFixedConfigurationSpecification(path + "/Selected Configuration [18x1]", [465 190 525 220]);
add_block("simulink/Ports & Subsystems/Out1", path + "/Configuration", "Port", "1", "Position", [545 190 575 210]);
for index = 1:numel(labels)
    add_line(path, labels(index) + "/1", "Pack Configuration/" + string(index));
end
add_line(path, "Pack Configuration/1", "Interactive Configuration Reshape/1");
add_line(path, "Interactive Configuration Reshape/1", "Interactive Configuration [18x1]/1");
add_line(path, "Interactive Configuration [18x1]/1", "Mode Selector/1");
add_line(path, "Qualification Scenario Source/1", "Qualification Configuration Reshape/1");
add_line(path, "Qualification Configuration Reshape/1", "Qualification Configuration [18x1]/1");
add_line(path, "Qualification Configuration [18x1]/1", "Mode Selector/2");
add_line(path, "Mode Selector/1", "Selected Configuration [18x1]/1");
add_line(path, "Selected Configuration [18x1]/1", "Configuration/1");
end

function buildVehicle(path)
add_block("simulink/Ports & Subsystems/In1", path + "/Configuration", "Port", "1");
addFixedConfigurationSpecification(path + "/Vehicle State Fixed Packed [18x1]", [85 45 145 75]);
add_block("simulink/Ports & Subsystems/Out1", path + "/Packed", "Port", "1");
add_line(path, "Configuration/1", "Vehicle State Fixed Packed [18x1]/1");
add_line(path, "Vehicle State Fixed Packed [18x1]/1", "Packed/1");
end

function buildEngine(path)
add_block("simulink/Ports & Subsystems/In1", path + "/Packed", "Port", "1");
addFixedConfigurationSpecification(path + "/Engine Excitation Fixed Packed [18x1]", [55 55 115 85]);
block = path + "/Order Harmonic Transient";
add_block("simulink/User-Defined Functions/MATLAB Function", block);
setChartScript(block, s12_sound_playground_function_scripts().engine);
s12_sound_playground_configure_function_interfaces(block, "EngineExcitation");
add_block("simulink/Ports & Subsystems/Out1", path + "/Excitation", "Port", "1");
add_block("simulink/Sources/Constant", path + "/Reset Zero", "Value", "0", "SampleTime", "0.02");
add_block("simulink/Discrete/Unit Delay", path + "/Reset Pulse", "InitialCondition", "1", "SampleTime", "0.02");
add_block("simulink/Ports & Subsystems/Out1", path + "/Packed Out", "Port", "2");
add_line(path, "Packed/1", "Engine Excitation Fixed Packed [18x1]/1");
add_line(path, "Engine Excitation Fixed Packed [18x1]/1", "Order Harmonic Transient/1");
add_line(path, "Reset Zero/1", "Reset Pulse/1");
add_line(path, "Reset Pulse/1", "Order Harmonic Transient/2");
add_line(path, "Order Harmonic Transient/1", "Excitation/1");
add_line(path, "Order Harmonic Transient/2", "Packed Out/1");
end

function addFixedConfigurationSpecification(path, position)
add_block("simulink/Signal Attributes/Signal Specification", path, ...
    "OutDataTypeStr", "double", "Dimensions", "[18 1]", "VarSizeSig", "No", "Position", position);
end

function addFixedConfigurationReshape(path, position)
add_block("simulink/Math Operations/Reshape", path, ...
    "OutputDimensionality", "Customize", "OutputDimensions", "[18,1]", "Position", position);
end

function buildPtr(path)
add_block("simulink/Ports & Subsystems/In1", path + "/Excitation", "Port", "1");
add_block("simulink/Ports & Subsystems/In1", path + "/Packed", "Port", "2");
block = path + "/Synthetic PTR Radiation";
add_block("simulink/User-Defined Functions/MATLAB Function", block);
setChartScript(block, s12_sound_playground_function_scripts().ptr);
s12_sound_playground_configure_function_interfaces(block, "PtrRadiationTuningAdapter");
add_block("simulink/Ports & Subsystems/Out1", path + "/Pressure", "Port", "1");
add_block("simulink/Sources/Constant", path + "/Reset Zero", "Value", "0", "SampleTime", "0.02");
add_block("simulink/Discrete/Unit Delay", path + "/Reset Pulse", "InitialCondition", "1", "SampleTime", "0.02");
add_block("simulink/Ports & Subsystems/Out1", path + "/Packed Out", "Port", "2");
add_line(path, "Excitation/1", "Synthetic PTR Radiation/1");
add_line(path, "Packed/1", "Synthetic PTR Radiation/2");
add_line(path, "Reset Zero/1", "Reset Pulse/1");
add_line(path, "Reset Pulse/1", "Synthetic PTR Radiation/3");
add_line(path, "Synthetic PTR Radiation/1", "Pressure/1");
add_line(path, "Synthetic PTR Radiation/2", "Packed Out/1");
end

function buildRenderer(path)
add_block("simulink/Ports & Subsystems/In1", path + "/Pressure", "Port", "1");
add_block("simulink/Ports & Subsystems/In1", path + "/Packed", "Port", "2");
block = path + "/Gain Stereo Renderer";
add_block("simulink/User-Defined Functions/MATLAB Function", block);
setChartScript(block, s12_sound_playground_function_scripts().renderer);
s12_sound_playground_configure_function_interfaces(block, "AudioRenderer");
add_block("simulink/Ports & Subsystems/Out1", path + "/PCM", "Port", "1");
add_line(path, "Pressure/1", "Gain Stereo Renderer/1");
add_line(path, "Packed/1", "Gain Stereo Renderer/2");
add_line(path, "Gain Stereo Renderer/1", "PCM/1");
end

function addTopLevelLines(model)
links = ["Dashboard/1", "Vehicle State/1"; "Vehicle State/1", "Engine Excitation/1"; ...
    "Engine Excitation/1", "PTR Radiation Tuning Adapter/1"; "Engine Excitation/2", "PTR Radiation Tuning Adapter/2"; ...
    "PTR Radiation Tuning Adapter/1", "Audio Renderer/1"; "PTR Radiation Tuning Adapter/2", "Audio Renderer/2"; ...
    "Audio Renderer/1", "Qualification PCM Sink/1"; "Audio Renderer/1", "Optional Device Output/1"];
for index = 1:size(links, 1)
    add_line(model, links(index, 1), links(index, 2));
end
end

function setChartScript(blockPath, script)
chart = sfroot().find("-isa", "Stateflow.EMChart", "Path", blockPath);
if numel(chart) ~= 1
    error("S12:Playground:StateflowChart", "Expected one chart at %s.", blockPath);
end
chart.Script = script;
end

function assertSignalSpecificationReadback(model)
names = [ ...
    "Dashboard/Interactive Configuration [18x1]", ...
    "Dashboard/Qualification Configuration [18x1]", ...
    "Dashboard/Selected Configuration [18x1]", ...
    "Vehicle State/Vehicle State Fixed Packed [18x1]", ...
    "Engine Excitation/Engine Excitation Fixed Packed [18x1]"];
for index = 1:numel(names)
    path = string(model) + "/" + names(index);
    dimensions = s12_sound_playground_require_text_scalar(get_param(path, "Dimensions"), "Dimensions");
    variableSize = s12_sound_playground_require_text_scalar(get_param(path, "VarSizeSig"), "VarSizeSig");
    dataType = s12_sound_playground_require_text_scalar(get_param(path, "OutDataTypeStr"), "OutDataTypeStr");
    if ~strcmp(dimensions, "[18 1]") || ~strcmp(variableSize, "No") || ~strcmp(dataType, "double")
        error("S12:Playground:SignalSpecification", "Signal Specification readback failed at %s.", path);
    end
end
end

function lease = ownedLease(modelName, owned, cleanupErrorPath)
lease = struct("model_name", string(modelName), "owned", logical(owned), "cleanup_error_path", string(cleanupErrorPath));
end

function results = closeOwnedBuilderResources(modelLease, libraryLease)
results = [s12_sound_playground_close_owned_model_without_save(modelLease), ...
    s12_sound_playground_close_owned_model_without_save(libraryLease)];
end

function fallbackOwnedCleanup(modelName, libraryOwned, temporaryRoot)
modelLease = ownedLease(modelName, bdIsLoaded(modelName), fullfile(temporaryRoot, "model_cleanup_failure.json"));
libraryLease = ownedLease("dspsnks4", libraryOwned && bdIsLoaded("dspsnks4"), ...
    fullfile(temporaryRoot, "library_cleanup_failure.json"));
closeOwnedBuilderResources(modelLease, libraryLease);
end

function writeFailure(path, cause, cleanupResults)
failure = struct("identifier", string(cause.identifier), "message", string(cause.message), ...
    "cleanup", cleanupResults);
folder = fileparts(path);
if isfolder(folder)
    s12_sound_playground_atomic_write_json(path, failure);
end
end
