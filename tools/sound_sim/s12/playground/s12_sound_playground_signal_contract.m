function contract = s12_sound_playground_signal_contract()
%S12_SOUND_PLAYGROUND_SIGNAL_CONTRACT Central fixed-size signal mapping.

contract.version = "v0.9-v7-offline-closeout-audit-v6";
contract.configuration = struct("shape", [18, 1], "mux_input_signal_count", 12, ...
    "compiled_output_element_count", 18, "data_type", "double", "fixed_size", true);
contract.excitation = struct("shape", [960, 1]);
contract.pressure = struct("shape", [960, 1]);
contract.pcm = struct("shape", [960, 2]);
contract.sample_rate_hz = 48000;
contract.frame_samples = 960;
contract.frame_duration_s = 0.02;
contract.frame_period_s = contract.frame_duration_s;
contract.qualification_frame_count = 500;
contract.qualification_stop_time_s = (contract.qualification_frame_count - 1) * contract.frame_duration_s;
contract.qualification_audio_duration_s = contract.qualification_frame_count * contract.frame_duration_s;
contract.indices = struct( ...
    "rpm", 1, "load", 2, "acceleration", 3, "throttle", 4, ...
    "cylinder_count", 5, "firing_order", 6:9, "order_gain", 10:13, ...
    "pipe_length", 14, "area", 15, "reflection", 16, "damping", 17, ...
    "gain_db", 18);
contract.sample_rate_policy = "FIXED_48000_HZ_NOT_PACKED_OR_TUNABLE";
contract.configuration_shape_checkpoints = ["interactive_branch", "qualification_branch", "mode_selector_output", ...
    "vehicle_state_output", "engine_excitation_input"];
contract.engine_scope = struct("cylinder_count", 4, "firing_order", 1:4, "order_gain_count", 4, ...
    "selected_order", 1, "selected_order_basis", "synthetic_fundamental_order_1", ...
    "status", "FIXED_FOUR_CYLINDER_SYNTHETIC_SCOPE");
contract.execution_policy = "REQUIRES_CONTROLLED_RUNTIME_CONFIRMATION";
contract.qualification_workspace_layout = "values = reshape(frames, 18, 1, frameCount); signals.dimensions = [18 1]";
end
