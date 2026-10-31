function plan = s12_v12_prepare_texture_simulink_candidate(sourceModel, outputModel, execute)
%S12_V12_PREPARE_TEXTURE_SIMULINK_CANDIDATE Copy and wire a research-only model.
arguments
    sourceModel (1,1) string
    outputModel (1,1) string
    execute (1,1) logical = false
end
sourceModel = string(java.io.File(char(sourceModel)).getCanonicalPath());
outputModel = string(java.io.File(char(outputModel)).getCanonicalPath());
if sourceModel == outputModel || ~isfile(sourceModel)
    error("S12:EngineSoundV12:Candidate", "A distinct existing source model is required.");
end
common = fileparts(mfilename("fullpath"));
project = fileparts(fileparts(fileparts(fileparts(fileparts(common)))));
definition = jsondecode(fileread(fullfile(project,"reports", ...
    "simulink-texture-topology-20261028","MODEL_EDIT_PLAN.json")));
plan = struct("status","READY_FOR_EXISTING_SESSION_MODEL_EDIT", ...
    "source_model",sourceModel,"output_model",outputModel, ...
    "source_sha256",fileSha(sourceModel),"contract",s12_v12_texture_simulink_contract(), ...
    "operations",{definition.operations},"mixer_function","s12_v12_model_texture_layers_step", ...
    "qualification","INSUFFICIENT_EVIDENCE_UNTIL_RUNTIME_AND_ACOUSTIC_GATES");
if ~execute, return; end
[folder, model] = fileparts(outputModel);
[~, source] = fileparts(sourceModel);
if isfile(outputModel) || bdIsLoaded(model)
    error("S12:EngineSoundV12:Candidate", "Refusing to overwrite an existing candidate.");
end
if ~isfolder(folder), mkdir(folder); end
addpath(common,fullfile(common,"shared_model"),folder);
load_system(sourceModel);
save_system(source,outputModel);
if bdIsLoaded(model), close_system(model,0); end
load_system(outputModel);
if ~isempty(find_system(model,"SearchDepth",1,"BlockType","Inport"))
    error("S12:EngineSoundV12:Candidate", "Source root input contract changed.");
end
ops = definition.operations;
if isstruct(ops), ops = num2cell(ops); end
isAdd = cellfun(@(op) string(op.op) == "add_block",ops);
created = string(model_edit(model,"root",jsonencode(ops(isAdd)),"incremental"));
requireOk(created);
refs = ["textureBody","textureMechanical","textureBroadband","textureWeights","textureMixer"];
ids = strings(size(refs));
for index = 1:numel(refs)
    token = regexp(created,refs(index)+":\s+blk_(\d+)","tokens","once");
    if isempty(token), error("S12:EngineSoundV12:Candidate","Missing created block ID."); end
    ids(index) = "blk_"+string(token{1});
end
mixPath = Simulink.ID.getFullName(model+":"+extractAfter(ids(5),"blk_"));
root = sfroot;
charts = root.find("-isa","Stateflow.EMChart","Path",mixPath);
if numel(charts) ~= 1, error("S12:EngineSoundV12:Candidate","Mixer chart is missing."); end
% model_edit creates the block; Stateflow's Script API sets its algorithm.
charts.Script = definition.mixerScript;
data = charts.find("-isa","Stateflow.Data");
for index = 1:numel(data)
    data(index).DataType = "double";
    if string(data(index).Name) == "weights"
        data(index).Props.Array.Size = "[1 3]";
    else
        data(index).Props.Array.Size = "[960 1]";
    end
end
connections = ops(~isAdd);
for index = 1:numel(connections)
    for ref = 1:numel(refs)
        connections{index}.target = strrep(connections{index}.target,"#"+refs(ref),ids(ref));
    end
end
requireOk(string(model_edit(model,"root",jsonencode(connections),"incremental")));
save_system(model,outputModel);
close_system(model,0);
load_system(outputModel);
if fileSha(sourceModel) ~= plan.source_sha256
    error("S12:EngineSoundV12:Candidate","Source model SHA changed.");
end
plan.status = "MODEL_CREATED_RESEARCH_ONLY";
plan.candidate_sha256 = fileSha(outputModel);
end

function requireOk(response)
if ~contains(response,"status: ok")
    error("S12:EngineSoundV12:Candidate","model_edit failed: %s",response);
end
end

function value = fileSha(path)
fid = fopen(path,"rb");
cleanup = onCleanup(@() fclose(fid));
bytes = fread(fid,Inf,"*uint8");
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(bytes);
value = string(lower(reshape(dec2hex(typecast(digest.digest(),"uint8"),2).',1,[])));
end
