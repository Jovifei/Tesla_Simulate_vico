function result = s12_v12_run_texture_candidate(candidateModel, externalInput, outputRoot, execute)
%S12_V12_RUN_TEXTURE_CANDIDATE Controlled candidate SimulationInput runner.
% execute=false is the safe default; true requires an existing MATLAB session.

if nargin < 4
    execute = false;
end
if ~isstruct(externalInput) || ~isfield(externalInput, "texture_residual") || ...
        ~isfield(externalInput, "texture_weight")
    error("S12:EngineSoundV12:CandidateRun", "External texture input is incomplete.");
end
if ~isfile(candidateModel)
    error("S12:EngineSoundV12:CandidateRun", "Candidate model is missing.");
end
if strlength(string(outputRoot)) == 0
    error("S12:EngineSoundV12:CandidateRun", "Output root is required.");
end
if ~execute
    result = struct( ...
        "status", "NOT_EXECUTED", ...
        "candidate_model", string(candidateModel), ...
        "frame_count", size(externalInput.texture_residual, 1), ...
        "state_qualification", "INSUFFICIENT_EVIDENCE", ...
        "purpose", "RESEARCH_ONLY_NOT_PRODUCT_AUDIO");
    return;
end

candidatePath = string(candidateModel);
[candidateFolder, candidateFile, ~] = fileparts(candidatePath);
addpath(candidateFolder);
modelName = string(candidateFile);
in = Simulink.SimulationInput(modelName);
in = in.setModelParameter("StopTime", num2str(externalInput.duration_seconds, 17));
in = in.setVariable("texture_residual_frames", externalInput.texture_residual);
in = in.setVariable("texture_weight_frames", externalInput.texture_weight);
out = sim(in);
pcm = out.playground_pcm;
if ~isnumeric(pcm) || any(~isfinite(pcm), "all") || any(abs(pcm) > 1, "all")
    error("S12:EngineSoundV12:CandidateRun", "Candidate PCM failed finite/peak contract.");
end
if ~isfolder(outputRoot)
    mkdir(outputRoot);
end
result = struct( ...
    "status", "SIMULATION_COMPLETED_RESEARCH_ONLY", ...
    "candidate_model", modelName, ...
    "frame_count", size(externalInput.texture_residual, 1), ...
    "pcm_dimensions", size(pcm), ...
    "state_qualification", "INSUFFICIENT_EVIDENCE", ...
    "purpose", "RESEARCH_ONLY_NOT_PRODUCT_AUDIO", ...
    "product_candidate", false);
save(fullfile(outputRoot, "texture_candidate_result.mat"), "result", "pcm", "-v7");
end
