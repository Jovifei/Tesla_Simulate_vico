function frame = s12_v12_model_radiation_step(packed)
%S12_V12_MODEL_RADIATION_STEP Fixed-frame frozen radiation adapter.

persistent context lastTime
if ~isnumeric(packed) || ~isequal(size(packed), [961, 1]) || ...
        any(~isfinite(packed), "all")
    error("S12:EngineSoundV12:ModelRadiation", ...
        "Model radiation input must be one finite [961,1] vector.");
end
time = packed(end);
if isempty(lastTime) || time <= lastTime
    context = [];
end
[frame, context] = s12_v12_apply_frozen_radiation_frame( ...
    packed(1:960), context, 48000);
lastTime = time;
end
