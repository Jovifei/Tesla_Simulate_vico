function analysis = s12_v11_analyze_sound(pcm, trace, events, sampleRateHz)
%S12_V11_ANALYZE_SOUND Aggregate derived analysis from synthetic PCM/trace.

rpm = extractRpm(trace);
analysis = struct( ...
    "input_scope", "synthetic_pcm_and_trace_only", ...
    "raw_reference_audio_used", false, ...
    "order_map", s12_v11_compute_order_map(pcm, rpm, sampleRateHz), ...
    "audio_metrics", s12_v11_compute_audio_metrics(pcm, sampleRateHz), ...
    "afterfire_statistics", s12_v11_compute_afterfire_statistics(events));
end

function rpm = extractRpm(trace)
if istable(trace)
    if ~ismember("rpm", string(trace.Properties.VariableNames))
        error("S12:EngineSoundV11:Analysis", "Trace table must contain rpm.");
    end
    rpm = trace.rpm;
elseif isstruct(trace)
    if isempty(trace) || ~isfield(trace, "rpm")
        error("S12:EngineSoundV11:Analysis", "Trace struct must contain rpm.");
    end
    rpm = [trace.rpm];
elseif isnumeric(trace)
    rpm = trace;
else
    error("S12:EngineSoundV11:Analysis", "Trace must be numeric, struct, or table data.");
end
end
