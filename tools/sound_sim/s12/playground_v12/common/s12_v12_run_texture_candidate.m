function [result, pcm] = s12_v12_run_texture_candidate(candidateModel, externalInput, outputRoot, execute)
%S12_V12_RUN_TEXTURE_CANDIDATE Bind real frame inputs and capture stereo PCM.
if nargin < 4, execute = false; end
pcm = [];
required = ["texture_residual","texture_weight","duration_seconds"];
if ~isstruct(externalInput) || ~isscalar(externalInput) || ~all(isfield(externalInput,required))
    fail("External texture input is incomplete.");
end
legacy = externalInput.texture_residual;
count = size(legacy,1);
if count < 1 || count > 4500 || ~isequal(size(legacy),[count,960]) || ~validNumeric(legacy)
    fail("Legacy texture frame dimensions or samples are invalid.");
end
duration = externalInput.duration_seconds;
if ~validNumeric(duration) || ~isscalar(duration) || abs(duration-count*0.02) > 1e-10 || ...
        (isfield(externalInput,"frame_count") && ~isequal(externalInput.frame_count,count))
    fail("Duration must contain exactly the declared whole frames.");
end
legacyWeight = externalInput.texture_weight;
if ~isequal(size(legacyWeight),[count,1]) || ~validNumeric(legacyWeight) || any(legacyWeight < 0 | legacyWeight > 1,"all")
    fail("Legacy texture weights are invalid.");
end
hasLayers = isfield(externalInput,"texture_layers");
hasWeights = isfield(externalInput,"texture_layer_weights");
if hasLayers ~= hasWeights, fail("Layered input fields must be supplied together."); end
if hasLayers
    layers = externalInput.texture_layers;
    weights = externalInput.texture_layer_weights;
else
    layers = zeros(count,960,3,"single");
    layers(:,:,1) = legacy;
    weights = [legacyWeight,zeros(count,2)];
end
if ~isequal(size(layers),[count,960,3]) || ~validNumeric(layers) || any(abs(layers)>1,"all") || ...
        ~isequal(size(weights),[count,3]) || ~validNumeric(weights) || any(weights<0 | weights>1,"all")
    fail("Layered texture input dimensions, samples or weights are invalid.");
end
if (isfield(externalInput,"sample_rate_hz") && externalInput.sample_rate_hz ~= 48000) || ...
        (isfield(externalInput,"frame_samples") && externalInput.frame_samples ~= 960)
    fail("Only 48 kHz frames of 960 samples are supported.");
end
candidateModel = string(candidateModel);
outputRoot = string(outputRoot);
if ~isscalar(candidateModel) || ~isfile(candidateModel), fail("Candidate model is missing."); end
if ~isscalar(outputRoot) || strlength(outputRoot)==0, fail("Output root is required."); end
result = struct("status","NOT_EXECUTED","candidate_model",candidateModel, ...
    "frame_count",count,"layered_input",hasLayers,"state_qualification","INSUFFICIENT_EVIDENCE", ...
    "purpose","RESEARCH_ONLY_NOT_PRODUCT_AUDIO","product_candidate",false);
if ~execute, return; end
if isfolder(outputRoot) || isfile(outputRoot), fail("Refusing to overwrite an existing result."); end
mkdir(outputRoot);
[candidateFolder,modelName] = fileparts(candidateModel);
common = fileparts(mfilename("fullpath"));
addpath(candidateFolder,common,fullfile(common,"shared_model"));
load_system(candidateModel);
cleanup = onCleanup(@() close_system(modelName,0));
clear s12_v12_model_texture_layers_step
time = (0:count-1)'*0.02;
in = Simulink.SimulationInput(modelName);
in = in.setModelParameter("StopTime",num2str(time(end),17), ...
    "SolverType","Fixed-step","Solver","FixedStepDiscrete","FixedStep","0.02", ...
    "SaveOutput","on","OutputSaveName","app8_pcm","SaveFormat","Dataset", ...
    "SaveTime","on","TimeSaveName","app8_time","SignalLogging","off", ...
    "ReturnWorkspaceOutputs","on");
ports = find_system(modelName,"SearchDepth",1,"BlockType","Inport");
if isempty(ports)
    if any(weights~=0,"all"), fail("Source baseline cannot consume nonzero texture."); end
    result.input_mode = "SOURCE_BASELINE_ZERO_WEIGHT";
elseif numel(ports)==4
    numbers = cellfun(@(p) str2double(get_param(p,"Port")),ports);
    [numbers,order] = sort(numbers);
    ports = ports(order);
    expected = ["Texture Body","Texture Mechanical","Texture Broadband","Texture Weights"];
    names = string(get_param(ports,"Name"));
    if ~isequal(numbers(:)',1:4) || ~isequal(names(:)',expected)
        fail("Candidate Root Inport mapping differs from its contract.");
    end
    dataset = Simulink.SimulationData.Dataset;
    for index = 1:3
        samples = reshape(double(layers(:,:,index)).',[960,1,count]);
        signal = timeseries(samples,time,"IsTimeFirst",false);
        signal = setinterpmethod(signal,"zoh");
        dataset = dataset.addElement(signal,expected(index));
    end
    signal = timeseries(reshape(double(weights).',[1,3,count]),time,"IsTimeFirst",false);
    signal = setinterpmethod(signal,"zoh");
    dataset = dataset.addElement(signal,expected(4));
    in = in.setExternalInput(dataset);
    result.input_mode = "FOUR_ROOT_INPORTS_DATASET";
else
    fail("Candidate must expose exactly four texture Root Inports.");
end
diagnostic = [];
captureDiagnostics = isfield(externalInput,"capture_diagnostics") && isequal(externalInput.capture_diagnostics,true);
if captureDiagnostics && numel(ports)==4
    mixer = find_system(modelName,"SearchDepth",1,"Name","Layered Texture Mixer");
    probes = {Simulink.ID.getFullName(modelName+":11"),mixer{1},ports{4}};
    probeNames = ["source_pressure","mixed_pressure","texture_weights"];
    for index=1:3
        handles = get_param(probes{index},"PortHandles");
        set_param(handles.Outport(1),"DataLogging","on","DataLoggingNameMode","Custom","DataLoggingName",probeNames(index));
    end
    in = in.setModelParameter("SignalLogging","on","SignalLoggingName","app8_diagnostics");
end
out = sim(in);
if captureDiagnostics, diagnostic=out.get("app8_diagnostics"); end
captured = out.get("app8_pcm");
if ~isa(captured,"Simulink.SimulationData.Dataset") || captured.numElements ~= 1
    fail("Expected one actual matrix PCM output.");
end
signal = captured.getElement(1).Values;
frames = signal.Data;
if numel(signal.Time)~=count || any(abs(signal.Time(:)-time)>1e-10)
    fail("Captured frame timestamps do not match the declared grid.");
end
if isequal(size(frames),[count,960,2]) && signal.IsTimeFirst
    frames = permute(frames,[2,3,1]);
end
if size(frames,1)~=960 || size(frames,2)~=2 || size(frames,3)~=count || ...
        numel(frames)~=count*960*2 || ~validNumeric(frames)
    fail("Captured PCM frame/channel dimensions are invalid.");
end
pcm = reshape(permute(frames,[1,3,2]),count*960,2);
if isempty(pcm) || any(abs(pcm)>1,"all") || ~any(pcm~=0,"all")
    fail("PCM must be nonempty, finite, non-silent and peak bounded.");
end
pcmPath = fullfile(outputRoot,"candidate.pcm.f64le");
wavPath = fullfile(outputRoot,"candidate.wav");
writePcm(pcmPath,pcm);
audiowrite(wavPath,pcm,48000,"BitsPerSample",24);
[readback,rate] = audioread(wavPath);
info = audioinfo(wavPath);
quantizationError = max(abs(readback-pcm),[],"all");
if rate~=48000 || info.BitsPerSample~=24 || ~isequal(size(readback),size(pcm)) || quantizationError > 2^-23+eps
    fail("WAV readback violates the fixed PCM24 quantization contract.");
end
delta = abs(diff(pcm));
result.status = "SIMULATION_COMPLETED_RESEARCH_ONLY";
result.pcm_dimensions = size(pcm);
result.sample_rate_hz = 48000;
result.duration_seconds = size(pcm,1)/48000;
result.last_frame_time_s = time(end);
result.peak = max(abs(pcm),[],"all");
result.rms = sqrt(mean(pcm.^2,"all"));
result.maximum_sample_jump = max(delta,[],"all");
if count>1, result.maximum_frame_jump = max(delta(960:960:end,:),[],"all"); else, result.maximum_frame_jump=0; end
result.wav_quantization_max_error = quantizationError;
result.pcm_encoding = "Float64LE interleaved stereo";
result.wav_encoding = "PCM24 48kHz stereo";
result.pcm_sha256 = fileSha(pcmPath);
result.wav_sha256 = fileSha(wavPath);
result.model_sha256 = fileSha(candidateModel);
if isfield(externalInput,"layer_source_sha256"), result.layer_source_sha256=externalInput.layer_source_sha256; end
save(fullfile(outputRoot,"texture_candidate_result.mat"),"result","pcm","frames","diagnostic","-v7.3");
fid=fopen(fullfile(outputRoot,"receipt.json"),"w","n","UTF-8");
fprintf(fid,'%s\n',jsonencode(result,PrettyPrint=true)); fclose(fid);
end

function yes = validNumeric(value)
yes = isnumeric(value) && isreal(value) && all(isfinite(value),"all");
end

function fail(message)
error("S12:EngineSoundV12:CandidateRun","%s",message);
end

function writePcm(path,pcm)
fid=fopen(path,"wb","ieee-le");
if fid<0, fail("Cannot create PCM output."); end
cleanup=onCleanup(@() fclose(fid));
fwrite(fid,pcm.',"double");
end

function value = fileSha(path)
fid=fopen(path,"rb"); cleanup=onCleanup(@() fclose(fid));
digest=java.security.MessageDigest.getInstance("SHA-256"); digest.update(fread(fid,Inf,"*uint8"));
value=string(lower(reshape(dec2hex(typecast(digest.digest(),"uint8"),2).',1,[])));
end
