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
        options.Reconstruction, ["first_order", "muscl_minmod", ...
        "muscl_minmod_pp"])} = "first_order"
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
result = runSelected(initialState, gamma, dx, dt(1), stepCount(1), cfl, ...
    stepModel, stageModel, options.Reconstruction);
for runIndex = 2:numel(dt)
    result(runIndex) = runSelected(initialState, gamma, dx, dt(runIndex), ...
        stepCount(runIndex), cfl, stepModel, stageModel, options.Reconstruction);
end
for runIndex = 1:numel(result)
    result(runIndex).reconstruction = options.Reconstruction;
end
end

function result = runSelected(initialState, gamma, dx, dt, stepCount, cfl, ...
        stepModel, stageModel, reconstruction)
if reconstruction == "muscl_minmod_pp"
    result = runOnePp(initialState, gamma, dx, dt, stepCount, ...
        stepModel, stageModel);
else
    result = runOne(initialState, gamma, dx, dt, stepCount, cfl, ...
        stepModel, stageModel, reconstruction);
end
end

function result = runOnePp(initialState, gamma, dx, dt, stepCount, ...
        stepModel, stageModel)
cflTarget = 0.45;
cflHardMaximum = 0.5;
maximumRetries = 8;
[initialRho, initialPressure] = densityPressure(initialState, gamma);
rhoFloor = min(1e-13, min(initialRho));
pFloor = min(1e-13, min(initialPressure));
state = initialState;
qualification = newQualification("muscl_minmod_pp");
qualification.rho_floor = rhoFloor;
qualification.p_floor = pFloor;
stageDt = zeros(stepCount, 3);
requestedDt = dt * ones(1, 3 * stepCount);
for timeStep = 1:stepCount
    baseState = state;
    attemptDt = dt;
    accepted = false;
    for attempt = 0:maximumRetries
        alpha0 = stageAlpha(baseState, gamma);
        if attemptDt * alpha0 / dx > cflHardMaximum
            qualification.rejected_step_count = qualification.rejected_step_count + 1;
            qualification.retry_count = qualification.retry_count + 1;
            attemptDt = cflTarget * dx / alpha0;
            continue
        end
        [euler0, used0, diagnostics0] = forwardEulerPp(stepModel, ...
            baseState, gamma, dx, attemptDt, cflTarget, rhoFloor, pFloor);
        assertStageDt(used0, attemptDt);
        state1 = combineStage(stageModel, baseState, euler0, 1);
        validateStateWithFloors(state1, gamma, rhoFloor, pFloor);
        alpha1 = stageAlpha(state1, gamma);
        if attemptDt * alpha1 / dx > cflHardMaximum
            qualification.rejected_step_count = qualification.rejected_step_count + 1;
            qualification.retry_count = qualification.retry_count + 1;
            attemptDt = cflTarget * dx / alpha1;
            continue
        end
        [euler1, used1, diagnostics1] = forwardEulerPp(stepModel, ...
            state1, gamma, dx, attemptDt, cflTarget, rhoFloor, pFloor);
        assertStageDt(used1, attemptDt);
        state2 = combineStage(stageModel, baseState, euler1, 2);
        validateStateWithFloors(state2, gamma, rhoFloor, pFloor);
        alpha2 = stageAlpha(state2, gamma);
        if attemptDt * alpha2 / dx > cflHardMaximum
            qualification.rejected_step_count = qualification.rejected_step_count + 1;
            qualification.retry_count = qualification.retry_count + 1;
            attemptDt = cflTarget * dx / alpha2;
            continue
        end
        [euler2, used2, diagnostics2] = forwardEulerPp(stepModel, ...
            state2, gamma, dx, attemptDt, cflTarget, rhoFloor, pFloor);
        assertStageDt(used2, attemptDt);
        state = combineStage(stageModel, baseState, euler2, 3);
        validateStateWithFloors(state, gamma, rhoFloor, pFloor);
        qualification = accumulatePpDiagnostics(qualification, ...
            diagnostics0, diagnostics1, diagnostics2, ...
            state1, state2, state, gamma);
        stageDt(timeStep, :) = attemptDt;
        accepted = true;
        break
    end
    if ~accepted
        error("S12:Positivity:RetryLimit", ...
            "The PP SSP-RK3 step exceeded the retry limit.");
    end
end
qualification.limited_cell_fraction = qualification.limited_cell_count / ...
    max(qualification.sampled_cell_count, 1);
qualification.reconstruction_pp_limited_cell_fraction = ...
    qualification.reconstruction_pp_limited_cell_count / ...
    max(qualification.reconstruction_pp_sampled_cell_count, 1);
qualification.flux_pp_limited_interface_fraction = ...
    qualification.flux_pp_limited_interface_count / ...
    max(qualification.flux_pp_sampled_interface_count, 1);
qualification.stage_dt = stageDt;
qualification.stage_diagnostics = qualification.stage_validation_count;
result = struct("final_state", state, "requested_dt", requestedDt, ...
    "used_dt", reshape(stageDt.', 1, []), "step_count", stepCount, ...
    "conservation_residual", sum(state - initialState, 2).', ...
    "boundary", "periodic", "qualification", qualification);
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
elseif reconstruction == "muscl_minmod_pp"
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
if reconstruction == "muscl_minmod_pp"
    qualification.positivity_mode = "hu_adams_shu.v1";
    qualification.reconstruction_pp_id = "primitive_slope_scaling.v1";
    qualification.high_order_flux_id = "hllc";
    qualification.low_order_anchor_id = "global_lax_friedrichs.v1";
    qualification.flux_pp_id = "hu_adams_shu.v1";
    qualification.time_integrator = "ssprk3";
    qualification.cfl_target = 0.45;
    qualification.cfl_pp_hard_max = 0.5;
    qualification.reconstruction_pp_activation_count = 0;
    qualification.reconstruction_pp_limited_cell_count = 0;
    qualification.reconstruction_pp_sampled_cell_count = 0;
    qualification.reconstruction_pp_limited_cell_fraction = 0;
    qualification.reconstruction_pp_min_theta = 1;
    qualification.flux_pp_activation_count = 0;
    qualification.flux_pp_limited_interface_count = 0;
    qualification.flux_pp_sampled_interface_count = 0;
    qualification.flux_pp_limited_interface_fraction = 0;
    qualification.flux_pp_min_theta = 1;
    qualification.minimum_anchor_partial_density = inf;
    qualification.minimum_anchor_partial_pressure = inf;
    qualification.minimum_final_partial_density = inf;
    qualification.minimum_final_partial_pressure = inf;
    qualification.alpha_stage_max = 0;
    qualification.maximum_flux_correction_norm = 0;
    qualification.rejected_step_count = 0;
    qualification.retry_count = 0;
    qualification.minimum_stage_density = inf(1, 3);
    qualification.minimum_stage_pressure = inf(1, 3);
    qualification.minimum_cell_density_by_stage = inf(1, 3);
    qualification.minimum_cell_pressure_by_stage = inf(1, 3);
    qualification.minimum_interface_density_by_stage = inf(1, 3);
    qualification.minimum_interface_pressure_by_stage = inf(1, 3);
    qualification.minimum_anchor_partial_density_by_stage = inf(1, 3);
    qualification.minimum_anchor_partial_pressure_by_stage = inf(1, 3);
    qualification.minimum_final_partial_density_by_stage = inf(1, 3);
    qualification.minimum_final_partial_pressure_by_stage = inf(1, 3);
end
end

function qualification = accumulatePpDiagnostics(qualification, d0, d1, d2, ...
        state1, state2, state3, gamma)
for diagnostics = [d0(:), d1(:), d2(:)]
    qualification.limiter_activation_count = ...
        qualification.limiter_activation_count + diagnostics(1);
    qualification.limited_cell_count = qualification.limited_cell_count + diagnostics(2);
    qualification.sampled_cell_count = qualification.sampled_cell_count + diagnostics(3);
    qualification.reconstruction_pp_activation_count = ...
        qualification.reconstruction_pp_activation_count + diagnostics(4);
    qualification.reconstruction_pp_limited_cell_count = ...
        qualification.reconstruction_pp_limited_cell_count + diagnostics(5);
    qualification.reconstruction_pp_sampled_cell_count = ...
        qualification.reconstruction_pp_sampled_cell_count + diagnostics(3);
    qualification.reconstruction_pp_min_theta = min( ...
        qualification.reconstruction_pp_min_theta, diagnostics(6));
    qualification.minimum_reconstructed_density = min( ...
        qualification.minimum_reconstructed_density, diagnostics(7));
    qualification.minimum_reconstructed_pressure = min( ...
        qualification.minimum_reconstructed_pressure, diagnostics(8));
    qualification.invalid_reconstruction_count = ...
        qualification.invalid_reconstruction_count + diagnostics(9);
    qualification.flux_pp_activation_count = ...
        qualification.flux_pp_activation_count + diagnostics(10);
    qualification.flux_pp_limited_interface_count = ...
        qualification.flux_pp_limited_interface_count + diagnostics(11);
    qualification.flux_pp_sampled_interface_count = ...
        qualification.flux_pp_sampled_interface_count + diagnostics(12);
    qualification.flux_pp_min_theta = min( ...
        qualification.flux_pp_min_theta, diagnostics(13));
    qualification.minimum_anchor_partial_density = min( ...
        qualification.minimum_anchor_partial_density, diagnostics(14));
    qualification.minimum_anchor_partial_pressure = min( ...
        qualification.minimum_anchor_partial_pressure, diagnostics(15));
    qualification.minimum_final_partial_density = min( ...
        qualification.minimum_final_partial_density, diagnostics(16));
    qualification.minimum_final_partial_pressure = min( ...
        qualification.minimum_final_partial_pressure, diagnostics(17));
    qualification.alpha_stage_max = max(qualification.alpha_stage_max, diagnostics(18));
    qualification.maximum_flux_correction_norm = max( ...
        qualification.maximum_flux_correction_norm, diagnostics(19));
    qualification.invalid_stage_count = qualification.invalid_stage_count + diagnostics(20);
end
states = {state1, state2, state3};
stageDiagnostics = [d0(:), d1(:), d2(:)];
for stageIndex = 1:3
    [rho, pressure] = densityPressure(states{stageIndex}, gamma);
    qualification.minimum_stage_density(stageIndex) = min( ...
        qualification.minimum_stage_density(stageIndex), min(rho));
    qualification.minimum_stage_pressure(stageIndex) = min( ...
        qualification.minimum_stage_pressure(stageIndex), min(pressure));
    qualification.minimum_cell_density_by_stage(stageIndex) = ...
        qualification.minimum_stage_density(stageIndex);
    qualification.minimum_cell_pressure_by_stage(stageIndex) = ...
        qualification.minimum_stage_pressure(stageIndex);
    qualification.minimum_interface_density_by_stage(stageIndex) = min( ...
        qualification.minimum_interface_density_by_stage(stageIndex), ...
        stageDiagnostics(7, stageIndex));
    qualification.minimum_interface_pressure_by_stage(stageIndex) = min( ...
        qualification.minimum_interface_pressure_by_stage(stageIndex), ...
        stageDiagnostics(8, stageIndex));
    qualification.minimum_anchor_partial_density_by_stage(stageIndex) = min( ...
        qualification.minimum_anchor_partial_density_by_stage(stageIndex), ...
        stageDiagnostics(14, stageIndex));
    qualification.minimum_anchor_partial_pressure_by_stage(stageIndex) = min( ...
        qualification.minimum_anchor_partial_pressure_by_stage(stageIndex), ...
        stageDiagnostics(15, stageIndex));
    qualification.minimum_final_partial_density_by_stage(stageIndex) = min( ...
        qualification.minimum_final_partial_density_by_stage(stageIndex), ...
        stageDiagnostics(16, stageIndex));
    qualification.minimum_final_partial_pressure_by_stage(stageIndex) = min( ...
        qualification.minimum_final_partial_pressure_by_stage(stageIndex), ...
        stageDiagnostics(17, stageIndex));
end
qualification.stage_validation_count = qualification.stage_validation_count + 3;
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

function [stateNext, dtUsed, diagnostics] = forwardEulerPp(modelName, state, ...
        gamma, dx, dt, cfl, rhoFloor, pFloor)
workspace = get_param(modelName, "ModelWorkspace");
setParameterValue(workspace, "S12_FVM_State", state);
setParameterValue(workspace, "S12_FVM_Gamma", gamma);
setParameterValue(workspace, "S12_FVM_Dx", dx);
setParameterValue(workspace, "S12_FVM_DtRequest", dt);
setParameterValue(workspace, "S12_FVM_CFL", cfl);
setParameterValue(workspace, "S12_PP_RhoFloor", rhoFloor);
setParameterValue(workspace, "S12_PP_PFloor", pFloor);
output = sim(modelName);
stateNext = squeeze(output.S12_FVMStateNext);
dtUsed = output.S12_FVMDtUsed(end);
diagnostics = output.S12_PPStepDiagnostics(end, :);
end

function modelName = periodicStepModel(reconstruction)
switch reconstruction
    case "first_order"
        modelName = "s12_euler_fvm_periodic_step_ref";
    case "muscl_minmod"
        modelName = "s12_euler_fvm_periodic_step_muscl_minmod_ref";
    case "muscl_minmod_pp"
        modelName = "s12_euler_fvm_periodic_step_muscl_minmod_pp_ref";
end
end

function assertStageDt(usedDt, requestedDt)
if abs(usedDt - requestedDt) > 32 * eps(max(1, requestedDt))
    error("S12:Benchmark:CflClipped", ...
        "A PP Forward-Euler stage changed the shared SSP step dt.");
end
end

function alpha = stageAlpha(state, gamma)
[rho, pressure] = densityPressure(state, gamma);
velocity = state(2, :) ./ rho;
alpha = max(abs(velocity) + sqrt(gamma * pressure ./ rho));
end

function [rho, pressure] = densityPressure(state, gamma)
rho = state(1, :);
velocity = state(2, :) ./ rho;
pressure = (gamma - 1) * (state(3, :) - 0.5 * rho .* velocity.^2);
end

function validateStateWithFloors(state, gamma, rhoFloor, pFloor)
[rho, pressure] = densityPressure(state, gamma);
if any(~isfinite(state), "all") || any(rho < rhoFloor) || any(pressure < pFloor)
    error("S12:Positivity:InvalidStage", ...
        "A PP SSP-RK3 stage violated the configured floors.");
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
