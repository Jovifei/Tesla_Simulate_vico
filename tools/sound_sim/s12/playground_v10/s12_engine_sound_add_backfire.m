function excitation = s12_engine_sound_add_backfire(excitation, events, frameIndex, sampleRate, frameSamples)
%S12_ENGINE_SOUND_ADD_BACKFIRE Add deterministic pressure bursts before PTR.

if isempty(events)
    return
end
globalSamples = (frameIndex - 1) * frameSamples + (0:frameSamples - 1).';
for index = 1:numel(events)
    eventSample = round(events(index).time_s * sampleRate);
    localSamples = globalSamples - eventSample;
    mask = localSamples >= 0 & localSamples < round(0.18 * sampleRate);
    if ~any(mask)
        continue
    end
    normalizedAge = localSamples(mask) / (0.08 * sampleRate);
    envelope = events(index).energy * events(index).decay .^ normalizedAge;
    phase = 2 * pi * (440 * localSamples(mask) / sampleRate + 0.0008 * localSamples(mask) .^ 2 / sampleRate);
    excitation(mask) = excitation(mask) + envelope .* (sin(phase) + 0.35 * sin(2 * phase));
end
end
