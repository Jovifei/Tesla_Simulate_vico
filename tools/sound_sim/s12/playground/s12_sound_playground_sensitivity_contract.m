function contract = s12_sound_playground_sensitivity_contract()
%S12_SOUND_PLAYGROUND_SENSITIVITY_CONTRACT Numeric synthetic-only acceptance thresholds.

signal = s12_sound_playground_signal_contract();
contract.version = "v0.9-v7-offline-closeout-audit-v6";
contract.selected_order = double(signal.engine_scope.selected_order);
contract.selected_order_basis = string(signal.engine_scope.selected_order_basis);
contract.frequency_absolute_tolerance_hz = 2.0;
contract.frequency_relative_tolerance = 0.10;
contract.order_band_orders = 1:4;
contract.order_band_half_bandwidth_hz = 25.0;
contract.order_energy_window = "HANN_PERIODIC";
contract.order_energy_spectrum = "ONE_SIDED_FFT_BIN_ENERGY";
contract.load_control_rpm = 6000;
contract.load_control_acceleration = 0;
contract.load_control_throttle = 0.10;
contract.load_values = [0.2, 0.8];
contract.minimum_load_rms_change = 1e-4;
contract.minimum_order2_to_order1_energy_ratio_change = 1e-4;
contract.load_expected_direction = "HIGHER_LOAD_INCREASES_RMS_AND_ORDER2_TO_ORDER1";
contract.transient_window_s = 0.2;
contract.acceleration_control_rpm = 6000;
contract.acceleration_control_load = 0.5;
contract.acceleration_control_throttle = 0.10;
contract.acceleration_values = [0, 2];
contract.minimum_delta_pcm_energy = 1e-6;
contract.minimum_delta_pcm_rms = 1e-6;
contract.minimum_delta_pcm_peak = 1e-5;
contract.acceleration_expected_direction = "POSITIVE_ACCELERATION_CHANGES_DELTA_PCM_IN_TRANSIENT_WINDOW";
end
