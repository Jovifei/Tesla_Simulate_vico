function run_m1_isolation(artifactRoot, runName, buildModels)
% Exercise the original and a private-context Frozen derivative in Simulink.
lab = string(fileparts(mfilename('fullpath')));
root = fileparts(fileparts(lab));
common = fullfile(root,'tools','sound_sim','s12','playground_v12','common');
shared = fullfile(common,'shared_model');
frozen = fullfile(shared,'S12_Frozen_Radiation_Adapter_v12.slx');
adapter = fullfile(common,'s12_v12_model_radiation_step.m');
kernel = fullfile(common,'s12_v12_apply_frozen_radiation_frame.m');
package = fullfile(root,'tools','sound_sim','s12','benchmark','baselines', ...
    'sprint-4d-b','radiation-boundary-package.json');
protected = [frozen,adapter,kernel,package];
before = arrayfun(@sha,protected);
assert(before(1)=="6079affc48fb9de2cd89e5853967718269427bbb75ddda688879f9c5d81cb644" && ...
    before(3)=="45aac7ea0112d9f9b7d615b09169ec93188f7268ca9f1e178db1d83dc0ebb613" && ...
    before(4)=="0f4b2ca494cd44f79d05968513759578d04e6ab38b1ee37f7621158abb0d2d6f", ...
    'App8M1:Dependency','Frozen dependency identity differs.');
assert(license('test','Simulink'),'App8M1:License','Simulink license unavailable.');
artifactRoot = string(artifactRoot);
runName = string(runName);
assert(isfolder(artifactRoot) && isscalar(runName) && ...
    ~isempty(regexp(char(runName),'^[A-Za-z0-9_-]+$','once')), ...
    'App8M1:Path','Invalid artifact root or run name.');
runRoot = fullfile(artifactRoot,runName);
assert(~isfolder(runRoot),'App8M1:Exists','Run output already exists.');
mkdir(runRoot);
models = fullfile(artifactRoot,'models');
originalPath = path;
restorePath = onCleanup(@()path(originalPath));
fileGen = Simulink.fileGenControl('getConfig');
restoreFileGen = onCleanup(@()Simulink.fileGenControl('setConfig','config',fileGen));
Simulink.fileGenControl('set','CacheFolder',fullfile(runRoot,'cache'), ...
    'CodeGenFolder',fullfile(runRoot,'codegen'),'createDir',true);
addpath(lab,common,shared);
assert(strcmpi(which('s12_v12_model_radiation_step'),adapter) && ...
    strcmpi(which('s12_v12_apply_frozen_radiation_frame'),kernel) && ...
    strcmpi(which('S12_Frozen_Radiation_Adapter_v12.slx'),frozen), ...
    'App8M1:Resolution','Unexpected Frozen dependency resolution.');
if buildModels
    assert(~isfolder(models),'App8M1:Exists','Generated model directory already exists.');
    mkdir(models);
    addpath(models);
    buildAll(frozen,models);
else
    assert(isfolder(models),'App8M1:Models','Build the isolated models first.');
    addpath(models);
end
names = ["M1_Single_Original","M1_Single_Private","M1_Dual_Private","M1_Dual_Collision"];
for name = names
    assert(isfile(fullfile(models,name+".slx")) && ~bdIsLoaded(name), ...
        'App8M1:Models','Missing or already loaded model %s.',name);
end
cleanup = onCleanup(@()closeModels(names));
time = (0:5)'*.02;
a = zeros(960,1,numel(time));
b = zeros(size(a));
a(956:960,1,1) = [.25;.5;1;.5;.25];
b(941:945,1,1) = [-.2;-.4;-.8;-.4;-.2];
b(200:204,1,3) = [.1;.2;.4;.2;.1];
z = zeros(size(a));
goldA = kernelFrames(a);
goldB = kernelFrames(b);
assert(norm(goldA(:,1,2))>1e-12 && norm(goldB(:))>1e-12, ...
    'App8M1:Fixture','Fixture does not exercise a nonzero cross-frame tail.');
fprintf('[1/5] Original single-instance A and B\n');
singleA = simulate(names(1),time,{a});
singleB = simulate(names(1),time,{b});
assert(bitsEqual(singleA{1},goldA) && bitsEqual(singleB{1},goldB), ...
    'App8M1:Single','Original Simulink instance differs from its numerical kernel.');
fprintf('[2/5] Private single-instance parity\n');
privateA = simulate(names(2),time,{a});
privateB = simulate(names(2),time,{b});
assert(bitsEqual(privateA{1},goldA) && bitsEqual(privateB{1},goldB), ...
    'App8M1:Private','Private Simulink instance differs from the original kernel.');
fprintf('[3/5] Simultaneous independent instances\n');
positive = simulate(names(3),time,{a,b});
assert(bitsEqual(positive{1},goldA) && bitsEqual(positive{2},goldB), ...
    'App8M1:Isolation','Simultaneous private instances are not independent.');
swapped = simulate(names(3),time,{b,a});
assert(bitsEqual(swapped{1},goldB) && bitsEqual(swapped{2},goldA), ...
    'App8M1:Isolation','Swapped simultaneous inputs changed output state.');
fprintf('[4/5] Shared-persistent negative control\n');
negative = simulate(names(4),time,{a,z});
errorA = max(abs(negative{1}-goldA),[],'all');
leakB = max(abs(negative{2}),[],'all');
assert(errorA>1e-12 || leakB>1e-12, ...
    'App8M1:Negative','Shared-context fixture did not reveal state collision.');
fprintf('[5/5] Reset/repeat and protected-file verification\n');
repeat = simulate(names(3),time,{a,b});
assert(bitsEqual(repeat{1},positive{1}) && bitsEqual(repeat{2},positive{2}), ...
    'App8M1:Reset','Reset/repeat changed the dual-instance outputs.');
after = arrayfun(@sha,protected);
assert(isequal(before,after),'App8M1:Protected','A protected Frozen dependency changed.');
files = strings(1,numel(names)+2);
files(1:4) = fullfile(models,names+".slx");
files(5) = fullfile(models,'M1_Frozen_Independent.slx');
files(6) = fullfile(models,'M1_Frozen_Collision.slx');
hashes = arrayfun(@sha,files);
receipt = struct('status','M1_DUAL_MODEL_REFERENCE_PASS', ...
    'qualification','SYNTHETIC_TEST_NO_HUMAN_OR_DEVICE_ACCEPTANCE', ...
    'matlab_version',version,'simulink_version',ver('simulink'), ...
    'process_id',feature('getpid'),'sample_rate_hz',48000,'frame_samples',960, ...
    'frame_period_s',.02,'time_s',time,'protected_path',protected, ...
    'protected_sha256_before',before,'protected_sha256_after',after, ...
    'generated_models',files,'generated_model_sha256',hashes, ...
    'single_original_matches_kernel',true,'single_private_matches_kernel',true, ...
    'simultaneous_parity',true,'swapped_parity',true,'reset_repeat_parity',true, ...
    'fixture_a_sha256',hashSignal(a),'fixture_b_sha256',hashSignal(b), ...
    'positive_a_sha256',hashSignal(positive{1}),'positive_b_sha256',hashSignal(positive{2}), ...
    'negative_a_sha256',hashSignal(negative{1}),'negative_b_sha256',hashSignal(negative{2}), ...
    'runner_sha256',sha(fullfile(lab,'run_m1_isolation.m')), ...
    'private_wrapper_sha256',sha(fullfile(lab,'app8_m1_independent_radiation_step.m')), ...
    'actual_input_binding_exact',true, ...
    'negative_a_error',errorA,'negative_b_leak',leakB,'negative_detected',true, ...
    'cross_frame_tail_max',max(abs(goldA(:,1,2))), ...
    'limitations','Synthetic fixtures only; cross-process comparison requires two independent receipts.');
writeJson(fullfile(runRoot,'receipt.json'),receipt);
fprintf('APP8_M1_PASS %s\n',runRoot);
end

function buildAll(frozen,models)
original = "S12_Frozen_Radiation_Adapter_v12";
independent = "M1_Frozen_Independent";
collision = "M1_Frozen_Collision";
createClone(frozen,fullfile(models,independent+".slx"),independent, ...
    'app8_m1_independent_radiation_step(u)');
createClone(frozen,fullfile(models,collision+".slx"),collision, ...
    's12_v12_model_radiation_step(u)');
buildTop('M1_Single_Original',models,original,"");
buildTop('M1_Single_Private',models,independent,"");
buildTop('M1_Dual_Private',models,original,independent);
buildTop('M1_Dual_Collision',models,original,collision);
end

function createClone(source,target,name,expression)
assert(~isfile(target) && ~bdIsLoaded(name),'App8M1:Exists','Clone already exists or is loaded.');
copyfile(source,target);
load_system(target);
cleanup = onCleanup(@()closeModel(name));
blocks = find_system(name,'SearchDepth',1,'BlockType','MATLABFcn', ...
    'Name','Frozen 4D-B Radiation Audio Adapter');
assert(numel(blocks)==1,'App8M1:Topology','Frozen adapter block is missing.');
set_param(blocks{1},'MATLABFcn',expression);
save_system(name,target);
clear cleanup
load_system(target);
cleanup = onCleanup(@()closeModel(name));
assert(strcmp(get_param(blocks{1},'MATLABFcn'),expression), ...
    'App8M1:Reload','Saved clone expression differs.');
end

function buildTop(name,models,first,second)
name = string(name);
new_system(name);
cleanup = onCleanup(@()closeModel(name));
set_param(name,'SolverType','Fixed-step','Solver','FixedStepDiscrete','FixedStep','0.02');
add_block('simulink/Sources/Clock',name+'/clock');
references = first;
if strlength(second)>0, references = [first second]; end
for index = 1:numel(references)
    in = "input"+index;
    ref = "frozen"+index;
    out = "output"+index;
    add_block('simulink/Sources/In1',name+'/'+in,'Port',num2str(index),'PortDimensions','960');
    add_block('simulink/Ports & Subsystems/Model',name+'/'+ref,'ModelName',references(index));
    add_block('simulink/Sinks/Out1',name+'/'+out,'Port',num2str(index));
    add_line(name,in+'/1',ref+'/1');
    add_line(name,'clock/1',ref+'/2');
    add_line(name,ref+'/1',out+'/1');
end
save_system(name,fullfile(models,name+'.slx'));
end

function outputs = simulate(model,time,inputs)
clear s12_v12_model_radiation_step app8_m1_independent_radiation_step
load_system(model);
cleanup = onCleanup(@()closeModel(model));
in = Simulink.SimulationInput(model);
in = in.setModelParameter('StopTime',num2str(time(end),17),'SolverType','Fixed-step', ...
    'Solver','FixedStepDiscrete','FixedStep','0.02','SaveOutput','on', ...
    'OutputSaveName','m1_outputs','SaveFormat','Dataset','ReturnWorkspaceOutputs','on', ...
    'SignalLogging','on','SignalLoggingName','m1_inputs');
dataset = Simulink.SimulationData.Dataset;
for index = 1:numel(inputs)
    ports = get_param(model+'/input'+string(index),'PortHandles');
    set_param(ports.Outport(1),'DataLogging','on','DataLoggingNameMode','Custom', ...
        'DataLoggingName',char('input'+string(index)));
    signal = timeseries(inputs{index},time,'IsTimeFirst',false);
    signal = setinterpmethod(signal,'zoh');
    dataset = dataset.addElement(signal,'input'+string(index));
end
in = in.setExternalInput(dataset);
out = sim(in);
result = out.get('m1_outputs');
inputLogs = out.get('m1_inputs');
assert(result.numElements==numel(inputs),'App8M1:Output','Unexpected output count.');
outputs = cell(1,numel(inputs));
for index = 1:numel(inputs)
    actualInput = inputLogs.getElement('input'+string(index)).Values;
    assert(numel(actualInput.Time)==numel(time) && max(abs(actualInput.Time(:)-time))<1e-10, ...
        'App8M1:Clock','Actual input times differ from requested times.');
    inputData = actualInput.Data;
    if actualInput.IsTimeFirst, inputData = reshape(inputData.',960,1,numel(time)); end
    assert(bitsEqual(inputData,inputs{index}),'App8M1:InputBinding','Actual input frames differ.');
    values = result.getElement(index).Values;
    assert(numel(values.Time)==numel(time) && max(abs(values.Time(:)-time))<1e-10, ...
        'App8M1:Clock','Output times differ from requested times.');
    data = values.Data;
    if values.IsTimeFirst, data = reshape(data.',960,1,numel(time)); end
    assert(isequal(size(data),[960 1 numel(time)]) && all(isfinite(data),'all'), ...
        'App8M1:Output','Unexpected output frame shape or values.');
    outputs{index} = data;
end
end

function output = kernelFrames(input)
output = zeros(size(input));
context = [];
for index = 1:size(input,3)
    [output(:,:,index),context] = s12_v12_apply_frozen_radiation_frame(input(:,:,index),context,48000);
end
end

function equal = bitsEqual(left,right)
equal = isequal(size(left),size(right)) && ...
    isequal(typecast(left(:),'uint64'),typecast(right(:),'uint64'));
end

function value = hashSignal(data)
digest = java.security.MessageDigest.getInstance('SHA-256');
digest.update(typecast(data(:),'uint8'));
value = string(lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[])));
end

function value = sha(path)
[fid,message] = fopen(path,'rb');
assert(fid>=0,'App8M1:IO','%s',message);
cleanup = onCleanup(@()fclose(fid));
digest = java.security.MessageDigest.getInstance('SHA-256');
digest.update(fread(fid,Inf,'*uint8'));
value = string(lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[])));
end

function writeJson(path,value)
assert(~isfile(path),'App8M1:Exists','Receipt already exists.');
[fid,message] = fopen(path,'w','n','UTF-8');
assert(fid>=0,'App8M1:IO','%s',message);
cleanup = onCleanup(@()fclose(fid));
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end

function closeModels(names)
for name = names, closeModel(name); end
end

function closeModel(name)
if bdIsLoaded(name), close_system(name,0); end
end
