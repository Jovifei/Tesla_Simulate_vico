function s12_sound_playground_apply_mode(modelName, modeName)
%S12_SOUND_PLAYGROUND_APPLY_MODE Controlled runtime mode binding.

modes = s12_sound_playground_modes();
if ~isfield(modes, modeName)
    error("S12:Playground:Mode", "Unknown mode: %s", modeName);
end
mode = modes.(modeName);
set_param(modelName + "/Optional Device Output", "Commented", ternary(mode.audio_device_writer_enabled, "off", "on"));
set_param(modelName + "/Qualification PCM Sink", "Commented", ternary(mode.pcm_logging_enabled, "off", "on"));
set_param(modelName + "/Dashboard/Mode Selector", "sw", mode.switch_value);
end

function value = ternary(condition, trueValue, falseValue)
if condition, value = trueValue; else, value = falseValue; end
end
