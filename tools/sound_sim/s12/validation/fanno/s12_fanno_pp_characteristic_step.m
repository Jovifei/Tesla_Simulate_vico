function result = s12_fanno_pp_characteristic_step(state, gamma, dx, dt, options)
%S12_FANNO_PP_CHARACTERISTIC_STEP One frozen PP SSP-RK3 step with Fanno ghosts.
arguments
    state (3,:) double
    gamma (1,1) double {mustBeGreaterThan(gamma, 1)}
    dx (1,1) double {mustBePositive}
    dt (1,1) double {mustBePositive}
    options.GasConstant (1,1) double {mustBePositive}
    options.InletStaticPressure (1,1) double {mustBePositive}
    options.InletStaticTemperature (1,1) double {mustBePositive}
    options.OutletMassFlux (1,1) double {mustBePositive}
    options.Cfl (1,1) double {mustBePositive} = 0.45
end
validatePhysical(state, gamma);
rhoFloor = min(1e-13, min(state(1, :)));
pFloor = min(1e-13, minimumPressure(state, gamma));
modelRoot = fullfile(fileparts(fileparts(fileparts(mfilename("fullpath")))), ...
    "models", "fvm_ref");
stepModel = "s12_euler_fvm_periodic_step_muscl_minmod_pp_ref";
stageModel = "s12_euler_ssprk3_periodic_ref";
stepWasLoaded = bdIsLoaded(stepModel);
stageWasLoaded = bdIsLoaded(stageModel);
load_system(fullfile(modelRoot, stepModel + ".slx"));
load_system(fullfile(modelRoot, stageModel + ".slx"));
cleanup = onCleanup(@() closeOwned(stepModel, stageModel, ...
    stepWasLoaded, stageWasLoaded));

[euler0, used0, diagnostics0] = forwardEuler(stepModel, state, gamma, dx, ...
    dt, options, rhoFloor, pFloor);
assertSharedDt(used0, dt);
state1 = combine(stageModel, state, euler0, 1);
validatePhysical(state1, gamma);

[euler1, used1, diagnostics1] = forwardEuler(stepModel, state1, gamma, dx, ...
    dt, options, rhoFloor, pFloor);
assertSharedDt(used1, dt);
state2 = combine(stageModel, state, euler1, 2);
validatePhysical(state2, gamma);

[euler2, used2, diagnostics2] = forwardEuler(stepModel, state2, gamma, dx, ...
    dt, options, rhoFloor, pFloor);
assertSharedDt(used2, dt);
state3 = combine(stageModel, state, euler2, 3);
validatePhysical(state3, gamma);
result = struct( ...
    "final_state", state3, ...
    "stage_dt", [used0, used1, used2], ...
    "stage_states", {{state1, state2, state3}}, ...
    "stage_diagnostics", {[diagnostics0(:), diagnostics1(:), diagnostics2(:)]}, ...
    "boundary_id", "subsonic_fanno_validation.v1", ...
    "rho_floor", rhoFloor, ...
    "p_floor", pFloor);
end

function [physicalNext, usedDt, diagnostics] = forwardEuler( ...
        modelName, physical, gamma, dx, dt, options, rhoFloor, pFloor)
padded = paddedState(physical, gamma, options);
workspace = get_param(modelName, "ModelWorkspace");
setValue(workspace, "S12_FVM_State", padded);
setValue(workspace, "S12_FVM_Gamma", gamma);
setValue(workspace, "S12_FVM_Dx", dx);
setValue(workspace, "S12_FVM_DtRequest", dt);
setValue(workspace, "S12_FVM_CFL", options.Cfl);
setValue(workspace, "S12_PP_RhoFloor", rhoFloor);
setValue(workspace, "S12_PP_PFloor", pFloor);
output = sim(modelName);
next = squeeze(output.S12_FVMStateNext);
physicalNext = next(:, 3:end-2);
usedDt = output.S12_FVMDtUsed(end);
diagnostics = output.S12_PPStepDiagnostics(end, :);
end

function padded = paddedState(state, gamma, options)
left = s12_fanno_inlet_pt_boundary(state(:, 1), gamma, ...
    options.GasConstant, options.InletStaticPressure, ...
    options.InletStaticTemperature);
right = s12_fanno_outlet_mdot_boundary(state(:, end), gamma, ...
    options.OutletMassFlux);
padded = [left, left, state, right, right];
end

function state = combine(modelName, baseState, eulerState, stageIndex)
workspace = get_param(modelName, "ModelWorkspace");
setValue(workspace, "S12_PRK3_BaseState", baseState);
setValue(workspace, "S12_PRK3_EulerState", eulerState);
setValue(workspace, "S12_PRK3_StageIndex", stageIndex);
output = sim(modelName);
state = squeeze(output.S12_PRK3StageState);
end

function setValue(workspace, name, value)
parameter = workspace.getVariable(name);
if isa(parameter, "Simulink.Parameter")
    parameter.Value = value;
    workspace.assignin(name, parameter);
else
    workspace.assignin(name, value);
end
end

function assertSharedDt(usedDt, requestedDt)
if abs(usedDt - requestedDt) > 32 * eps(max(1, requestedDt))
    error("S12:Fanno:CflClipped", ...
        "A frozen PP stage changed the shared Fanno Strang dt.");
end
end

function validatePhysical(state, gamma)
if any(~isfinite(state), "all") || any(state(1, :) <= 0) || ...
        minimumPressure(state, gamma) <= 0
    error("S12:Fanno:InvalidState", "Fanno characteristic step is nonphysical.");
end
end

function minimum = minimumPressure(state, gamma)
density = state(1, :);
velocity = state(2, :) ./ density;
minimum = min((gamma - 1) * (state(3, :) - 0.5 * density .* velocity.^2));
end

function closeOwned(stepModel, stageModel, stepWasLoaded, stageWasLoaded)
if ~stepWasLoaded && bdIsLoaded(stepModel)
    close_system(stepModel, 0);
end
if ~stageWasLoaded && bdIsLoaded(stageModel)
    close_system(stageModel, 0);
end
end
