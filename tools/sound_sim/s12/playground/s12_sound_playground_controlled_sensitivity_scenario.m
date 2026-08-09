function scenario = s12_sound_playground_controlled_sensitivity_scenario(variable, value)
%S12_SOUND_PLAYGROUND_CONTROLLED_SENSITIVITY_SCENARIO Hold non-varied controls fixed.

variable = s12_sound_playground_require_text_scalar(variable, "sensitivity variable");
scenario = s12_sound_playground_scenario_source("idle");
signal = s12_sound_playground_signal_contract();
contract = s12_sound_playground_sensitivity_contract();

switch variable
    case "rpm"
        fixed = struct( ...
            "load", scenario.configuration_frames(signal.indices.load, 1), ...
            "acceleration", scenario.configuration_frames(signal.indices.acceleration, 1), ...
            "throttle", scenario.configuration_frames(signal.indices.throttle, 1));
    case "load"
        fixed = struct("rpm", contract.load_control_rpm, ...
            "acceleration", contract.load_control_acceleration, ...
            "throttle", contract.load_control_throttle);
    case "acceleration"
        fixed = struct("rpm", contract.acceleration_control_rpm, ...
            "load", contract.acceleration_control_load, ...
            "throttle", contract.acceleration_control_throttle);
    otherwise
        error("S12:Playground:Sensitivity", "Unsupported sensitivity variable %s.", variable);
end

names = string(fieldnames(fixed));
for index = 1:numel(names)
    control = names(index);
    scenario.configuration_frames(signal.indices.(char(control)), :) = fixed.(control);
end
scenario.configuration_frames(signal.indices.(char(variable)), :) = value;
scenario = s12_sound_playground_finalize_scenario(scenario);
end
