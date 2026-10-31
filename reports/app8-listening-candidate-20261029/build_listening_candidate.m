function artifact=build_listening_candidate(contractPath,execute)
% Copy the stock model; modify only the isolated state source and expression.
if nargin<2, execute=false; end
lab=string(fileparts(mfilename("fullpath"))); project=fileparts(fileparts(lab));
common=fullfile(project,"tools","sound_sim","s12","playground_v12","common");
source=fullfile(common,"..","vehicles","hellcat_2022_stock","S12_hellcat_2022_stock_v12.slx");
target=lab+"/isolated/S12_hellcat_2022_stock_v12_listening_candidate.slx";
cfg=jsondecode(fileread(contractPath));
if cfg.renderer_gain~=.1 || cfg.recorded_pcm_pressure_injection || cfg.engineering_tones_in_listening_output
    error("S12:Listening:Build","Listening isolation contract is invalid.");
end
artifact=struct("status","NOT_EXECUTED","source",source,"candidate",target, ...
    "source_sha256",sha(source),"contract_sha256",sha(contractPath));
if ~execute, return; end
if isfile(target), error("S12:Listening:Build","Refusing to overwrite a candidate."); end
folder=fileparts(target);if ~isfolder(folder),mkdir(folder);end
addpath(common,fullfile(common,"shared_model"),lab,folder);
[~,original]=fileparts(source); [~,model]=fileparts(target);
load_system(source);save_system(original,target);
if bdIsLoaded(model),close_system(model,0);end
load_system(target);
operations={struct("op","disconnect","target","blk_9.y1 -> blk_17.u1"), ...
    struct("op","disconnect","target","blk_17.y1 -> blk_11.u1"), ...
    struct("op","delete","target","blk_17"), ...
    struct("op","add_block","type","In","name","Listening Vehicle State","ref","state", ...
        "params",struct("Port","1","PortDimensions","[9 1]","SampleTime","0.02","OutDataTypeStr","double","Interpolate","off"))};
response=string(model_edit(model,"root",jsonencode(operations),"incremental"));requireOk(response);
token=regexp(response,"state:\s+blk_(\d+)","tokens","once");
if isempty(token),error("S12:Listening:Build","Missing state input block ID.");end
stateId="blk_"+string(token{1});
expression="s12_v12_model_listening_source_step(u, '"+replace(string(contractPath),"'","''")+"', 'C')";
operations={struct("op","connect","target",stateId+".y1 -> blk_11.u1"), ...
    struct("op","configure","target","blk_11","params",struct("MATLABFcn",expression)), ...
    struct("op","configure","target","config:"+model, ...
        "params",struct("StopTime","89.98","SolverType","Fixed-step","Solver","FixedStepDiscrete","FixedStep","0.02"))};
response=string(model_edit(model,"root",jsonencode(operations),"incremental"));requireOk(response);
save_system(model,target);close_system(model,0);load_system(target);
check=string(model_check(model,"root",'["all"]'));
if ~contains(check,"status: healthy"),error("S12:Listening:Build","%s",check);end
set_param(model,"SimulationCommand","update");
feval(model,[],[],[],"compile");
ports=find_system(model,"SearchDepth",1,"BlockType","Inport");
if numel(ports)~=1,error("S12:Listening:Build","Expected exactly one state input.");end
artifact.compiled_state_dimensions=get_param(ports{1},"CompiledPortDimensions");
artifact.compiled_state_type=get_param(ports{1},"CompiledPortDataTypes");
artifact.compiled_state_sample_time=get_param(ports{1},"CompiledSampleTime");
feval(model,[],[],[],"term");close_system(model,0);
if sha(source)~=artifact.source_sha256,error("S12:Listening:Build","Original model changed.");end
artifact.status="BUILT_COMPILED_RESEARCH_ONLY";artifact.candidate_sha256=sha(target);artifact.model_check=check;
fid=fopen(lab+"/build-receipt.json","w","n","UTF-8");fprintf(fid,'%s\n',jsonencode(artifact,PrettyPrint=true));fclose(fid);
end

function requireOk(response)
if ~contains(response,"status: ok"),error("S12:Listening:Build","%s",response);end
end
function value=sha(path)
fid=fopen(path,"rb");cleanup=onCleanup(@() fclose(fid));d=java.security.MessageDigest.getInstance("SHA-256");
d.update(fread(fid,Inf,"*uint8"));value=string(lower(reshape(dec2hex(typecast(d.digest(),"uint8"),2).',1,[])));
end
