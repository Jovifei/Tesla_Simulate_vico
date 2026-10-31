function result = calibrate_cabin_candidate(outputPath)
% One 2200/.35/.32 calibration. outputPath must be new and inside the lab.
lab=string(fileparts(mfilename('fullpath')));root=fileparts(fileparts(lab));
outputPath=string(java.io.File(char(outputPath)).getCanonicalPath());
if ~startsWith(lower(outputPath),lower(lab+filesep)) || isfile(outputPath)
    error('Cabin:CalibrationOutput','Calibration receipt must be a new file inside the lab.');
end
profile=jsondecode(fileread(fullfile(root,'tools','sound_sim','s12','playground_v12', ...
    'vehicles','hellcat_2022_stock','source_profile.json')));
options=struct('enabled',true,'cut_minimum',.35,'whine_scale',1,'induction_scale',1, ...
    'voicing_rpm_band',[2000 3500],'mechanical_gain',1,'mechanical_mod_depth',0);
state=struct('rpm',2200,'load',.35,'throttle',.32,'acceleration',0,'shift_event',0, ...
    'shift_progress',0,'afterfire_kind','none','afterfire_progress',0);
source=[];modal=[];frozen=[];dcIn=[0 0];dcOut=[0 0];old=zeros(288000,1);fresh=old;
for j=1:300
    [~,source,~,p]=mb_source_frame(state,profile,source,48000,960,'hellcat_2022_stock',options,false);
    raw=p.old_mechanical_raw;filtered=zeros(size(raw));
    for n=1:960
        filtered(n,:)=raw(n,:)-dcIn+.995*dcOut;dcIn=raw(n,:);dcOut=filtered(n,:);
    end
    [reference,frozen]=s12_v12_apply_frozen_radiation_frame(.5*(filtered(:,1)+filtered(:,2)),frozen,48000);
    [~,mechanical,modal]=mb_event_modal_frame(p.cycle_phase,p.rpm,p.load,48000,modal,0:90:630);
    indices=(j-1)*960+(1:960);old(indices)=.1*reference;fresh(indices)=.1*mechanical;
end
window=48001:240000;oldRms=sqrt(mean(old(window).^2));newRms=sqrt(mean(fresh(window).^2));
[folder,~,~]=fileparts(outputPath);oldPath=fullfile(folder,'calibration-old-reference.f64le');
newPath=fullfile(folder,'calibration-new-unscaled.f64le');
writeBinary(oldPath,old);writeBinary(newPath,fresh);
if ~isfinite(oldRms) || ~isfinite(newRms) || oldRms<=0 || newRms<=0
    error('Cabin:CalibrationSafety','Calibration RMS is zero or nonfinite; no gain rescue allowed.');
end
k=oldRms/newRms;
if ~isfinite(k) || k<=0 || any(~isfinite(k*fresh),'all') || max(abs(k*fresh))>1
    error('Cabin:CalibrationSafety','Calibrated mechanical reference is unsafe.');
end
result=struct('status','CALIBRATED_COMBINED_PCM_GATE_PENDING','rpm',2200,'load',.35,'throttle',.32, ...
    'window_s',[1 5],'old_reference_rms',oldRms,'new_unscaled_rms',newRms,'k',k, ...
    'old_reference_peak',max(abs(old)),'new_scaled_peak',max(abs(k*fresh)), ...
    'old_reference_path',oldPath,'old_reference_sha256',sha(oldPath), ...
    'new_unscaled_path',newPath,'new_unscaled_sha256',sha(newPath), ...
    'wave_dtype','float64-le','samples',numel(old),'window_one_based_inclusive',[48001 240000], ...
    'qualification','dimensionless self-reference, not vehicle acoustic calibration');
fid=fopen(outputPath,'w','n','UTF-8');if fid<0,error('Cabin:CalibrationOutput','Cannot write calibration receipt.');end
cleanup=onCleanup(@()fclose(fid));fprintf(fid,'%s\n',jsonencode(result,PrettyPrint=true));
end
function writeBinary(path,data)
if isfile(path),error('Cabin:OutputExists','Calibration waveform exists: %s',path);end
fid=fopen(path,'wb','ieee-le');if fid<0,error('Cabin:IO','Cannot write calibration waveform.');end
cleanup=onCleanup(@()fclose(fid));fwrite(fid,data,'double');
end
function value=sha(path)
fid=fopen(path,'rb');if fid<0,error('Cabin:IO','Cannot read calibration waveform.');end
cleanup=onCleanup(@()fclose(fid));digest=java.security.MessageDigest.getInstance('SHA-256');
digest.update(fread(fid,Inf,'*uint8'));value=string(lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[])));
end
