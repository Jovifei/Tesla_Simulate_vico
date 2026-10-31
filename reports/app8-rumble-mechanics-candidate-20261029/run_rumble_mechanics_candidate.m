function summary=run_rumble_mechanics_candidate(contractPath,mode)
% Actual Simulink experiments using native prior-B packets, never CSV replay.
if nargin<2,mode='smoke';end
mode=string(mode);if ~ismember(mode,["smoke","full","short"]),error('S12:Rumble:Mode','Invalid run mode.');end
lab=string(fileparts(mfilename('fullpath')));project=fileparts(fileparts(lab));
common=fullfile(project,'tools','sound_sim','s12','playground_v12','common');
addpath(lab,common,fullfile(common,'shared_model'));
cfg=jsondecode(fileread(contractPath));contractHash=sha(contractPath);
Simulink.fileGenControl('set','CacheFolder',lab+'/cache','CodeGenFolder',lab+'/codegen','createDir',true);
if ~isfile(lab+'/build-receipt.json'),build_rumble_mechanics_candidate(contractPath,true);end
artifact=jsondecode(fileread(lab+'/build-receipt.json'));
if sha(artifact.candidate)~=string(artifact.candidate_sha256) || contractHash~=string(artifact.contract_sha256)
    error('S12:Rumble:Identity','Model or frozen contract changed.');
end
if sha(cfg.reference.capture_mat)~=string(cfg.reference.capture_mat_sha256),error('S12:Rumble:Reference','Prior native MAT changed.');end
reference=load(cfg.reference.capture_mat,'actualState');reference=reference.actualState;
if ~isa(reference,'double') || ~isequal(size(reference),[4500,9]) || any(~isfinite(reference),'all')
    error('S12:Rumble:Reference','Prior native packets violate frame contract.');
end
run=lab+'/runs/'+mode+'-'+string(datetime('now','Format','yyyyMMdd-HHmmss-SSS'));
if isfolder(run),error('S12:Rumble:OutputExists','Run exists.');end
mkdir(run);nativeExport=exportBinary(run+'/reference_controls.f64le',reference);
dependencies=dependencySnapshot(lab,common,project,contractPath,artifact);
summary=struct('status','RUNNING','run_root',run,'mode',mode,'contract_path',string(contractPath), ...
    'contract_sha256',contractHash,'dependency_snapshot',{dependencies},'reference',cfg.reference, ...
    'build_receipt_sha256',sha(lab+'/build-receipt.json'),'build_receipt_path',lab+'/build-receipt.json', ...
    'reference_controls',nativeExport,'qualification','DIGITAL_RESEARCH_ONLY_HUMAN_PENDING');
try
    if mode~="short"
        count=4500;if mode=="smoke",count=100;end
        drive=struct('state',reference(1:count,:),'time',reference(1:count,9));
        modes=string(cfg.full_cases);modes=modes(:)';
        for k=1:numel(modes)
            label=modes(k);voice=erase(label,'_repeat');
            fprintf('RUMBLE_STAGE drive [%d/%d] %s %gs\n',k,numel(modes),label,count*.02);
            summary.cases.(label)=oneCase(label,artifact,drive,voice,run+'/'+label,contractPath,dependencies,false);
            if label=="B0"
                if mode=="full" && summary.cases.B0.pcm_sha256~=string(cfg.reference.pcm_sha256)
                    error('S12:Rumble:BaselineDrift','B0 differs from prior exact native B PCM.');
                end
                prior=fopen(string(fileparts(cfg.reference.capture_mat))+'/candidate.pcm.f64le','rb','ieee-le');
                cleanup=onCleanup(@() fclose(prior));old=fread(prior,count*960*2,'*double');clear cleanup;
                current=fopen(summary.cases.B0.pcm_path,'rb','ieee-le');cleanup=onCleanup(@() fclose(current));new=fread(current,Inf,'*double');clear cleanup;
                if ~isequal(old,new),error('S12:Rumble:BaselineDrift','B0 samples differ from native prior B prefix.');end
                summary.baseline_pcm_exact=true;
            end
            if contains(label,'_repeat')
                if summary.cases.(label).pcm_sha256~=summary.cases.(voice).pcm_sha256 || summary.cases.(label).wav_sha256~=summary.cases.(voice).wav_sha256
                    error('S12:Rumble:Repeat','Same-session repeat differs.');
                end
            end
            writeJson(run+'/progress-'+string(k)+'.json',summary);
        end
    end
    summary.short_cases=struct;
    for k=1:numel(cfg.short_cases)
        label=string(cfg.short_cases{k});a=cfg.short_state;time=(0:round(cfg.short_seconds/.02)-1)'*.02;
        state=[repmat([a.rpm,a.load,a.throttle,0,0,0,0,0],numel(time),1),time];
        fprintf('RUMBLE_STAGE short [%d/%d] %s\n',k,numel(cfg.short_cases),label);
        summary.short_cases.(label)=oneCase(label,artifact,struct('time',time,'state',state),label, ...
            run+'/short/'+label,contractPath,dependencies,true);
    end
    summary.stationary={};
    if mode=="full"
        for j=1:numel(cfg.anchors)
            anchor=cfg.anchors(j);time=(0:round(cfg.stationary_seconds/.02)-1)'*.02;
            state=[repmat([anchor.rpm,anchor.load,anchor.throttle,0,0,0,0,0],numel(time),1),time];
            item=anchor;item.cases=struct;
            for k=1:numel(cfg.stationary_cases)
                label=string(cfg.stationary_cases{k});fprintf('RUMBLE_STAGE anchor [%d/42] %s %s\n',(j-1)*6+k,string(anchor.name),label);
                item.cases.(label)=oneCase(label,artifact,struct('time',time,'state',state),label, ...
                    run+'/stationary/'+string(anchor.name)+'/'+label,contractPath,dependencies,false);
            end
            summary.stationary{j}=item;writeJson(run+'/stationary-progress-'+string(j)+'.json',summary);
        end
    end
    verifyDependencies(dependencies);summary.status='RENDERED_DIGITAL_PASS_ANALYSIS_PENDING';
    writeJson(run+'/run-summary.json',summary);
    if mode=="smoke",writeJson(lab+'/runtime-evaluation-proof.json',struct('run_summary',run+'/run-summary.json','run_summary_sha256',sha(run+'/run-summary.json'),'contract_sha256',contractHash,'baseline_pcm_exact',summary.baseline_pcm_exact));end
    fprintf('RUMBLE_%s_DIGITAL_PASS %s\n',upper(mode),run);
catch failure
    summary.status='FAILED';summary.error_id=string(failure.identifier);summary.error=string(failure.message);
    writeJson(run+'/failure.json',summary);fprintf('RUMBLE_FAILED %s %s\n',failure.identifier,failure.message);rethrow(failure);
end
end

function result=oneCase(label,artifact,input,voice,directory,contractPath,dependencies,keepMechanics)
cfg=jsondecode(fileread(contractPath));verifyDependencies(dependencies);
if isfolder(directory),error('S12:Rumble:OutputExists','Case exists.');end
mkdir(directory);n=numel(input.time);modelPath=string(artifact.candidate);[folder,model]=fileparts(modelPath);addpath(folder);
load_system(modelPath);cleanup=onCleanup(@() close_system(model,0));
gain=Simulink.ID.getFullName(model+':13');if str2double(get_param(gain,'Value'))~=.1,error('S12:Rumble:Gain','Gain differs.');end
source=Simulink.ID.getFullName(model+':11');radiation=Simulink.ID.getFullName(model+':12');clock=Simulink.ID.getFullName(model+':9');
expression="s12_v12_model_rumble_mechanics_step(u, '"+replace(string(contractPath),"'","''")+"', '"+voice+"')";
in=Simulink.SimulationInput(model);
in=in.setModelParameter('StopTime',num2str(input.time(end),17),'SolverType','Fixed-step','Solver','FixedStepDiscrete', ...
    'FixedStep','0.02','SaveOutput','on','OutputSaveName','rumble_pcm','SaveFormat','Dataset', ...
    'ReturnWorkspaceOutputs','on','SignalLogging','on','SignalLoggingName','rumble_logs');
in=in.setBlockParameter(source,'MATLABFcn',expression);
if string(in.BlockParameters(1).Value)~=expression,error('S12:Rumble:Expression','SimulationInput override differs.');end
ds=Simulink.SimulationData.Dataset;signal=timeseries(reshape(input.state.',9,1,n),input.time,'IsTimeFirst',false);
signal=setinterpmethod(signal,'zoh');ds=ds.addElement(signal,'Listening Vehicle State');in=in.setExternalInput(ds);
h=get_param(source,'PortHandles');line=get_param(h.Inport(1),'Line');statePort=get_param(line,'SrcPortHandle');logPort(statePort,'rumble_state');
logPort(h.Outport(1),'source_pressure');h=get_param(radiation,'PortHandles');logPort(h.Outport(1),'radiated_pressure');
h=get_param(clock,'PortHandles');logPort(h.Outport(1),'actual_clock');
s12_v12_model_rumble_mechanics_step([],contractPath,'reset');clear s12_v12_model_radiation_step;
traceRadiation=n<=100;
if traceRadiation
    assignin('base','rumble_radiation_times',zeros(0,1));
    assignin('base','rumble_trace_handle',@radiationTrace);
    condition="feval(evalin('base','rumble_trace_handle'),packed)";
    dbstop('in','s12_v12_model_radiation_step','at','5','if',char(condition));
    clearBreakpoint=onCleanup(@() dbclear('in','s12_v12_model_radiation_step'));
else
    proofPath=string(fileparts(mfilename('fullpath')))+'/runtime-evaluation-proof.json';
    proof=jsondecode(fileread(proofPath));
    if string(proof.contract_sha256)~=sha(contractPath) || ~proof.baseline_pcm_exact || string(proof.run_summary_sha256)~=sha(proof.run_summary)
        error('S12:Rumble:EvaluationProof','Missing or changed successful smoke initialization proof.');
    end
end
profile clear;profile on;
out=sim(in);profile off;executionProfile=profile('info');
if traceRadiation,radiationTimes=evalin('base','rumble_radiation_times');clear clearBreakpoint;evalin('base','clear rumble_radiation_times rumble_trace_handle');else,radiationTimes=[];end
logs=out.get('rumble_logs');actualState=reshape(frameData(logs.getElement('rumble_state').Values,9,1,input.time),9,n).';
actualClock=reshape(frameData(logs.getElement('actual_clock').Values,1,1,input.time),n,1);
if ~isequal(actualState,input.state) || any(abs(actualClock-actualState(:,9))>1e-10)
    error('S12:Rumble:InputConsumption','Actual state or independent clock differs.');
end
sourcePressure=frameData(logs.getElement('source_pressure').Values,960,1,input.time);
radiatedPressure=frameData(logs.getElement('radiated_pressure').Values,960,1,input.time);
output=out.get('rumble_pcm');frames=frameData(output.getElement(1).Values,960,2,input.time);
pcm=reshape(permute(frames,[1,3,2]),n*960,2);
[~,sourceTelemetry]=s12_v12_model_rumble_mechanics_step([],contractPath,'report');
sourcePressureBefore=sourceTelemetry.pre_pressure;cyclePhase=sourceTelemetry.cycle_phase;mechanics=sourceTelemetry.mechanics;
sourceTelemetry=rmfield(sourceTelemetry,{'pre_pressure','cycle_phase','mechanics'});
if sourceTelemetry.frame_count~=n || sourceTelemetry.mode~=voice || ~isequal(sourceTelemetry.values(:,2),(1:n)')
    error('S12:Rumble:SourceState','Wrong mode/frame context consumed.');
end
v=sourceTelemetry.values;phaseError=abs(atan2(sin(v(2:end,3)-v(1:end-1,4)),cos(v(2:end,3)-v(1:end-1,4))));
if any(phaseError>1e-10),error('S12:Rumble:Phase','Crank phase discontinuity.');end
if any(v(:,17)~=v(:,18)) || any(v(:,19)~=v(:,20)) || any(v(:,21)~=v(:,22))
    error('S12:Rumble:Cut','Mechanical or whine was incorrectly combustion-cut.');
end
if any(input.state(:,5)~=0) && min(v(:,5))>cfg.research_options.cut_minimum+.005,error('S12:Rumble:Cut','Shift cut absent.');end
if any(v(input.state(:,5)==0,5)~=1),error('S12:Rumble:Cut','Cut remains outside shift.');end
if ~isreal(pcm) || any(~isfinite(pcm),'all') || ~any(pcm~=0,'all') || any(abs(pcm)>1,'all')
    error('S12:Rumble:PCM','Final PCM contract failed.');
end
result=struct('label',label,'directory',directory,'pcm_path',directory+'/candidate.pcm.f64le','wav_path',directory+'/candidate.wav', ...
    'frame_count',n,'samples_per_channel',n*960,'sample_rate_hz',48000,'channels',2,'duration_seconds',n*.02, ...
    'last_frame_time_s',input.time(end),'actual_control_matches',true,'actual_clock_matches',true, ...
    'wrapper_expression',expression,'SimulationInput_wrapper_expression',string(in.BlockParameters(1).Value), ...
    'actual_wrapper_mode',sourceTelemetry.mode,'source_evaluation_count',sourceTelemetry.evaluation_count, ...
    'source_duplicate_count',sourceTelemetry.duplicate_count,'unique_source_frames',sourceTelemetry.frame_count, ...
    'source_phase_origin',sourceTelemetry.phase_origin,'contract_sha256',sha(contractPath),'model_sha256',sha(modelPath), ...
    'reference_capture_mat_sha256',cfg.reference.capture_mat_sha256,'dependency_snapshot',{dependencies});
result.function_calls=profileCalls(executionProfile);
result.radiation_evaluation_times=radiationTimes;
if traceRadiation
    if ~isequal(radiationTimes,[0;actualClock]),error('S12:Rumble:EvaluationTimes','Unexpected actual radiation invocation times.');end
    expected=zeros(size(radiatedPressure));frozenContext=[];
    for j=1:n,[expected(:,:,j),frozenContext]=s12_v12_apply_frozen_radiation_frame(sourcePressure(:,:,j),frozenContext,48000);end
    result.sequential_frozen_max_error=max(abs(expected-radiatedPressure),[],'all');
    if result.sequential_frozen_max_error>1e-14,error('S12:Rumble:FrozenReset','Model pressure differs from independent sequential Frozen reference.');end
    result.radiation_initialization_proof='actual trace [0;frame clocks]; all captured frames match sequential reference';
else
    result.radiation_initialization_proof=proofPath;result.radiation_initialization_proof_sha256=sha(proofPath);
end
if result.function_calls.source_frame~=n || result.function_calls.frozen_frame~=n+1 || result.function_calls.radiation_wrapper~=n+1 || sourceTelemetry.duplicate_count~=0
    save(directory+'/failed-capture.mat','actualState','actualClock','sourcePressureBefore','sourcePressure','radiatedPressure','frames','pcm','sourceTelemetry','cyclePhase','mechanics','executionProfile','result','-v7.3');
    writeJson(directory+'/failure-counts.json',result);
    error('S12:Rumble:EvaluationCounts','Unexpected actual calls %s; inspect saved profile.',jsonencode(result.function_calls));
end
result.binary_exports=struct;
result.binary_exports.pcm=exportBinary(result.pcm_path,pcm);
result.binary_exports.actual_control=exportBinary(directory+'/actual_control.f64le',actualState);
result.binary_exports.actual_clock=exportBinary(directory+'/actual_clock.f64le',actualClock);
result.binary_exports.source_pressure=exportBinary(directory+'/source_pressure.f64le',reshape(sourcePressure,[],1));
result.binary_exports.source_pressure_before=exportBinary(directory+'/source_pressure_before.f64le',reshape(sourcePressureBefore,[],1));
result.binary_exports.radiated_pressure=exportBinary(directory+'/radiated_pressure.f64le',reshape(radiatedPressure,[],1));
result.binary_exports.cycle_phase=exportBinary(directory+'/cycle_phase.f64le',reshape(cyclePhase,[],1));
if keepMechanics
    fields=fieldnames(mechanics);
    for j=1:numel(fields)
        name=string(fields{j});a=mechanics.(name);data=reshape(permute(a,[1,3,2]),n*960,size(a,2));
        result.binary_exports.('mechanics_'+name)=exportBinary(directory+'/mechanics_'+name+'.f64le',data);
    end
else,mechanics=struct;end
audiowrite(result.wav_path,pcm,48000,'BitsPerSample',24);[back,fs]=audioread(result.wav_path);info=audioinfo(result.wav_path);
quantization=max(abs(back-pcm),[],'all');
if fs~=48000 || info.BitsPerSample~=24 || ~isequal(size(back),size(pcm)) || quantization>2^-23+eps,error('S12:Rumble:WAV','PCM24 readback failed.');end
delta=abs(diff(pcm));boundary=0;if n>1,boundary=max(delta(960:960:end,:),[],'all');end
result.maximum_sample_jump=max(delta,[],'all');result.maximum_frame_jump=boundary;result.peak=max(abs(pcm),[],'all');
result.rms=sqrt(mean(pcm.^2,'all'));result.wav_quantization_max_error=quantization;
result.pcm_sha256=sha(result.pcm_path);result.wav_sha256=sha(result.wav_path);
if result.maximum_sample_jump>cfg.screening.maximum_sample_jump || boundary>cfg.screening.continuity_reference_A_frame_jump+cfg.screening.frame_jump_increase_over_reference_max
    save(directory+'/failed-capture.mat','actualState','actualClock','sourcePressureBefore','sourcePressure','radiatedPressure','frames','pcm','sourceTelemetry','cyclePhase','mechanics','executionProfile','-v7.3');
    error('S12:Rumble:Continuity','Predeclared sample/frame continuity gate failed.');
end
result.actual_control_csv=directory+'/actual_control.csv';writematrix(actualState,result.actual_control_csv);result.actual_control_sha256=sha(result.actual_control_csv);
result.drive_csv=directory+'/drive.csv';writetable(array2table([input.time,input.state], ...
    'VariableNames',{'time_s','rpm','load','throttle','acceleration','shift_event','shift_progress','afterfire_code','afterfire_progress','source_time_s'}),result.drive_csv);
result.drive_sha256=sha(result.drive_csv);result.source_telemetry_csv=directory+'/source-telemetry.csv';
writetable(array2table(sourceTelemetry.values,'VariableNames',cellstr(sourceTelemetry.columns)),result.source_telemetry_csv);
result.source_telemetry_sha256=sha(result.source_telemetry_csv);verifyDependencies(dependencies);
result.capture_mat=directory+'/capture.mat';result.receipt_path=directory+'/receipt.json';
save(result.capture_mat,'actualState','actualClock','sourcePressureBefore','sourcePressure','radiatedPressure','frames','pcm','sourceTelemetry','cyclePhase','mechanics','executionProfile','result','-v7.3');
result.capture_mat_sha256=sha(result.capture_mat);writeJson(result.receipt_path,result);result.receipt_sha256=sha(result.receipt_path);
end

function logPort(port,name)
set_param(port,'DataLogging','on','DataLoggingNameMode','Custom','DataLoggingName',name);
end
function stop=radiationTrace(packed)
assignin('base','rumble_radiation_times',[evalin('base','rumble_radiation_times');packed(end)]);
stop=false;
end
function calls=profileCalls(p)
names={'s12_v12_render_source_frame','s12_v12_apply_frozen_radiation_frame','s12_v12_model_radiation_step'};
keys={'source_frame','frozen_frame','radiation_wrapper'};calls=struct;
for j=1:numel(names)
    ix=strcmp({p.FunctionTable.FunctionName},names{j});calls.(keys{j})=sum([p.FunctionTable(ix).NumCalls]);
end
end
function data=frameData(signal,rows,columns,time)
n=numel(time);data=signal.Data;
if numel(signal.Time)~=n || any(abs(signal.Time(:)-time(:))>1e-10),error('S12:Rumble:Capture','Captured timestamps differ.');end
if size(data,1)==n && signal.IsTimeFirst
    if columns==1,data=reshape(data.',rows,1,n);else,data=permute(data,[2,3,1]);end
end
if size(data,1)~=rows || size(data,2)~=columns || size(data,3)~=n || numel(data)~=rows*columns*n || ~isreal(data) || any(~isfinite(data),'all')
    error('S12:Rumble:Capture','Captured frame shape/finite contract differs.');
end
end
function meta=exportBinary(path,data)
if isfile(path),error('S12:Rumble:OutputExists','Binary exists.');end
fid=fopen(path,'wb','ieee-le');cleanup=onCleanup(@() fclose(fid));fwrite(fid,data.','double');clear cleanup;
meta=struct('path',path,'sha256',sha(path),'shape',size(data),'order','row-major','dtype','float64-le');
end
function writeJson(path,value)
if isfile(path),error('S12:Rumble:OutputExists','Receipt exists.');end
fid=fopen(path,'w','n','UTF-8');cleanup=onCleanup(@() fclose(fid));fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));
end
function value=sha(path)
fid=fopen(path,'rb');cleanup=onCleanup(@() fclose(fid));d=java.security.MessageDigest.getInstance('SHA-256');d.update(fread(fid,Inf,'*uint8'));
value=string(lower(reshape(dec2hex(typecast(d.digest(),'uint8'),2).',1,[])));
end
function snapshot=dependencySnapshot(lab,common,project,contractPath,artifact)
files=[dir(common+'/*.m');dir(common+'/shared_model/*.slx');dir(lab+'/*.m')];paths=strings(numel(files),1);
for j=1:numel(files),paths(j)=fullfile(files(j).folder,files(j).name);end
vehicle=fullfile(common,'..','vehicles','hellcat_2022_stock');
paths=[paths;string(contractPath);string(artifact.source);string(artifact.candidate); ...
    fullfile(vehicle,'source_profile.json');fullfile(vehicle,'engine_identity_profile.json');fullfile(vehicle,'scenario_profile.json'); ...
    fullfile(project,'tools','sound_sim','s12','benchmark','baselines','sprint-4d-b','radiation-boundary-package.json')];
snapshot=cell(numel(paths),1);paths=sort(paths);
for j=1:numel(paths),path=string(java.io.File(char(paths(j))).getCanonicalPath());[~,name,ext]=fileparts(path);resolved={};
    if ext==".m",resolved=cellstr(which(name,'-all'));if isempty(resolved) || string(resolved{1})~=path,error('S12:Rumble:Resolution','Unexpected resolved dependency %s',name);end;end
    snapshot{j}=struct('path',path,'sha256',sha(path),'which_all',{resolved});
end
end
function verifyDependencies(snapshot)
for j=1:numel(snapshot),entry=snapshot{j};if ~isfile(entry.path) || sha(entry.path)~=entry.sha256,error('S12:Rumble:DependencyDrift','Dependency changed: %s',entry.path);end;end
end
