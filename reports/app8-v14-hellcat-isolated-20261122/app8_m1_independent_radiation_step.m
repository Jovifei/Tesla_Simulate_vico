function frame = app8_m1_independent_radiation_step(packed)
% Preserve the original adapter's frame and reset semantics in a private instance.
persistent context lastTime
if ~isnumeric(packed) || ~isequal(size(packed),[961,1]) || any(~isfinite(packed),'all')
    error('App8M1:Input','Expected a finite 961-by-1 radiation packet.');
end
time = packed(end);
if isempty(lastTime) || time <= lastTime
    context = [];
end
[frame,context] = s12_v12_apply_frozen_radiation_frame(packed(1:960),context,48000);
lastTime = time;
end
