function receipt = verify_cabin_dimension_variants()
% Run bounded B0/N/M/D/MD probes on the repaired isolated model.
lab = fileparts(mfilename('fullpath'));
modelPath = fullfile(lab,'isolated', ...
    'S12_hellcat_cabin_event_bank_dimfix_20261031_154809_713.slx');
if ~isfile(modelPath)
    error('Cabin:VariantProbe','Repaired model is missing.');
end
cfg = jsondecode(fileread(fullfile(lab,'EXPERIMENT_CONTRACT.json')));
loaded = load(cfg.reference.capture_mat,'actualState');
nFrames = 100;
input = loaded.actualState(1:nFrames,:);
time = input(:,9);

results = struct();
labels = ["B0","N","M","D","MD"];
for i = 1:numel(labels)
    label = labels(i);
    fprintf('CABIN dimension probe %d/%d %s\n',i,numel(labels),label);
    if label == "B0"
        results.B0 = runB0(lab,input,time,nFrames);
    else
        results.(char(label)) = runVariant(modelPath,label,input,time,1,nFrames);
    end
end

receipt = struct('status','ALL_VARIANT_DIMENSION_PROBES_PASS', ...
    'model',modelPath,'frames',nFrames,'results',results, ...
    'matlab_version',version,'simulink_version',ver('simulink'));
outPath = fullfile(lab,'research-iteration3', ...
    ['variant-dimension-receipt-' char(datetime('now','Format','yyyyMMdd_HHmmss_SSS')) '.json']);
writeJson(outPath,receipt);
end

function result = runVariant(modelPath,voice,input,time,k,nFrames)
[folder,model] = fileparts(modelPath);
addpath(folder);
if bdIsLoaded(model), close_system(model,0); end
open_system(modelPath);
cleanup = onCleanup(@()close_system(model,0));

pathBlock = one(model,'Combustion_Network_And_Event');
receiver = one(model,'Mechanical_Receiver');
logSignal(model,'Combustion_Network_And_Event','path_bus');
logSignal(model,'Pre_Frozen_Split','pre_frozen');
logSignal(model,'Mechanical_Split','mechanical_input');
logSignal(model,'Mechanical_Receiver','mechanical_after_frozen');
logSignal(model,'Frozen_Column_Normalize','frozen_column');
logSignal(model,'Post_Frozen_Mechanical_Sum','post_frozen_sum');

mb_source_step('reset');
mb_path_step('reset');
mb_receiver_step('reset');
mb_mechanical_mono_step('reset');
mb_runtime_probe('disarm');

simIn = baseInput(model,input,time,nFrames);
simIn = simIn.setBlockParameter(pathBlock,'MATLABFcn', ...
    "mb_path_bus_step(u, '"+voice+"')");
simIn = simIn.setBlockParameter(receiver,'MATLABFcn', ...
    "mb_mechanical_mono_step(u, '"+voice+"', "+string(num2str(k,17))+")");
out = sim(simIn);
logs = out.get('verify_logs');
if isempty(logs)
    error('Cabin:VariantProbe','Missing verify_logs for %s.',voice);
end

pathFrames = getFrames(logs,'path_bus',960,2,nFrames);
preFrames = getFrames(logs,'pre_frozen',960,1,nFrames);
mechanicalInput = getFrames(logs,'mechanical_input',960,1,nFrames);
mechanical = getFrames(logs,'mechanical_after_frozen',960,1,nFrames);
frozen = getFrames(logs,'frozen_column',960,1,nFrames);
summed = getFrames(logs,'post_frozen_sum',960,1,nFrames);

if ~isequal(preFrames,pathFrames(:,1,:)) || ...
        ~isequal(mechanicalInput,pathFrames(:,2,:))
    error('Cabin:VariantProbe','Path split failed for %s.',voice);
end
expected = zeros(960,1,nFrames);
if voice=="M" || voice=="MD"
    expected = k*mechanicalInput;
end
if max(abs(mechanical-expected),[],'all') > 1e-14
    error('Cabin:VariantProbe','Mechanical route failed for %s.',voice);
end
if max(abs(summed-frozen-mechanical),[],'all') > 1e-13
    error('Cabin:VariantProbe','Post-Frozen Sum failed for %s.',voice);
end
pcm = extractOutput(out);
if any(~isfinite(pcm),'all') || ~any(pcm~=0,'all')
    error('Cabin:VariantProbe','PCM failed for %s.',voice);
end

result = struct('voice',voice,'path_shape',size(pathFrames), ...
    'mechanical_shape',size(mechanical),'frozen_shape',size(frozen), ...
    'sum_shape',size(summed),'mechanical_nonzero',any(mechanical~=0,'all'), ...
    'sum_max_error',max(abs(summed-frozen-mechanical),[],'all'), ...
    'pcm_shape',size(pcm),'pcm_peak',max(abs(pcm),[],'all'));
clear cleanup;
end

function result = runB0(lab,input,time,nFrames)
receipts = dir(fullfile(lab,'cabin-build-receipt.json'));
if isempty(receipts)
    error('Cabin:VariantProbe','Build receipt is missing.');
end
build = jsondecode(fileread(fullfile(lab,receipts(1).name)));
[folder,model] = fileparts(build.baseline_copy);
addpath(folder,lab);
if bdIsLoaded(model), close_system(model,0); end
open_system(build.baseline_copy);
cleanup = onCleanup(@()close_system(model,0));
source = Simulink.ID.getFullName(string(model)+":11");
contract = fullfile(fileparts(fileparts(lab)), ...
    'reports','app8-rumble-mechanics-candidate-20261029','EXPERIMENT_CONTRACT.json');
s12_v12_model_rumble_mechanics_step([],contract,'reset');
mb_b0_step('reset');
simIn = baseInput(model,input,time,nFrames);
simIn = simIn.setBlockParameter(source,'MATLABFcn', ...
    "mb_b0_step(u, '"+replace(contract,"'","''")+"')");
out = sim(simIn);
pcm = extractOutput(out);
if any(~isfinite(pcm),'all') || ~any(pcm~=0,'all')
    error('Cabin:VariantProbe','B0 PCM failed.');
end
result = struct('voice',"B0",'pcm_shape',size(pcm), ...
    'pcm_peak',max(abs(pcm),[],'all'));
clear cleanup;
end

function simIn = baseInput(model,input,time,nFrames)
ds = Simulink.SimulationData.Dataset;
signal = timeseries(reshape(input.',9,1,nFrames),time,'IsTimeFirst',false);
signal = setinterpmethod(signal,'zoh');
ds = ds.addElement(signal,'Listening Vehicle State');
simIn = Simulink.SimulationInput(model);
simIn = simIn.setExternalInput(ds).setModelParameter( ...
    'StopTime',num2str(time(end),17),'SolverType','Fixed-step', ...
    'Solver','FixedStepDiscrete','FixedStep','0.02', ...
    'SaveOutput','on','OutputSaveName','yout', ...
    'SaveFormat','Dataset','ReturnWorkspaceOutputs','on', ...
    'SignalLogging','on','SignalLoggingName','verify_logs');
end

function logSignal(model,name,logName)
block = one(model,name);
h = get_param(block,'PortHandles');
set_param(h.Outport(1),'DataLogging','on', ...
    'DataLoggingNameMode','Custom','DataLoggingName',logName);
end

function frames = getFrames(logs,name,rows,columns,n)
ts = logs.getElement(name).Values;
data = ts.Data;
if size(data,1)==n
    data = permute(data,[2 3 1]);
elseif size(data,2)==n
    data = reshape(data,rows,columns,n);
elseif ndims(data)==3
    data = reshape(data,rows,columns,n);
else
    error('Cabin:VariantProbe','Unexpected log shape for %s.',name);
end
if ~isequal(size(data),[rows columns n]) || any(~isfinite(data),'all')
    error('Cabin:VariantProbe','Invalid log for %s.',name);
end
frames = data;
end

function pcm = extractOutput(out)
node = out.get('yout');
if isempty(node)
    error('Cabin:VariantProbe','Model returned no yout.');
end
if isa(node,'Simulink.SimulationData.Dataset')
    values = node.getElement(1).Values;
elseif isa(node,'timeseries')
    values = node;
else
    values = node;
end
if isa(values,'timeseries')
    pcm = values.Data;
else
    pcm = values;
end
if isempty(pcm)
    error('Cabin:VariantProbe','Model output is empty.');
end
end

function path = one(model,name)
items = find_system(model,'SearchDepth',1,'Name',name);
if numel(items) ~= 1
    error('Cabin:VariantProbe','Expected one block named %s.',name);
end
path = items{1};
end

function writeJson(path,value)
fid = fopen(path,'w','n','UTF-8');
if fid < 0, error('Cabin:IO','Cannot write %s.',path); end
closer = onCleanup(@()fclose(fid));
fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));
clear closer;
end
