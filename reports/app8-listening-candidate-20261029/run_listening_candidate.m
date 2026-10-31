function summary=run_listening_candidate(contractPath,mode)
% Actual A/B/C model experiment; measured screening is performed separately.
if nargin<2,mode="smoke";end
mode=string(mode);if ~ismember(mode,["smoke","full"]),error("S12:Listening:Run","Invalid run mode.");end
lab=string(fileparts(mfilename("fullpath")));project=fileparts(fileparts(lab));
common=fullfile(project,"tools","sound_sim","s12","playground_v12","common");
addpath(lab,common,fullfile(common,"shared_model"));
cfg=jsondecode(fileread(contractPath));contractHash=sha(contractPath);
Simulink.fileGenControl("set","CacheFolder",lab+"/cache","CodeGenFolder",lab+"/codegen","createDir",true);
artifactPath=lab+"/build-receipt.json";
if ~isfile(artifactPath),build_listening_candidate(contractPath,true);end
artifact=jsondecode(fileread(artifactPath));
if sha(artifact.candidate)~=string(artifact.candidate_sha256) || contractHash~=string(artifact.contract_sha256)
    error("S12:Listening:Run","Candidate or frozen contract changed.");
end
run=lab+"/runs/"+mode+"-"+string(datetime('now','Format','yyyyMMdd-HHmmss'));
if isfolder(run),error("S12:Listening:Run","Refusing to overwrite results.");end
mkdir(run);drive=compile_listening_drive(contractPath);
if mode=="smoke",count=700;else,count=4500;end
drive.time=drive.time(1:count);drive.state=drive.state(1:count,:);
drive.speed_mps=drive.speed_mps(1:count);drive.gear=drive.gear(1:count);drive.slip=drive.slip(1:count);
writeDrive(run+"/drive.csv",drive,true);
dependencies=dependencySnapshot(lab,common,project,contractPath);
old=zeros(count,9);
for k=1:count,old(k,:)=s12_v12_model_vehicle_cycle_step(drive.time(k),"hellcat_2022_stock").';end
oldDrive=struct("time",drive.time,"state",old);
summary=struct("status","RUNNING","run_root",run,"contract_path",string(contractPath), ...
    "contract_sha256",contractHash,"drive_csv",run+"/drive.csv","events",drive.events, ...
    "mode",mode,"qualification","CONTROLLED_LISTENING_RESEARCH_NOT_OEM_ACCEPTANCE");
summary.drive_sha256=sha(run+"/drive.csv");summary.dependency_snapshot=dependencies;
try
    fprintf('LISTENING_STAGE A original cycle %gs\n',count*.02);
    summary.cases.A=oneCase("A",string(artifact.source),oldDrive,"A",run+"/A",false,contractPath,dependencies);
    summary.cases.A.control_kind="original_cycle";
    expected="2e809bf2f17e1ea07f9a3e9c1b54027da12d9d09f8cd85f974ce39f66ce2f74d";
    if mode=="full" && summary.cases.A.pcm_sha256~=expected,error("S12:Listening:DefaultDrift","Original default PCM changed.");end
    fprintf('LISTENING_STAGE B coherent shifts %gs\n',count*.02);
    summary.cases.B=oneCase("B",string(artifact.candidate),drive,"B",run+"/B",true,contractPath,dependencies);
    fprintf('LISTENING_STAGE C voiced %gs\n',count*.02);
    summary.cases.C=oneCase("C",string(artifact.candidate),drive,"C",run+"/C",true,contractPath,dependencies);
    fprintf('LISTENING_STAGE C repeat same MATLAB session\n');
    summary.cases.C_repeat=oneCase("C_repeat",string(artifact.candidate),drive,"C",run+"/C_repeat",true,contractPath,dependencies);
    if summary.cases.C.pcm_sha256~=summary.cases.C_repeat.pcm_sha256 || summary.cases.C.wav_sha256~=summary.cases.C_repeat.wav_sha256
        error("S12:Listening:Repeat","Repeated C output differs.");
    end
    referenceJump=summary.cases.A.maximum_frame_jump;
    for name=["B","C","C_repeat"]
        if summary.cases.(name).maximum_sample_jump>cfg.screening.maximum_sample_jump || ...
                summary.cases.(name).maximum_frame_jump>referenceJump+cfg.screening.frame_jump_increase_over_reference_max
            error("S12:Listening:Continuity","Predeclared continuity gate failed.");
        end
    end
    summary.stationary={};
    if mode=="full"
        for anchorIndex=1:numel(cfg.anchors)
            anchor=cfg.anchors(anchorIndex);folder=run+"/stationary/"+string(anchor.name);mkdir(folder);
            time=(0:round(cfg.stationary_seconds/.02)-1)'*.02;n=numel(time);
            state=[repmat([anchor.rpm,anchor.load,anchor.throttle,0,0,0,0,0],n,1),time];
            held=struct("time",time,"state",state);writeDrive(folder+"/drive.csv",held,false);
            fprintf('LISTENING_STAGE anchor %d/%d %gRPM\n',anchorIndex,numel(cfg.anchors),anchor.rpm);
            b=oneCase("B",string(artifact.candidate),held,"B",folder+"/B",true,contractPath,dependencies);
            c=oneCase("C",string(artifact.candidate),held,"C",folder+"/C",true,contractPath,dependencies);
            summary.stationary{anchorIndex}=struct("name",string(anchor.name),"role",string(anchor.role), ...
                "rpm",anchor.rpm,"load",anchor.load,"throttle",anchor.throttle, ...
                "B_directory",b.directory,"C_directory",c.directory,"drive_csv",folder+"/drive.csv", ...
                "drive_sha256",sha(folder+"/drive.csv"),"B_receipt_sha256",b.receipt_sha256,"C_receipt_sha256",c.receipt_sha256);
        end
    end
    if sha(contractPath)~=contractHash || sha(artifact.source)~=string(artifact.source_sha256) || ...
            sha(artifact.candidate)~=string(artifact.candidate_sha256)
        error("S12:Listening:Identity","Source, candidate or contract changed during run.");
    end
    verifyDependencies(dependencies);
    summary.status="RENDERED_DIGITAL_PASS_SCREENING_PENDING";
    writeJson(run+"/run-summary.json",summary);writeJson(lab+"/latest-"+mode+".json",summary);
    fprintf('LISTENING_%s_DIGITAL_PASS %s\n',upper(mode),run);
catch failure
    summary.status="FAILED";summary.error_id=string(failure.identifier);summary.error=string(failure.message);
    writeJson(run+"/failure.json",summary);rethrow(failure);
end
end

function result=oneCase(label,modelPath,input,voice,directory,candidate,contractPath,dependencies)
        cfg=jsondecode(fileread(contractPath));contractHash=sha(contractPath);verifyDependencies(dependencies);
        if isfolder(directory) || isfile(directory),error("S12:Listening:OutputExists","Refusing to overwrite a case directory.");end
        mkdir(directory);n=numel(input.time);[folder,modelName]=fileparts(modelPath);addpath(folder);
        load_system(modelPath);closeModel=onCleanup(@() close_system(modelName,0));
        gain=Simulink.ID.getFullName(modelName+":13");
        if str2double(get_param(gain,"Value"))~=.1,error("S12:Listening:Gain","Renderer gain drifted.");end
        simIn=Simulink.SimulationInput(modelName);
        simIn=simIn.setModelParameter("StopTime",num2str(input.time(end),17), ...
            "SolverType","Fixed-step","Solver","FixedStepDiscrete","FixedStep","0.02", ...
            "SaveOutput","on","OutputSaveName","listening_pcm","SaveFormat","Dataset", ...
            "ReturnWorkspaceOutputs","on","SignalLogging","on","SignalLoggingName","listening_logs");
        source=Simulink.ID.getFullName(modelName+":11");
        if candidate
            expression="s12_v12_model_listening_source_step(u, '"+replace(string(contractPath),"'","''")+"', '"+voice+"')";
            simIn=simIn.setBlockParameter(source,"MATLABFcn",expression);
            ds=Simulink.SimulationData.Dataset;
            signal=timeseries(reshape(input.state.',9,1,n),input.time,"IsTimeFirst",false);signal=setinterpmethod(signal,"zoh");
            ds=ds.addElement(signal,"Listening Vehicle State");simIn=simIn.setExternalInput(ds);
        end
        h=get_param(source,"PortHandles");line=get_param(h.Inport(1),"Line");statePort=get_param(line,"SrcPortHandle");
        set_param(statePort,"DataLogging","on","DataLoggingNameMode","Custom","DataLoggingName","listening_state");
        set_param(h.Outport(1),"DataLogging","on","DataLoggingNameMode","Custom","DataLoggingName","source_pressure");
        radiation=Simulink.ID.getFullName(modelName+":12");h=get_param(radiation,"PortHandles");
        set_param(h.Outport(1),"DataLogging","on","DataLoggingNameMode","Custom","DataLoggingName","radiated_pressure");
        simOut=sim(simIn);logs=simOut.get("listening_logs");
        actualState=reshape(frameData(logs.getElement("listening_state").Values,9,1,input.time),9,n).';
        if ~isequal(actualState,input.state),error("S12:Listening:InputConsumption","Actual model state differs from the supplied packets.");end
        sourcePressure=frameData(logs.getElement("source_pressure").Values,960,1,input.time);
        radiatedPressure=frameData(logs.getElement("radiated_pressure").Values,960,1,input.time);
        output=simOut.get("listening_pcm");if output.numElements~=1,error("S12:Listening:Capture","Expected one PCM output.");end
        frames=frameData(output.getElement(1).Values,960,2,input.time);
        pcm=reshape(permute(frames,[1,3,2]),n*960,2);
        if ~isreal(pcm) || any(~isfinite(pcm),"all") || ~any(pcm~=0,"all") || any(abs(pcm)>1,"all")
            error("S12:Listening:PCM","Final PCM failed finite/real/non-silent/peak contract.");
        end
        writeDrive(directory+"/drive.csv",input,isfield(input,"speed_mps"));
        writematrix(actualState,directory+"/actual_control.csv");
        telemetryPath="";
        if candidate
            [~,telemetry]=s12_v12_model_listening_source_step([],contractPath,"report");
            if telemetry.frame_count~=n || ~isequal(telemetry.values(:,2),(1:n)')
                error("S12:Listening:SourceState","Source context reset or dropped frames inside a run.");
            end
            phaseError=abs(atan2(sin(telemetry.values(2:end,3)-telemetry.values(1:end-1,4)), ...
                cos(telemetry.values(2:end,3)-telemetry.values(1:end-1,4))));
            if any(phaseError>1e-10),error("S12:Listening:Phase","Crank phase reset inside a run.");end
            telemetryPath=directory+"/source-telemetry.csv";
            writetable(array2table(telemetry.values,"VariableNames",cellstr(telemetry.columns)),telemetryPath);
            if any(telemetry.values(:,17)~=telemetry.values(:,18)) || any(telemetry.values(:,19)~=telemetry.values(:,20)) || any(telemetry.values(:,21)~=telemetry.values(:,22))
                error("S12:Listening:SelectiveCut","Whine/mechanical sources were incorrectly cut.");
            end
            if any(input.state(:,5)~=0) && min(telemetry.values(:,5))>cfg.research_options.cut_minimum+.005
                error("S12:Listening:CutNotConsumed","The declared combustion cut was not consumed.");
            end
            if any(telemetry.values(input.state(:,5)==0,5)~=1)
                error("S12:Listening:CutRecovery","Combustion cut remained active outside a shift.");
            end
        end
        pcmPath=directory+"/candidate.pcm.f64le";wavPath=directory+"/candidate.wav";
        fid=fopen(pcmPath,"wb","ieee-le");fwrite(fid,pcm.',"double");fclose(fid);
        audiowrite(wavPath,pcm,48000,"BitsPerSample",24);[back,fs]=audioread(wavPath);info=audioinfo(wavPath);
        quantization=max(abs(back-pcm),[],"all");
        if fs~=48000 || info.BitsPerSample~=24 || ~isequal(size(back),size(pcm)) || quantization>2^-23+eps
            error("S12:Listening:WAV","PCM24 readback failed.");
        end
        delta=abs(diff(pcm));boundary=0;if n>1,boundary=max(delta(960:960:end,:),[],"all");end
        result=struct("label",label,"directory",directory,"drive_csv",directory+"/drive.csv", ...
            "source_telemetry_csv",telemetryPath,"pcm_path",pcmPath,"wav_path",wavPath, ...
            "frame_count",n,"samples_per_channel",n*960,"sample_rate_hz",48000,"channels",2, ...
            "duration_seconds",n*.02,"last_frame_time_s",input.time(end),"actual_control_matches",true, ...
            "peak",max(abs(pcm),[],"all"),"rms",sqrt(mean(pcm.^2,"all")), ...
            "maximum_sample_jump",max(delta,[],"all"),"maximum_frame_jump",boundary, ...
            "wav_quantization_max_error",quantization,"pcm_sha256",sha(pcmPath),"wav_sha256",sha(wavPath), ...
            "model_sha256",sha(modelPath),"contract_sha256",contractHash,"purpose","LISTENING_RESEARCH_NOT_HUMAN_ACCEPTED");
        result.drive_sha256=sha(result.drive_csv);
        result.actual_control_csv=directory+"/actual_control.csv";result.actual_control_sha256=sha(result.actual_control_csv);
        result.source_telemetry_sha256="";if strlength(telemetryPath)>0,result.source_telemetry_sha256=sha(telemetryPath);end
        result.dependency_snapshot=dependencies;result.receipt_path=directory+"/receipt.json";
        verifyDependencies(dependencies);
        save(directory+"/capture.mat","frames","pcm","actualState","sourcePressure","radiatedPressure","result","-v7.3");
        writeJson(directory+"/receipt.json",result);
        result.receipt_sha256=sha(result.receipt_path);
end

function data=frameData(signal,rows,columns,time)
n=numel(time);data=signal.Data;
if numel(signal.Time)~=n || any(abs(signal.Time(:)-time(:))>1e-10),error("S12:Listening:Time","Captured timestamps mismatch.");end
if size(data,1)==n && signal.IsTimeFirst
    if columns==1,data=reshape(data.',rows,1,n);else,data=permute(data,[2,3,1]);end
end
if size(data,1)~=rows || size(data,2)~=columns || size(data,3)~=n || numel(data)~=rows*columns*n || ...
        ~isnumeric(data) || ~isreal(data) || any(~isfinite(data),"all")
    error("S12:Listening:Capture","Captured matrix/frame dimensions mismatch.");
end
end
function writeDrive(path,drive,withSpeed)
names=["time_s","rpm","load","throttle","acceleration","shift_event","shift_progress","afterfire_code","afterfire_progress","source_time_s"];
data=[drive.time,drive.state];
if withSpeed,names=[names,"speed_mps","gear","slip_flag"];data=[data,drive.speed_mps,drive.gear,double(drive.slip)];end
writetable(array2table(data,"VariableNames",cellstr(names)),path);
end
function writeJson(path,value)
fid=fopen(path,"w","n","UTF-8");fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));fclose(fid);
end
function value=sha(path)
fid=fopen(path,"rb");cleanup=onCleanup(@() fclose(fid));d=java.security.MessageDigest.getInstance("SHA-256");
d.update(fread(fid,Inf,"*uint8"));value=string(lower(reshape(dec2hex(typecast(d.digest(),"uint8"),2).',1,[])));
end

function snapshot=dependencySnapshot(lab,common,project,contractPath)
files=[dir(common+"/*.m");dir(lab+"/*.m")];paths=strings(numel(files),1);
for index=1:numel(files),paths(index)=fullfile(files(index).folder,files(index).name);end
vehicle=fullfile(common,"..","vehicles","hellcat_2022_stock");
paths=[paths;string(contractPath);fullfile(vehicle,"source_profile.json"); ...
    fullfile(vehicle,"engine_identity_profile.json");fullfile(vehicle,"scenario_profile.json"); ...
    fullfile(project,"tools","sound_sim","s12","benchmark","baselines","sprint-4d-b","radiation-boundary-package.json")];
paths=sort(paths);snapshot=cell(numel(paths),1);
for index=1:numel(paths)
    path=string(java.io.File(char(paths(index))).getCanonicalPath());
    snapshot{index}=struct("path",path,"sha256",sha(path));
end
end
function verifyDependencies(snapshot)
for index=1:numel(snapshot)
    entry=snapshot{index};
    if ~isfile(entry.path) || sha(entry.path)~=entry.sha256
        error("S12:Listening:DependencyDrift","Executed source/profile/contract dependency changed.");
    end
end
end
