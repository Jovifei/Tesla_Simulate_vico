function result = s12_run_transmissive_ssprk3(initialState, gamma, dx, ...
        endTime, cfl, maxSteps)
%S12_RUN_TRANSMISSIVE_SSPRK3 Run the validated long-time SSP-RK3 model.
arguments
    initialState (3,:) double
    gamma (1,1) double {mustBeGreaterThan(gamma, 1)}
    dx (1,1) double {mustBePositive}
    endTime (1,1) double {mustBeNonnegative}
    cfl (1,1) double {mustBePositive}
    maxSteps (1,1) double {mustBeInteger, mustBePositive}
end
benchmarkRoot = fileparts(mfilename("fullpath"));
s12Root = fileparts(benchmarkRoot);
modelRoot = fullfile(s12Root, "models", "fvm_ref");
modelName = "s12_euler_ssprk3_sod_ref";
wasLoaded = bdIsLoaded(modelName);
load_system(fullfile(modelRoot, modelName + ".slx"));
cleanup = onCleanup(@() closeOwnedModel(modelName, wasLoaded));
workspace = get_param(modelName, "ModelWorkspace");
setParameterValue(workspace, "S12_RK3_State", initialState);
setParameterValue(workspace, "S12_RK3_Gamma", gamma);
setParameterValue(workspace, "S12_RK3_Dx", dx);
setParameterValue(workspace, "S12_RK3_EndTime", endTime);
setParameterValue(workspace, "S12_RK3_CFL", cfl);
setParameterValue(workspace, "S12_RK3_MaxSteps", maxSteps);
output = sim(modelName);
result = struct( ...
    "final_state", squeeze(output.S12_RK3FinalState), ...
    "final_time", output.S12_RK3FinalTime(end), ...
    "step_count", output.S12_RK3StepCount(end), ...
    "max_courant", output.S12_RK3MaxCourant(end), ...
    "conservation_residual", reshape( ...
        squeeze(output.S12_RK3ConservationResidual), 1, []), ...
    "boundary", "transmissive");
end

function setParameterValue(workspace, name, value)
parameter = workspace.getVariable(name);
parameter.Value = value;
workspace.assignin(name, parameter);
end

function closeOwnedModel(modelName, wasLoaded)
if ~wasLoaded && bdIsLoaded(modelName)
    close_system(modelName, 0);
end
end
