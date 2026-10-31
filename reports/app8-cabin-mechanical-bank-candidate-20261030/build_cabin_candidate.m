function receipt = build_cabin_candidate()
% Build once, save, cold reload and inspect the actual saved isolated model.
lab=string(fileparts(mfilename('fullpath')));root=fileparts(fileparts(lab));
source=fullfile(root,'reports','app8-rumble-mechanics-candidate-20261029','isolated', ...
    'S12_hellcat_2022_stock_v12_rumble_mechanics.slx');
suffix=char(datetime('now','Format','yyyyMMdd_HHmmss_SSS'));
target=fullfile(lab,'isolated',['S12_hellcat_cabin_event_bank_' suffix '.slx']);
b0Copy=fullfile(lab,'isolated',['S12_hellcat_cabin_B0_reference_' suffix '.slx']);
contract=fullfile(lab,'EXPERIMENT_CONTRACT.json');cfg=jsondecode(fileread(contract));
if isfile(target) || isfile(b0Copy),error('Cabin:BuildExists','Refusing to overwrite an isolated model.');end
if sha(source)~=string(cfg.reference.baseline_model_sha256),error('Cabin:ProtectedHash','Baseline model changed.');end
folder=fileparts(target);if ~isfolder(folder),mkdir(folder);end
common=fullfile(root,'tools','sound_sim','s12','playground_v12','common');
addpath(lab,common,fullfile(common,'shared_model'),folder);
Simulink.fileGenControl('set','CacheFolder',fullfile(lab,'cabin-cache'), ...
    'CodeGenFolder',fullfile(lab,'cabin-codegen'),'createDir',true);
[~,model]=fileparts(target);[~,b0Model]=fileparts(b0Copy);
if bdIsLoaded(model) || bdIsLoaded(b0Model)
    error('Cabin:LoadedModel','An isolated target name is already loaded; preserve its unsaved work.');
end
copyfile(source,target);copyfile(source,b0Copy);
if sha(target)~=sha(source) || sha(b0Copy)~=sha(source)
    error('Cabin:ModelCopy','Isolated copies differ from the protected baseline.');
end
open_system(target);
before=string(model_read(model,'root'));
preShape={struct('op','configure','target','blk_11','params',struct('MATLABFcn','mb_source_step(u)','Output1D','off'))};
preResponse=string(model_edit(model,'root',jsonencode(preShape),'incremental'));
if ~contains(preResponse,'status: ok'),error('Cabin:ModelEdit','Source shape preconfiguration failed: %s',preResponse);end
set_param(model,'SimulationCommand','update');
ops={};
ops=[ops addBlock('combustion','Combustion_Split') addBlock('other','Other_Split') ...
    addBlock('control','Control_Split') addBlock('join','Source_Branch_Join') ...
    addBlock('path','Combustion_Network_And_Event') addBlock('pre','Pre_Frozen_Split') ...
    addBlock('modal','Mechanical_Split') addBlock('receiver','Mechanical_Receiver') ...
    addBlock('mix','Post_Frozen_Mechanical_Sum')];
links={
    'blk_11.y1 -> #combustion.u1','blk_11.y1 -> #other.u1','blk_11.y1 -> #control.u1', ...
    '#combustion.y1 -> #join.u1','#other.y1 -> #join.u2','#control.y1 -> #join.u3', ...
    '#join.y1 -> #path.u1','#path.y1 -> #pre.u1','#path.y1 -> #modal.u1', ...
    '#pre.y1 -> blk_12.u1','#modal.y1 -> #receiver.u1','blk_12.y1 -> #mix.u1', ...
    '#receiver.y1 -> #mix.u2','#mix.y1 -> blk_14.u1'};
for i=1:numel(links),ops{end+1}=struct('op','connect','target',links{i});end
response=string(model_edit(model,'root',jsonencode(ops),'incremental'));
if ~contains(response,'status: ok')
    model_read(model,'root');model_check(model,'root','["all"]');
    error('Cabin:ModelEdit','Model edit did not fully succeed: %s',response);
end
% R2026a infers MATLAB Function dimensions only after Output1D is disabled.
shapeOps={struct('op','configure','target','blk_11','params',struct('Output1D','off')), ...
    struct('op','configure','target',createdIds(response).path,'params',struct('Output1D','off')), ...
    struct('op','configure','target',createdIds(response).receiver,'params',struct('Output1D','off'))};
shapeResponse=string(model_edit(model,'root',jsonencode(shapeOps),'incremental'));
if ~contains(shapeResponse,'status: ok'), error('Cabin:ModelEdit','Failed to enable multidimensional ports: %s',shapeResponse); end
set_param(singleBlock(model,'Hellcat Synthetic Source'),'MATLABFcn','mb_source_step(u)','OutputDimensions','[960 9]','Output1D','off');
set_param(singleBlock(model,'Combustion_Split'),'MATLABFcn','mb_split_combustion(u)','OutputDimensions','[960 2]','Output1D','off');
set_param(singleBlock(model,'Other_Split'),'MATLABFcn','mb_split_other(u)','OutputDimensions','[960 2]','Output1D','off');
set_param(singleBlock(model,'Control_Split'),'MATLABFcn','mb_split_control(u)','OutputDimensions','[960 5]','Output1D','off');
set_param(singleBlock(model,'Combustion_Network_And_Event'),'MATLABFcn','mb_path_bus_step(u, ''N'')','OutputDimensions','[960 2]','Output1D','off');
set_param(singleBlock(model,'Pre_Frozen_Split'),'MATLABFcn','mb_pre_bus_step(u)','OutputDimensions','[960 1]','Output1D','off');
set_param(singleBlock(model,'Mechanical_Split'),'MATLABFcn','mb_split_modal_bus(u)','OutputDimensions','[960 1]','Output1D','off');
set_param(singleBlock(model,'Mechanical_Receiver'),'MATLABFcn','mb_mechanical_mono_step(u, ''N'', 1)','OutputDimensions','[960 1]','Output1D','off');
set_param(model,'SimulationCommand','update');
after=string(model_read(model,'root'));
% Explicit save is essential; closing a dirty copy discards all edits.
save_system(model,target);close_system(model,0);open_system(target);
sourceBlock=Simulink.ID.getFullName(model+':11');frozen=Simulink.ID.getFullName(model+':12');
sourceExpr=string(get_param(sourceBlock,'MATLABFcn'));
if sourceExpr~="mb_source_step(u)",error('Cabin:ColdReload','Saved source expression differs.');end
names=["Combustion_Split","Other_Split","Control_Split","Pre_Frozen_Split", ...
    "Mechanical_Split","Combustion_Network_And_Event","Mechanical_Receiver", ...
    "Post_Frozen_Mechanical_Sum","Source_Branch_Join"];
blocks=strings(size(names));
for i=1:numel(names)
    found=find_system(model,'SearchDepth',1,'Name',char(names(i)));
    if numel(found)~=1,error('Cabin:ColdReload','Expected exactly one saved %s.',names(i));end
    blocks(i)=string(found{1});
end
assertSource(blocks(8),1,frozen);assertSource(blocks(8),2,blocks(7));
assertSource(Simulink.ID.getFullName(model+':14'),1,blocks(8));
assertSource(frozen,1,blocks(4));
for i=1:3,assertSource(blocks(i),1,sourceBlock);assertSource(blocks(9),i,blocks(i));end
assertSource(blocks(6),1,blocks(9));assertSource(blocks(4),1,blocks(6));
assertSource(blocks(5),1,blocks(6));assertSource(blocks(7),1,blocks(5));
archive=zipEntries(target);required=["Combustion_Split","Other_Split","Control_Split", ...
    "Pre_Frozen_Split","Mechanical_Split","Post_Frozen_Mechanical_Sum","mb_source_step(u)"];
for i=1:numel(required)
    if ~contains(archive,required(i)),error('Cabin:SavedTopology','SLX ZIP lacks %s.',required(i));end
end
mb_runtime_probe('build',model);probeCleanup=onCleanup(@()mb_runtime_probe('disarm'));
mb_source_step('reset');mb_path_step('reset');mb_receiver_step('reset');
set_param(model,'SimulationCommand','update');
mb_source_step('reset');mb_path_step('reset');mb_receiver_step('reset');
feval(model,[],[],[],'compile');compileCleanup=onCleanup(@()feval(model,[],[],[],'term'));
compiledNames=["source",names];compiledBlocks=[string(sourceBlock),blocks];compiled=cell(numel(compiledBlocks),1);
for i=1:numel(compiledBlocks)
    compiled{i}=struct('name',compiledNames(i),'path',compiledBlocks(i), ...
        'dimensions',get_param(compiledBlocks(i),'CompiledPortDimensions'), ...
        'data_types',get_param(compiledBlocks(i),'CompiledPortDataTypes'), ...
        'sample_time',get_param(compiledBlocks(i),'CompiledSampleTime'));
end
rootInput=Simulink.ID.getFullName(model+':18');
compiled{end+1}=struct('name','native_state_inport','path',rootInput, ...
    'dimensions',get_param(rootInput,'CompiledPortDimensions'), ...
    'data_types',get_param(rootInput,'CompiledPortDataTypes'), ...
    'sample_time',get_param(rootInput,'CompiledSampleTime'));
clear compileCleanup;
clear probeCleanup;
check=string(model_check(model,'root','["all"]'));
if ~contains(check,'status: healthy'),error('Cabin:ModelCheck','%s',check);end
if sha(source)~=string(cfg.reference.baseline_model_sha256),error('Cabin:ProtectedHash','Baseline model changed.');end
receipt=struct('status','COLD_RELOAD_UPDATE_COMPILE_MODEL_CHECK_PASS', ...
    'model',target,'model_sha256',sha(target),'source_sha256',sha(source),'contract_sha256',sha(contract), ...
    'baseline_copy',b0Copy,'baseline_copy_sha256',sha(b0Copy), ...
    'saved_source_expression',sourceExpr,'saved_blocks',names,'before_model_read',before, ...
    'compiled_ports',{compiled}, ...
    'after_model_read',after,'cold_model_read',string(model_read(model,'root')),'model_check',check, ...
    'matlab_version',version,'simulink_version',ver('simulink'));
close_system(model,0);
writeNewJson(fullfile(lab,'cabin-build-receipt.json'),receipt);
end

function operations=addBlock(ref,name)
types=struct('combustion','MATLABFcn','other','MATLABFcn','control','MATLABFcn','join','Matrix Concatenate', ...
    'path','MATLABFcn','pre','MATLABFcn','modal','MATLABFcn','receiver','MATLABFcn','mix','Sum');
if strcmp(types.(ref),'Selector'),operations={struct('op','add_block','type','Selector','name',name,'ref',ref)};
elseif strcmp(types.(ref),'MATLABFcn'),operations={struct('op','add_block','type','MATLABFcn','name',name,'ref',ref,'params',struct('Output1D','off'))};
elseif strcmp(types.(ref),'Matrix Concatenate'),operations={struct('op','add_block','type','Matrix Concatenate','name',name,'ref',ref,'params',struct('NumInputs','3','Mode','Multidimensional array','ConcatenateDimension','2'))};
else,operations={struct('op','add_block','type','Sum','name',name,'ref',ref,'params',struct('Inputs','++'))};end
end
function ids=createdIds(response)
names={'combustion','other','control','join','path','pre','modal','receiver','mix'};ids=struct();
for i=1:numel(names)
 token=regexp(char(response),[names{i} ':\s+(blk_\d+)'],'tokens','once');
 if isempty(token),error('Cabin:ModelEdit','Created id missing for %s.',names{i});end
 ids.(names{i})=token{1};
end
end
function assertSource(destination,input,expected)
h=get_param(destination,'PortHandles');line=get_param(h.Inport(input),'Line');
if line==-1 || get_param(line,'SrcBlockHandle')~=get_param(expected,'Handle')
    error('Cabin:SavedTopology','Unexpected source for %s input %d.',destination,input);
end
end
function path=singleBlock(model,name)
blocks=find_system(model,'SearchDepth',1,'Name',name);
if numel(blocks)~=1,error('Cabin:SavedTopology','Expected one %s.',name);end
path=blocks{1};
end
function result=zipEntries(path)
zip=java.util.zip.ZipFile(char(path));cleanup=onCleanup(@()zip.close());
entry=zip.getEntry('simulink/systems/system_root.xml');
if isempty(entry),error('Cabin:SavedTopology','Root system missing in SLX ZIP.');end
stream=zip.getInputStream(entry);reader=java.io.InputStreamReader(stream,'UTF-8');
scanner=java.util.Scanner(reader).useDelimiter('\A');
if scanner.hasNext(),result=string(char(scanner.next()));else,result="";end
scanner.close();
end
function value=sha(path)
fid=fopen(path,'rb');if fid<0,error('Cabin:IO','Cannot read %s.',path);end
cleanup=onCleanup(@()fclose(fid));digest=java.security.MessageDigest.getInstance('SHA-256');
digest.update(fread(fid,Inf,'*uint8'));value=string(lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[])));
end
function writeNewJson(path,value)
if isfile(path),error('Cabin:OutputExists','Receipt already exists: %s',path);end
fid=fopen(path,'w','n','UTF-8');if fid<0,error('Cabin:IO','Cannot write %s.',path);end
cleanup=onCleanup(@()fclose(fid));fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));
end
