function metrics = s12_sound_playground_delta_pcm_metrics(basePcmPath, variedPcmPath)
%S12_SOUND_PLAYGROUND_DELTA_PCM_METRICS Measure only the fixed-window PCM difference.

base = readStereoPcm(basePcmPath);
varied = readStereoPcm(variedPcmPath);
if ~isequal(size(base), size(varied))
    error("S12:Playground:DeltaPcm", "Sensitivity PCM pair dimensions differ.");
end
signal = s12_sound_playground_signal_contract();
contract = s12_sound_playground_sensitivity_contract();
sampleCount = min(size(base, 1), round(contract.transient_window_s * signal.sample_rate_hz));
delta_pcm = varied(1:sampleCount, 1) - base(1:sampleCount, 1);
metrics = struct("transient_window_s", contract.transient_window_s, "delta_pcm", "PERSISTED_PAIR_DIFFERENCE", ...
    "delta_energy", sum(delta_pcm .^ 2), "delta_rms", rms(delta_pcm), "delta_peak", max(abs(delta_pcm)));
end

function pcm = readStereoPcm(path)
file = fopen(path, "r");
if file < 0
    error("S12:Playground:DeltaPcm", "Cannot read PCM evidence %s.", path);
end
cleanup = onCleanup(@() fclose(file));
raw = fread(file, inf, "double=>double");
if mod(numel(raw), 2) ~= 0
    error("S12:Playground:DeltaPcm", "PCM evidence is not stereo interleaved.");
end
pcm = reshape(raw, 2, []).';
end
