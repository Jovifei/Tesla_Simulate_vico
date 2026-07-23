function result = s12_run_radiation_boundary_fixed_driver(config)
%S12_RUN_RADIATION_BOUNDARY_FIXED_DRIVER Run one fixed-size 4D-B feedback simulation.
arguments
    config (1,1) struct
end
validateConfig(config);
root = fileparts(fileparts(fileparts(mfilename("fullpath"))));
modelRoot = fullfile(root, "models", "fvm_ref");
benchmarkRoot = fullfile(root, "benchmark");
driverPath = fullfile(modelRoot, "s12_euler_fvm_radiation_boundary_driver_ref.slx");
if ~isfile(driverPath)
    error("S12:Radiation:MissingFixedDriver", "The fixed-size radiation driver is missing.");
end

ambient = primitives(config.ambient_state, config.gamma);
schedule = fixedSchedule(config, ambient);
transactionRoot = fullfile(tempdir, "s12b_" + shortToken());
cacheRoot = fullfile(transactionRoot, "slcache");
codeGenRoot = fullfile(transactionRoot, "codegen");
mkdir(transactionRoot); mkdir(cacheRoot); mkdir(codeGenRoot);
pathBefore = path;
fileGenConfig = Simulink.fileGenControl("getConfig");
addpath(modelRoot);
addpath(benchmarkRoot);
Simulink.fileGenControl("set", "CacheFolder", cacheRoot, "CodeGenFolder", codeGenRoot);
try
    [modelName, workspaceNames] = buildTransactionDriver(driverPath, transactionRoot, ...
        config, schedule, ambient);
catch exception
    cleanupTransaction(transactionRoot, strings(0, 1), pathBefore, fileGenConfig);
    rethrow(exception)
end
cleanup = onCleanup(@() cleanupTransaction(transactionRoot, workspaceNames, ...
    pathBefore, fileGenConfig));
simResult = runDriver(modelName, config, schedule, ambient);
result = struct( ...
    "final_state", simResult.final_state, ...
    "final_radiation_state", simResult.final_radiation_state, ...
    "final_time_s", schedule.stop_time_s, ...
    "step_count", schedule.step_count, ...
    "maximum_cfl", simResult.maximum_cfl, ...
    "trace_time_s", simResult.trace_time_s, ...
    "trace_outgoing_pressure_pa", simResult.trace_outgoing_pressure_pa, ...
    "trace_incoming_pressure_pa", simResult.trace_incoming_pressure_pa, ...
    "trace_boundary3_radiation_state", simResult.trace_boundary3_radiation_state, ...
    "trace_input_pressure_pa", simResult.trace_input_pressure_pa, ...
    "model_path", driverPath, ...
    "runner_id", "s12.radiation.fixed_size_feedback", ...
    "runner_version", "1.0.0", ...
    "driver_path", driverPath, ...
    "driver_sha256", sha256File(driverPath), ...
    "execution_mode", "fixed_size_discrete_feedback.v1", ...
    "physical_step_count", schedule.step_count, ...
    "sim_call_count", 1, ...
    "compile_count", 1, ...
    "boundary_crossing_count", 1, ...
    "qualification", struct( ...
        "retry_count", 0, "rejected_step_count", 0, "rollback_count", 0, ...
        "clipping_count", 0, "fallback_count", 0, "end_time_clipping_count", 0, ...
        "maximum_radiation_stage_pole_amplification", schedule.maximum_amplification, ...
        "radiation_state_dimension", numel(simResult.final_radiation_state), ...
        "radiation_state_order", numel(simResult.final_radiation_state), ...
        "radiation_state_initialization", "package_initial_state.v1", ...
        "input_stage_time_id", "ssprk3_c_0_1_half.v1", ...
        "fast_restart_used", false));
end

function schedule = fixedSchedule(config, ambient)
cellCount = size(config.initial_state, 2);
dx = config.pipe_length_m / cellCount;
radiationState = fieldOr(config, "initial_radiation_state", config.radiation_package.initial_state);
alpha = stageAlphaBound(config.initial_state, radiationState, config, ambient);
nominalDt = config.cfl * dx / alpha;
stepCount = max(1, ceil(config.end_time_s / nominalDt));
if stepCount > config.max_steps
    error("S12:Radiation:MaxSteps", "Fixed-size driver exceeds the explicit step capacity.");
end
dt = config.end_time_s / stepCount;
limit = fieldOr(config, "maximum_radiation_stage_pole_amplification", 1 + 1e-10);
stability = s12_radiation_boundary_step_stability(config.radiation_package, dt);
while stability.maximum_stage_pole_amplification > limit
    stepCount = stepCount + 1;
    if stepCount > config.max_steps
        error("S12:Radiation:PoleTimeStep", ...
            "No fixed-size step count satisfies the radiation stability limit.");
    end
    dt = config.end_time_s / stepCount;
    stability = s12_radiation_boundary_step_stability(config.radiation_package, dt);
end
schedule = struct("dx_m", dx, "dt_s", dt, "step_count", stepCount, ...
    "stop_time_s", config.end_time_s, ...
    "maximum_amplification", stability.maximum_stage_pole_amplification);
end

function [modelName, workspaceNames] = buildTransactionDriver(driverPath, transactionRoot, config, schedule, ambient)
clonePath = fullfile(transactionRoot, ...
    "d_" + shortToken() + ".slx");
copyfile(driverPath, clonePath, "f");
modelName = loadTransactionModel(clonePath);
workspaceNames = configureFeedbackTopology(modelName, schedule.step_count);
configureFeedbackInputs(modelName, config, schedule, ambient);
assignStageInputs(workspaceNames, config.input_signal, schedule);
end

function modelName = loadTransactionModel(clonePath)
before = loadedBlockDiagrams();
load_system(clonePath);
after = loadedBlockDiagrams();
candidates = setdiff(after, before, "stable");
if isempty(candidates)
    candidates = after(cellfun(@(name) strcmpi(char(get_param(name, "FileName")), ...
        char(clonePath)), after));
end
if numel(candidates) ~= 1
    error("S12:Driver:FeedbackClone", "Expected exactly one fixed-driver transaction model.");
end
modelName = string(candidates{1});
end

function workspaceNames = configureFeedbackTopology(modelName, maxPoints)
add_block("simulink/Discrete/Unit Delay", modelName + "/StateMemory", ...
    "Position", [20 80 130 110], "SampleTime", "-1", "InitialCondition", "zeros(3,25)");
add_block("simulink/Discrete/Unit Delay", modelName + "/RadiationMemory", ...
    "Position", [20 140 130 170], "SampleTime", "-1", "InitialCondition", "zeros(2,1)");
replaceInput(modelName, "StateMemory", 1, "Boundary1", 1);
replaceInput(modelName, "StateMemory", 1, "Stage1", 1);
replaceInput(modelName, "StateMemory", 1, "Stage2", 1);
replaceInput(modelName, "StateMemory", 1, "Stage3", 1);
replaceInput(modelName, "RadiationMemory", 1, "Boundary1", 2);
replaceInput(modelName, "RadiationMemory", 1, "RadEuler", 1);
replaceInput(modelName, "RadiationMemory", 1, "RadStage2", 1);
replaceInput(modelName, "RadiationMemory", 1, "RadStage3", 1);
for block = ["U0", "X0"]
    path = modelName + "/" + block;
    if getSimulinkBlockHandle(path) >= 0, delete_block(path); end
end
connect(modelName, "Stage3", 1, "StateMemory", 1);
connect(modelName, "RadStage3", 1, "RadiationMemory", 1);

token = uniqueToken();
workspaceNames = "s12_4db_" + token + ["_left_1"; "_left_2"; "_left_3"];
for index = 1:3
    block = "LeftInputStage" + index;
    add_block("simulink/Sources/From Workspace", modelName + "/" + block, ...
        "Position", [20 210 + 55 * index 130 235 + 55 * index], ...
        "VariableName", workspaceNames(index));
    replaceInput(modelName, block, 1, "Boundary" + index, 9);
end
addTrace(modelName, "StateMemoryTrace", "s12_4db_state_" + token, [1450 80 1560 110], maxPoints + 1);
addTrace(modelName, "RadiationMemoryTrace", "s12_4db_radiation_" + token, [1450 140 1560 170], maxPoints + 1);
addTrace(modelName, "ProbeTrace", "s12_4db_probe_" + token, [1450 200 1560 230], maxPoints + 1);
addTrace(modelName, "Boundary3RadiationTrace", "s12_4db_boundary3_radiation_" + token, [1450 260 1560 290], maxPoints + 1);
connect(modelName, "StateMemory", 1, "StateMemoryTrace", 1);
connect(modelName, "RadiationMemory", 1, "RadiationMemoryTrace", 1);
connect(modelName, "Boundary3", 2, "ProbeTrace", 1);
connect(modelName, "RadStage2", 1, "Boundary3RadiationTrace", 1);
workspaceNames = [workspaceNames; "s12_4db_state_" + token; ...
    "s12_4db_radiation_" + token; "s12_4db_probe_" + token; ...
    "s12_4db_boundary3_radiation_" + token];
end

function addTrace(modelName, block, variableName, position, maxPoints)
add_block("simulink/Sinks/To Workspace", modelName + "/" + block, ...
    "Position", position, "VariableName", variableName, ...
    "SaveFormat", "Structure With Time", "MaxDataPoints", num2str(maxPoints));
end

function configureFeedbackInputs(modelName, config, schedule, ambient)
state = config.initial_state;
radiationState = fieldOr(config, "initial_radiation_state", config.radiation_package.initial_state);
set_param(modelName + "/StateMemory", "InitialCondition", mat2str(state, 17), ...
    "SampleTime", mat2str(schedule.dt_s, 17));
set_param(modelName + "/RadiationMemory", "InitialCondition", mat2str(radiationState, 17), ...
    "SampleTime", mat2str(schedule.dt_s, 17));
set_param(modelName + "/Gamma", "Value", mat2str(config.gamma, 17));
set_param(modelName + "/Dx", "Value", mat2str(schedule.dx_m, 17));
set_param(modelName + "/Dt", "Value", mat2str(schedule.dt_s, 17));
set_param(modelName + "/Cfl", "Value", mat2str(config.cfl, 17));
set_param(modelName + "/RhoFloor", "Value", mat2str(min(1e-13, min(state(1, :))), 17));
set_param(modelName + "/PFloor", "Value", mat2str(min(1e-13, minimumPressure(state, config.gamma)), 17));
set_param(modelName + "/Ambient", "Value", mat2str([ambient.density_kg_m3; 0; ...
    ambient.pressure_pa / (config.gamma - 1)], 17));
set_param(modelName + "/A", "Value", mat2str(config.radiation_package.state_space_A, 17));
set_param(modelName + "/B", "Value", mat2str(config.radiation_package.state_space_B, 17));
set_param(modelName + "/C", "Value", mat2str(config.radiation_package.state_space_C, 17));
set_param(modelName + "/D", "Value", mat2str(config.radiation_package.state_space_D, 17));
set_param(modelName + "/SmallSignal", "Value", mat2str(config.small_signal_limit, 17));
set_param(modelName, "FixedStep", mat2str(schedule.dt_s, 17), ...
    "StopTime", mat2str(schedule.stop_time_s, 17));
end

function assignStageInputs(names, signal, schedule)
time = reshape((0:schedule.step_count).' * schedule.dt_s, [], 1);
stageOffsets = [0, schedule.dt_s, 0.5 * schedule.dt_s];
for index = 1:3
    values = inputPressure(signal, time + stageOffsets(index));
    assignin("base", names(index), timeseries(reshape(values, [], 1), time));
end
end

function result = runDriver(modelName, config, schedule, ambient)
tic;
set_param(modelName, "SimulationCommand", "update");
compileSeconds = toc;
tic;
simOut = sim(modelName, "ReturnWorkspaceOutputs", "on");
simulationSeconds = toc;
stateTrace = readTrace(simOut, "s12_4db_state_", modelName);
radiationTrace = readTrace(simOut, "s12_4db_radiation_", modelName);
probeTrace = readTrace(simOut, "s12_4db_probe_", modelName);
boundary3RadiationTrace = readTrace(simOut, "s12_4db_boundary3_radiation_", modelName);
[stateHistory, stateSize] = traceHistory(stateTrace);
[radiationHistory, radiationSize] = traceHistory(radiationTrace);
[probeHistory, probeSize] = traceHistory(probeTrace);
[boundary3RadiationHistory, boundary3RadiationSize] = traceHistory(boundary3RadiationTrace);
if ~isequal(stateSize, size(config.initial_state)) || ~isequal(radiationSize, [2, 1]) || ...
        ~isequal(boundary3RadiationSize, [2, 1]) || probeSize ~= 1
    error("S12:Driver:FeedbackShape", "Fixed-size feedback output shape failed.");
end
time = reshape(probeTrace.time, 1, []);
sampleCount = numel(time);
if sampleCount < 2 || size(stateHistory, 2) ~= sampleCount || ...
        size(radiationHistory, 2) ~= sampleCount || ...
        size(boundary3RadiationHistory, 2) ~= sampleCount || ...
        size(probeHistory, 2) ~= sampleCount
    error("S12:Driver:TraceLength", "Fixed-size feedback traces are incomplete.");
end
outgoing = reshape(probeHistory, 1, []);
incoming = zeros(size(outgoing));
for index = 1:sampleCount
    radiationState = reshape(boundary3RadiationHistory(:, index), boundary3RadiationSize);
    boundary = s12_radiation_boundary_stage(config.radiation_package, radiationState, ...
        outgoing(index), ambient, config.gamma, config.small_signal_limit);
    incoming(index) = boundary.incoming_pressure_pa;
end
finalState = reshape(stateHistory(:, end), stateSize);
finalRadiationState = reshape(radiationHistory(:, end), radiationSize);
if any(~isfinite(finalState), "all") || any(~isfinite(finalRadiationState), "all")
    error("S12:Driver:FeedbackShape", "Fixed-size feedback output is non-finite.");
end
result = struct("final_state", finalState, "final_radiation_state", finalRadiationState, ...
    "maximum_cfl", maximumCfl(stateHistory, stateSize, schedule.dx_m, schedule.dt_s, config.gamma), ...
    "trace_time_s", time, "trace_outgoing_pressure_pa", outgoing, ...
    "trace_incoming_pressure_pa", incoming, ...
    "trace_boundary3_radiation_state", boundary3RadiationHistory, ...
    "trace_input_pressure_pa", inputPressure(config.input_signal, time), ...
    "compile_seconds", compileSeconds, "simulation_seconds", simulationSeconds);
end

function trace = readTrace(simOut, prefix, modelName)
token = regexp(char(modelName), "[A-Za-z0-9_]+$", "match", "once");
names = string(simOut.who);
index = find(startsWith(names, prefix), 1);
if isempty(index)
    error("S12:Driver:TraceMissing", "A fixed-driver trace is missing.");
end
raw = simOut.get(names(index));
if isstruct(raw) && isfield(raw, "signals")
    trace = struct("data", raw.signals.values, "time", raw.time);
elseif isa(raw, "timeseries")
    trace = struct("data", raw.Data, "time", raw.Time);
else
    error("S12:Driver:TraceType", "Fixed-driver trace %s is not time-addressable.", token);
end
end

function [history, sampleSize] = traceHistory(trace)
data = trace.data;
timeCount = numel(trace.time);
timeDimension = find(size(data) == timeCount, 1, "last");
if isempty(timeDimension)
    error("S12:Driver:TraceShape", "Cannot identify the fixed-driver trace time dimension.");
end
order = [setdiff(1:ndims(data), timeDimension, "stable"), timeDimension];
ordered = permute(data, order);
sampleSize = size(ordered);
sampleSize = sampleSize(1:end-1);
if isempty(sampleSize), sampleSize = 1; end
history = reshape(ordered, prod(sampleSize), timeCount);
end

function value = maximumCfl(history, stateSize, dx, dt, gamma)
value = 0;
for index = 1:size(history, 2)
    value = max(value, dt * stageAlpha(reshape(history(:, index), stateSize), gamma) / dx);
end
end

function connect(modelName, source, sourcePort, destination, destinationPort)
src = get_param(modelName + "/" + source, "PortHandles");
dst = get_param(modelName + "/" + destination, "PortHandles");
if sourcePort > numel(src.Outport) || destinationPort > numel(dst.Inport) || ...
        get_param(dst.Inport(destinationPort), "Line") ~= -1
    error("S12:Driver:PortContract", "Fixed-driver connection contract failed.");
end
add_line(modelName, src.Outport(sourcePort), dst.Inport(destinationPort), "autorouting", "on");
end

function replaceInput(modelName, source, sourcePort, destination, destinationPort)
src = get_param(modelName + "/" + source, "PortHandles");
dst = get_param(modelName + "/" + destination, "PortHandles");
if sourcePort > numel(src.Outport) || destinationPort > numel(dst.Inport)
    error("S12:Driver:PortContract", "Fixed-driver replacement port does not exist.");
end
oldLine = get_param(dst.Inport(destinationPort), "Line");
if oldLine ~= -1
    delete_line(modelName, get_param(oldLine, "SrcPortHandle"), dst.Inport(destinationPort));
end
if get_param(dst.Inport(destinationPort), "Line") ~= -1
    error("S12:Driver:PortContract", "Fixed-driver destination port was not released.");
end
add_line(modelName, src.Outport(sourcePort), dst.Inport(destinationPort), "autorouting", "on");
end

function models = loadedBlockDiagrams()
models = find_system("SearchDepth", 0, "Type", "block_diagram");
models = models(:).';
end

function value = inputPressure(signal, time)
if ~isstruct(signal) || isempty(fieldnames(signal))
    value = zeros(size(time));
else
    value = s12_radiation_input_signal(signal, time);
end
end

function value = fieldOr(config, name, fallback)
if isfield(config, name), value = config.(name); else, value = fallback; end
end

function value = primitives(state, gamma)
density = state(1); velocity = state(2) / density;
pressure = (gamma - 1) * (state(3) - 0.5 * density * velocity^2);
if density <= 0 || pressure <= 0
    error("S12:Radiation:InvalidInput", "Ambient state is nonphysical.");
end
value = struct("density_kg_m3", density, "pressure_pa", pressure, ...
    "sound_speed_mps", sqrt(gamma * pressure / density));
end

function alpha = stageAlpha(state, gamma)
density = state(1, :); velocity = state(2, :) ./ density;
pressure = (gamma - 1) * (state(3, :) - 0.5 * density .* velocity.^2);
alpha = max(abs(velocity) + sqrt(gamma * pressure ./ density));
end

function alpha = stageAlphaBound(state, radiationState, config, ambient)
alpha = stageAlpha(state, config.gamma);
sourceBound = inputAmplitudeBound(config.input_signal);
if sourceBound > 0
    positive = s12_radiation_left_driven_boundary_state(state(:, 1), ...
        config.ambient_state, config.gamma, sourceBound, config.small_signal_limit);
    negative = s12_radiation_left_driven_boundary_state(state(:, 1), ...
        config.ambient_state, config.gamma, -sourceBound, config.small_signal_limit);
    alpha = max(alpha, stageAlpha([positive.state, negative.state], config.gamma));
end
outgoing = outgoingPressure(state(:, end), ambient, config.gamma);
right = s12_radiation_boundary_stage(config.radiation_package, radiationState, ...
    outgoing, ambient, config.gamma, config.small_signal_limit);
rightState = [right.boundary_density_kg_m3; ...
    right.boundary_density_kg_m3 * right.boundary_velocity_mps; ...
    right.boundary_pressure_pa / (config.gamma - 1) + 0.5 * ...
    right.boundary_density_kg_m3 * right.boundary_velocity_mps^2];
alpha = max(alpha, stageAlpha(rightState, config.gamma));
end

function value = inputAmplitudeBound(signal)
if ~isstruct(signal) || isempty(fieldnames(signal))
    value = 0;
    return
end
switch string(signal.id)
    case "multisine.v1"
        value = sum(abs(signal.amplitude_pa));
    case {"single_tone.v1", "chirp_linear.v1", "gaussian_pulse.v1"}
        value = abs(signal.amplitude_pa);
    otherwise
        error("S12:Radiation:UnsupportedInput", "Unsupported radiation input signal.");
end
end

function value = outgoingPressure(state, ambient, gamma)
density = state(1); velocity = state(2) / density;
pressure = (gamma - 1) * (state(3) - 0.5 * density * velocity^2);
value = 0.5 * ((pressure - ambient.pressure_pa) + ...
    ambient.density_kg_m3 * ambient.sound_speed_mps * velocity);
end

function value = minimumPressure(state, gamma)
density = state(1, :); velocity = state(2, :) ./ density;
value = min((gamma - 1) * (state(3, :) - 0.5 * density .* velocity.^2));
end

function validateConfig(config)
required = ["gamma", "pipe_length_m", "initial_state", "ambient_state", "end_time_s", ...
    "cfl", "max_steps", "small_signal_limit", "radiation_package"];
if ~all(isfield(config, required)) || size(config.initial_state, 1) ~= 3 || ...
        size(config.initial_state, 2) < 3 || ~isequal(size(config.ambient_state), [3, 1]) || ...
        config.gamma <= 1 || config.pipe_length_m <= 0 || config.end_time_s <= 0 || ...
        config.cfl <= 0 || config.cfl > 0.5 || config.max_steps < 1 || ...
        config.small_signal_limit <= 0 || any(~isfinite(config.initial_state), "all") || ...
        (isfield(config, "initial_radiation_state") && ...
        (~isequal(size(config.initial_radiation_state), [2, 1]) || ...
        any(~isfinite(config.initial_radiation_state))))
    error("S12:Radiation:InvalidInput", "Fixed-size radiation configuration is invalid.");
end
end

function value = sha256File(path)
[file, message] = fopen(path, "rb");
if file < 0, error("S12:Radiation:HashFailure", "Cannot read %s: %s.", path, message); end
cleanup = onCleanup(@() fclose(file));
bytes = fread(file, "*uint8");
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(bytes);
raw = typecast(digest.digest(), "uint8");
value = upper(string(reshape(dec2hex(raw, 2).', 1, [])));
end

function value = uniqueToken()
value = string(strrep(char(java.util.UUID.randomUUID), "-", "_"));
end

function value = shortToken()
value = extractBefore(uniqueToken(), 9);
end

function cleanupTransaction(transactionRoot, workspaceNames, pathBefore, fileGenConfig)
for model = loadedBlockDiagrams()
    try
        fileName = string(get_param(model{1}, "FileName"));
        if startsWith(fileName, transactionRoot, "IgnoreCase", true)
            close_system(model{1}, 0);
        end
    catch
    end
end
for index = 1:numel(workspaceNames)
    evalin("base", "clear('" + workspaceNames(index) + "')");
end
Simulink.fileGenControl("setConfig", "config", fileGenConfig);
path(pathBefore);
if isfolder(transactionRoot), rmdir(transactionRoot, "s"); end
end
