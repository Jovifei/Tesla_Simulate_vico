function tests = test_s12_sound_playground_offline_repair
%TEST_S12_SOUND_PLAYGROUND_OFFLINE_REPAIR Offline-only v0.9 v3 contracts.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
addpath(fullfile(s12Root, "playground"));
testCase.addTeardown(@() rmpath(fullfile(s12Root, "playground")));
end

function testKnownEvidenceIdentityIsExplicit(testCase)
port = s12_sound_playground_port_contract();
workspace = port.artifacts.workspace_unvalidated_intermediate;
historical = port.artifacts.historical_pre_repair_invalid;
verifyEqual(testCase, workspace.sha256, ...
    "43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5");
verifyEqual(testCase, historical.sha256, ...
    "FA91F46A2F8F6D78586FAE407E795BCEB99AD529F76925A4AF806F9AC73595C0");
verifyFalse(testCase, workspace.mutable);
verifyTrue(testCase, contains(workspace.allowed_operations, "package"));
end

function testNamedPortAndExactLinkContracts(testCase)
port = s12_sound_playground_port_contract();
verifyEqual(testCase, port.subsystems.Dashboard.inputs, 0);
verifyEqual(testCase, port.subsystems.EngineExcitation.input_names, "Packed");
verifyEqual(testCase, port.subsystems.PtrRadiationTuningAdapter.input_names, ["Excitation", "Packed"]);
verifyEqual(testCase, port.top_level_connections(1).destination, "Vehicle State.Configuration");
verifyEqual(testCase, port.top_level_connections(2).source, "Vehicle State.Packed");
end

function testSignalContractHasOneCentral18ElementMapping(testCase)
signal = s12_sound_playground_signal_contract();
verifyEqual(testCase, signal.configuration.shape, [18, 1]);
verifyEqual(testCase, signal.configuration.mux_input_signal_count, 12);
verifyEqual(testCase, signal.qualification_frame_count, 500);
verifyEqual(testCase, signal.qualification_stop_time_s, 9.98, "AbsTol", 1e-12);
verifyEqual(testCase, signal.qualification_audio_duration_s, 10, "AbsTol", 1e-12);
verifyFalse(testCase, isfield(signal.indices, "sample_rate"));
end

function testBuildPlanSeparatesFormalAndTemporaryPaths(testCase)
plan = s12_sound_playground_build_plan("offline_repair_test");
verifyNotEqual(testCase, plan.formal.path, plan.temporary.model_path);
verifyNotEqual(testCase, plan.formal.model_name, plan.temporary.model_name);
verifyTrue(testCase, contains(plan.temporary.model_name, "offline_repair_test"));
verifyEqual(testCase, plan.execution_policy, "BLOCKED_PENDING_EXPLICIT_AUTHORIZATION_AND_INDEPENDENT_REVIEW");
end

function testValidationContractsRejectMismatchedManifests(testCase)
port = s12_sound_playground_port_contract();
badPorts = struct("subsystems", port.subsystems, "top_level_connections", port.top_level_connections);
badPorts.subsystems.EngineExcitation.inputs = 2;
verifyError(testCase, @() s12_sound_playground_validate_ports(badPorts), "S12:Playground:PortContract");
signal = s12_sound_playground_signal_contract();
badDimensions = struct("configuration", [1, 1], "excitation", [960, 1], ...
    "configuration_vehicle_input", [18, 1], "configuration_vehicle_output", [18, 1], ...
    "configuration_engine_input", [18, 1], "pressure", [960, 1], "pcm", [960, 2]);
verifyError(testCase, @() s12_sound_playground_validate_dimensions(badDimensions, signal), ...
    "S12:Playground:DimensionContract");
end

function testDecoderAndPcmNormalizerFailClosed(testCase)
verifyEqual(testCase, s12_sound_playground_decode_compiled_dimensions([2 960 2], 0, "NOT_BUS", "x", "pcm"), [960 2]);
verifyEqual(testCase, s12_sound_playground_decode_compiled_dimensions([2 18 1], 0, "NOT_BUS", "x", "packed"), [18 1]);
verifyError(testCase, @() s12_sound_playground_decode_compiled_dimensions([2 960], 0, "NOT_BUS", "x", "pcm"), ...
    "S12:Playground:CompiledDimensions");
verifyError(testCase, @() s12_sound_playground_decode_compiled_dimensions([2 960 2], 1, "NOT_BUS", "x", "pcm"), ...
    "S12:Playground:CompiledDimensionsMode");
pcm = zeros(500 * 960, 2);
verifySize(testCase, s12_sound_playground_normalize_logged_pcm(pcm, 500), [480000 2]);
verifyError(testCase, @() s12_sound_playground_normalize_logged_pcm(zeros(960, 2, 500), 500), ...
    "S12:Playground:LoggedPcmShape");
end

function testModesResetAndRunnerAreExplicit(testCase)
modes = s12_sound_playground_modes();
verifyEqual(testCase, modes.qualification.selected_input, 2);
verifyEqual(testCase, modes.qualification.switch_value, "0");
verifyEqual(testCase, modes.interactive.selected_input, 1);
verifyEqual(testCase, modes.interactive.switch_value, "1");
scenario = s12_sound_playground_scenario_source("acceleration");
verifyEqual(testCase, scenario.frame_count, 500);
verifyEqual(testCase, scenario.stop_time_s, 9.98, "AbsTol", 1e-12);
reset = s12_sound_playground_reset_contract();
verifyEqual(testCase, reset.reset_signal.first_frame, 1);
verifyEqual(testCase, reset.fast_restart_policy, "OFF_UNTIL_CONTROLLED_RUNTIME_PROOF");
plan = s12_sound_playground_build_plan("runner_contract_test");
runner = s12_sound_playground_run_simulink_case("idle", plan, false);
verifyEqual(testCase, runner.status, "NOT_EXECUTED");
verifyEqual(testCase, runner.expected_stop_time_s, 9.98, "AbsTol", 1e-12);
end

function testInterfacesAndCanonicalPlanArePrepared(testCase)
interfaces = s12_sound_playground_function_interfaces();
verifyEqual(testCase, interfaces.EngineExcitation.inputs.packed, [18, 1]);
verifyEqual(testCase, interfaces.EngineExcitation.input_order, ["packed", "reset"]);
verifyEqual(testCase, interfaces.AudioRenderer.outputs.pcm, [960, 2]);
canonical = s12_sound_playground_canonical_path_plan();
verifyEqual(testCase, canonical.offline_repair_action, "NO_FILE_OPERATION");
verifyEqual(testCase, canonical.current_workspace_state, "WORKSPACE_UNVALIDATED_INTERMEDIATE");
end
