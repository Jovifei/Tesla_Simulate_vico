function result = s12_run_periodic_ssprk3(initialState, gamma, dx, dt, ...
        stepCount, cfl)
%S12_RUN_PERIODIC_SSPRK3 Compose SSP-RK3 from the validated periodic step.
arguments
    initialState (3,:) double
    gamma (1,1) double {mustBeGreaterThan(gamma, 1)}
    dx (1,1) double {mustBePositive}
    dt (1,:) double {mustBePositive}
    stepCount (1,:) double {mustBeInteger, mustBeNonnegative}
    cfl (1,1) double {mustBePositive}
end

benchmarkRoot = fileparts(mfilename("fullpath"));
s12Root = fileparts(benchmarkRoot);
modelRoot = fullfile(s12Root, "models", "fvm_ref");
stepModel = "s12_euler_fvm_periodic_step_ref";
stageModel = "s12_euler_ssprk3_periodic_ref";
stepWasLoaded = bdIsLoaded(stepModel);
stageWasLoaded = bdIsLoaded(stageModel);
load_system(fullfile(modelRoot, stepModel + ".slx"));
load_system(fullfile(modelRoot, stageModel + ".slx"));
set_param(stepModel, "FastRestart", "on");
set_param(stageModel, "FastRestart", "on");
cleanup = onCleanup(@() closeOwnedModels(stepModel, stageModel, ...
    stepWasLoaded, stageWasLoaded));

validateState(initialState, gamma);
if numel(dt) ~= numel(stepCount)
    error("S12:Benchmark:TimeGridSize", ...
        "dt and stepCount must contain the same number of entries.");
end
result = runOne(initialState, gamma, dx, dt(1), stepCount(1), cfl, ...
    stepModel, stageModel);
for runIndex = 2:numel(dt)
    result(runIndex) = runOne(initialState, gamma, dx, dt(runIndex), ...
        stepCount(runIndex), cfl, stepModel, stageModel);
end
end

function result = runOne(initialState, gamma, dx, dt, stepCount, cfl, ...
        stepModel, stageModel)
state = initialState;
requestedDt = dt * ones(1, 3 * stepCount);
usedDt = zeros(size(requestedDt));
traceIndex = 0;
for timeStep = 1:stepCount
    baseState = state;
    [eulerState, used] = forwardEuler(stepModel, baseState, ...
        gamma, dx, dt, cfl);
    traceIndex = traceIndex + 1;
    usedDt(traceIndex) = used;
    state1 = combineStage(stageModel, baseState, eulerState, 1);

    [eulerState, used] = forwardEuler(stepModel, state1, ...
        gamma, dx, dt, cfl);
    traceIndex = traceIndex + 1;
    usedDt(traceIndex) = used;
    state2 = combineStage(stageModel, baseState, eulerState, 2);

    [eulerState, used] = forwardEuler(stepModel, state2, ...
        gamma, dx, dt, cfl);
    traceIndex = traceIndex + 1;
    usedDt(traceIndex) = used;
    state = combineStage(stageModel, baseState, eulerState, 3);
    validateState(state, gamma);
end

dtTolerance = 32 * eps(max(1, dt));
if any(abs(usedDt - requestedDt) > dtTolerance)
    error("S12:Benchmark:CflClipped", ...
        "A requested SSP-RK3 stage dt was clipped by the CFL limiter.");
end

result = struct( ...
    "final_state", state, ...
    "requested_dt", requestedDt, ...
    "used_dt", usedDt, ...
    "step_count", stepCount, ...
    "conservation_residual", sum(state - initialState, 2).', ...
    "boundary", "periodic");
end

function [stateNext, dtUsed] = forwardEuler(modelName, state, gamma, ...
        dx, dt, cfl)
workspace = get_param(modelName, "ModelWorkspace");
setParameterValue(workspace, "S12_FVM_State", state);
setParameterValue(workspace, "S12_FVM_Gamma", gamma);
setParameterValue(workspace, "S12_FVM_Dx", dx);
setParameterValue(workspace, "S12_FVM_DtRequest", dt);
setParameterValue(workspace, "S12_FVM_CFL", cfl);
output = sim(modelName);
stateNext = squeeze(output.S12_FVMStateNext);
dtUsed = output.S12_FVMDtUsed(end);
end

function stageState = combineStage(modelName, baseState, eulerState, stageIndex)
workspace = get_param(modelName, "ModelWorkspace");
setParameterValue(workspace, "S12_PRK3_BaseState", baseState);
setParameterValue(workspace, "S12_PRK3_EulerState", eulerState);
setParameterValue(workspace, "S12_PRK3_StageIndex", stageIndex);
output = sim(modelName);
stageState = squeeze(output.S12_PRK3StageState);
end

function validateState(state, gamma)
rho = state(1, :);
velocity = state(2, :) ./ rho;
pressure = (gamma - 1) * (state(3, :) - 0.5 * rho .* velocity.^2);
if any(~isfinite(state), "all") || any(rho <= 0) || any(pressure <= 0)
    error("S12:Benchmark:NonphysicalState", ...
        "Periodic SSP-RK3 encountered a nonphysical state.");
end
end

function setParameterValue(workspace, name, value)
parameter = workspace.getVariable(name);
parameter.Value = value;
workspace.assignin(name, parameter);
end

function closeOwnedModels(stepModel, stageModel, stepWasLoaded, stageWasLoaded)
if bdIsLoaded(stepModel)
    set_param(stepModel, "FastRestart", "off");
end
if bdIsLoaded(stageModel)
    set_param(stageModel, "FastRestart", "off");
end
if ~stepWasLoaded && bdIsLoaded(stepModel)
    close_system(stepModel, 0);
end
if ~stageWasLoaded && bdIsLoaded(stageModel)
    close_system(stageModel, 0);
end
end
