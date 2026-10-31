function artifact=build_rumble_mechanics_candidate(contractPath,execute)
% Copy the prior isolated listening model and change only its expression.
if nargin<2,execute=false;end
lab=string(fileparts(mfilename('fullpath')));project=fileparts(fileparts(lab));
common=fullfile(project,'tools','sound_sim','s12','playground_v12','common');
source=fullfile(project,'reports','app8-listening-candidate-20261029','isolated','S12_hellcat_2022_stock_v12_listening_candidate.slx');
target=lab+'/isolated/S12_hellcat_2022_stock_v12_rumble_mechanics.slx';
cfg=jsondecode(fileread(contractPath));
if cfg.renderer_gain~=.1 || ~cfg.research_options.enabled || cfg.research_options.cut_minimum~=.35 || ...
        cfg.research_options.whine_scale~=1 || cfg.research_options.induction_scale~=1
    error('S12:Rumble:Build','Frozen baseline contract differs from approved B.');
end
artifact=struct('status','NOT_EXECUTED','source',source,'candidate',target,'source_sha256',sha(source), ...
    'contract_sha256',sha(contractPath),'library_declaration','Inherited registered-root .satk confirmed_none; no new blocks');
if ~execute,return;end
if isfile(target),error('S12:Rumble:Build','Refusing to overwrite model.');end
if ~isfolder(fileparts(target)),mkdir(fileparts(target));end
addpath(common,fullfile(common,'shared_model'),lab,fileparts(target));
[~,old]=fileparts(source);[~,model]=fileparts(target);
open_system(source);save_system(old,target);if bdIsLoaded(model),close_system(model,0);end
open_system(target);artifact.before_model_read=string(model_read(model,'root'));
expression="s12_v12_model_rumble_mechanics_step(u, '"+replace(string(contractPath),"'","''")+"', 'B0')";
ops={struct('op','configure','target','blk_11','params',struct('MATLABFcn',expression))};
response=string(model_edit(model,'root',jsonencode(ops),'incremental'));
if ~contains(response,'status: ok'),error('S12:Rumble:Build','%s',response);end
save_system(model,target);close_system(model,0);open_system(target);
artifact.after_model_read=string(model_read(model,'root'));artifact.model_check=string(model_check(model,'root','["all"]'));
if ~contains(artifact.model_check,'status: healthy'),error('S12:Rumble:Build','%s',artifact.model_check);end
s12_v12_model_rumble_mechanics_step([],contractPath,'reset');
set_param(model,'SimulationCommand','update');[~,artifact.update_evaluations]=s12_v12_model_rumble_mechanics_step([],contractPath,'report');
s12_v12_model_rumble_mechanics_step([],contractPath,'reset');
feval(model,[],[],[],'compile');
ports=find_system(model,'SearchDepth',1,'BlockType','Inport');
if numel(ports)~=1,error('S12:Rumble:Build','Expected one root input.');end
artifact.compiled_state_dimensions=get_param(ports{1},'CompiledPortDimensions');
artifact.compiled_state_type=get_param(ports{1},'CompiledPortDataTypes');artifact.compiled_state_sample_time=get_param(ports{1},'CompiledSampleTime');
feval(model,[],[],[],'term');[~,r]=s12_v12_model_rumble_mechanics_step([],contractPath,'report');
artifact.compile_evaluation_count=r.evaluation_count;artifact.update_evaluations=rmfield(artifact.update_evaluations,{'pre_pressure','cycle_phase','mechanics'});
close_system(model,0);artifact.wrapper_expression=expression;
if sha(source)~=artifact.source_sha256,error('S12:Rumble:Build','Prior model changed.');end
artifact.status='BUILT_COLD_RELOAD_UPDATE_COMPILE_MODEL_CHECK';artifact.candidate_sha256=sha(target);
writeJson(lab+'/build-receipt.json',artifact);
end
function writeJson(path,value)
if isfile(path),error('S12:Rumble:OutputExists','Refusing to overwrite receipt.');end
fid=fopen(path,'w','n','UTF-8');cleanup=onCleanup(@() fclose(fid));fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));
end
function value=sha(path)
fid=fopen(path,'rb');cleanup=onCleanup(@() fclose(fid));d=java.security.MessageDigest.getInstance('SHA-256');
d.update(fread(fid,Inf,'*uint8'));value=string(lower(reshape(dec2hex(typecast(d.digest(),'uint8'),2).',1,[])));
end
