function s12_sound_playground_configure_audio_device_writer(blockPath)
%S12_SOUND_PLAYGROUND_CONFIGURE_AUDIO_DEVICE_WRITER Fixed audition format.
% Mask parameter names require controlled R2026a confirmation.

set_param(blockPath, "InheritSampleRate", "off", "SampleRate", "48000", ...
    "BitDepth", "24-bit integer", "Device", "Default");
end
