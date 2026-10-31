function frame = mb_formal_source_bank_modal_step(packet,mode)
% Isolated source -> dual-bank network -> event/modal adapter for the formal SLX.
if nargin<2, mode="MD"; end
mode=string(mode);
if ~ismember(mode,["N","M","D","MD"]), error('Cabin:FormalMode','Unsupported formal mode.'); end
persistent profile sourceState bankState modalState lastTime phases
if ~isa(packet,'double') || ~isreal(packet) || ~isequal(size(packet),[9 1]) || any(~isfinite(packet))
    error('Cabin:FormalPacket','Expected one finite native double 9x1 packet.');
end
time=packet(9);
if isempty(lastTime) || time<=lastTime
    sourceState=[]; bankState=[]; modalState=[]; profile=[]; phases=[];
end
if isempty(profile)
    lab=fileparts(mfilename('fullpath')); project=fileparts(fileparts(lab));
    raw=jsondecode(fileread(fullfile(project,'tools','sound_sim','s12','playground_v12', ...
        'vehicles','hellcat_2022_stock','source_profile.json')));
    profile=raw;
    phases=s12_v12_validate_source_profile(raw).firing_phases_deg;
end
if time==0 && all(packet==0)
    frame=zeros(960,1); return
end
kinds=["none","upshift_bark","downshift_blip_pop","overrun_crackle"];
code=packet(7)+1;
if code~=fix(code) || code<1 || code>4, error('Cabin:FormalAfterfire','Invalid afterfire code.'); end
state=struct('rpm',packet(1),'load',packet(2),'throttle',packet(3), ...
    'acceleration',packet(4),'shift_event',packet(5),'shift_progress',packet(6), ...
    'afterfire_kind',kinds(code),'afterfire_progress',packet(8));
options=struct('enabled',true,'cut_minimum',.35,'whine_scale',1,'induction_scale',1, ...
    'voicing_rpm_band',[2000 3500],'mechanical_gain',1,'mechanical_mod_depth',0);
[banks,sourceState,~,parts]=mb_source_frame(state,profile,sourceState,48000,960, ...
    'hellcat_2022_stock',options,true);
if mode=="N" || mode=="M"
    frame=s12_v12_mix_bank_excitation(banks);
else
    [frame,bankState]=mb_bank_network_frame(banks,bankState,struct());
end
if mode=="M" || mode=="MD"
    [~,modal,modalState]=mb_event_modal_frame(parts.cycle_phase,parts.rpm,parts.load,48000,modalState,phases);
    frame=frame+modal;
end
if ~isequal(size(frame),[960 1]) || any(~isfinite(frame)), error('Cabin:FormalFrame','Invalid formal frame.'); end
lastTime=time;
end
