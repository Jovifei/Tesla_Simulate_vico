function result = s12_run_radiation_boundary_fvm(config)
%S12_RUN_RADIATION_BOUNDARY_FVM Run explicit PP FVM with 4D-B right boundary.
arguments
    config (1,1) struct
end
validateConfig(config);
root = fileparts(fileparts(fileparts(mfilename("fullpath"))));
transientRoot = fullfile(root, "validation", "transient_wave");
addedTransient = ~any(string(strsplit(path,pathsep)) == transientRoot);
if addedTransient, addpath(transientRoot); end
cleanup = onCleanup(@() cleanupPath(transientRoot,addedTransient));
modelRoot = fullfile(root, "models", "fvm_ref");
stepModel = "s12_euler_fvm_periodic_step_muscl_minmod_pp_ref";
stageModel = "s12_euler_ssprk3_periodic_ref";
stepWasLoaded = bdIsLoaded(stepModel); stageWasLoaded = bdIsLoaded(stageModel);
load_system(fullfile(modelRoot, stepModel + ".slx"));
load_system(fullfile(modelRoot, stageModel + ".slx"));
fastRestart = configureFastRestart(stepModel, stageModel, fieldOr(config, "use_fast_restart", true));
modelCleanup = onCleanup(@() closeOwnedModels(stepModel, stageModel, ...
    stepWasLoaded, stageWasLoaded, fastRestart));
ambient = primitives(config.ambient_state, config.gamma);
ambientPrimitive = struct("pressure_pa",ambient.pressure,"density_kg_m3",ambient.density, ...
    "sound_speed_mps",ambient.sound_speed);
state = config.initial_state;
radiationState = fieldOr(config, "initial_radiation_state", config.radiation_package.initial_state);
time = 0; stepCount = 0; maximumCfl = 0; endClipCount = 0;
maximumAmplification = 0;
retryCount = 0; rejectedStepCount = 0; rollbackCount = 0;
stabilityLimit = fieldOr(config, "maximum_radiation_stage_pole_amplification", 1 + 1e-10);
maximumRetries = fieldOr(config, "maximum_retries", 8);
traceTime = zeros(1, config.max_steps + 1);
traceOutgoing = zeros(1, config.max_steps + 1);
traceIncoming = zeros(1, config.max_steps + 1);
traceInput = zeros(1, config.max_steps + 1);
traceOutgoing(1) = outgoingPressure(state(:, end), ambientPrimitive, config.gamma);
initialBoundary = s12_radiation_boundary_stage(config.radiation_package, radiationState, ...
    traceOutgoing(1), ambientPrimitive, config.gamma, config.small_signal_limit);
traceIncoming(1) = initialBoundary.incoming_pressure_pa;
traceInput(1) = inputPressure(config, 0);
while time < config.end_time_s
    if stepCount >= config.max_steps
        error("S12:Radiation:MaxSteps", "Radiation run exhausted explicit step capacity.");
    end
    alpha = stageAlphaBound(state, radiationState, config, ambientPrimitive);
    nominalDt = config.cfl * (config.pipe_length_m/size(state,2)) / alpha;
    dt = min(nominalDt,config.end_time_s-time);
    endClipCount = endClipCount + double(dt < nominalDt);
    stateStart = state; radiationStart = radiationState;
    candidateState = stateStart; candidateRadiationState = radiationStart;
    accepted = false;
    for attempt = 0:maximumRetries
        try
            stability = s12_radiation_boundary_step_stability(config.radiation_package,dt);
            if stability.maximum_stage_pole_amplification > stabilityLimit
                error("S12:Radiation:PoleTimeStep", ...
                    "Radiation SSP-RK3 pole amplification exceeds the configured limit.");
            end
            step = s12_radiation_pp_characteristic_step(candidateState,config.gamma, ...
                config.pipe_length_m/size(candidateState,2),dt,"Package",config.radiation_package, ...
                "RadiationState",candidateRadiationState,"AmbientState",config.ambient_state, ...
                "AmbientPrimitives",ambientPrimitive,"SmallSignalLimit",config.small_signal_limit, ...
                "Cfl",config.cfl, "LeftIncomingPressureStages", ...
                inputPressure(config, [time, time + dt, time + 0.5 * dt]));
            accepted = true;
            break
        catch exception
            if attempt >= maximumRetries || ~any(string(exception.identifier) == ...
                    ["S12:Radiation:PoleTimeStep", "S12:Radiation:CflClipped"])
                rethrow(exception)
            end
            retryCount = retryCount + 1;
            rejectedStepCount = rejectedStepCount + 1;
            rollbackCount = rollbackCount + 1;
            candidateState = stateStart;
            candidateRadiationState = radiationStart;
            dt = 0.5 * dt;
        end
    end
    if ~accepted
        error("S12:Radiation:RetryLimit", ...
            "Radiation FVM exceeded the explicit retry limit.");
    end
    state = step.final_state; radiationState = step.final_radiation_state;
    maximumAmplification = max(maximumAmplification, ...
        step.maximum_radiation_stage_pole_amplification);
    maximumCfl = max(maximumCfl, dt*alpha/(config.pipe_length_m/size(state,2)));
    time = time+dt; stepCount = stepCount+1;
    traceTime(stepCount + 1) = time;
    traceOutgoing(stepCount + 1) = step.outgoing_pressure_pa(3);
    finalBoundary = s12_radiation_boundary_stage(config.radiation_package, radiationState, ...
        traceOutgoing(stepCount + 1), ambientPrimitive, config.gamma, config.small_signal_limit);
    traceIncoming(stepCount + 1) = finalBoundary.incoming_pressure_pa;
    traceInput(stepCount + 1) = inputPressure(config, time);
end
result = struct("final_state",state,"final_radiation_state",radiationState, ...
    "final_time_s",time,"step_count",stepCount,"maximum_cfl",maximumCfl, ...
    "trace_time_s",traceTime(1:stepCount+1), ...
    "trace_outgoing_pressure_pa",traceOutgoing(1:stepCount+1), ...
    "trace_incoming_pressure_pa",traceIncoming(1:stepCount+1), ...
    "trace_input_pressure_pa",traceInput(1:stepCount+1), ...
    "model_path",fullfile(root,"models","fvm_ref","s12_euler_fvm_radiation_boundary_ref.slx"), ...
    "qualification",struct("retry_count",retryCount,"rejected_step_count",rejectedStepCount, ...
    "rollback_count",rollbackCount, ...
    "clipping_count",0,"fallback_count",0,"end_time_clipping_count",endClipCount, ...
    "maximum_radiation_stage_pole_amplification",maximumAmplification, ...
    "radiation_state_dimension",numel(radiationState), ...
    "radiation_state_order",numel(radiationState), ...
    "radiation_state_initialization","package_initial_state.v1", ...
    "input_stage_time_id","ssprk3_c_0_1_half.v1", ...
    "fast_restart_used",fastRestart.used));
end

function result = configureFastRestart(stepModel, stageModel, requested)
result = struct("used", logical(requested), "step_previous", get_param(stepModel, "FastRestart"), ...
    "stage_previous", get_param(stageModel, "FastRestart"));
if requested
    set_param(stepModel, "FastRestart", "on");
    set_param(stageModel, "FastRestart", "on");
end
end

function value = inputPressure(config, time)
if ~isfield(config, "input_signal")
    value = zeros(size(time));
    return
end
signal = config.input_signal;
if ~isstruct(signal)
    error("S12:Radiation:InvalidInput", "Input signal contract is invalid.");
end
if isempty(fieldnames(signal))
    value = zeros(size(time));
    return
end
value = s12_radiation_input_signal(signal, time);
end

function value = fieldOr(config, name, defaultValue)
if isfield(config, name), value = config.(name); else, value = defaultValue; end
end

function value = outgoingPressure(state, ambient, gamma)
density = state(1); velocity = state(2) / density;
pressure = (gamma - 1) * (state(3) - 0.5 * density * velocity^2);
value = 0.5 * ((pressure - ambient.pressure_pa) + ...
    ambient.density_kg_m3 * ambient.sound_speed_mps * velocity);
end

function validateConfig(config)
required=["gamma","pipe_length_m","initial_state","ambient_state","end_time_s", ...
    "cfl","max_steps","small_signal_limit","radiation_package"];
if ~all(isfield(config,required)) || size(config.initial_state,1)~=3 || ...
        size(config.initial_state,2)<3 || ~isequal(size(config.ambient_state),[3,1]) || ...
        config.gamma<=1 || config.pipe_length_m<=0 || config.end_time_s<0 || ...
        config.cfl<=0 || config.cfl>0.5 || config.max_steps<1 || ...
        config.small_signal_limit<=0 || any(~isfinite(config.initial_state),"all") || ...
        (isfield(config,"initial_radiation_state") && ...
        (~isequal(size(config.initial_radiation_state),[2,1]) || ...
        any(~isfinite(config.initial_radiation_state))))
    error("S12:Radiation:InvalidInput", "Radiation FVM configuration is invalid.");
end
end

function value=primitives(state,gamma)
density=state(1); velocity=state(2)/density; pressure=(gamma-1)*(state(3)-0.5*density*velocity^2);
if density<=0 || pressure<=0, error("S12:Radiation:InvalidInput","Ambient state is nonphysical."); end
value=struct("density",density,"pressure",pressure,"sound_speed",sqrt(gamma*pressure/density));
end

function alpha=stageAlpha(state,gamma)
density=state(1,:); velocity=state(2,:)./density;
pressure=(gamma-1)*(state(3,:)-0.5*density.*velocity.^2);
alpha=max(abs(velocity)+sqrt(gamma*pressure./density));
end

function alpha = stageAlphaBound(state, radiationState, config, ambient)
alpha = stageAlpha(state, config.gamma);
sourceBound = inputAmplitudeBound(config);
if sourceBound > 0
    positive = s12_radiation_left_driven_boundary_state(state(:,1), ...
        config.ambient_state, config.gamma, sourceBound, config.small_signal_limit);
    negative = s12_radiation_left_driven_boundary_state(state(:,1), ...
        config.ambient_state, config.gamma, -sourceBound, config.small_signal_limit);
    alpha = max(alpha, stageAlpha([positive.state, negative.state], config.gamma));
end
outgoing = outgoingPressure(state(:,end), ambient, config.gamma);
right = s12_radiation_boundary_stage(config.radiation_package, radiationState, ...
    outgoing, ambient, config.gamma, config.small_signal_limit);
rightState = [right.boundary_density_kg_m3; ...
    right.boundary_density_kg_m3 * right.boundary_velocity_mps; ...
    right.boundary_pressure_pa / (config.gamma - 1) + 0.5 * ...
    right.boundary_density_kg_m3 * right.boundary_velocity_mps^2];
alpha = max(alpha, stageAlpha(rightState, config.gamma));
end

function value = inputAmplitudeBound(config)
if ~isfield(config, "input_signal") || isempty(fieldnames(config.input_signal))
    value = 0;
    return
end
signal = config.input_signal;
switch string(signal.id)
    case "multisine.v1"
        value = sum(abs(signal.amplitude_pa));
    case {"single_tone.v1", "chirp_linear.v1", "gaussian_pulse.v1"}
        value = abs(signal.amplitude_pa);
    otherwise
        error("S12:Radiation:UnsupportedInput", ...
            "Unsupported radiation input signal '%s'.", string(signal.id));
end
end

function cleanupPath(pathName,wasAdded)
if wasAdded, rmpath(pathName); end
end

function closeOwnedModels(stepModel, stageModel, stepWasLoaded, stageWasLoaded, fastRestart)
if bdIsLoaded(stepModel), set_param(stepModel, "FastRestart", fastRestart.step_previous); end
if bdIsLoaded(stageModel), set_param(stageModel, "FastRestart", fastRestart.stage_previous); end
if ~stepWasLoaded && bdIsLoaded(stepModel), close_system(stepModel, 0); end
if ~stageWasLoaded && bdIsLoaded(stageModel), close_system(stageModel, 0); end
end
