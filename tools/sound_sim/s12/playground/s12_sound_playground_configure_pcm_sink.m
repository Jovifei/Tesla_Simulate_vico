function s12_sound_playground_configure_pcm_sink(blockPath)
%S12_SOUND_PLAYGROUND_CONFIGURE_PCM_SINK Apply the qualification log contract.
% To Workspace mask parameter spelling requires controlled R2026a confirmation.

contract = s12_sound_playground_pcm_logging_contract();
set_param(blockPath, "VariableName", contract.variable_name, "SaveFormat", contract.save_format, ...
    "Save2DSignal", contract.save_2d_signals, "MaxDataPoints", contract.max_data_points, ...
    "Decimation", contract.decimation);
assertMaskValue(blockPath, "VariableName", contract.variable_name);
assertMaskValue(blockPath, "SaveFormat", contract.save_format);
assertMaskValue(blockPath, "Save2DSignal", contract.save_2d_signals);
assertMaskValue(blockPath, "MaxDataPoints", contract.max_data_points);
assertMaskValue(blockPath, "Decimation", contract.decimation);
end

function assertMaskValue(blockPath, parameter, expected)
actual = s12_sound_playground_require_text_scalar(get_param(blockPath, parameter), "PCM sink " + string(parameter));
expected = s12_sound_playground_require_text_scalar(expected, "expected PCM sink value");
if ~strcmp(actual, expected)
    error("S12:Playground:PcmSinkContract", ...
        "PCM sink %s expected %s but read %s.", parameter, string(expected), actual);
end
end
