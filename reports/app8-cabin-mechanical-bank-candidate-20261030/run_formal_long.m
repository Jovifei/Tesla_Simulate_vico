function summary = run_formal_long()
% Run isolated formal candidate modes using the native internal vehicle cycle.
lab = string(fileparts(mfilename('fullpath')));
project = fileparts(fileparts(lab));
common = fullfile(project,'tools','sound_sim','s12','playground_v12','common');
addpath(lab,common,fullfile(common,'shared_model'));
modelPath = fullfile(lab,'isolated-model','S12_hellcat_cabin_formal_candidate.slx');
originalPath = fullfile(project,'tools','sound_sim','s12','playground_v12','vehicles', ...
    'hellcat_2022_stock','S12_hellcat_2022_stock_v12.slx');
stamp = char(datetime('now','Format','yyyyMMdd-HHmmss-SSS'));
runRoot = fullfile(lab,'runs',['formal-long-' stamp]);
mkdir(runRoot);
summary = struct('status','RUNNING','run_root',runRoot,'sample_rate_hz',48000, ...
    'frame_samples',960,'frame_period_s',0.02,'frame_count',4500, ...
    'stop_time_s',89.98,'modes',{{}},'model_sha256',sha(modelPath), ...
    'original_model_sha256',sha(originalPath));
try
    modes = ["B0","N","M","D","MD","MD-repeat","MD-cold"];
    for index = 1:numel(modes)
        label = modes(index);
        fprintf('FORMAL_LONG [%d/%d] %s\n',index,numel(modes),label);
        if label == "B0"
            result = runCase(originalPath,runRoot,'B0',"B0",false);
        elseif label == "MD-cold"
            result = runCase(modelPath,runRoot,label,"MD",true);
        else
            result = runCase(modelPath,runRoot,label,erase(label,"-repeat"),false);
        end
        summary.(matlab.lang.makeValidName(label)) = result;
        summary.modes{end+1} = label;
        writeJson(fullfile(runRoot,['progress-' num2str(index) '.json']),summary);
    end
    summary.status = 'PASS_DIGITAL_RESEARCH_ONLY';
    writeJson(fullfile(runRoot,'run-summary.json'),summary);
catch failure
    summary.status = 'FAILED';
    summary.error_id = string(failure.identifier);
    summary.error = string(failure.message);
    writeJson(fullfile(runRoot,'failure.json'),summary);
    rethrow(failure);
end
end

function result = runCase(modelPath,runRoot,label,mode,coldReload)
[~,modelName] = fileparts(modelPath);
model = char(modelName);
if coldReload && bdIsLoaded(model), close_system(model,0); end
load_system(modelPath);
cleanup = onCleanup(@() close_system(model,0));
source = [model '/Hellcat Synthetic Source'];
cycle = [model '/90 s Synthetic Vehicle Cycle'];
clock = [model '/Simulation Time'];
radiation = [model '/Frozen 4D-B Radiation Adapter'];
renderer = [model '/Stereo Renderer'];
if label == "B0"
    expression = "s12_v12_model_source_step(u, 'hellcat_2022_stock')";
else
    expression = "mb_formal_source_bank_modal_step(u, '" + mode + "')";
end
in = Simulink.SimulationInput(model);
in = in.setModelParameter('StopTime','89.98','SolverType','Fixed-step', ...
    'Solver','FixedStepDiscrete','FixedStep','0.02','SaveOutput','on', ...
    'OutputSaveName','yout','SaveFormat','Dataset','ReturnWorkspaceOutputs','on', ...
    'SignalLogging','on','SignalLoggingName','formal_logs');
in = in.setBlockParameter(source,'MATLABFcn',char(expression));
if string(in.BlockParameters(1).Value) ~= expression
    error('Cabin:FormalExpression','SimulationInput expression mismatch.');
end
logPort(getSourcePort(cycle),'vehicle_state');
logPort(getOutputPort(clock),'actual_clock');
logPort(getOutputPort(source),'source_pressure');
logPort(getOutputPort(radiation),'radiated_pressure');
logPort(getOutputPort(renderer),'renderer_pcm');
runDir = fullfile(runRoot,label);
if isfolder(runDir), error('Cabin:FormalOutputExists','Output exists: %s',runDir); end
mkdir(runDir);
clear mb_formal_source_bank_modal_step;
out = sim(in);
ds = out.yout;
element = ds.getElement(1);
frames = element.Values.Data;
times = element.Values.Time;
if ndims(frames) ~= 3 || size(frames,1) ~= 960 || size(frames,2) ~= 2 || size(frames,3) ~= 4500
    error('Cabin:FormalPCMShape','Unexpected PCM shape %s for %s.',mat2str(size(frames)),label);
end
pcm = reshape(permute(frames,[1 3 2]),[],2);
if numel(times) ~= 4500 || any(abs(times(:)-(0:0.02:89.98)')>1e-10)
    error('Cabin:FormalTime','Unexpected output time grid for %s.',label);
end
if ~isreal(pcm) || any(~isfinite(pcm),'all') || ~any(pcm~=0,'all') || any(abs(pcm)>1,'all')
    error('Cabin:FormalPCM','PCM safety failed for %s.',label);
end
if isprop(out,'logsout')
    logs = out.logsout;
else
    logs = Simulink.SimulationData.Dataset;
end
result = struct('label',label,'mode',mode,'model',modelPath,'model_sha256',sha(modelPath), ...
    'wrapper_expression',expression,'frame_count',4500,'samples_per_channel',size(pcm,1), ...
    'sample_rate_hz',48000,'channels',2,'duration_seconds',90,'last_frame_time_s',times(end), ...
    'pcm_path',fullfile(runDir,'candidate.pcm.f64le'),'wav_path',fullfile(runDir,'candidate.wav'), ...
    'peak',max(abs(pcm),[],'all'),'rms',sqrt(mean(pcm.^2,'all')));
result.binary_pcm = exportBinary(result.pcm_path,pcm);
audiowrite(result.wav_path,pcm,48000,'BitsPerSample',24);
[back,fs] = audioread(result.wav_path); info = audioinfo(result.wav_path);
result.wav_sample_rate=fs; result.wav_bits=info.BitsPerSample;
result.wav_quantization_max_error=max(abs(back-pcm),[],'all');
if fs~=48000 || info.BitsPerSample~=24 || ~isequal(size(back),size(pcm)) || ...
        result.wav_quantization_max_error > 2^-23 + eps
    error('Cabin:FormalWAV','PCM24 readback failed for %s.',label);
end
delta=abs(diff(pcm)); result.maximum_sample_jump=max(delta,[],'all');
result.maximum_frame_jump=max(delta(960:960:end,:),[],'all');
result.pcm_sha256=sha(result.pcm_path); result.wav_sha256=sha(result.wav_path);
if result.maximum_sample_jump>0.25 || result.maximum_frame_jump>0.0269080675
    error('Cabin:FormalContinuity','Continuity gate failed for %s.',label);
end
result.time_path=fullfile(runDir,'time.f64le'); result.time_binary=exportBinary(result.time_path,times);
if logs.numElements > 0
    result.logged_names = strings(logs.numElements,1);
    for k=1:logs.numElements
        entry=logs.getElement(k); result.logged_names(k)=string(entry.Name);
        values=entry.Values.Data; save(fullfile(runDir,[char(entry.Name) '.mat']),'values','-v7.3');
    end
end
save(fullfile(runDir,'capture.mat'),'pcm','frames','times','result','-v7.3');
result.capture_path=fullfile(runDir,'capture.mat'); result.capture_sha256=sha(result.capture_path);
writeJson(fullfile(runDir,'receipt.json'),result);
result.receipt_sha256=sha(fullfile(runDir,'receipt.json'));
end

function port=getSourcePort(block)
h=get_param(block,'PortHandles'); line=get_param(h.Inport(1),'Line'); port=get_param(line,'SrcPortHandle');
end
function port=getOutputPort(block)
h=get_param(block,'PortHandles'); port=h.Outport(1);
end
function logPort(port,name)
set_param(port,'DataLogging','on','DataLoggingNameMode','Custom','DataLoggingName',name);
end
function meta=exportBinary(path,data)
fid=fopen(path,'wb','ieee-le'); if fid<0,error('Cabin:FormalIO','Cannot open %s.',path);end
cleanup=onCleanup(@() fclose(fid)); fwrite(fid,data.','double'); clear cleanup;
meta=struct('path',path,'shape',size(data),'dtype','float64-le','sha256',sha(path));
end
function value=sha(path)
fid=fopen(path,'rb'); if fid<0,error('Cabin:FormalIO','Cannot open %s.',path);end
cleanup=onCleanup(@() fclose(fid)); d=java.security.MessageDigest.getInstance('SHA-256'); d.update(fread(fid,Inf,'*uint8'));
value=string(lower(reshape(dec2hex(typecast(d.digest(),'uint8'),2).',1,[])));
end
function writeJson(path,value)
fid=fopen(path,'w','n','UTF-8'); if fid<0,error('Cabin:FormalIO','Cannot open %s.',path);end
cleanup=onCleanup(@() fclose(fid)); fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));
end
