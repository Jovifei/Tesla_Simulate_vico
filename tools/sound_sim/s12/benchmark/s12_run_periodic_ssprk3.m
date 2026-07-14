function result = s12_run_periodic_ssprk3(initialState, gamma, dx, dt, ...
        stepCount, cfl, options)
%S12_RUN_PERIODIC_SSPRK3 Compose SSP-RK3 from the validated periodic step.
arguments
    initialState (3,:) double
    gamma (1,1) double {mustBeGreaterThan(gamma, 1)}
    dx (1,1) double {mustBePositive}
    dt (1,:) double {mustBePositive}
    stepCount (1,:) double {mustBeInteger, mustBeNonnegative}
    cfl (1,1) double {mustBePositive}
    options.Reconstruction (1,1) string {mustBeMember( ...
        options.Reconstruction, ["first_order", "muscl_minmod"])} = "first_order"
end

benchmarkRoot = fileparts(mfilename("fullpath"));
s12Root = fileparts(benchmarkRoot);
modelRoot = fullfile(s12Root, "models", "fvm_ref");
stepModel = periodicStepModel(options.Reconstruction);
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
    stepModel, stageModel, options.Reconstruction);
for runIndex = 2:numel(dt)
    result(runIndex) = runOne(initialState, gamma, dx, dt(runIndex), ...
        stepCount(runIndex), cfl, stepModel, stageModel, options.Reconstruction);
end
for runIndex = 1:numel(result)
    result(runIndex).reconstruction = options.Reconstruction;
end
end

function result = runOne(initialState, gamma, dx, dt, stepCount, cfl, ...
        stepModel, stageModel, reconstruction)
state = initialState;
requestedDt = dt * ones(1, 3 * stepCount);
usedDt = zeros(size(requestedDt));
traceIndex = 0;
qualification = newQualification(reconstruction);
for timeStep = 1:stepCount
    baseState = state;
    qualification = observeReconstruction(qualification, baseState, gamma, reconstruction);
    [eulerState, used] = forwardEuler(stepModel, baseState, ...
        gamma, dx, dt, cfl);
    traceIndex = traceIndex + 1;
    usedDt(traceIndex) = used;
    state1 = combineStage(stageModel, baseState, eulerState, 1);
    validateState(state1, gamma);
    qualification.stage_validation_count = qualification.stage_validation_count + 1;

    qualification = observeReconstruction(qualification, state1, gamma, reconstruction);
    [eulerState, used] = forwardEuler(stepModel, state1, ...
        gamma, dx, dt, cfl);
    traceIndex = traceIndex + 1;
    usedDt(traceIndex) = used;
    state2 = combineStage(stageModel, baseState, eulerState, 2);
    validateState(state2, gamma);
    qualification.stage_validation_count = qualification.stage_validation_count + 1;

    qualification = observeReconstruction(qualification, state2, gamma, reconstruction);
    [eulerState, used] = forwardEuler(stepModel, state2, ...
        gamma, dx, dt, cfl);
    traceIndex = traceIndex + 1;
    usedDt(traceIndex) = used;
    state = combineStage(stageModel, baseState, eulerState, 3);
    validateState(state, gamma);
    qualification.stage_validation_count = qualification.stage_validation_count + 1;
end

dtTolerance = 32 * eps(max(1, dt));
if any(abs(usedDt - requestedDt) > dtTolerance)
    error("S12:Benchmark:CflClipped", ...
        "A requested SSP-RK3 stage dt was clipped by the CFL limiter.");
end
qualification.limited_cell_fraction = qualification.limited_cell_count / ...
    max(qualification.sampled_cell_count, 1);

result = struct( ...
    "final_state", state, ...
    "requested_dt", requestedDt, ...
    "used_dt", usedDt, ...
    "step_count", stepCount, ...
    "conservation_residual", sum(state - initialState, 2).', ...
    "boundary", "periodic", ...
    "qualification", qualification);
end

function qualification = newQualification(reconstruction)
limiter = "none";
if reconstruction == "muscl_minmod"
    limiter = "minmod";
end
qualification = struct( ...
    "spatial_scheme", reconstruction, ...
    "reconstruction_variables", "primitive_rho_u_p", ...
    "limiter", limiter, ...
    "limiter_activation_count", 0, ...
    "limited_cell_count", 0, ...
    "sampled_cell_count", 0, ...
    "limited_cell_fraction", 0, ...
    "minimum_reconstructed_density", inf, ...
    "minimum_reconstructed_pressure", inf, ...
    "invalid_reconstruction_count", 0, ...
    "stage_validation_count", 0, ...
    "invalid_stage_count", 0, ...
    "end_time_clipping_count", 0, ...
    "clipping_count", 0, ...
    "flux_fallback_count", 0, ...
    "automatic_retry_count", 0, ...
    "cfl_changed", false);
end

function qualification = observeReconstruction(qualification, state, gamma, reconstruction)
diagnostics = s12_reconstruction_diagnostics(state, gamma, reconstruction);
if diagnostics.invalid_reconstruction_count ~= 0
    error("S12:Benchmark:InvalidReconstruction", ...
        "Periodic SSP-RK3 encountered a nonphysical reconstructed interface.");
end
qualification.minimum_reconstructed_density = min( ...
    qualification.minimum_reconstructed_density, diagnostics.minimum_reconstructed_density);
qualification.minimum_reconstructed_pressure = min( ...
    qualification.minimum_reconstructed_pressure, diagnostics.minimum_reconstructed_pressure);
qualification.invalid_reconstruction_count = qualification.invalid_reconstruction_count + ...
    diagnostics.invalid_reconstruction_count;
qualification.limiter_activation_count = qualification.limiter_activation_count + ...
    diagnostics.limiter_activation_count;
qualification.limited_cell_count = qualification.limited_cell_count + ...
    diagnostics.limited_cell_count;
qualification.sampled_cell_count = qualification.sampled_cell_count + ...
    diagnostics.sampled_cell_count;
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

function modelName = periodicStepModel(reconstruction)
switch reconstruction
    case "first_order"
        modelName = "s12_euler_fvm_periodic_step_ref";
    case "muscl_minmod"
        modelName = "s12_euler_fvm_periodic_step_muscl_minmod_ref";
end
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
