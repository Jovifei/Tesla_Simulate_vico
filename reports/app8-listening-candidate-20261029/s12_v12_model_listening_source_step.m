function [frame, report]=s12_v12_model_listening_source_step(packed,contractPath,mode)
% Research source adapter; only run start/rewind resets phase and filter state.
persistent activePath activeMode cfg profile context lastTime rows
if nargin<3, mode="C"; end
mode=string(mode); report=[];
names=["time_s","frame_index","phase_before","phase_after","cut_min","cut_max","cut_mean", ...
    "whine_scale","induction_scale","voicing_activation","combustion_before","combustion_after", ...
    "orders_before","orders_after","identity_exhaust_before","identity_exhaust_after", ...
    "identity_whine_before","identity_whine_after","identity_mechanical_before","identity_mechanical_after", ...
    "mechanical_before","mechanical_after"];
if mode=="report"
    frame=[]; valid=~isnan(rows(:,1)); report=struct("columns",names,"values",rows(valid,:),"frame_count",nnz(valid)); return;
end
if mode=="reset"
    activePath=[];activeMode=[];context=[];lastTime=[];rows=[];frame=[];return;
end
if ~ismember(mode,["B","C"]) || ~isnumeric(packed) || ~isreal(packed) || ...
        ~isequal(size(packed),[9,1]) || any(~isfinite(packed))
    error("S12:Listening:Packet","Expected a finite 9x1 state and B/C mode.");
end
time=packed(9); index=round(time/.02)+1;
if time<0 || index>4500 || abs(time-(index-1)*.02)>1e-8
    error("S12:Listening:Packet","Packet clock is outside its frame grid.");
end
path=string(contractPath);
if isempty(activePath) || activePath~=path || isempty(activeMode) || activeMode~=mode || isempty(lastTime) || time<=lastTime
    cfg=jsondecode(fileread(path));
    lab=fileparts(mfilename("fullpath")); project=fileparts(fileparts(lab));
    profile=jsondecode(fileread(fullfile(project,"tools","sound_sim","s12","playground_v12", ...
        "vehicles","hellcat_2022_stock","source_profile.json")));
    context=[];lastTime=[];rows=NaN(4500,numel(names));activePath=path;activeMode=mode;
end
before=0;if ~isempty(context), before=context.cycle_phase_rad;end
kinds=["none","upshift_bark","downshift_blip_pop","overrun_crackle"];
code=packed(7)+1;
if code~=fix(code) || code<1 || code>4, error("S12:Listening:Packet","Invalid afterfire code."); end
state=struct("rpm",packed(1),"load",packed(2),"throttle",packed(3),"acceleration",packed(4), ...
    "shift_event",packed(5),"shift_progress",packed(6),"afterfire_kind",kinds(code),"afterfire_progress",packed(8));
options=struct("enabled",true,"cut_minimum",cfg.research_options.cut_minimum, ...
    "whine_scale",1,"induction_scale",1,"voicing_rpm_band",reshape(cfg.research_options.voicing_rpm_band,1,2));
if mode=="C"
    options.whine_scale=cfg.research_options.C_whine_scale;
    options.induction_scale=cfg.research_options.C_induction_scale;
end
[banks,context,diagnostics]=s12_v12_render_source_frame(state,profile,context,48000,960,"hellcat_2022_stock",options);
frame=s12_v12_mix_bank_excitation(banks);
d=diagnostics.research; pre=d.cut_energy_before; post=d.cut_energy_after;
rows(index,:)=[time,context.frame_index,before,context.cycle_phase_rad,d.cut_min,d.cut_max,mean(d.cut_multiplier), ...
    mean(d.whine_scale),mean(d.induction_scale),mean(d.voicing_activation), ...
    pre.combustion,post.combustion,pre.orders,post.orders,pre.identity_exhaust,post.identity_exhaust, ...
    pre.identity_whine,post.identity_whine,pre.identity_mechanical,post.identity_mechanical,pre.mechanical,post.mechanical];
lastTime=time;
end
