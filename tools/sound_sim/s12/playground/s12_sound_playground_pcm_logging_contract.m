function contract = s12_sound_playground_pcm_logging_contract()
%S12_SOUND_PLAYGROUND_PCM_LOGGING_CONTRACT Fixed qualification PCM logging.

signal = s12_sound_playground_signal_contract();
contract.variable_name = "playground_pcm";
contract.save_format = "Array";
contract.save_2d_signals = "2-D array (concatenate along first dimension)";
contract.max_data_points = "inf";
contract.decimation = "1";
contract.shape = signal.pcm.shape;
contract.runtime_status = "REQUIRES_CONTROLLED_RUNTIME_CONFIRMATION";
end
