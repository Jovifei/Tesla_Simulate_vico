function drive=compile_listening_drive(contractPath)
%COMPILE_LISTENING_DRIVE Coherent virtual speed/ratio state, not OEM telemetry.
try, cfg=jsondecode(fileread(contractPath)); catch, fail('Cannot read listening contract.'); end
if cfg.duration_seconds~=90 || cfg.frame_time_s~=.02 || cfg.frame_samples~=960 || cfg.sample_rate_hz~=48000
    fail('Unsupported frame or duration contract.');
end
ratios=double(cfg.gear_ratios(:));
knots=double(cfg.speed_knots_s(:)); values=double(cfg.speed_knots_mps(:));
if numel(ratios)<2 || any(~isfinite(ratios) | ratios<=0) || any(diff(ratios)>=0) || ...
        numel(knots)~=numel(values) || numel(knots)<2 || knots(1)~=0 || knots(end)~=90 || ...
        any(~isfinite(knots)) || any(diff(knots)<=0) || any(~isfinite(values) | values<0) || ...
        ~isscalar(cfg.wheel_radius_m) || cfg.wheel_radius_m<=0 || ~isfinite(cfg.wheel_radius_m) || ...
        ~isscalar(cfg.final_drive) || cfg.final_drive<=0 || ~isfinite(cfg.final_drive)
    fail('Speed or virtual drivetrain assumptions are invalid.');
end
time=(0:4499)'*.02; count=numel(time);
speed=zeros(count,1); acceleration=speed;
for segment=1:numel(knots)-1
    selected=time>=knots(segment) & time<knots(segment+1);
    span=knots(segment+1)-knots(segment); u=(time(selected)-knots(segment))/span;
    delta=values(segment+1)-values(segment);
    speed(selected)=values(segment)+delta*(3*u.^2-2*u.^3);
    acceleration(selected)=delta/span*6*u.*(1-u);
end
gear=ones(count,1); effectiveRatio=ratios(1)*ones(count,1);
shift=zeros(count,1); progress=shift;
events=reshape(cfg.events,1,[]);
lastEnd=-.02; lastGear=1;
for index=1:numel(events)
    event=events(index);
    grid=[event.start_s,event.duration_s]/.02;
    if any(~isfinite(grid)) || any(abs(grid-round(grid))>1e-8) || event.duration_s<.04 || ...
            event.start_s<lastEnd+.02 || event.start_s+event.duration_s>=90 || ...
            event.from_gear~=lastGear || any([event.from_gear,event.to_gear]~=fix([event.from_gear,event.to_gear])) || ...
            event.to_gear<1 || event.to_gear>numel(ratios) || abs(event.to_gear-event.from_gear)~=1
        fail('Events must be ordered, complete, nonoverlapping adjacent-gear changes.');
    end
    first=round(event.start_s/.02)+1; frames=round(event.duration_s/.02);
    active=first:first+frames-1; after=first+frames;
    p=linspace(0,1,frames)'; blend=3*p.^2-2*p.^3;
    effectiveRatio(first:end)=ratios(event.to_gear);
    effectiveRatio(active)=ratios(event.from_gear)+(ratios(event.to_gear)-ratios(event.from_gear))*blend;
    gear(first:end)=event.to_gear;gear(active)=event.from_gear;
    kind=sign(event.to_gear-event.from_gear);
    shift(active)=kind;progress(active)=p;
    events(index).kind=kind;events(index).end_s=event.start_s+event.duration_s;
    events(index).first_frame=first;events(index).last_frame=after-1;
    lastEnd=events(index).end_s;lastGear=event.to_gear;
end
factor=60/(2*pi*cfg.wheel_radius_m)*cfg.final_drive;
lockedRpm=factor*speed.*effectiveRatio;
rpm=max(cfg.idle_rpm,lockedRpm);
slip=lockedRpm<cfg.idle_rpm | shift~=0;
load=min(.95,max(.08,.12+.25*max(acceleration,0)+.005*speed));
throttle=min(1,max(.03,.06+.30*max(acceleration,0)+.003*speed));
coast=acceleration<-.2;load(coast)=.08+.002*speed(coast);throttle(coast)=.03;
if any(rpm>12000 | ~isfinite(rpm)) || any(abs(acceleration)>20)
    fail('Compiled state exceeds the existing source input limits.');
end
for index=1:numel(events)
    first=events(index).first_frame;after=events(index).last_frame+1;
    events(index).rpm_before=rpm(first);
    events(index).rpm_after=rpm(after);
    events(index).speed_before=speed(first);events(index).speed_after=speed(after);
    if events(index).kind*(rpm(first)-rpm(after))<=0
        fail('The declared shift does not produce its required RPM movement.');
    end
end
state=[rpm,load,throttle,acceleration,shift,progress,zeros(count,2),time];
drive=struct('time',time,'state',state,'speed_mps',speed,'acceleration_mps2',acceleration, ...
    'gear',gear,'effective_ratio',effectiveRatio,'slip',slip,'events',events, ...
    'parameter_status','RESEARCH_ASSUMPTIONS_NOT_OEM_CALIBRATION');
end

function fail(message)
error('S12:Listening:Drive','%s',message);
end
