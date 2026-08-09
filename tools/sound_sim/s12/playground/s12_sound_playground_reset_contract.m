function contract = s12_sound_playground_reset_contract()
%S12_SOUND_PLAYGROUND_RESET_CONTRACT Explicit repeatability semantics.

contract.phase_reset_on_simulation_start = true;
contract.ptr_state_reset_on_simulation_start = true;
contract.mechanism = "internal_unit_delay_reset_pulse";
contract.reset_signal = struct("shape", [1, 1], "type", "double", "first_frame", 1, "remaining_frames", 0);
contract.reset_targets = ["phase", "transient", "lastThrottle", "delayLine", "writeIndex"];
contract.scenario_or_mode_change = "requires_controlled_simulation_restart";
contract.required_events = ["simulation_start", "explicit_restart", "cold_reload", "stop_then_run"];
contract.forbidden_dependency = "clear all";
contract.fast_restart_policy = "OFF_UNTIL_CONTROLLED_RUNTIME_PROOF";
contract.status = "REQUIRES_CONTROLLED_RUNTIME_CONFIRMATION";
end
