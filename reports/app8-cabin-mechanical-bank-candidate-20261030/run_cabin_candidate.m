function summary = run_cabin_candidate(stage,runRoot)
% Staged execution; a cold repeat is accepted only from a different process.
if nargin<1,stage='preflight';end
stage=string(stage);lab=string(fileparts(mfilename('fullpath')));root=fileparts(fileparts(lab));
common=fullfile(root,'tools','sound_sim','s12','playground_v12','common');
legacy=fullfile(root,'reports','app8-rumble-mechanics-candidate-20261029');
addpath(lab,common,fullfile(common,'shared_model'),legacy);
if nargin<2 || strlength(string(runRoot))==0
    if stage~="preflight",error('Cabin:RunRoot','Reuse the successful preflight run root.');end
    runRoot=fullfile(lab,'runs','approved-'+string(datetime('now','Format','yyyyMMdd-HHmmss-SSS')));
    if isfolder(runRoot),error('Cabin:OutputExists','Run directory already exists.');end
    mkdir(runRoot);
else
    runRoot=string(java.io.File(char(runRoot)).getCanonicalPath());
    if ~startsWith(lower(runRoot),lower(lab+filesep))
        error('Cabin:RunRoot','Run root must be inside the lab.');
    end
    if stage=="preflight"
        if isfolder(runRoot),error('Cabin:OutputExists','Preflight run directory already exists.');end
        mkdir(runRoot);
    elseif ~isfolder(runRoot)
        error('Cabin:RunRoot','Use the already existing preflight run root.');
    end
end
cfg=jsondecode(fileread(fullfile(lab,'EXPERIMENT_CONTRACT.json')));
summary=struct('stage',stage,'status','RUNNING','run_root',runRoot, ...
    'process',processIdentity(),'matlab_version',version,'simulink_version',ver('simulink'), ...
    'md_cold','NOT_RUN','qualification','DIGITAL_RESEARCH_ONLY_HUMAN_AND_DEVICE_PENDING');
try
    verifyReference(cfg,legacy);
    ref=load(cfg.reference.capture_mat,'actualState');ref=ref.actualState;
    if ~isa(ref,'double') || ~isequal(size(ref),[4500 9]) || any(~isfinite(ref),'all') || ...
            any(abs(ref(:,9)-(0:4499)'*.02)>1e-10)
        error('Cabin:Reference','Native B actualState failed its data or clock contract.');
    end
    switch stage
        case "preflight"
            tests=captureCall(@()runTests(lab),fullfile(runRoot,'01-unit-tests.log'));
            summary.tests=tests;
            if isfile(fullfile(lab,'cabin-build-receipt.json'))
                build=jsondecode(fileread(fullfile(lab,'cabin-build-receipt.json')));
                if string(build.contract_sha256)~=sha(fullfile(lab,'EXPERIMENT_CONTRACT.json'))
                    error('Cabin:BuildReceipt','Existing build receipt contract hash differs.');
                end
                build.reused_existing_receipt=true;
            else
                build=captureCall(@()build_cabin_candidate(),fullfile(runRoot,'02-build.log'));
            end
            summary.build=build;summary.dependencies=dependencies(lab,root,legacy);
            drive=ref(1:100,:);
            summary.B0_short=captureCall(@()oneCase(lab,root,legacy,runRoot,'short-B0',drive,'B0',1,true), ...
                fullfile(runRoot,'03-short-B0.log'));
            summary.N_short=captureCall(@()oneCase(lab,root,legacy,runRoot,'short-N',drive,'N',1,true), ...
                fullfile(runRoot,'04-short-N.log'));
            calibrationPath=fullfile(runRoot,'calibration.json');
            summary.calibration=captureCall(@()calibrate_cabin_candidate(calibrationPath), ...
                fullfile(runRoot,'05-calibration.log'));
            summary.calibration_sha256=sha(calibrationPath);
            summary.M_short=captureCall(@()oneCase(lab,root,legacy,runRoot,'short-M',drive,'M',summary.calibration.k,true), ...
                fullfile(runRoot,'06-short-M.log'));
            summary.D_short=captureCall(@()oneCase(lab,root,legacy,runRoot,'short-D',drive,'D',summary.calibration.k,true), ...
                fullfile(runRoot,'07-short-D.log'));
            summary.MD_short=captureCall(@()oneCase(lab,root,legacy,runRoot,'short-MD',drive,'MD',summary.calibration.k,true), ...
                fullfile(runRoot,'08-short-MD.log'));
            summary.short_contrasts=verifyContrasts(runRoot,'short-');
            anchorTime=(0:299)'*.02;
            anchor=[repmat([2200 .35 .32 0 0 0 0 0],300,1),anchorTime];
            summary.calibration_gate_M=captureCall(@()oneCase(lab,root,legacy,runRoot, ...
                'calibration-gate-M',anchor,'M',summary.calibration.k,false),fullfile(runRoot,'09-calibration-M.log'));
            summary.calibration_gate_MD=captureCall(@()oneCase(lab,root,legacy,runRoot, ...
                'calibration-gate-MD',anchor,'MD',summary.calibration.k,false),fullfile(runRoot,'10-calibration-MD.log'));
            if sha(calibrationPath)~=summary.calibration_sha256
                error('Cabin:CalibrationHash','The one frozen calibration changed during the safety diagnostics.');
            end
            verifyDependencies(summary.dependencies);
            summary.status='PREFLIGHT_PASS_LONG_AND_COLD_NOT_RUN';
            writeNewJson(fullfile(runRoot,'preflight.json'),summary);
        case "full"
            pre=loadPreflight(runRoot);verifyDependencies(pre.dependencies);
            k=pre.calibration.k;labels=["B0","N","M","D","MD","MD-repeat"];
            summary.cases=struct;
            for i=1:numel(labels)
                label=labels(i);voice=erase(label,'-repeat');
                fprintf('CABIN drive [%d/%d] %s\n',i,numel(labels),label);
                summary.cases.(matlab.lang.makeValidName(label))=captureCall( ...
                    @()oneCase(lab,root,legacy,runRoot,label,ref,voice,k,false), ...
                    fullfile(runRoot,label+'.log'));
                writeNewJson(fullfile(runRoot,'drive-progress-'+string(i)+'.json'),summary);
            end
            if summary.cases.MD.pcm_sha256~=summary.cases.MD_repeat.pcm_sha256 || ...
                    summary.cases.MD.wav_sha256~=summary.cases.MD_repeat.wav_sha256
                error('Cabin:Repeat','Same-process MD repeat differs.');
            end
            summary.drive_contrasts=verifyContrasts(runRoot,'');
            old=jsondecode(fileread(fullfile(legacy,'EXPERIMENT_CONTRACT.json')));
            voices=["B0","N","M","D","MD"];
            for j=1:numel(old.anchors)
                a=old.anchors(j);time=(0:299)'*.02;
                input=[repmat([a.rpm a.load a.throttle 0 0 0 0 0],300,1),time];
                for i=1:numel(voices)
                    label="anchor-"+string(a.name)+"-"+voices(i);
                    fprintf('CABIN anchor [%d/%d] %s\n',(j-1)*5+i,numel(old.anchors)*5,label);
                    summary.anchors.(matlab.lang.makeValidName(label))=captureCall( ...
                        @()oneCase(lab,root,legacy,runRoot,label,input,voices(i),k,false), ...
                        fullfile(runRoot,label+'.log'));
                end
                summary.anchors.(matlab.lang.makeValidName("anchor-"+string(a.name)+"-contrasts"))= ...
                    verifyContrasts(runRoot,"anchor-"+string(a.name)+"-");
            end
            verifyDependencies(pre.dependencies);
            summary.status='FULL_PASS_COLD_AND_AUDITION_NOT_RUN';
            writeNewJson(fullfile(runRoot,'full.json'),summary);
        case "cold"
            pre=loadPreflight(runRoot);full=jsondecode(fileread(fullfile(runRoot,'full.json')));
            current=processIdentity();
            if isequal(current,full.process)
                error('Cabin:ColdProcess','MD-cold requires a new MATLAB process, not a model reload.');
            end
            verifyDependencies(pre.dependencies);
            summary.MD_cold=captureCall(@()oneCase(lab,root,legacy,runRoot,'MD-cold',ref,'MD',pre.calibration.k,false), ...
                fullfile(runRoot,'MD-cold.log'));
            if summary.MD_cold.pcm_sha256~=string(full.cases.MD.pcm_sha256) || ...
                    summary.MD_cold.wav_sha256~=string(full.cases.MD.wav_sha256)
                error('Cabin:ColdRepeat','New-process MD repeat differs.');
            end
            verifyDependencies(pre.dependencies);summary.md_cold='PASS_NEW_PROCESS';
            summary.status='DIGITAL_RUNS_COMPLETE_ANALYSIS_AND_HUMAN_PENDING';
            writeNewJson(fullfile(runRoot,'cold.json'),summary);
        otherwise,error('Cabin:Stage','Stage must be preflight, full, or cold.');
    end
catch failure
    summary.status='FAILED';summary.error_id=string(failure.identifier);summary.error=string(getReport(failure,'extended','hyperlinks','off'));
    summary.last_probe_trace=mb_runtime_probe('report');
    writeNewJson(fullfile(runRoot,'failure-'+stage+'-'+string(datetime('now','Format','HHmmssSSS'))+'.json'),summary);
    rethrow(failure);
end
end

function result=runTests(lab)
files={'test_cabin_source.m','test_cabin_paths.m','test_approved_cabin_steps.m'};
results=runtests(fullfile(lab,files{1}));
for i=2:numel(files),results=[results runtests(fullfile(lab,files{i}))];end %#ok<AGROW>
disp(table(results));
if any([results.Failed]) || any([results.Incomplete]),error('Cabin:UnitTests','MATLAB unit tests failed or incomplete.');end
result=struct('total',numel(results),'passed',nnz([results.Passed]),'failed',nnz([results.Failed]));
end

function result=oneCase(lab,root,legacy,runRoot,label,input,voice,k,traceFrozen)
directory=fullfile(runRoot,label);if isfolder(directory),error('Cabin:OutputExists','Case exists.');end
mkdir(directory);cfg=jsondecode(fileread(fullfile(lab,'EXPERIMENT_CONTRACT.json')));
if voice=="B0"
    modelPath=string(jsondecode(fileread(fullfile(lab,'cabin-build-receipt.json'))).baseline_copy);
    contractPath=fullfile(legacy,'EXPERIMENT_CONTRACT.json');
    if sha(modelPath)~=string(cfg.reference.baseline_model_sha256),error('Cabin:ModelHash','Isolated B0 copy changed.');end
else
    build=jsondecode(fileread(fullfile(lab,'cabin-build-receipt.json')));
    modelPath=string(build.model);contractPath='';
    if sha(modelPath)~=string(build.model_sha256),error('Cabin:ModelHash','Saved candidate changed.');end
end
[folder,model]=fileparts(modelPath);addpath(folder);
if bdIsLoaded(model),error('Cabin:LoadedModel','Model already loaded; preserve any unsaved work.');end
open_system(modelPath);
cleanup=onCleanup(@()close_system(model,0));
source=Simulink.ID.getFullName(model+':11');frozen=Simulink.ID.getFullName(model+':12');
clock=Simulink.ID.getFullName(model+':9');renderer=Simulink.ID.getFullName(model+':15');
gain=Simulink.ID.getFullName(model+':13');
if str2double(get_param(gain,'Value'))~=.1,error('Cabin:RendererGain','Frozen renderer gain changed.');end
in=Simulink.SimulationInput(model);time=input(:,9);n=numel(time);
in=in.setModelParameter('StopTime',num2str(time(end),17),'SolverType','Fixed-step', ...
    'Solver','FixedStepDiscrete','FixedStep','0.02','SaveOutput','on','OutputSaveName','cabin_pcm', ...
    'SaveFormat','Dataset','ReturnWorkspaceOutputs','on','SignalLogging','on','SignalLoggingName','cabin_logs');
ds=Simulink.SimulationData.Dataset;signal=timeseries(reshape(input.',9,1,n),time,'IsTimeFirst',false);
signal=setinterpmethod(signal,'zoh');ds=ds.addElement(signal,'Listening Vehicle State');in=in.setExternalInput(ds);
if voice=="B0"
    expression="mb_b0_step(u, '"+replace(string(contractPath),"'","''")+"')";
    in=in.setBlockParameter(source,'MATLABFcn',expression);
    s12_v12_model_rumble_mechanics_step([],contractPath,'reset');mb_b0_step('reset');
else
    pathBlock=singleBlock(model,'Combustion_Network_And_Event');receiver=singleBlock(model,'Mechanical_Receiver');
    modalBlock=singleBlock(model,'Mechanical_Split');
    in=in.setBlockParameter(pathBlock,'MATLABFcn',"mb_path_bus_step(u, '"+voice+"')");
    in=in.setBlockParameter(modalBlock,'MATLABFcn','mb_split_modal_bus(u)');
    in=in.setBlockParameter(receiver,'MATLABFcn',"mb_mechanical_mono_step(u, '"+voice+"', "+string(num2str(k,17))+")");
    mb_source_step('reset');mb_path_step('reset');mb_receiver_step('reset');mb_mechanical_mono_step('reset');mb_runtime_probe('disarm');
end
mb_runtime_probe('arm',input(1,:).',model);probeCleanup=onCleanup(@()mb_runtime_probe('disarm'));
clear s12_v12_model_radiation_step;
h=get_param(source,'PortHandles');sourceInput=get_param(get_param(h.Inport(1),'Line'),'SrcPortHandle');
logPort(sourceInput,'actual_state');logOutput(clock,'actual_clock');logOutput(source,'source_packet');
logOutput(frozen,'frozen_output');logOutput(renderer,'renderer_output');
if voice~="B0"
    logOutput(singleBlock(model,'Combustion_Split'),'combustion_branch');
    logOutput(singleBlock(model,'Other_Split'),'other_branch');
    logOutput(singleBlock(model,'Control_Split'),'control_branch');
    logOutput(singleBlock(model,'Combustion_Network_And_Event'),'path_state');
    logOutput(singleBlock(model,'Pre_Frozen_Split'),'pre_frozen');
    logOutput(singleBlock(model,'Mechanical_Receiver'),'mechanical_after_frozen');
    logOutput(singleBlock(model,'Post_Frozen_Mechanical_Sum'),'post_frozen_sum');
end
if traceFrozen
    assignin('base','cabin_radiation_times',zeros(0,1));assignin('base','cabin_trace_handle',@radiationTrace);
    dbstop('in','s12_v12_model_radiation_step','at','5','if',"feval(evalin('base','cabin_trace_handle'),packed)");
    clearTrace=onCleanup(@()dbclear('in','s12_v12_model_radiation_step'));
end
out=sim(in);
if traceFrozen
    radiationTimes=evalin('base','cabin_radiation_times');clear clearTrace;
    evalin('base','clear cabin_radiation_times cabin_trace_handle');
else,radiationTimes=[];end
% Missing cabin_logs is a hard failure; never silently read an empty logsout.
logs=out.get('cabin_logs');pcmOutput=out.get('cabin_pcm');
required=["actual_state","actual_clock","source_packet","frozen_output","renderer_output"];
if voice~="B0",required=[required,"combustion_branch","other_branch","control_branch", ...
    "path_state","pre_frozen","mechanical_after_frozen","post_frozen_sum"];end
names=string(logs.getElementNames);
for j=1:numel(required)
    if nnz(names==required(j))~=1
        save(fullfile(directory,'missing-log-capture.mat'),'logs','pcmOutput','names','required','-v7.3');
        error('Cabin:MissingLog','Missing or duplicate actual log %s.',required(j));
    end
end
actual=reshape(frameData(logs.getElement('actual_state').Values,9,1,time),9,n).';
actualClock=reshape(frameData(logs.getElement('actual_clock').Values,1,1,time),n,1);
frames=frameData(pcmOutput.getElement(1).Values,960,2,time);
pcm=reshape(permute(frames,[1 3 2]),[],2);
if voice=="B0",[~,sourceReport]=s12_v12_model_rumble_mechanics_step([],contractPath,'report');pathReport=[];receiverReport=[];
else,[~,sourceReport]=mb_source_step('report');[~,pathReport]=mb_path_step('report');[~,receiverReport]=mb_mechanical_mono_step('report');end
probeTrace=mb_runtime_probe('report');clear probeCleanup;
capturePath=fullfile(directory,'capture.mat');
save(capturePath,'actual','actualClock','logs','frames','pcm','sourceReport','pathReport','receiverReport','radiationTimes','probeTrace','-v7.3');
if ~isequal(actual,input) || any(abs(actualClock-time)>1e-10),error('Cabin:ActualControl','Logged native state/clock differ.');end
if voice=="B0"
    if sourceReport.frame_count~=n,error('Cabin:ActualState','Legacy source did not advance once per frame.');end
else
    mechanicalFrames=frameData(logs.getElement('mechanical_after_frozen').Values,960,1,time);
    receiverFramesOk = size(mechanicalFrames,3)==n && all(isfinite(mechanicalFrames),'all');
    if sourceReport.frames~=n || pathReport.frames~=n || ~receiverFramesOk
        error('Cabin:ActualState','An experimental branch did not advance once per frame.');
    end
    sourceFrames=frameData(logs.getElement('source_packet').Values,960,9,time);
    combustion=frameData(logs.getElement('combustion_branch').Values,960,2,time);
    other=frameData(logs.getElement('other_branch').Values,960,2,time);
    control=frameData(logs.getElement('control_branch').Values,960,5,time);
    pathFrames=frameData(logs.getElement('path_state').Values,960,2,time);
    preFrames=frameData(logs.getElement('pre_frozen').Values,960,1,time);
    frozenFrames=frameData(logs.getElement('frozen_output').Values,960,1,time);
    sumFrames=frameData(logs.getElement('post_frozen_sum').Values,960,1,time);
    if ~isequal(combustion,sourceFrames(:,1:2,:)) || ~isequal(other,sourceFrames(:,3:4,:)) || ...
            ~isequal(control,sourceFrames(:,5:9,:)) || ~isequal(preFrames,pathFrames(:,1,:))
        error('Cabin:ActualRouting','Logged Selector branches do not reproduce the source package.');
    end
    mb_path_step('reset'); expectedPath=zeros(size(pathFrames));
    for jj=1:n, expectedPath(:,:,jj)=mb_path_bus_step(sourceFrames(:,:,jj),voice); end
    if max(abs(expectedPath-pathFrames),[],'all')>1e-13
        error('Cabin:ActualRouting','Actual path bus differs from the declared source/path wrapper.');
    end
    if voice=="M" || voice=="MD",expectedMechanical=k*pathFrames(:,2,:);
    else,expectedMechanical=zeros(size(mechanicalFrames));end
    if ~isequal(mechanicalFrames,expectedMechanical)
        error('Cabin:ActualRouting','Post-Frozen mechanical Sum does not match actual branches.');
    end
    frozenRaw=logs.getElement('frozen_output').Values.Data;
    frozenForSum=reshape(frozenRaw.',960,1,n);
    if max(abs(sumFrames-frozenForSum-mechanicalFrames),[],'all')>1e-13
        error('Cabin:ActualRouting','Post-Frozen mechanical Sum does not match actual branches.');
    end
end
if ~isreal(pcm) || any(~isfinite(pcm),'all') || ~any(pcm~=0,'all') || any(abs(pcm)>1,'all')
    error('Cabin:PCM','Final PCM safety failed; capture retained.');
end
delta=abs(diff(pcm));maxJump=max(delta,[],'all');boundary=max(delta(960:960:end,:),[],'all');
if maxJump>cfg.screening.sample_jump_max || boundary>cfg.screening.frame_jump_max
    error('Cabin:Continuity','Final PCM continuity failed; capture retained.');
end
pcmPath=fullfile(directory,'candidate.pcm.f64le');fid=fopen(pcmPath,'wb','ieee-le');
if fid<0,error('Cabin:IO','Cannot write PCM.');end;closer=onCleanup(@()fclose(fid));fwrite(fid,pcm.','double');clear closer;
wavPath=fullfile(directory,'candidate.wav');audiowrite(wavPath,pcm,48000,'BitsPerSample',24);
[back,fs]=audioread(wavPath);info=audioinfo(wavPath);
if fs~=48000 || info.BitsPerSample~=24 || ~isequal(size(back),size(pcm)) || max(abs(back-pcm),[],'all')>2^-23+eps
    error('Cabin:WAV','PCM24 readback failed; capture retained.');
end
if voice=="B0" && startsWith(label,"short-")
    prior=fopen(fullfile(fileparts(cfg.reference.capture_mat),'candidate.pcm.f64le'),'rb','ieee-le');
    if prior<0,error('Cabin:Reference','Prior PCM absent.');end;closer=onCleanup(@()fclose(prior));
    original=fread(prior,numel(pcm),'*double');clear closer;
    if ~isequal(original,reshape(pcm.',[],1)),error('Cabin:B0Prefix','B0 differs from original B PCM prefix.');end
elseif voice=="B0" && n==4500 && sha(pcmPath)~=string(cfg.reference.pcm_sha256)
    error('Cabin:B0Exact','B0 does not reproduce original B PCM SHA.');
end
if voice=="B0",sourcePressure=frameData(logs.getElement('source_packet').Values,960,1,time);
else,sourcePressure=preFrames;end
actualFrozen=frameData(logs.getElement('frozen_output').Values,960,1,time);
context=[];frozenError=0;
for j=1:n
    [expected,context]=s12_v12_apply_frozen_radiation_frame(sourcePressure(:,:,j),context,48000);
    frozenError=max(frozenError,max(abs(expected-actualFrozen(:,:,j))));
end
if frozenError>1e-14,error('Cabin:FrozenSequence','Observed Frozen output differs from sequential state reference.');end
preBinary=exportBinary(fullfile(directory,'pre_frozen.f64le'),sourcePressure(:));
frozenBinary=exportBinary(fullfile(directory,'frozen_output.f64le'),actualFrozen(:));
if voice=="B0",mechanicalBinary=[];
else,mechanicalBinary=exportBinary(fullfile(directory,'mechanical_stem.f64le'),mechanicalFrames(:));end
result=struct('label',label,'voice',voice,'frame_count',n,'actual_control_matches',true, ...
    'logged_signals',names,'radiation_evaluation_times',radiationTimes,'sequential_frozen_max_error',frozenError, ...
    'initialization_probes',probeTrace, ...
    'pre_frozen',preBinary,'frozen_output',frozenBinary,'mechanical_stem',mechanicalBinary, ...
    'capture_path',capturePath,'capture_sha256',sha(capturePath),'pcm_path',pcmPath,'pcm_sha256',sha(pcmPath), ...
    'wav_path',wavPath,'wav_sha256',sha(wavPath),'maximum_sample_jump',maxJump, ...
    'maximum_frame_jump',boundary,'peak',max(abs(pcm),[],'all'),'model_sha256',sha(modelPath));
writeNewJson(fullfile(directory,'receipt.json'),result);
end

function result=verifyContrasts(runRoot,prefix)
prefix=string(prefix);names=["N","M","D","MD"];pre=cell(1,4);stem=cell(1,4);pcm=cell(1,4);
for j=1:4
    directory=fullfile(runRoot,prefix+names(j));
    pre{j}=readBinary(fullfile(directory,'pre_frozen.f64le'),1);
    stem{j}=readBinary(fullfile(directory,'mechanical_stem.f64le'),1);
    pcm{j}=readBinary(fullfile(directory,'candidate.pcm.f64le'),2);
end
if ~isequal(pre{1},pre{2}) || ~isequal(pre{3},pre{4})
    error('Cabin:ContrastPreFrozen','N/M or D/MD pre-Frozen inputs differ.');
end
if any(stem{1}~=0) || any(stem{3}~=0) || ~isequal(stem{2},stem{4})
    error('Cabin:ContrastMechanical','Mechanical stems do not match the declared matrix.');
end
expected=repmat(.1*stem{2},2,1);
mError=max(abs((pcm{2}-pcm{1})-expected),[],'all');
mdError=max(abs((pcm{4}-pcm{3})-expected),[],'all');
if ~isfinite(mError) || ~isfinite(mdError) || mError>1e-13 || mdError>1e-13
    error('Cabin:ContrastPCM','Rendered M-N or MD-D differs from the calibrated mechanical stem.');
end
result=struct('N_M_pre_frozen_exact',true,'D_MD_pre_frozen_exact',true, ...
    'M_N_mechanical_max_error',mError,'MD_D_mechanical_max_error',mdError, ...
    'mechanical_gain_domain','stem is post-Frozen pre-renderer; PCM expected 0.1 * stem');
end
function value=readBinary(path,channels)
fid=fopen(path,'rb','ieee-le');if fid<0,error('Cabin:IO','Cannot read %s.',path);end
closer=onCleanup(@()fclose(fid));value=fread(fid,[channels Inf],'*double');
if isempty(value) || any(~isfinite(value),'all'),error('Cabin:IO','Invalid binary data: %s.',path);end
end
function result=exportBinary(path,data)
if isfile(path),error('Cabin:OutputExists','Binary already exists: %s',path);end
fid=fopen(path,'wb','ieee-le');if fid<0,error('Cabin:IO','Cannot write %s.',path);end
closer=onCleanup(@()fclose(fid));fwrite(fid,data,'double');clear closer;
result=struct('path',path,'sha256',sha(path),'samples',numel(data),'dtype','float64-le');
end

function data=frameData(signal,rows,columns,time)
n=numel(time);data=signal.Data;
if numel(signal.Time)~=n || any(abs(signal.Time(:)-time)>1e-10),error('Cabin:LogTime','Log timestamps differ.');end
if size(data,1)==n && signal.IsTimeFirst
    if columns==1,data=reshape(data.',rows,1,n);else,data=permute(data,[2 3 1]);end
end
if size(data,1)~=rows || size(data,2)~=columns || size(data,3)~=n || numel(data)~=rows*columns*n || any(~isfinite(data),'all')
    error('Cabin:LogShape','Unexpected actual signal shape or contents.');
end
end
function stop=radiationTrace(packed)
assignin('base','cabin_radiation_times',[evalin('base','cabin_radiation_times');packed(end)]);stop=false;
end
function logOutput(block,name)
h=get_param(block,'PortHandles');logPort(h.Outport(1),name);
end
function logPort(port,name)
set_param(port,'DataLogging','on','DataLoggingNameMode','Custom','DataLoggingName',name);
end
function path=singleBlock(model,name)
blocks=find_system(model,'SearchDepth',1,'Name',name);
if numel(blocks)~=1,error('Cabin:SavedTopology','Expected one %s.',name);end;path=blocks{1};
end
function value=captureCall(call,logPath)
value=[];failure=[];output=evalc('try, value=call(); catch caught, failure=caught; end');
if isfile(logPath),error('Cabin:OutputExists','Log already exists: %s',logPath);end
fid=fopen(logPath,'w','n','UTF-8');if fid<0,error('Cabin:IO','Cannot write log.');end
closer=onCleanup(@()fclose(fid));fprintf(fid,'%s',output);clear closer;
if ~isempty(failure),rethrow(failure);end
end
function pre=loadPreflight(runRoot)
path=fullfile(runRoot,'preflight.json');if ~isfile(path),error('Cabin:Preflight','Successful preflight required.');end
pre=jsondecode(fileread(path));
cal=jsondecode(fileread(fullfile(runRoot,'calibration.json')));
if string(pre.status)~="PREFLIGHT_PASS_LONG_AND_COLD_NOT_RUN" || ...
        sha(fullfile(runRoot,'calibration.json'))~=string(pre.calibration_sha256) || ...
        ~isequal(pre.calibration.k,cal.k) || ~isfinite(cal.k) || cal.k<=0
    error('Cabin:Preflight','Preflight or frozen calibration changed.');
end
end
function verifyReference(cfg,legacy)
if sha(cfg.reference.capture_mat)~=string(cfg.reference.capture_mat_sha256) || ...
        sha(fullfile(fileparts(cfg.reference.capture_mat),'candidate.pcm.f64le'))~=string(cfg.reference.pcm_sha256) || ...
        sha(fullfile(legacy,'EXPERIMENT_CONTRACT.json'))~=string(cfg.reference.baseline_contract_sha256) || ...
        sha(fullfile(legacy,'isolated','S12_hellcat_2022_stock_v12_rumble_mechanics.slx'))~=string(cfg.reference.baseline_model_sha256)
    error('Cabin:ProtectedHash','A protected native B input changed.');
end
end
function snapshot=dependencies(lab,root,legacy)
paths=[fullfile(lab,'EXPERIMENT_CONTRACT.json');fullfile(lab,'mb_source_step.m');fullfile(lab,'mb_path_step.m'); ...
    fullfile(lab,'mb_receiver_step.m');fullfile(lab,'mb_runtime_probe.m');fullfile(lab,'mb_b0_step.m'); ...
    fullfile(lab,'private','mb_is_initial_probe.m');fullfile(lab,'private','mb_source_frame.m'); ...
    fullfile(lab,'private','mb_identity_frame.m');fullfile(lab,'private','mb_event_modal_frame.m'); ...
    fullfile(lab,'private','mb_bank_network_frame.m');fullfile(lab,'private','mb_step_gate.m'); ...
    fullfile(lab,'calibrate_cabin_candidate.m');fullfile(lab,'build_cabin_candidate.m');fullfile(lab,'start_cabin_async.m'); ...
    fullfile(lab,'test_cabin_source.m');fullfile(lab,'test_cabin_paths.m');fullfile(lab,'test_approved_cabin_steps.m'); ...
    fullfile(lab,'run_cabin_candidate.m');string(jsondecode(fileread(fullfile(lab,'cabin-build-receipt.json'))).model); ...
     string(jsondecode(fileread(fullfile(lab,'cabin-build-receipt.json'))).baseline_copy); ...
    fullfile(legacy,'s12_v12_model_rumble_mechanics_step.m'); ...
    fullfile(legacy,'rumble_pressure_color_frame.m');fullfile(legacy,'EXPERIMENT_CONTRACT.json'); ...
    fullfile(legacy,'isolated','S12_hellcat_2022_stock_v12_rumble_mechanics.slx'); ...
    fullfile(root,'tools','sound_sim','s12','benchmark','baselines','sprint-4d-b','radiation-boundary-package.json')];
vehicle=fullfile(root,'tools','sound_sim','s12','playground_v12','vehicles','hellcat_2022_stock');
paths=[paths;fullfile(vehicle,'source_profile.json');fullfile(vehicle,'engine_identity_profile.json'); ...
    fullfile(vehicle,'scenario_profile.json');fullfile(vehicle,'S12_hellcat_2022_stock_v12.slx')];
common=fullfile(root,'tools','sound_sim','s12','playground_v12','common');
files=[dir(fullfile(common,'*.m'));dir(fullfile(common,'shared_model','*.slx'))];
for j=1:numel(files),paths(end+1,1)=string(fullfile(files(j).folder,files(j).name));end
paths=unique(paths,'stable');
snapshot=cell(numel(paths),1);
for j=1:numel(paths)
    path=string(paths(j));[~,name,ext]=fileparts(path);resolved={};
    if ext==".m" && ~contains(path,filesep+"private"+filesep)
        resolved=cellstr(which(name,'-all'));
        if isempty(resolved) || ~strcmpi(string(java.io.File(resolved{1}).getCanonicalPath()), ...
                string(java.io.File(char(path)).getCanonicalPath()))
            error('Cabin:FunctionResolution','Unexpected MATLAB resolution for %s.',path);
        end
    end
    snapshot{j}=struct('path',path,'sha256',sha(path),'which_all',{resolved});
end
end
function verifyDependencies(snapshot)
for j=1:numel(snapshot)
    item=snapshot(j);if iscell(snapshot),item=snapshot{j};end
    if sha(item.path)~=string(item.sha256),error('Cabin:DependencyHash','Dependency changed: %s',item.path);end
    [~,name,ext]=fileparts(string(item.path));
    if ext==".m" && ~contains(string(item.path),filesep+"private"+filesep)
        actual=string(cellstr(which(name,'-all')));expected=string(item.which_all);
        if ~isequal(actual(:),expected(:))
            error('Cabin:FunctionResolution','MATLAB function resolution changed: %s.',item.path);
        end
    end
end
end
function result=processIdentity()
runtime=java.lang.management.ManagementFactory.getRuntimeMXBean();
result=struct('pid',feature('getpid'),'start_ms',double(runtime.getStartTime()));
end
function value=sha(path)
fid=fopen(path,'rb');if fid<0,error('Cabin:IO','Cannot read %s.',path);end
closer=onCleanup(@()fclose(fid));digest=java.security.MessageDigest.getInstance('SHA-256');
digest.update(fread(fid,Inf,'*uint8'));value=string(lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[])));
end
function writeNewJson(path,value)
if isfile(path),error('Cabin:OutputExists','Receipt exists: %s',path);end
fid=fopen(path,'w','n','UTF-8');if fid<0,error('Cabin:IO','Cannot write receipt.');end
closer=onCleanup(@()fclose(fid));fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));
end
