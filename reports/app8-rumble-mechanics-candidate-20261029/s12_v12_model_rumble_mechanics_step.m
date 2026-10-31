function [frame,report]=s12_v12_model_rumble_mechanics_step(packed,contractPath,mode)
% Isolated model source; a repeated evaluation reuses the identical frame.
persistent activePath activeMode cfg profile context filterState lastTime lastPacket lastFrame rows prePressure phases mechanics calls duplicates
if nargin<3,mode='B0';end
mode=string(mode);report=[];
names=["time_s","frame_index","phase_before","phase_after","cut_min","cut_max","cut_mean", ...
    "whine_scale","induction_scale","voicing_activation","combustion_before","combustion_after", ...
    "orders_before","orders_after","identity_exhaust_before","identity_exhaust_after", ...
    "identity_whine_before","identity_whine_after","identity_mechanical_before","identity_mechanical_after", ...
    "mechanical_before","mechanical_after","mechanics_source_before","mechanics_source_after", ...
    "mechanics_identity_before","mechanics_identity_after","multiplier_min","multiplier_max"];
if mode=="report"
    if isempty(rows)
        frame=[];report=struct('columns',names,'values',zeros(0,numel(names)),'frame_count',0, ...
            'evaluation_count',0,'evaluation_times',zeros(0,1),'duplicate_count',0, ...
            'pre_pressure',zeros(960,1,0),'cycle_phase',zeros(960,1,0),'mechanics',struct, ...
            'mode',activeMode,'phase_origin','derived_from_actual_pre_context_and_exact_source_smoothControl');return;
    end
    valid=~isnan(rows(:,1));frame=[];
    report=struct('columns',names,'values',rows(valid,:),'frame_count',nnz(valid), ...
        'evaluation_count',numel(calls),'evaluation_times',calls,'duplicate_count',duplicates, ...
        'pre_pressure',prePressure(:,:,valid),'cycle_phase',phases(:,:,valid),'mechanics',mechanics, ...
        'mode',activeMode,'phase_origin','derived_from_actual_pre_context_and_exact_source_smoothControl');return;
end
if mode=="reset"
    activePath=[];activeMode=[];context=[];filterState=[];lastTime=[];lastPacket=[];lastFrame=[];
    rows=[];prePressure=[];phases=[];mechanics=[];calls=[];duplicates=0;frame=[];return;
end
if ~isa(packed,'double') || ~isreal(packed) || ~isequal(size(packed),[9,1]) || any(~isfinite(packed))
    error('S12:Rumble:Packet','Expected finite native double 9x1.');
end
time=packed(9);index=round(time/.02)+1;
if time<0 || index>4500 || abs(time-(index-1)*.02)>1e-8,error('S12:Rumble:Packet','Invalid frame clock.');end
path=string(contractPath);
if isempty(activePath) || activePath~=path || isempty(activeMode) || activeMode~=mode || isempty(lastTime) || time<lastTime
    cfg=jsondecode(fileread(path));
    if ~isfield(cfg.cases,char(mode)),error('S12:Rumble:Mode','Mode absent from frozen contract.');end
    lab=fileparts(mfilename('fullpath'));project=fileparts(fileparts(lab));
    profile=jsondecode(fileread(fullfile(project,'tools','sound_sim','s12','playground_v12','vehicles','hellcat_2022_stock','source_profile.json')));
    context=[];filterState=[];lastTime=[];lastPacket=[];lastFrame=[];rows=NaN(4500,numel(names));
    prePressure=zeros(960,1,4500);phases=zeros(960,1,4500);mechanics=struct;calls=[];duplicates=0;
    activePath=path;activeMode=mode;
end
calls(end+1,1)=time;
if ~isempty(lastTime) && time==lastTime
    if ~isequal(packed,lastPacket),error('S12:Rumble:Duplicate','Repeated clock with changed packet.');end
    duplicates=duplicates+1;frame=lastFrame;return;
end
if index~=nnz(~isnan(rows(:,1)))+1,error('S12:Rumble:FrameOrder','Dropped or reordered source frame.');end
before=0;previousRpm=packed(1);if ~isempty(context),before=context.cycle_phase_rad;previousRpm=context.rpm_control;end
rpm=linspace(previousRpm,packed(1),960)';increment=pi*rpm/(60*48000);
cycle=before+[0;cumsum(increment(1:end-1))];
kinds=["none","upshift_bark","downshift_blip_pop","overrun_crackle"];code=packed(7)+1;
if code~=fix(code) || code<1 || code>4,error('S12:Rumble:Packet','Invalid afterfire.');end
state=struct('rpm',packed(1),'load',packed(2),'throttle',packed(3),'acceleration',packed(4), ...
    'shift_event',packed(5),'shift_progress',packed(6),'afterfire_kind',kinds(code),'afterfire_progress',packed(8));
options=cfg.research_options;options.voicing_rpm_band=reshape(options.voicing_rpm_band,1,2);
setting=cfg.cases.(mode);options.mechanical_gain=setting.mechanical_gain;options.mechanical_mod_depth=setting.mechanical_mod_depth;
[banks,context,diagnostics]=s12_v12_render_source_frame(state,profile,context,48000,960,'hellcat_2022_stock',options);
pre=s12_v12_mix_bank_excitation(banks);[frame,filterState]=rumble_pressure_color_frame(pre,filterState,48000,setting.rumble_k);
prePressure(:,:,index)=pre;phases(:,:,index)=cycle;
d=diagnostics.research;p=d.cut_energy_before;q=d.cut_energy_after;extra=[p.mechanical,p.mechanical,p.identity_mechanical,p.identity_mechanical,1,1];
if isfield(d,'mechanics')
    m=d.mechanics;if ~isequal(cycle,m.cycle_phase_rad),error('S12:Rumble:PhaseTrace','Derived phase differs from actual source diagnostic.');end
    phases(:,:,index)=m.cycle_phase_rad;
    extra=[sum(m.source_before.^2,'all'),sum(m.source_after.^2,'all'),sum(m.identity_before.^2,'all'),sum(m.identity_after.^2,'all'),min(m.multiplier,[],'all'),max(m.multiplier,[],'all')];
    if cfg.capture_short_mechanics && index<=round(cfg.short_seconds/.02)
        fields={'cycle_phase_rad','envelope','multiplier','source_before','source_after','identity_before','identity_after'};
        for j=1:numel(fields),mechanics.(fields{j})(:,:,index)=m.(fields{j});end
    end
end
rows(index,:)=[time,context.frame_index,before,context.cycle_phase_rad,d.cut_min,d.cut_max,mean(d.cut_multiplier), ...
    mean(d.whine_scale),mean(d.induction_scale),mean(d.voicing_activation),p.combustion,q.combustion,p.orders,q.orders, ...
    p.identity_exhaust,q.identity_exhaust,p.identity_whine,q.identity_whine,p.identity_mechanical,q.identity_mechanical,p.mechanical,q.mechanical,extra];
lastTime=time;lastPacket=packed;lastFrame=frame;
end
