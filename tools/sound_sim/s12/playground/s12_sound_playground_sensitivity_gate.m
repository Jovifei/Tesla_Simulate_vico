function result = s12_sound_playground_sensitivity_gate(plan, outputRoot, requestedVariable)
%S12_SOUND_PLAYGROUND_SENSITIVITY_GATE Future-only one-variable PCM sensitivity qualification.

if nargin < 3
    requestedVariable = "all";
end
switch string(requestedVariable)
    case "rpm"
        result = struct("rpm_800_vs_3000", runPair("rpm", 800, 3000, "dominant_order_frequency"));
    case "load"
        result = struct("load_02_vs_08", runPair("load", 0.2, 0.8, "rms_and_order2_to_order1"));
    case "acceleration"
        result = struct("acceleration_0_vs_positive", runPair("acceleration", 0, 2, "delta_pcm_transient"));
    case "all"
        result = struct( ...
            "rpm_800_vs_3000", runPair("rpm", 800, 3000, "dominant_order_frequency"), ...
            "load_02_vs_08", runPair("load", 0.2, 0.8, "rms_and_order2_to_order1"), ...
            "acceleration_0_vs_positive", runPair("acceleration", 0, 2, "delta_pcm_transient"));
    otherwise
        error("S12:Playground:Sensitivity", "Unsupported requested sensitivity variable %s.", requestedVariable);
end

    function pair = runPair(variable, baseValue, variedValue, metric)
        base = s12_sound_playground_controlled_sensitivity_scenario(variable, baseValue);
        varied = s12_sound_playground_controlled_sensitivity_scenario(variable, variedValue);
        controls = assertSingleVariableDelta(base, varied, variable);
        baseRoot = fullfile(outputRoot, variable + "_base");
        variedRoot = fullfile(outputRoot, variable + "_varied");
        baseRun = s12_sound_playground_run_simulink_case("idle", plan, true, baseRoot, base);
        variedRun = s12_sound_playground_run_simulink_case("idle", plan, true, variedRoot, varied);
        baseMetrics = s12_sound_playground_case_order_metrics(baseRun.evidence.pcm_path, scenarioRpm(base));
        variedMetrics = s12_sound_playground_case_order_metrics(variedRun.evidence.pcm_path, scenarioRpm(varied));
        comparison = assertMetricDelta(variable, baseMetrics, variedMetrics, baseRun.evidence.pcm_path, variedRun.evidence.pcm_path, baseValue, variedValue);
        pair = struct("variable", variable, "metric", string(metric), "controls", controls, ...
            "base", baseRun.evidence, "varied", variedRun.evidence, ...
            "base_metrics", baseMetrics, "varied_metrics", variedMetrics, "comparison", comparison);
    end
end

function controls = assertSingleVariableDelta(base, varied, variable)
signal = s12_sound_playground_signal_contract();
index = signal.indices.(char(variable));
baseFrames = workspaceFrames(base);
variedFrames = workspaceFrames(varied);
different = find(any(baseFrames ~= variedFrames, 2));
if numel(different) ~= 1 || different ~= index || ...
        isequal(baseFrames(index, :), variedFrames(index, :))
    error("S12:Playground:SensitivityContract", "Pair must change exactly one configured variable.");
end
controls = struct("only_one_variable_changes", true, "same_reset_state", true, ...
    "same_ptr", true, "same_gain", true, "same_scenario_length", isequal(base.frame_count, varied.frame_count), ...
    "rpm", scenarioValue(base, signal.indices.rpm), "load", scenarioValue(base, signal.indices.load), ...
    "acceleration", scenarioValue(base, signal.indices.acceleration), "throttle", scenarioValue(base, signal.indices.throttle), ...
    "pipe_length", scenarioValue(base, signal.indices.pipe_length), "area", scenarioValue(base, signal.indices.area), ...
    "reflection", scenarioValue(base, signal.indices.reflection), "damping", scenarioValue(base, signal.indices.damping), ...
    "gain_db", scenarioValue(base, signal.indices.gain_db));
if ~controls.same_scenario_length
    error("S12:Playground:SensitivityContract", "Sensitivity pair scenario length changed.");
end
end

function comparison = assertMetricDelta(variable, base, varied, basePath, variedPath, baseValue, variedValue)
contract = s12_sound_playground_sensitivity_contract();
switch string(variable)
    case "rpm"
        expectedBase = double(baseValue) / 60 * contract.selected_order;
        expectedVaried = double(variedValue) / 60 * contract.selected_order;
        baseComparison = frequencyComparison(expectedBase, base.dominant_order_frequency_hz, contract);
        variedComparison = frequencyComparison(expectedVaried, varied.dominant_order_frequency_hz, contract);
        if abs(expectedBase - expectedVaried) <= eps || ...
                abs(base.dominant_order_frequency_hz - varied.dominant_order_frequency_hz) <= eps
            error("S12:Playground:Sensitivity", "RPM pair did not change dominant order frequency.");
        end
        comparison = struct("selected_order", contract.selected_order, "base", baseComparison, ...
            "varied", variedComparison, "expected_frequency_delta_hz", expectedVaried - expectedBase, ...
            "measured_frequency_delta_hz", varied.dominant_order_frequency_hz - base.dominant_order_frequency_hz);
    case "load"
        rmsChange = varied.rms - base.rms;
        orderRatioChange = varied.order2_to_order1_energy_ratio - base.order2_to_order1_energy_ratio;
        if rmsChange < contract.minimum_load_rms_change || ...
                orderRatioChange < contract.minimum_order2_to_order1_energy_ratio_change
            error("S12:Playground:Sensitivity", "Load pair missed the frozen RMS or order2/order1 threshold.");
        end
        comparison = struct("rms_change", rmsChange, "minimum_load_rms_change", contract.minimum_load_rms_change, ...
            "order2_to_order1_energy_ratio_change", orderRatioChange, ...
            "minimum_order2_to_order1_energy_ratio_change", contract.minimum_order2_to_order1_energy_ratio_change, ...
            "expected_direction", contract.load_expected_direction);
    case "acceleration"
        deltaMetrics = s12_sound_playground_delta_pcm_metrics(basePath, variedPath);
        if abs(deltaMetrics.transient_window_s - contract.transient_window_s) > eps
            error("S12:Playground:Sensitivity", "Acceleration delta PCM was not measured in the fixed transient window.");
        end
        if deltaMetrics.delta_energy < contract.minimum_delta_pcm_energy || ...
                deltaMetrics.delta_rms < contract.minimum_delta_pcm_rms || ...
                deltaMetrics.delta_peak < contract.minimum_delta_pcm_peak
            error("S12:Playground:Sensitivity", "Acceleration pair missed the frozen delta PCM threshold.");
        end
        comparison = struct("transient_window_s", contract.transient_window_s, ...
            "delta_energy", deltaMetrics.delta_energy, "minimum_delta_pcm_energy", contract.minimum_delta_pcm_energy, ...
            "delta_rms", deltaMetrics.delta_rms, "minimum_delta_pcm_rms", contract.minimum_delta_pcm_rms, ...
            "delta_peak", deltaMetrics.delta_peak, "minimum_delta_pcm_peak", contract.minimum_delta_pcm_peak, ...
            "expected_direction", contract.acceleration_expected_direction);
    otherwise
        error("S12:Playground:Sensitivity", "Unsupported sensitivity variable %s.", variable);
end
end

function comparison = frequencyComparison(expectedFrequencyHz, measuredFrequencyHz, contract)
absoluteError = abs(measuredFrequencyHz - expectedFrequencyHz);
relativeError = absoluteError / max(abs(expectedFrequencyHz), realmin);
if absoluteError > contract.frequency_absolute_tolerance_hz || ...
        relativeError > contract.frequency_relative_tolerance
    error("S12:Playground:Sensitivity", "RPM order frequency missed the numeric tracking tolerance.");
end
comparison = struct("expected_frequency_hz", expectedFrequencyHz, ...
    "measured_frequency_hz", measuredFrequencyHz, "absolute_error_hz", absoluteError, ...
    "relative_error", relativeError, ...
    "allowed_absolute_error_hz", contract.frequency_absolute_tolerance_hz, ...
    "allowed_relative_error", contract.frequency_relative_tolerance);
end

function value = scenarioRpm(scenario)
signal = s12_sound_playground_signal_contract();
value = scenarioValue(scenario, signal.indices.rpm);
end

function value = scenarioValue(scenario, index)
values = workspaceFrames(scenario);
values = values(index, :);
if any(values ~= values(1))
    error("S12:Playground:SensitivityContract", "Sensitivity control value must be constant across frames.");
end
value = values(1);
end

function frames = workspaceFrames(scenario)
values = scenario.workspace_signal.signals.values;
frames = reshape(values, 18, scenario.frame_count);
if ~isequal(frames, scenario.configuration_frames)
    error("S12:Playground:SensitivityContract", "Scenario workspace signal does not match configuration_frames.");
end
end
