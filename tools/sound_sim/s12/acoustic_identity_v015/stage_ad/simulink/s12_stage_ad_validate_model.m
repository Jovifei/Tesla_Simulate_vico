function receipt = s12_stage_ad_validate_model(modelName, outputJsonPath)
%S12_STAGE_AD_VALIDATE_MODEL Static/update validation for the S12 Simulink mirror.
%
% This is deliberately fail-closed. It validates the known v0.9 failure modes
% before any Stage-AD closed-loop iteration is allowed to use Simulink output.

arguments
    modelName (1,1) string
    outputJsonPath (1,1) string
end

cleanupObj = onCleanup(@() localCleanup(modelName)); %#ok<NASGU>
load_system(modelName);

errors = strings(0,1);
checks = struct();
checks.model_loaded = true;
checks.solver = string(get_param(modelName, "Solver"));
checks.fixed_step = string(get_param(modelName, "FixedStep"));
if checks.solver ~= "FixedStepDiscrete"
    errors(end+1) = "solver must be FixedStepDiscrete"; %#ok<AGROW>
end
if abs(str2double(checks.fixed_step) - 0.02) > 1e-12
    errors(end+1) = "fixed step must be 0.02 s"; %#ok<AGROW>
end

subsystems = ["Dashboard", "Vehicle State", "Engine Excitation", ...
    "PTR Radiation Tuning Adapter", "Audio Renderer"];
for i = 1:numel(subsystems)
    path = modelName + "/" + subsystems(i);
    if getSimulinkBlockHandle(path) <= 0
        errors(end+1) = "missing subsystem: " + subsystems(i); %#ok<AGROW>
        continue;
    end
    if getSimulinkBlockHandle(path + "/In1") > 0
        errors(end+1) = "forbidden default bypass In1 remains: " + subsystems(i); %#ok<AGROW>
    end
    if getSimulinkBlockHandle(path + "/Out1") > 0
        errors(end+1) = "forbidden default bypass Out1 remains: " + subsystems(i); %#ok<AGROW>
    end
end

pcmBlock = modelName + "/PCM To Workspace";
if getSimulinkBlockHandle(pcmBlock) <= 0
    errors(end+1) = "missing PCM To Workspace"; %#ok<AGROW>
else
    checks.pcm_workspace_variable = string(get_param(pcmBlock, "VariableName"));
    if checks.pcm_workspace_variable ~= "S12ClosedLoopPCM"
        errors(end+1) = "PCM To Workspace variable must be S12ClosedLoopPCM"; %#ok<AGROW>
    end
end

try
    set_param(modelName, "SimulationCommand", "update");
    checks.update_diagram = "PASS";
catch ME
    checks.update_diagram = "FAIL";
    errors(end+1) = "Update Diagram failed: " + string(ME.message); %#ok<AGROW>
end

receipt = struct();
receipt.schema = "s12.stage_ad.simulink_validation.v1";
receipt.model = modelName;
receipt.checks = checks;
receipt.errors = cellstr(errors);
receipt.passed = isempty(errors);
receipt.authority = "Python S12 remains authoritative until simulation/equivalence also pass";

fid = fopen(outputJsonPath, "w");
assert(fid >= 0, "StageAD:OutputOpen", "cannot open validation receipt output");
cleaner = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, "%s\n", jsonencode(receipt, PrettyPrint=true));
end

function localCleanup(modelName)
if bdIsLoaded(modelName)
    close_system(modelName, 0);
end
end
