function run_synthetic_diagnostic_v2(artifactRoot)
% Run the predeclared pulse-envelope variant through the saved M1 path.
lab = string(fileparts(mfilename('fullpath')));
root = fileparts(fileparts(lab));
common = fullfile(root,'tools','sound_sim','s12','playground_v12','common');
shared = fullfile(common,'shared_model');
models = fullfile(artifactRoot,'models');
runRoot = fullfile(artifactRoot,'synthetic_diagnostic_v2');
model = "App8_Synthetic_Diagnostic_V2";
target = fullfile(models,model+".slx");
template = fullfile(models,'App8_Synthetic_Diagnostic.slx');
clone = fullfile(models,'M1_Frozen_Independent.slx');
contractPath = fullfile(lab,'SYNTHETIC-DIAGNOSTIC-V2.json');
v1Path = fullfile(artifactRoot,'synthetic_diagnostic','receipt.json');
v1Analysis = fullfile(artifactRoot,'synthetic_diagnostic','analysis.json');
profile = fullfile(root,'tools','sound_sim','s12','playground_v12','vehicles', ...
    'hellcat_2022_stock','source_profile.json');
frozen = fullfile(shared,'S12_Frozen_Radiation_Adapter_v12.slx');
kernel = fullfile(common,'s12_v12_apply_frozen_radiation_frame.m');
package = fullfile(root,'tools','sound_sim','s12','benchmark','baselines', ...
    'sprint-4d-b','radiation-boundary-package.json');
assert(~isfolder(runRoot) && ~isfile(target) && isfile(template) && isfile(v1Path) && ...
    isfile(v1Analysis),'App8DiagnosticV2:Path','V1 evidence missing or V2 output exists.');
contract = readJson(contractPath);
assert(isequal([contract.conditions.rpm],[750 1200]) && ...
    isequal([contract.conditions.load],[.16 .16]) && contract.sample_rate_hz==48000 && ...
    contract.frame_samples==960 && contract.frame_count==150 && ...
    contract.pulse.rise_fraction_of_90_crank_degrees==.125 && ...
    contract.pulse.decay_fraction_of_90_crank_degrees==.375 && ...
    contract.pulse.per_cylinder_weight==.25 && contract.pulse.dc_mean_per_cylinder==.03125 && ...
    isequal(contract.bank_weights(:).',[.55 .45]) && contract.direct_weight==.5 && ...
    contract.frozen_weight==.5 && contract.renderer_gain==.1 && ...
    contract.peak_max==1 && contract.sample_jump_max==.25 && ...
    contract.frame_jump_max==.0269080675 && ...
    isequal(contract.measurement_window_s(:).',[1 3]), ...
    'App8DiagnosticV2:Contract','V2 contract differs from the fixed implementation.');
v1 = readJson(v1Path);
v1Measurements = readJson(v1Analysis);
protected = [frozen,kernel,package,profile,clone,template,v1Path,v1Analysis,contractPath];
before = arrayfun(@sha,protected);
assert(before(1)=="6079affc48fb9de2cd89e5853967718269427bbb75ddda688879f9c5d81cb644" && ...
    before(2)=="45aac7ea0112d9f9b7d615b09169ec93188f7268ca9f1e178db1d83dc0ebb613" && ...
    before(3)=="0f4b2ca494cd44f79d05968513759578d04e6ab38b1ee37f7621158abb0d2d6f" && ...
    before(4)=="21d30ba69d7eb8d819a079a2e4b442a3aed27d2abf2421ce423656d8912038d9" && ...
    before(6)==string(v1.model_sha256) && ...
    string(v1.status)=="SYNTHETIC_DIAGNOSTIC_SIMULINK_PASS" && ...
    string(v1.qualification)=="SYNTHETIC_DIAGNOSTIC_NOT_FORMAL_M2" && ...
    before(7)==string(v1Measurements.source_receipt_sha256) && ...
    string(v1.source_sha256)==sha(fullfile(lab,'app8_synthetic_cylinder_frame.m')) && ...
    string(v1.runner_sha256)==sha(fullfile(lab,'run_synthetic_diagnostic.m')) && ...
    string(v1.contract_sha256)==sha(fullfile(lab,'SYNTHETIC-DIAGNOSTIC.json')), ...
    'App8DiagnosticV2:Protected','V1 or Frozen dependency identity differs.');
assert(license('test','Simulink'),'App8DiagnosticV2:License','Simulink license unavailable.');
mkdir(runRoot);
oldPath = path;
restorePath = onCleanup(@()path(oldPath));
fileGen = Simulink.fileGenControl('getConfig');
restoreFileGen = onCleanup(@()Simulink.fileGenControl('setConfig','config',fileGen));
Simulink.fileGenControl('set','CacheFolder',fullfile(runRoot,'cache'), ...
    'CodeGenFolder',fullfile(runRoot,'codegen'),'createDir',true);
addpath(lab,common,shared,models);
assert(~bdIsLoaded(model),'App8DiagnosticV2:Loaded','V2 model is already loaded.');
copyfile(template,target);
load_system(target);
modelCleanup = onCleanup(@()closeModel(model));
set_param(model+'/source','MATLABFcn','app8_synthetic_cylinder_v2_frame(u)');
save_system(model,target);
clear modelCleanup
load_system(target);
modelCleanup = onCleanup(@()closeModel(model));
assert(strcmp(get_param(model+'/source','MATLABFcn'),'app8_synthetic_cylinder_v2_frame(u)') && ...
    strcmp(get_param(model+'/frozen','ModelName'),'M1_Frozen_Independent') && ...
    strcmp(get_param(model+'/convex_mix','Gain'),'0.5') && ...
    strcmp(get_param(model+'/renderer','Gain'),'0.1'), ...
    'App8DiagnosticV2:Saved','Saved V2 model does not preserve declared routing.');
clear modelCleanup
modelHash = sha(target);
results = cell(1,2);
for index = 1:2
    condition = contract.conditions(index);
    fprintf('[%d/2] V2 RPM %d load %.2f\n',index,condition.rpm,condition.load);
    [source,cabin,combined,input] = simulate(model,condition.rpm,condition.load,contract);
    assert(hashSignal(input)==string(v1.conditions(index).input_sha256), ...
        'App8DiagnosticV2:Input','V2 input does not match the frozen V1 input.');
    expectedSource = zeros(size(source));
    expectedCabin = zeros(size(cabin));
    context = [];
    for frame = 1:contract.frame_count
        expectedSource(:,:,frame) = app8_synthetic_cylinder_v2_frame(input(:,:,frame));
        [expectedCabin(:,:,frame),context] = ...
            s12_v12_apply_frozen_radiation_frame(expectedSource(:,:,frame),context,48000);
    end
    assert(bitsEqual(source,expectedSource) && bitsEqual(cabin,expectedCabin), ...
        'App8DiagnosticV2:Path','Simulink source or Frozen output differs from direct evaluation.');
    expected = .1.*(.5.*(source+cabin));
    assert(max(abs(combined-expected),[],'all')<1e-14, ...
        'App8DiagnosticV2:Mix','Fixed-mix routing differs.');
    jump = abs(diff(combined(:)));
    peak = max(abs(combined),[],'all');
    frameJump = max(jump(960:960:end));
    assert(peak<contract.peak_max && max(jump)<=contract.sample_jump_max && ...
        frameJump<=contract.frame_jump_max,'App8DiagnosticV2:PCM','Peak or continuity gate failed.');
    folder = fullfile(runRoot,'rpm_'+string(condition.rpm));
    mkdir(folder);
    sourcePath = fullfile(folder,'source.f64le');
    cabinPath = fullfile(folder,'frozen.f64le');
    combinedPath = fullfile(folder,'combined.f64le');
    writeFloat(sourcePath,source);
    writeFloat(cabinPath,cabin);
    writeFloat(combinedPath,combined);
    sourceRendered = .1.*source;
    cabinRendered = .1.*cabin;
    sourceRaw32 = fullfile(folder,'source-rendered.f32le');
    cabinRaw32 = fullfile(folder,'frozen-cabin-rendered.f32le');
    combinedRaw32 = fullfile(folder,'combined-rendered.f32le');
    writeFloat32(sourceRaw32,sourceRendered);
    writeFloat32(cabinRaw32,cabinRendered);
    writeFloat32(combinedRaw32,combined);
    sourceWav = fullfile(folder,'source.wav');
    cabinWav = fullfile(folder,'frozen-cabin.wav');
    writeWav(sourceWav,sourceRendered);
    writeWav(cabinWav,cabinRendered);
    wavePath = fullfile(folder,'combined.wav');
    writeWav(wavePath,combined);
    results{index} = struct('rpm',condition.rpm,'load',condition.load, ...
        'input_sha256',hashSignal(input),'source_path',sourcePath,'source_sha256',sha(sourcePath), ...
        'frozen_path',cabinPath,'frozen_sha256',sha(cabinPath), ...
        'combined_path',combinedPath,'combined_sha256',sha(combinedPath), ...
        'wav_path',wavePath,'wav_sha256',sha(wavePath),'samples',numel(combined), ...
        'source_wav_path',sourceWav,'source_wav_sha256',sha(sourceWav), ...
        'frozen_cabin_wav_path',cabinWav,'frozen_cabin_wav_sha256',sha(cabinWav), ...
        'source_rendered_f32_path',sourceRaw32,'source_rendered_f32_sha256',sha(sourceRaw32), ...
        'frozen_cabin_rendered_f32_path',cabinRaw32,'frozen_cabin_rendered_f32_sha256',sha(cabinRaw32), ...
        'combined_rendered_f32_path',combinedRaw32,'combined_rendered_f32_sha256',sha(combinedRaw32), ...
        'stem_rendering','Each individual stem uses the same fixed 0.1 renderer; combined retains 0.5 weights.', ...
        'peak',peak,'sample_jump_max',max(jump),'frame_jump_max',frameJump, ...
        'actual_input_binding_exact',true,'source_and_frozen_kernel_parity',true);
end
after = arrayfun(@sha,protected);
assert(isequal(before,after) && sha(target)==modelHash, ...
    'App8DiagnosticV2:Protected','A protected dependency or saved model changed.');
receipt = struct('status','SYNTHETIC_DIAGNOSTIC_SIMULINK_PASS','version',2, ...
    'qualification','SYNTHETIC_DIAGNOSTIC_NOT_FORMAL_M2', ...
    'limitations','Dimensionless fixed pulses; no measured vehicle or cabin calibration.', ...
    'v1_receipt_sha256',sha(v1Path),'model_path',target,'model_sha256',modelHash, ...
    'runner_sha256',sha(fullfile(lab,'run_synthetic_diagnostic_v2.m')), ...
    'source_sha256',sha(fullfile(lab,'app8_synthetic_cylinder_v2_frame.m')), ...
    'contract_sha256',sha(contractPath),'process_id',feature('getpid'), ...
    'matlab_version',version,'simulink_version',ver('simulink'), ...
    'protected_path',protected,'protected_sha256_before',before,'protected_sha256_after',after, ...
    'conditions',{results},'formal_T1_T4_C0','NOT_RUN','human_device_vehicle','NOT_RUN');
writeJson(fullfile(runRoot,'receipt.json'),receipt);
fprintf('APP8_SYNTHETIC_DIAGNOSTIC_V2_PASS %s\n',runRoot);
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
actual = frames(out.get('diagnostic_inputs').getElement('actual_control').Values,960,4,time);
assert(bitsEqual(actual,input),'App8DiagnosticV2:Input','Actual control packet differs.');
outputs = out.get('diagnostic_outputs');
assert(outputs.numElements==3,'App8DiagnosticV2:Output','Unexpected output count.');
source = frames(outputs.getElement(1).Values,960,1,time);
cabin = frames(outputs.getElement(2).Values,960,1,time);
combined = frames(outputs.getElement(3).Values,960,1,time);
end

function data = frames(signal,rows,columns,time)
assert(numel(signal.Time)==numel(time) && max(abs(signal.Time(:)-time))<1e-10, ...
    'App8DiagnosticV2:Clock','Simulation times differ.');
data = signal.Data;
if signal.IsTimeFirst
    if columns==1, data=reshape(data.',rows,1,numel(time));
    else, data=permute(data,[2 3 1]); end
end
assert(isequal(size(data),[rows columns numel(time)]) && all(isfinite(data),'all'), ...
    'App8DiagnosticV2:Output','Unexpected frame dimensions or values.');
end

function writeFloat(path,data)
assert(~isfile(path),'App8DiagnosticV2:Exists','Output already exists.');
[fid,message] = fopen(path,'wb','ieee-le');
assert(fid>=0,'App8DiagnosticV2:IO','%s',message);
cleanup = onCleanup(@()fclose(fid));
assert(fwrite(fid,data(:),'double')==numel(data),'App8DiagnosticV2:IO','Short write.');
end

function writeFloat32(path,data)
assert(~isfile(path),'App8DiagnosticV2:Exists','Output already exists.');
[fid,message] = fopen(path,'wb','ieee-le');
assert(fid>=0,'App8DiagnosticV2:IO','%s',message);
cleanup = onCleanup(@()fclose(fid));
assert(fwrite(fid,single(data(:)),'single')==numel(data),'App8DiagnosticV2:IO','Short write.');
end

function writeWav(path,data)
assert(~isfile(path) && max(abs(data),[],'all')<1,'App8DiagnosticV2:WAV','Invalid or existing WAV.');
audiowrite(path,data(:),48000,'BitsPerSample',24);
[back,fs] = audioread(path);
assert(fs==48000 && isequal(size(back),[numel(data) 1]) && ...
    max(abs(back-data(:)))<=2^-23+eps,'App8DiagnosticV2:WAV','WAV readback differs from PCM.');
end

function value = hashSignal(data)
digest = java.security.MessageDigest.getInstance('SHA-256');
digest.update(typecast(data(:),'uint8'));
value = digestHex(digest);
end

function value = sha(path)
[fid,message] = fopen(path,'rb');
assert(fid>=0,'App8DiagnosticV2:IO','%s',message);
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
assert(~isfile(path),'App8DiagnosticV2:Exists','Receipt already exists.');
[fid,message] = fopen(path,'w','n','UTF-8');
assert(fid>=0,'App8DiagnosticV2:IO','%s',message);
cleanup = onCleanup(@()fclose(fid));
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end

function closeModel(name)
if bdIsLoaded(name), close_system(name,0); end
end
