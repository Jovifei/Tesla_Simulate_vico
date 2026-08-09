function pcm = s12_sound_playground_normalize_logged_pcm(raw, expectedFrames)
%S12_SOUND_PLAYGROUND_NORMALIZE_LOGGED_PCM Accept only approved PCM layouts.

signal = s12_sound_playground_signal_contract();
if ~isnumeric(raw) || ~isreal(raw)
    error("S12:Playground:LoggedPcmType", "Logged PCM must be a real numeric array.");
end
expectedRows = expectedFrames * signal.frame_samples;
if ~isequal(size(raw), [expectedRows, signal.pcm.shape(2)])
    error("S12:Playground:LoggedPcmShape", "Unsupported logged PCM shape %s.", mat2str(size(raw)));
end
pcm = double(raw);
if ~all(isfinite(pcm), "all")
    error("S12:Playground:LoggedPcmFinite", "Logged PCM contains NaN or Inf.");
end
end
