function pressure = s12_sound_playground_ptr_tuning_step(excitation, pipeLengthM, areaM2, reflection, damping, reset)
%S12_SOUND_PLAYGROUND_PTR_TUNING_STEP Synthetic visual/audition adapter only.
% It never invokes or changes the frozen PTR/radiation numerical core.

persistent delayLine writeIndex
sampleRate = 48000;
speedOfSound = 343;
maximumDelaySamples = 4096;
if isempty(delayLine) || reset
    delayLine = zeros(maximumDelaySamples, 1);
    writeIndex = 1;
end

delaySamples = min(max(round(pipeLengthM / speedOfSound * sampleRate), 1), maximumDelaySamples - 1);
areaScale = sqrt(areaM2 / 0.020);
pressure = zeros(size(excitation));
for sample = 1:numel(excitation)
    readIndex = writeIndex - delaySamples;
    if readIndex < 1
        readIndex = readIndex + maximumDelaySamples;
    end
    delayed = delayLine(readIndex);
    pressure(sample) = (1 - damping) * areaScale * (excitation(sample) + reflection * delayed);
    delayLine(writeIndex) = excitation(sample) + 0.15 * reflection * delayed;
    writeIndex = writeIndex + 1;
    if writeIndex > maximumDelaySamples
        writeIndex = 1;
    end
end
end
