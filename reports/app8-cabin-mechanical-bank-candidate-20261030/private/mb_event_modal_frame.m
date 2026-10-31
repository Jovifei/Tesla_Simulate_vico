function [event, output, context, trace] = mb_event_modal_frame(phase, rpm, load, fs, context, phasesDeg)
% Private, uncalibrated event/modal research model. Inputs are sample holds.
if nargin < 6, phasesDeg = 0:90:630; end
if fs ~= 48000 || ~iscolumn(phase) || ~isequal(size(phase),size(rpm),size(load)) || ...
        any(~isfinite([phase;rpm;load])) || any(rpm < 0 | rpm > 12000) || any(load < 0 | load > 1) || ...
        ~isnumeric(phasesDeg) || isempty(phasesDeg) || any(~isfinite(phasesDeg)) || ...
        any(phasesDeg < 0 | phasesDeg >= 720) || numel(unique(phasesDeg)) ~= numel(phasesDeg)
    error('Cabin:EventInput','Invalid event inputs.');
end
n = numel(phase); T = .0006;
if isempty(context)
    context = struct('age',zeros(0,1),'gain',zeros(0,1),'state',zeros(2,4), ...
        'dc_input',0,'dc_output',0,'expected_phase',[],'total_events',0);
end
if n == 0, event=zeros(0,1);output=event;trace=struct('event_count',0,'modal_before_dc',event);return;end
increments = pi * rpm / (60 * fs);
if ~isempty(context.expected_phase) && abs(atan2(sin(phase(1)-context.expected_phase), ...
        cos(phase(1)-context.expected_phase))) > 1e-9
    error('Cabin:EventPhase','Phase is discontinuous across frames.');
end
if n > 1
    err = phase(2:end) - phase(1:end-1) - increments(1:end-1);
    if any(abs(atan2(sin(err),cos(err))) > 1e-9),error('Cabin:EventPhase','Phase is discontinuous within frame.');end
end
angles = reshape(2*pi*double(phasesDeg)/720,1,[]);
delta = mod(angles - mod(phase,2*pi),2*pi);
[indices,which] = find((delta < increments) & (increments > 0));
starts = 1 - context.age * fs;
gains = context.gain;
if ~isempty(indices)
    selected = sub2ind(size(delta),indices,which);
    starts = [starts; indices + delta(selected)./increments(indices)];
    gains = [gains; .25+.75*load(indices)];
end
event = zeros(n,1);
for j = 1:numel(starts)
    first = max(1,floor(starts(j))); last = min(n,ceil(starts(j)+T*fs)-1);
    if first <= last
        ii = (first:last)'; left = max(0,min(T,(ii-starts(j))/fs));
        right = max(0,min(T,(ii+1-starts(j))/fs));
        area = ((right-left)-T/(2*pi)*(sin(2*pi*right/T)-sin(2*pi*left/T)))/T;
        event(ii) = event(ii) + gains(j)*fs*area;
    end
end
age = (n+1-starts)/fs; keep = age < T;
context.age = age(keep);context.gain = gains(keep);
context.expected_phase = mod(phase(end)+increments(end),2*pi);
context.total_events = context.total_events + numel(indices);
frequencies=[160 370 820 1630]; damping=[.18 .14 .12 .10]; raw=zeros(n,1);
for j=1:4
    omega=2*pi*frequencies(j); A=[0 1;-omega^2 -2*damping(j)*omega]; B=[0;.25];
    Ad=expm(A/fs);Bd=A\((Ad-eye(2))*B);tr=traceMatrix(Ad);detA=det(Ad);
    state=context.state(:,j);az=[1 -tr detA];ab=Ad*Bd;initial=Ad*state;
    [position,~]=filter([Bd(1) ab(1)-tr*Bd(1) 0],az,event,[initial(1);-detA*state(1)]);
    [velocity,~]=filter([Bd(2) ab(2)-tr*Bd(2) 0],az,event,[initial(2);-detA*state(2)]);
    raw=raw+.25*position;context.state(:,j)=[position(end);velocity(end)];
end
alpha=exp(-2*pi*15/fs);
[output,~]=filter([alpha -alpha],[1 -alpha],raw,alpha*(context.dc_output-context.dc_input));
context.dc_input=raw(end);context.dc_output=output(end);
trace=struct('event_count',numel(indices),'modal_before_dc',raw, ...
    'fractional_offsets_samples',delta(sub2ind(size(delta),indices,which))./increments(indices));
end
function value=traceMatrix(x)
value=x(1,1)+x(2,2);
end
