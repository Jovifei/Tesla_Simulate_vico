function result = s12_radiation_pp_characteristic_step(state, gamma, dx, dt, options)
%S12_RADIATION_PP_CHARACTERISTIC_STEP One frozen PP step with radiation ghost.
arguments
    state (3,:) double
    gamma (1,1) double {mustBeFinite, mustBeGreaterThan(gamma, 1)}
    dx (1,1) double {mustBeFinite, mustBeGreaterThan(dx, 0)}
    dt (1,1) double {mustBeFinite, mustBeGreaterThan(dt, 0)}
    options.Package (1,1) struct
    options.RadiationState (2,1) double {mustBeFinite}
    options.AmbientState (3,1) double {mustBeFinite}
    options.AmbientPrimitives (1,1) struct
    options.SmallSignalLimit (1,1) double {mustBeFinite, mustBeGreaterThan(options.SmallSignalLimit, 0)}
    options.Cfl (1,1) double {mustBeFinite, mustBeGreaterThan(options.Cfl, 0)} = 0.45
    options.LeftIncomingPressureStages (1,3) double {mustBeFinite} = zeros(1,3)
end
validatePhysical(state, gamma);
rhoFloor = min(1e-13, min(state(1, :)));
pFloor = min(1e-13, minimumPressure(state, gamma));
root = fileparts(fileparts(fileparts(mfilename("fullpath"))));
benchmarkRoot = fullfile(root, "benchmark");
addedBenchmark = ~any(string(strsplit(path,pathsep)) == benchmarkRoot);
if addedBenchmark, addpath(benchmarkRoot); end
pathCleanup = onCleanup(@() cleanupPath(benchmarkRoot, addedBenchmark));
modelRoot = fullfile(root, "models", "fvm_ref");
stepModel = "s12_euler_fvm_periodic_step_muscl_minmod_pp_ref";
stageModel = "s12_euler_ssprk3_periodic_ref";
stepWasLoaded = bdIsLoaded(stepModel);
stageWasLoaded = bdIsLoaded(stageModel);
load_system(fullfile(modelRoot, stepModel + ".slx"));
load_system(fullfile(modelRoot, stageModel + ".slx"));
cleanup = onCleanup(@() closeOwned(stepModel, stageModel, stepWasLoaded, stageWasLoaded));

[euler0, used0, diagnostics0, outgoing0, residual0] = forwardEuler(stepModel, state, ...
    options.RadiationState, gamma, dx, dt, options, rhoFloor, pFloor, ...
    options.LeftIncomingPressureStages(1));
assertSharedDt(used0, dt);
state1 = combine(stageModel, state, euler0, 1);
radiation1 = radiationEuler(options.Package, options.RadiationState, outgoing0, dt);
validatePhysical(state1, gamma);

[euler1, used1, diagnostics1, outgoing1, residual1] = forwardEuler(stepModel, state1, ...
    radiation1, gamma, dx, dt, options, rhoFloor, pFloor, ...
    options.LeftIncomingPressureStages(2));
assertSharedDt(used1, dt);
state2 = combine(stageModel, state, euler1, 2);
radiation2 = radiationStage2(options.Package, options.RadiationState, radiation1, outgoing1, dt);
validatePhysical(state2, gamma);

[euler2, used2, diagnostics2, outgoing2, residual2] = forwardEuler(stepModel, state2, ...
    radiation2, gamma, dx, dt, options, rhoFloor, pFloor, ...
    options.LeftIncomingPressureStages(3));
assertSharedDt(used2, dt);
state3 = combine(stageModel, state, euler2, 3);
radiation3 = s12_radiation_boundary_ssprk3_state(options.Package, ...
    options.RadiationState, [outgoing0, outgoing1, outgoing2], dt);
validatePhysical(state3, gamma);
stability = s12_radiation_boundary_step_stability(options.Package, dt);
result = struct("final_state", state3, "final_radiation_state", radiation3.final_state, ...
    "stage_radiation_state", [radiation1, radiation2], "stage_dt_s", [used0, used1, used2], ...
    "outgoing_pressure_pa", [outgoing0, outgoing1, outgoing2], ...
    "maximum_radiation_stage_pole_amplification", ...
    stability.maximum_stage_pole_amplification, ...
    "stage_diagnostics", [diagnostics0(:), diagnostics1(:), diagnostics2(:)], ...
    "stage_residual", [residual0(:), residual1(:), residual2(:)], ...
    "boundary_id", "radiation_impedance_state_space.v1", ...
    "rho_floor", rhoFloor, "p_floor", pFloor);
end

function [physicalNext, usedDt, diagnostics, outgoing, residual] = forwardEuler(modelName, physical, radiationState, gamma, dx, dt, options, rhoFloor, pFloor, leftIncomingPressure)
[padded, outgoing] = paddedState(physical, radiationState, gamma, options, leftIncomingPressure);
workspace = get_param(modelName, "ModelWorkspace");
setValue(workspace, "S12_FVM_State", padded);
setValue(workspace, "S12_FVM_Gamma", gamma);
setValue(workspace, "S12_FVM_Dx", dx);
setValue(workspace, "S12_FVM_DtRequest", dt);
setValue(workspace, "S12_FVM_CFL", options.Cfl);
setValue(workspace, "S12_PP_RhoFloor", rhoFloor);
setValue(workspace, "S12_PP_PFloor", pFloor);
set_param(modelName, "SimulationCommand", "update");
output = sim(modelName);
next = squeeze(output.S12_FVMStateNext);
physicalNext = next(:, 3:end-2);
usedDt = output.S12_FVMDtUsed(end);
diagnostics = output.S12_PPStepDiagnostics(end, :);
residual = squeeze(output.S12_FVMConservationResidual);
residual = residual(:).';
end

function [padded, outgoing] = paddedState(state, radiationState, gamma, options, leftIncomingPressure)
if leftIncomingPressure == 0
    left = s12_transient_wave_boundary_state(state(:, 1), options.AmbientState, ...
        gamma, "left", "nonreflecting_reference_boundary");
else
    left = s12_radiation_left_driven_boundary_state(state(:, 1), ...
        options.AmbientState, gamma, leftIncomingPressure, options.SmallSignalLimit);
end
[~, velocity, pressure] = primitives(state(:, end), gamma);
outgoing = 0.5 * ((pressure - options.AmbientPrimitives.pressure_pa) + ...
    options.AmbientPrimitives.density_kg_m3 * options.AmbientPrimitives.sound_speed_mps * velocity);
right = s12_radiation_boundary_stage(options.Package, radiationState, outgoing, ...
    options.AmbientPrimitives, gamma, options.SmallSignalLimit);
rightState = conservative(right.boundary_density_kg_m3, right.boundary_velocity_mps, ...
    right.boundary_pressure_pa, gamma);
padded = [left.state, left.state, state, rightState, rightState];
end

function value = radiationEuler(package, state, outgoing, dt)
value = state + dt * (package.state_space_A * state + package.state_space_B * outgoing);
end

function value = radiationStage2(package, base, state1, outgoing, dt)
value = 0.75 * base + 0.25 * (state1 + dt * ...
    (package.state_space_A * state1 + package.state_space_B * outgoing));
end

function state = combine(modelName, baseState, eulerState, stageIndex)
workspace = get_param(modelName, "ModelWorkspace");
setValue(workspace, "S12_PRK3_BaseState", baseState);
setValue(workspace, "S12_PRK3_EulerState", eulerState);
setValue(workspace, "S12_PRK3_StageIndex", stageIndex);
output = sim(modelName); state = squeeze(output.S12_PRK3StageState);
end

function setValue(workspace, name, value)
parameter = workspace.getVariable(name);
if isa(parameter, "Simulink.Parameter"), parameter.Value = value; workspace.assignin(name, parameter); else, workspace.assignin(name, value); end
end

function cleanupPath(pathName, wasAdded)
if wasAdded, rmpath(pathName); end
end

function assertSharedDt(usedDt, requestedDt)
if abs(usedDt-requestedDt) > 32*eps(max(1,requestedDt))
    error("S12:Radiation:CflClipped", "A frozen PP stage changed the shared radiation dt.");
end
end

function validatePhysical(state, gamma)
if size(state,2) < 3 || any(~isfinite(state),"all") || any(state(1,:)<=0) || minimumPressure(state,gamma)<=0
    error("S12:Radiation:InvalidState", "Radiation PP step is nonphysical.");
end
end

function value = minimumPressure(state,gamma)
[~,~,pressure] = primitives(state,gamma); value = min(pressure);
end

function [rho,velocity,pressure] = primitives(state,gamma)
rho=state(1,:); velocity=state(2,:)./rho; pressure=(gamma-1)*(state(3,:)-0.5*rho.*velocity.^2);
end

function state = conservative(rho,velocity,pressure,gamma)
state=[rho;rho*velocity;pressure/(gamma-1)+0.5*rho*velocity^2];
end

function closeOwned(stepModel,stageModel,stepWasLoaded,stageWasLoaded)
if ~stepWasLoaded && bdIsLoaded(stepModel), close_system(stepModel,0); end
if ~stageWasLoaded && bdIsLoaded(stageModel), close_system(stageModel,0); end
end
