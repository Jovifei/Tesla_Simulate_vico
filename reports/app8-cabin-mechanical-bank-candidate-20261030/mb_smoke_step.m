function [frame,report]=mb_smoke_step(packet,action)
% Minimal diagnostic ONLY: exercises private functions, not the final signal path.
persistent cfg profile modalPhases sourceState bankState modalState lastPacket lastFrame lastIndex times duplicates peaks
if nargin<2,action='step';end
action=string(action);report=[];
if action=="reset"
    cfg=[];profile=[];modalPhases=[];sourceState=[];bankState=[];modalState=[];lastPacket=[];lastFrame=[];
    lastIndex=[];times=[];duplicates=0;peaks=[];frame=[];return
end
if action=="report"
    frame=[];report=struct('frame_count',numel(peaks),'evaluation_times',times, ...
        'duplicate_count',duplicates,'frame_peaks',peaks,'diagnostic_only',true);return
end
if action~="step" || ~isa(packet,'double') || ~isreal(packet) || ...
        ~isequal(size(packet),[9 1]) || any(~isfinite(packet))
    error('Cabin:SmokePacket','Expected one finite native double 9x1 packet.');
end
time=packet(9);index=round(time/.02);
if time<0 || abs(time-index*.02)>1e-10,error('Cabin:SmokePacket','Time is not on the 20 ms frame grid.');end
% Simulink evaluates a root MATLAB Function once with an all-zero init packet
% before loading the first external-input sample at the same simulation time.
% Keep that probe silent; real repeated packets remain fail-closed below.
if isempty(lastIndex) && index==0 && all(packet==0)
    frame=zeros(960,1);return
end
if ~isempty(lastIndex) && index==lastIndex
    if ~isequal(packet,lastPacket)
        error('Cabin:SmokeDuplicate','Repeated time has changed input: last=%s current=%s.', ...
            mat2str(lastPacket.'),mat2str(packet.'));
    end
    times(end+1,1)=time;duplicates=duplicates+1;frame=lastFrame;return
end
if isempty(lastIndex),expected=0;else,expected=lastIndex+1;end
if index~=expected,error('Cabin:SmokeOrder','Missing, reordered, or unreset frame.');end
if isempty(profile)
    lab=fileparts(mfilename('fullpath'));project=fileparts(fileparts(lab));
    profile=jsondecode(fileread(fullfile(project,'tools','sound_sim','s12','playground_v12','vehicles','hellcat_2022_stock','source_profile.json')));
    modalPhases=s12_v12_validate_source_profile(profile).firing_phases_deg;
    cfg=struct('enabled',true,'cut_minimum',.35,'whine_scale',1,'induction_scale',1, ...
        'voicing_rpm_band',[2000 3500],'mechanical_gain',1,'mechanical_mod_depth',0);
end
kinds=["none","upshift_bark","downshift_blip_pop","overrun_crackle"];code=packet(7)+1;
if code~=fix(code) || code<1 || code>4,error('Cabin:SmokePacket','Invalid afterfire enum.');end
state=struct('rpm',packet(1),'load',packet(2),'throttle',packet(3),'acceleration',packet(4), ...
    'shift_event',packet(5),'shift_progress',packet(6),'afterfire_kind',kinds(code),'afterfire_progress',packet(8));
[~,sourceState,~,parts]=mb_source_frame(state,profile,sourceState,48000,960,'hellcat_2022_stock',cfg,true);
[network,bankState]=mb_bank_network_frame(parts.combustion_raw,bankState,struct());
[~,modal,modalState]=mb_event_modal_frame(parts.cycle_phase,parts.rpm,parts.load,48000,modalState,modalPhases);
frame=network+modal;
if ~isequal(size(frame),[960 1]) || any(~isfinite(frame)),error('Cabin:SmokeFrame','Diagnostic frame is invalid.');end
lastPacket=packet;lastFrame=frame;lastIndex=index;times(end+1,1)=time;peaks(end+1,1)=max(abs(frame));
end
