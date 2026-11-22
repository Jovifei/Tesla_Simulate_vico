function run_synthetic_diagnostic(artifactRoot)
% Two fixed, dimensionless engineering conditions through the M1 Simulink path.
lab = string(fileparts(mfilename('fullpath')));
root = fileparts(fileparts(lab));
common = fullfile(root,'tools','sound_sim','s12','playground_v12','common');
shared = fullfile(common,'shared_model');
models = fullfile(artifactRoot,'models');
runRoot = fullfile(artifactRoot,'synthetic_diagnostic');
model = "App8_Synthetic_Diagnostic";
modelPath = fullfile(models,model+".slx");
clone = fullfile(models,'M1_Frozen_Independent.slx');
contractPath = fullfile(lab,'SYNTHETIC-DIAGNOSTIC.json');
profile = fullfile(root,'tools','sound_sim','s12','playground_v12','vehicles', ...
    'hellcat_2022_stock','source_profile.json');
frozen = fullfile(shared,'S12_Frozen_Radiation_Adapter_v12.slx');
kernel = fullfile(common,'s12_v12_apply_frozen_radiation_frame.m');
package = fullfile(root,'tools','sound_sim','s12','benchmark','baselines', ...
    'sprint-4d-b','radiation-boundary-package.json');
crossPath = fullfile(artifactRoot,'m1-cross-process-receipt.json');
m1Path = fullfile(artifactRoot,'run_c','receipt.json');
assert(isfolder(models) && isfile(crossPath) && isfile(m1Path) && ...
    ~isfolder(runRoot) && ~isfile(modelPath), ...
    'App8Diagnostic:Path','M1 evidence missing or diagnostic output already exists.');
cross = readJson(crossPath);
m1 = readJson(m1Path);
assert(string(cross.status)=="PASS_FRESH_PROCESS_IDENTICAL" && ...
    sha(m1Path)==string(cross.run_c_receipt_sha256) && ...
    sha(clone)==string(m1.generated_model_sha256(5)), ...
    'App8Diagnostic:M1','M1 receipt or isolated Frozen model differs.');
contract = readJson(contractPath);
assert(string(contract.qualification)=="SYNTHETIC_DIAGNOSTIC_NOT_FORMAL_M2" && ...
    isequal([contract.conditions.rpm],[750 1200]) && ...
    isequal([contract.conditions.load],[.16 .16]) && ...
    contract.sample_rate_hz==48000 && contract.frame_samples==960 && contract.frame_count==150 && ...
    contract.direct_weight==.5 && contract.frozen_weight==.5 && ...
    contract.renderer_gain==.1 && contract.source_gain==1 && ...
    contract.pulse_exponent==16 && isequal(contract.bank_weights(:).',[.55 .45]) && ...
    contract.peak_max==1 && contract.sample_jump_max==.25 && ...
    contract.frame_jump_max==.0269080675 && ...
    isequal(contract.measurement_window_s(:).',[1 3]), ...
    'App8Diagnostic:Contract','Diagnostic contract differs from the fixed implementation.');
protected = [frozen,kernel,package,profile,clone,contractPath,crossPath,m1Path];
before = arrayfun(@sha,protected);
assert(before(1)=="6079affc48fb9de2cd89e5853967718269427bbb75ddda688879f9c5d81cb644" && ...
    before(2)=="45aac7ea0112d9f9b7d615b09169ec93188f7268ca9f1e178db1d83dc0ebb613" && ...
    before(3)=="0f4b2ca494cd44f79d05968513759578d04e6ab38b1ee37f7621158abb0d2d6f" && ...
    before(4)=="21d30ba69d7eb8d819a079a2e4b442a3aed27d2abf2421ce423656d8912038d9", ...
    'App8Diagnostic:Dependency','Frozen or synthetic profile identity differs.');
assert(license('test','Simulink'),'App8Diagnostic:License','Simulink license unavailable.');
mkdir(runRoot);
oldPath = path;
restorePath = onCleanup(@()path(oldPath));
fileGen = Simulink.fileGenControl('getConfig');
restoreFileGen = onCleanup(@()Simulink.fileGenControl('setConfig','config',fileGen));
Simulink.fileGenControl('set','CacheFolder',fullfile(runRoot,'cache'), ...
    'CodeGenFolder',fullfile(runRoot,'codegen'),'createDir',true);
addpath(lab,common,shared,models);
assert(~bdIsLoaded(model) && ~bdIsLoaded('S12_Frozen_Radiation_Adapter_v12'), ...
    'App8Diagnostic:Loaded','A model required for this test is already loaded.');
buildModel(model,modelPath,frozen);
modelHash = sha(modelPath);
closeModels = onCleanup(@()closeModel(model));
results = cell(1,2);
for index = 1:2
    condition = contract.conditions(index);
    fprintf('[%d/2] Synthetic RPM %d load %.2f\n',index,condition.rpm,condition.load);
    [source,cabin,combined,input] = simulate(model,condition.rpm,condition.load,contract);
    expectedSource = zeros(size(source));
    expectedCabin = zeros(size(cabin));
    context = [];
    for frame = 1:contract.frame_count
        expectedSource(:,:,frame) = app8_synthetic_cylinder_frame(input(:,:,frame));
        [expectedCabin(:,:,frame),context] = ...
            s12_v12_apply_frozen_radiation_frame(expectedSource(:,:,frame),context,48000);
    end
    assert(bitsEqual(source,expectedSource) && bitsEqual(cabin,expectedCabin), ...
        'App8Diagnostic:Path','Simulink source or Frozen output differs from direct evaluation.');
    expected = .1.*(.5.*(source+cabin));
    assert(max(abs(combined-expected),[],'all')<1e-14, ...
        'App8Diagnostic:Mix','Actual fixed-mix routing differs.');
    jump = abs(diff(combined(:)));
    peak = max(abs(combined),[],'all');
    frameJump = max(jump(960:960:end));
    assert(peak<contract.peak_max && max(jump)<=contract.sample_jump_max && ...
        frameJump<=contract.frame_jump_max,'App8Diagnostic:PCM','Peak or continuity gate failed.');
    folder = fullfile(runRoot,'rpm_'+string(condition.rpm));
    mkdir(folder);
    sourcePath = fullfile(folder,'source.f64le');
    cabinPath = fullfile(folder,'frozen.f64le');
    combinedPath = fullfile(folder,'combined.f64le');
    writeFloat(sourcePath,source);
    writeFloat(cabinPath,cabin);
    writeFloat(combinedPath,combined);
    wavePath = fullfile(folder,'combined.wav');
    audiowrite(wavePath,combined(:),48000,'BitsPerSample',24);
    [back,fs] = audioread(wavePath);
    assert(fs==48000 && isequal(size(back),[numel(combined) 1]) && ...
        max(abs(back-combined(:)))<=2^-23+eps, ...
        'App8Diagnostic:WAV','WAV readback differs from raw PCM.');
    results{index} = struct('rpm',condition.rpm,'load',condition.load, ...
        'input_sha256',hashSignal(input),'source_path',sourcePath,'source_sha256',sha(sourcePath), ...
        'frozen_path',cabinPath,'frozen_sha256',sha(cabinPath), ...
        'combined_path',combinedPath,'combined_sha256',sha(combinedPath), ...
        'wav_path',wavePath,'wav_sha256',sha(wavePath),'samples',numel(combined), ...
        'peak',peak,'sample_jump_max',max(jump),'frame_jump_max',frameJump, ...
        'actual_input_binding_exact',true,'source_and_frozen_kernel_parity',true);
end
after = arrayfun(@sha,protected);
assert(isequal(before,after) && sha(modelPath)==modelHash, ...
    'App8Diagnostic:Protected','A protected dependency or saved model changed.');
receipt = struct('status','SYNTHETIC_DIAGNOSTIC_SIMULINK_PASS', ...
    'qualification','SYNTHETIC_DIAGNOSTIC_NOT_FORMAL_M2', ...
    'limitations','Dimensionless fixed pulses and Frozen adapter, not measured Hellcat or cabin calibration.', ...
    'm1_receipt_sha256',sha(crossPath),'model_path',modelPath,'model_sha256',modelHash, ...
    'runner_sha256',sha(fullfile(lab,'run_synthetic_diagnostic.m')), ...
    'source_sha256',sha(fullfile(lab,'app8_synthetic_cylinder_frame.m')), ...
    'contract_sha256',sha(contractPath),'process_id',feature('getpid'), ...
    'matlab_version',version,'simulink_version',ver('simulink'), ...
    'protected_path',protected,'protected_sha256_before',before,'protected_sha256_after',after, ...
    'conditions',{results},'formal_T1_T4_C0','NOT_RUN','human_device_vehicle','NOT_RUN');
writeJson(fullfile(runRoot,'receipt.json'),receipt);
fprintf('APP8_SYNTHETIC_DIAGNOSTIC_PASS %s\n',runRoot);
end

function buildModel(model,target,frozen)
load_system(frozen);
cleanupFrozen = onCleanup(@()closeModel('S12_Frozen_Radiation_Adapter_v12'));
new_system(model);
cleanupModel = onCleanup(@()closeModel(model));
set_param(model,'SolverType','Fixed-step','Solver','FixedStepDiscrete','FixedStep','.02');
add_block('simulink/Sources/In1',model+'/control','PortDimensions','[960 4]');
add_block('simulink/Sources/Clock',model+'/clock');
add_block('S12_Frozen_Radiation_Adapter_v12/Frozen 4D-B Radiation Audio Adapter',model+'/source');
set_param(model+'/source','MATLABFcn','app8_synthetic_cylinder_frame(u)', ...
    'OutputDimensions','[960 1]','Output1D','off');
add_block('simulink/Ports & Subsystems/Model',model+'/frozen','ModelName','M1_Frozen_Independent');
add_block('simulink/Math Operations/Sum',model+'/sum','Inputs','++');
add_block('simulink/Math Operations/Gain',model+'/convex_mix','Gain','0.5');
add_block('simulink/Math Operations/Gain',model+'/renderer','Gain','0.1');
for index = 1:3
    add_block('simulink/Sinks/Out1',model+'/out'+string(index),'Port',num2str(index));
end
add_line(model,'control/1','source/1');
add_line(model,'source/1','frozen/1');
add_line(model,'clock/1','frozen/2');
add_line(model,'source/1','sum/1');
add_line(model,'frozen/1','sum/2');
add_line(model,'sum/1','convex_mix/1');
add_line(model,'convex_mix/1','renderer/1');
add_line(model,'source/1','out1/1');
add_line(model,'frozen/1','out2/1');
add_line(model,'renderer/1','out3/1');
save_system(model,target);
clear cleanupModel cleanupFrozen
load_system(target);
cleanupModel = onCleanup(@()closeModel(model));
assert(strcmp(get_param(model+'/source','MATLABFcn'),'app8_synthetic_cylinder_frame(u)') && ...
    strcmp(get_param(model+'/frozen','ModelName'),'M1_Frozen_Independent') && ...
    strcmp(get_param(model+'/convex_mix','Gain'),'0.5') && ...
    strcmp(get_param(model+'/renderer','Gain'),'0.1'), ...
    'App8Diagnostic:Saved','Saved model does not preserve declared routing parameters.');
end

function [source,cabin,combined,input] = simulate(model,rpm,loadValue,contract)
clear app8_m1_independent_radiation_step
load_system(model);
cleanup = onCleanup(@()closeModel(model));
time = (0:contract.frame_count-1)'*.02;
sample = reshape(0:contract.frame_count*960-1,960,1,contract.frame_count);
input = zeros(960,4,contract.frame_count);
input(:,1,:) = mod(sample.*(pi*rpm/(60*48000)),2*pi);
input(:,2,:) = rpm;
input(:,3,:) = loadValue;
input(:,4,:) = sample./48000;
ports = get_param(model+'/control','PortHandles');
set_param(ports.Outport(1),'DataLogging','on','DataLoggingNameMode','Custom', ...
    'DataLoggingName','actual_control');
in = Simulink.SimulationInput(model);
in = in.setModelParameter('StopTime',num2str(time(end),17),'SolverType','Fixed-step', ...
    'Solver','FixedStepDiscrete','FixedStep','.02','SaveOutput','on','OutputSaveName','diagnostic_outputs', ...
    'SaveFormat','Dataset','ReturnWorkspaceOutputs','on','SignalLogging','on','SignalLoggingName','diagnostic_inputs');
signal = timeseries(input,time,'IsTimeFirst',false);
dataset = Simulink.SimulationData.Dataset;
dataset = dataset.addElement(setinterpmethod(signal,'zoh'),'control');
in = in.setExternalInput(dataset);
out = sim(in);
actual = out.get('diagnostic_inputs').getElement('actual_control').Values;
actual = frames(actual,960,4,time);
assert(bitsEqual(actual,input),'App8Diagnostic:Input','Actual control packet differs.');
outputs = out.get('diagnostic_outputs');
assert(outputs.numElements==3,'App8Diagnostic:Output','Unexpected output count.');
source = frames(outputs.getElement(1).Values,960,1,time);
cabin = frames(outputs.getElement(2).Values,960,1,time);
combined = frames(outputs.getElement(3).Values,960,1,time);
end

function data = frames(signal,rows,columns,time)
assert(numel(signal.Time)==numel(time) && max(abs(signal.Time(:)-time))<1e-10, ...
    'App8Diagnostic:Clock','Simulation times differ.');
data = signal.Data;
if signal.IsTimeFirst
    if columns==1, data=reshape(data.',rows,1,numel(time));
    else, data=permute(data,[2 3 1]); end
end
assert(isequal(size(data),[rows columns numel(time)]) && all(isfinite(data),'all'), ...
    'App8Diagnostic:Output','Unexpected frame dimensions or values.');
end

function writeFloat(path,data)
assert(~isfile(path),'App8Diagnostic:Exists','Output already exists.');
[fid,message] = fopen(path,'wb','ieee-le');
assert(fid>=0,'App8Diagnostic:IO','%s',message);
cleanup = onCleanup(@()fclose(fid));
assert(fwrite(fid,data(:),'double')==numel(data),'App8Diagnostic:IO','Short write.');
end

function value = hashSignal(data)
digest = java.security.MessageDigest.getInstance('SHA-256');
digest.update(typecast(data(:),'uint8'));
value = digestHex(digest);
end

function value = sha(path)
[fid,message] = fopen(path,'rb');
assert(fid>=0,'App8Diagnostic:IO','%s',message);
cleanup = onCleanup(@()fclose(fid));
digest = java.security.MessageDigest.getInstance('SHA-256');
digest.update(fread(fid,Inf,'*uint8'));
value = digestHex(digest);
end

function value = digestHex(digest)
value = string(lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[])));
end

function equal = bitsEqual(left,right)
equal = isequal(size(left),size(right)) && isequal(typecast(left(:),'uint64'),typecast(right(:),'uint64'));
end

function value = readJson(path)
value = jsondecode(fileread(path));
end

function writeJson(path,value)
assert(~isfile(path),'App8Diagnostic:Exists','Receipt already exists.');
[fid,message] = fopen(path,'w','n','UTF-8');
assert(fid>=0,'App8Diagnostic:IO','%s',message);
cleanup = onCleanup(@()fclose(fid));
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end

function closeModel(name)
if bdIsLoaded(name), close_system(name,0); end
end
