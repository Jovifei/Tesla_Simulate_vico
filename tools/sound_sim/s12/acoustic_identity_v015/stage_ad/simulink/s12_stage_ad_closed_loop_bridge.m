function receipt = s12_stage_ad_closed_loop_bridge(modelName, requestJsonPath, outputJsonPath)
%S12_STAGE_AD_CLOSED_LOOP_BRIDGE Fail-closed bridge for Stage-AD Simulink work.
%
% Python S12 remains authoritative. This helper only transfers one Stage-AD
% parameter request into a Simulink diagnostic model and captures validated PCM.
% It refuses to silently use the historically-invalid scalar bypass path.
%
% Required model contract:
%   * 48 kHz / 20 ms fixed-step framing (960 samples)
%   * fixed 19x1 configuration vector
%   * 960x1 excitation
%   * 960x1 pressure
%   * 960x2 PCM
%   * To Workspace variable named S12ClosedLoopPCM
%
% Run this inside the existing user-controlled MATLAB session. Do not start
% MATLAB automatically from Python.

arguments
    modelName (1,1) string
    requestJsonPath (1,1) string
    outputJsonPath (1,1) string
end

request = jsondecode(fileread(requestJsonPath));
assert(isfield(request, "parameter_overrides"), "StageAD:MissingOverrides", ...
    "request JSON must contain parameter_overrides");
assert(isfield(request, "iteration"), "StageAD:MissingIteration", ...
    "request JSON must contain iteration");
assert(isfield(request, "scene"), "StageAD:MissingScene", ...
    "request JSON must contain scene");

assignin("base", "S12ClosedLoopRequest", request);
cleanupObj = onCleanup(@() localCleanup(modelName)); %#ok<NASGU>
load_system(modelName);

requiredBlocks = [
    modelName + "/Dashboard"
    modelName + "/Vehicle State"
    modelName + "/Engine Excitation"
    modelName + "/PTR Radiation Tuning Adapter"
    modelName + "/Audio Renderer"
    modelName + "/PCM To Workspace"
];
for i = 1:numel(requiredBlocks)
    assert(getSimulinkBlockHandle(requiredBlocks(i)) > 0, "StageAD:MissingBlock", ...
        "required block missing: %s", requiredBlocks(i));
end

% Update Diagram is a hard gate; the old v0.9 binary failed before simulation.
set_param(modelName, "SimulationCommand", "update");

% Require the dedicated PCM variable; never fall back to arbitrary out1.
pcmBlock = modelName + "/PCM To Workspace";
variableName = string(get_param(pcmBlock, "VariableName"));
assert(variableName == "S12ClosedLoopPCM", "StageAD:WrongWorkspaceVariable", ...
    "PCM To Workspace must write S12ClosedLoopPCM, got %s", variableName);

simOut = sim(modelName, "ReturnWorkspaceOutputs", "on");
assert(simOut.hasVariable("S12ClosedLoopPCM"), "StageAD:MissingPCM", ...
    "simulation did not produce S12ClosedLoopPCM");
pcm = simOut.get("S12ClosedLoopPCM");
if isa(pcm, "timeseries")
    pcm = pcm.Data;
elseif isstruct(pcm) && isfield(pcm, "signals")
    pcm = pcm.signals.values;
end
pcm = double(pcm);
assert(isfinite(sum(pcm, "all")), "StageAD:NonFinitePCM", "PCM contains non-finite values");
assert(size(pcm, 2) == 2, "StageAD:PCMChannels", "PCM must be Nx2 stereo");
assert(mod(size(pcm, 1), 960) == 0, "StageAD:PCMFrame", ...
    "PCM sample count must be a multiple of 960");

receipt = struct();
receipt.schema = "s12.stage_ad.simulink_bridge_receipt.v1";
receipt.model = modelName;
receipt.iteration = request.iteration;
receipt.scene = request.scene;
receipt.frame_count = size(pcm, 1) / 960;
receipt.sample_count = size(pcm, 1);
receipt.channel_count = size(pcm, 2);
receipt.sample_rate_hz = 48000;
receipt.finite = true;
receipt.scope = "diagnostic Simulink mirror only; Python S12 remains authoritative";

fid = fopen(outputJsonPath, "w");
assert(fid >= 0, "StageAD:OutputOpen", "cannot open receipt output");
cleaner = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, "%s\n", jsonencode(receipt, PrettyPrint=true));
assignin("base", "S12ClosedLoopResult", receipt);
end

function localCleanup(modelName)
if bdIsLoaded(modelName)
    close_system(modelName, 0);
end
end
