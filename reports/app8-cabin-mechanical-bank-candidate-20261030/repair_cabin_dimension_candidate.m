function receipt = repair_cabin_dimension_candidate()
% Repair and verify one isolated candidate without touching historical models.
lab = fileparts(mfilename('fullpath'));
source = fullfile(lab,'isolated', ...
    'S12_hellcat_cabin_event_bank_20261031_112747_734.slx');
if ~isfile(source)
    error('Cabin:DimensionFix','Saved candidate is missing: %s',source);
end

suffix = char(datetime('now','Format','yyyyMMdd_HHmmss_SSS'));
target = fullfile(lab,'isolated', ...
    ['S12_hellcat_cabin_event_bank_dimfix_' suffix '.slx']);
receiptPath = fullfile(lab,'research-iteration3', ...
    ['dimension-fix-receipt-' suffix '.json']);
if isfile(target) || isfile(receiptPath)
    error('Cabin:OutputExists','Dimension-fix output already exists.');
end

copyfile(source,target);
[~,model] = fileparts(target);
root = fileparts(fileparts(lab));
common = fullfile(root,'tools','sound_sim','s12','playground_v12','common');
legacy = fullfile(root,'reports','app8-rumble-mechanics-candidate-20261029');
addpath(lab,common,fullfile(common,'shared_model'),legacy,fileparts(target));
open_system(target);
cleanup = onCleanup(@()closeIfLoaded(model));

% Enforce explicit fixed-size contracts on every isolated MATLAB Function.
setBlock(model,'Hellcat Synthetic Source','mb_source_step(u)','[960 9]');
setBlock(model,'Combustion_Split','mb_split_combustion(u)','[960 2]');
setBlock(model,'Other_Split','mb_split_other(u)','[960 2]');
setBlock(model,'Control_Split','mb_split_control(u)','[960 5]');
setBlock(model,'Combustion_Network_And_Event', ...
    'mb_path_bus_step(u, ''N'')','[960 2]');
setBlock(model,'Pre_Frozen_Split','mb_pre_bus_step(u)','[960 1]');
setBlock(model,'Mechanical_Split','mb_split_modal_bus(u)','[960 1]');
setBlock(model,'Mechanical_Receiver', ...
    'mb_mechanical_mono_step(u, ''N'', 1)','[960 1]');

% Normalize the model-reference output before the visible post-Frozen Sum.
normalizerName = 'Frozen_Column_Normalize';
normalizer = find_system(model,'SearchDepth',1,'Name',normalizerName);
if isempty(normalizer)
    template = one(model,'Pre_Frozen_Split');
    add_block(template,[model '/' normalizerName]);
    normalizer = {[model '/' normalizerName]};
elseif numel(normalizer) ~= 1
    error('Cabin:DimensionFix','Expected one %s block.',normalizerName);
end
set_param(normalizer{1},'MATLABFcn','mb_column_frame(u)', ...
    'OutputDimensions','[960 1]','Output1D','off');

frozen = one(model,'Frozen 4D-B Radiation Adapter');
sumBlock = one(model,'Post_Frozen_Mechanical_Sum');
sumHandles = get_param(sumBlock,'PortHandles');
oldLine = get_param(sumHandles.Inport(1),'Line');
if oldLine == -1
    error('Cabin:DimensionFix','Frozen output is not connected to Sum input 1.');
end
delete_line(oldLine);
frozenHandles = get_param(frozen,'PortHandles');
normalizerHandles = get_param(normalizer{1},'PortHandles');
add_line(model,frozenHandles.Outport(1),normalizerHandles.Inport(1),'autorouting','on');
add_line(model,normalizerHandles.Outport(1),sumHandles.Inport(1),'autorouting','on');

set_param(model,'SimulationCommand','update');
save_system(model,target);
close_system(model,0);
open_system(target);
set_param(model,'SimulationCommand','update');

% Compile and record the relevant ports before any simulation.
feval(model,[],[],[],'compile');
compileCleanup = onCleanup(@()feval(model,[],[],[],'term'));
names = {'Hellcat Synthetic Source','Combustion_Split','Other_Split', ...
    'Control_Split','Combustion_Network_And_Event','Pre_Frozen_Split', ...
    'Mechanical_Split','Mechanical_Receiver','Frozen_Column_Normalize', ...
    'Post_Frozen_Mechanical_Sum'};
ports = cell(numel(names),1);
for i = 1:numel(names)
    block = one(model,names{i});
    ports{i} = struct('name',names{i},'path',block, ...
        'dimensions',get_param(block,'CompiledPortDimensions'), ...
        'data_types',get_param(block,'CompiledPortDataTypes'), ...
        'sample_time',get_param(block,'CompiledSampleTime'));
end
clear compileCleanup;

% Use five native B frames for a bounded real simulation smoke test.
cfg = jsondecode(fileread(fullfile(lab,'EXPERIMENT_CONTRACT.json')));
loaded = load(cfg.reference.capture_mat,'actualState');
actualState = loaded.actualState(1:5,:);
time = actualState(:,9);
ds = Simulink.SimulationData.Dataset;
signal = timeseries(reshape(actualState.',9,1,5),time,'IsTimeFirst',false);
signal = setinterpmethod(signal,'zoh');
ds = ds.addElement(signal,'Listening Vehicle State');
simIn = Simulink.SimulationInput(model);
simIn = simIn.setExternalInput(ds).setModelParameter( ...
    'StopTime',num2str(time(end),17),'SolverType','Fixed-step', ...
    'Solver','FixedStepDiscrete','FixedStep','0.02', ...
    'SaveOutput','on','OutputSaveName','yout', ...
    'SaveFormat','Dataset','ReturnWorkspaceOutputs','on');
out = sim(simIn);
if isempty(out)
    error('Cabin:DimensionFix','Short simulation returned no output.');
end

receipt = struct('status','DIMENSION_FIX_COMPILE_SHORT_SIM_PASS', ...
    'source_model',source,'target_model',target, ...
    'target_model_sha256',sha(target),'source_model_sha256',sha(source), ...
    'saved_receiver_expression',get_param(one(model,'Mechanical_Receiver'),'MATLABFcn'), ...
    'saved_normalizer_expression',get_param(normalizer{1},'MATLABFcn'), ...
    'compiled_ports',{ports},'short_frames',5, ...
    'short_state_sha256',sha(cfg.reference.capture_mat), ...
    'matlab_version',version,'simulink_version',ver('simulink'));
close_system(model,0);
writeJson(receiptPath,receipt);
clear cleanup;
end

function setBlock(model,name,expression,dimensions)
block = one(model,name);
set_param(block,'MATLABFcn',expression,'OutputDimensions',dimensions,'Output1D','off');
end

function path = one(model,name)
items = find_system(model,'SearchDepth',1,'Name',name);
if numel(items) ~= 1
    error('Cabin:DimensionFix','Expected one block named %s.',name);
end
path = items{1};
end

function closeIfLoaded(model)
if bdIsLoaded(model)
    close_system(model,0);
end
end

function value = sha(path)
fid = fopen(path,'rb');
if fid < 0, error('Cabin:IO','Cannot read %s.',path); end
closer = onCleanup(@()fclose(fid));
digest = java.security.MessageDigest.getInstance('SHA-256');
digest.update(fread(fid,Inf,'*uint8'));
value = string(lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[])));
clear closer;
end

function writeJson(path,value)
fid = fopen(path,'w','n','UTF-8');
if fid < 0, error('Cabin:IO','Cannot write %s.',path); end
closer = onCleanup(@()fclose(fid));
fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));
clear closer;
end
