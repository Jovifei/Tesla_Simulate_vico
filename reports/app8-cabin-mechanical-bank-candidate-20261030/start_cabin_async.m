function job = start_cabin_async(stage,runRoot)
% Queue a single timer in the current exclusive MATLAB process and return.
if nargin<1,stage='preflight';end
stage=string(stage);lab=string(fileparts(mfilename('fullpath')));
if ~ismember(stage,["preflight","full","cold"]),error('Cabin:Stage','Unknown async stage.');end
stamp=string(datetime('now','Format','yyyyMMdd-HHmmss-SSS'));
if nargin<2 || strlength(string(runRoot))==0
    if stage~="preflight",error('Cabin:RunRoot','An existing preflight run is required.');end
    runRoot=fullfile(lab,'runs','approved-'+stamp);
else
    runRoot=string(java.io.File(char(runRoot)).getCanonicalPath());
    if ~startsWith(lower(runRoot),lower(lab+filesep)),error('Cabin:RunRoot','Run root is outside lab.');end
end
jobRoot=fullfile(lab,'async-jobs',stamp+'-'+stage);
if isfolder(jobRoot),error('Cabin:OutputExists','Async job already exists.');end
mkdir(jobRoot);
job=struct('status','QUEUED','stage',stage,'job_root',jobRoot,'run_root',runRoot, ...
    'matlab_pid',feature('getpid'),'matlab_version',version, ...
    'started_marker',fullfile(jobRoot,'started.json'),'complete_marker',fullfile(jobRoot,'complete.json'), ...
    'failure_marker',fullfile(jobRoot,'failure.json'),'console_log',fullfile(jobRoot,'console.log'));
writeNewJson(fullfile(jobRoot,'queued.json'),job);
worker=timer('ExecutionMode','singleShot','StartDelay',5, ...
    'TimerFcn',@(~,~)executeJob(job),'StopFcn',@(t,~)delete(t), ...
    'ErrorFcn',@(~,event)timerError(job,event));
start(worker);
end

function executeJob(job)
started=job;started.status='RUNNING';started.started_at=string(datetime('now'));
writeNewJson(job.started_marker,started);
result=[];failure=[];
output=evalc('try, result=run_cabin_candidate(job.stage,job.run_root); catch caught, failure=caught; end');
fid=fopen(job.console_log,'w','n','UTF-8');
if fid<0,error('Cabin:IO','Cannot write asynchronous console log.');end
closer=onCleanup(@()fclose(fid));fprintf(fid,'%s',output);clear closer;
if isempty(failure)
    done=job;done.status=string(result.status);done.finished_at=string(datetime('now'));
    writeNewJson(job.complete_marker,done);
else
    failed=job;failed.status='FAILED';failed.error_id=string(failure.identifier);
    failed.error=string(getReport(failure,'extended','hyperlinks','off'));failed.finished_at=string(datetime('now'));
    writeNewJson(job.failure_marker,failed);
end
end
function timerError(job,event)
path=fullfile(job.job_root,'timer-error.json');
detail=string(evalc('disp(event.Data)'));
if ~isfile(path),writeNewJson(path,struct('status','TIMER_ERROR','detail',detail));end
end
function writeNewJson(path,value)
if isfile(path),error('Cabin:OutputExists','Async marker exists: %s',path);end
fid=fopen(path,'w','n','UTF-8');if fid<0,error('Cabin:IO','Cannot write async marker.');end
closer=onCleanup(@()fclose(fid));fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));
end
