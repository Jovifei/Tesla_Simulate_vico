function [frame, report] = mb_source_step(packet)
% Output [combustion L/R, other L/R, phase, rpm, load, cut, sample time].
persistent gate sourceContext profile history
report=[];
if ischar(packet) || isstring(packet)
    switch string(packet)
        case "reset"
            gate=[];sourceContext=[];profile=[];history=zeros(0,4);frame=[];return
        case "report"
            frame=[];report=gate;if isempty(report),report=struct('frames',0,'duplicates',0);end
            report.frame_states=history;report.source_context=sourceContext;return
        otherwise,error('Cabin:Command','Unknown source command.');
    end
end
if ~isa(packet,'double') || ~isreal(packet) || ~isequal(size(packet),[9 1]) || any(~isfinite(packet))
    error('Cabin:SourceInput','Expected a finite native double 9x1 packet.');
end
alreadyAdvanced=~isempty(gate) && gate.frames>0;
if mb_runtime_probe('source',packet,alreadyAdvanced)
    frame=[zeros(960,8),(0:959)'/48000];return
end
t=packet(9);[gate,duplicate,newRun]=mb_step_gate(gate,t,packet);
if newRun,sourceContext=[];end
if duplicate,frame=gate.last_output;return;end
if isempty(profile)
    root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
    profile=jsondecode(fileread(fullfile(root,'tools','sound_sim','s12','playground_v12', ...
        'vehicles','hellcat_2022_stock','source_profile.json')));
    history=zeros(0,4);
end
kinds=["none","upshift_bark","downshift_blip_pop","overrun_crackle"];code=packet(7)+1;
if code~=fix(code) || code<1 || code>4,error('Cabin:SourceInput','Invalid afterfire code.');end
state=struct('rpm',packet(1),'load',packet(2),'throttle',packet(3),'acceleration',packet(4), ...
    'shift_event',packet(5),'shift_progress',packet(6),'afterfire_kind',kinds(code),'afterfire_progress',packet(8));
options=struct('enabled',true,'cut_minimum',.35,'whine_scale',1,'induction_scale',1, ...
    'voicing_rpm_band',[2000 3500],'mechanical_gain',1,'mechanical_mod_depth',0);
phaseBefore=0;if ~isempty(sourceContext),phaseBefore=sourceContext.cycle_phase_rad;end
[~,sourceContext,~,parts]=mb_source_frame(state,profile,sourceContext,48000,960, ...
    'hellcat_2022_stock',options,true);
frame=[parts.combustion_raw,parts.other_raw,parts.cycle_phase,parts.rpm,parts.load,parts.cut, ...
    t+(0:959)'/48000];
if ~isequal(size(frame),[960 9]) || any(~isfinite(frame),'all')
    error('Cabin:SourceFrame','Invalid packaged source frame.');
end
history(end+1,:)=[t sourceContext.frame_index phaseBefore sourceContext.cycle_phase_rad];
gate.last_time=t;gate.last_key=packet;gate.last_output=frame;gate.frames=gate.frames+1;
end
