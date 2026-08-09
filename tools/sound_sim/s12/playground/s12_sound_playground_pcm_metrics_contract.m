function contract = s12_sound_playground_pcm_metrics_contract()
%S12_SOUND_PLAYGROUND_PCM_METRICS_CONTRACT Qualification thresholds.

signal = s12_sound_playground_signal_contract();
contract.sample_rate_hz = signal.sample_rate_hz;
contract.frame_samples = signal.frame_samples;
contract.channels = signal.pcm.shape(2);
contract.peak_must_be_less_than = 1.0;
contract.clipping_count_must_equal = 0;
contract.dc_absolute_limit = 1e-3;
contract.boundary_jump_absolute_limit = 0.5;
contract.duration_s = signal.qualification_audio_duration_s;
contract.status = "SYNTHETIC_QUALIFICATION_CONTRACT_NOT_RUNTIME_EVIDENCE";
end
