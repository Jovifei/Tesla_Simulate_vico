function tests = test_s12_engine_sound_v11_simulink_models
%TEST_S12_ENGINE_SOUND_V11_SIMULINK_MODELS Runtime gates for the v1.1 wrappers.
% Author this suite now, but run it only on the approved existing shared
% Desktop after the controller has declared the MATLAB/MCP control plane safe.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
v11 = fullfile(s12Root, "playground_v11");
addpath(v11);
addpath(fullfile(v11, "common"));
testCase.TestData.v11 = v11;
end

function teardownOnce(testCase)
rmpath(testCase.TestData.v11);
rmpath(fullfile(testCase.TestData.v11, "common"));
end

function testBuildColdReloadUpdateAndPcmPortContract(testCase)
% This test requires one user-started, visible MATLAB Desktop.  It must not
% be invoked through batch/nodesktop/MCP variants or an unsafe control plane.
expectedFrozenPtrAdapterSha256 = "3ce53f44883686ed2fa10a6c5b20cfe15d11b813ff75fb164489c62a241020e1";
frozenAdapter = s12_v11_resolve_frozen_ptr_adapter(expectedFrozenPtrAdapterSha256);
results = s12_v11_build_simulink_models("AllowModelCreation", true, ...
    "ExpectedFrozenPtrAdapterSha256", expectedFrozenPtrAdapterSha256);
verifyEqual(testCase, results(1).frozen_ptr_adapter_path, frozenAdapter.source_path);
verifyEqual(testCase, results(1).frozen_ptr_adapter_sha256, frozenAdapter.sha256);
close_system(results(1).core_model_name, 0);
load_system(results(1).core_model_path); % cold reload shared core
set_param(results(1).core_model_name, 'SimulationCommand', 'update');
verifyEqual(testCase, string(get_param(results(1).core_model_name, "SolverType")), "Fixed-step");
verifyEqual(testCase, str2double(get_param(results(1).core_model_name, "FixedStep")), 0.02, "AbsTol", 1e-12);
verifyEqual(testCase, string(get_param(results(1).core_model_name + "/PTR Radiation Adapter", "BlockType")), "MATLABFcn");
verifyInterpretedFcnSingleInput(testCase, results(1).core_model_name + "/PTR Radiation Adapter");
verifyMuxWidth(testCase, results(1).core_model_name + "/PTR Input Mux", 3);
close_system(results(1).core_model_name, 0);
for result = results
    close_system(result.model_name, 0);
    load_system(result.model_path); % cold reload
    set_param(result.model_name, 'SimulationCommand', 'update');
    verifyEqual(testCase, string(get_param(result.model_name, "SolverType")), "Fixed-step");
    verifyEqual(testCase, str2double(get_param(result.model_name, "FixedStep")), 0.02, "AbsTol", 1e-12);
    verifyEqual(testCase, str2double(get_param(result.model_name, "StopTime")), 90, "AbsTol", 1e-12);
    verifyEqual(testCase, string(get_param(result.model_name + "/Vehicle State", "BlockType")), "MATLABFcn");
    verifyEqual(testCase, string(get_param(result.model_name + "/Vehicle Excitation Afterfire", "BlockType")), "MATLABFcn");
    verifyEqual(testCase, string(get_param(result.model_name + "/PTR Radiation Model Reference", "BlockType")), "ModelReference");
    verifyEqual(testCase, string(get_param(result.model_name + "/Stereo Renderer", "BlockType")), "MATLABFcn");
    verifyEqual(testCase, string(get_param(result.model_name + "/PCM Output", "BlockType")), "Outport");
    for interpreted = ["Vehicle State", "Vehicle Excitation Afterfire", ...
            "PTR Control Selector", "Renderer Gain Selector", "Stereo Renderer"]
        verifyInterpretedFcnSingleInput(testCase, result.model_name + "/" + interpreted);
    end
    verifyMuxWidth(testCase, result.model_name + "/Excitation Clock Mux", 2);
    verifyMuxWidth(testCase, result.model_name + "/Renderer Input Mux", 2);
    for dashboard = ["Dashboard RPM", "Dashboard Load", "Dashboard Acceleration", ...
            "Dashboard Throttle", "Dashboard Order Balance", "Dashboard Transient", ...
            "Dashboard Backfire Level", "Dashboard PTR Pipe Length", ...
            "Dashboard PTR Area", "Dashboard PTR Reflection", ...
            "Dashboard PTR Damping", "Dashboard Gain"]
        binding = get_param(result.model_name + "/" + dashboard, "Binding");
        verifyFalse(testCase, isempty(binding));
    end
    compiled = get_param(result.model_name + "/PCM Output", "CompiledPortDimensions");
    pcmDimensions = compiled.Inport;
    if iscell(pcmDimensions)
        pcmDimensions = pcmDimensions{1};
    end
    if numel(pcmDimensions) >= 2 && pcmDimensions(1) == numel(pcmDimensions) - 1
        pcmDimensions = pcmDimensions(2:end);
    end
    verifyEqual(testCase, pcmDimensions, [960 2]);
    verifyEqual(testCase, result.pcm_size, [960,2]);
    close_system(result.model_name, 0);
end
end

function testClockRewindResetsPersistentModelState(testCase)
% The source helper uses the Clock time, never an invocation counter.  This
% direct gate proves rewind/run-start resets both shift and excitation context.
profile = s12_v11_load_profile("hellcat_2022_stock");
controls = s12_v11_model_dashboard_controls(profile);
controlVector = reshape([controls.default], [], 1);
cycle = s12_v11_compile_vehicle_cycle(profile);
verifyEqual(testCase, cycle.duration_s, 90);
verifyEqual(testCase, cycle.frame_count, 4500);
verifyEqual(testCase, cycle.frame_samples, 960);
verifyEqual(testCase, cycle.frame_samples / cycle.sample_rate_hz, 0.02, "AbsTol", 1e-12);
stateStart = s12_v11_model_vehicle_state_step([controlVector; 0], 1);
frameStart = s12_v11_model_excitation_afterfire_step([stateStart; 0], profile.vehicle_id);
verifyEqual(testCase, size(frameStart), [960 1]);
rpmIndex = find(string({controls.field}) == "rpm", 1, "first");
accelerating = controlVector;
accelerating(rpmIndex) = profile.vehicle_state.upshift_rpm_threshold;
stateLater = s12_v11_model_vehicle_state_step([accelerating; 20], 1);
frameLater = s12_v11_model_excitation_afterfire_step([stateLater; 20], profile.vehicle_id);
verifyEqual(testCase, size(frameLater), [960 1]);
stateReset = s12_v11_model_vehicle_state_step([controlVector; 0], 1);
frameReset = s12_v11_model_excitation_afterfire_step([stateReset; 0], profile.vehicle_id);
verifyEqual(testCase, stateReset(7), 0);
verifyEqual(testCase, frameReset, frameStart);
end

function testDashboardControlStateShiftAndConsumerContracts(testCase)
% Direct helper behavior gate.  It is authored for the approved Desktop and
% covers every Dashboard value, profile-driven up/down shifts, and fixed ports.
profile = s12_v11_load_profile("hellcat_2022_stock");
controls = s12_v11_model_dashboard_controls(profile);
expected = ["rpm", "load", "acceleration", "throttle", "order_balance", ...
    "transient", "backfire_level", "ptr_pipe_length_m", "ptr_area_m2", ...
    "ptr_reflection", "ptr_damping", "gain"];
verifyEqual(testCase, string({controls.field}), expected);
controlVector = reshape([controls.default], [], 1);
stateIdle = s12_v11_model_vehicle_state_step([controlVector; 0], 1);
verifyEqual(testCase, size(stateIdle), [21 1]);
for index = 1:numel(controls)
    altered = controlVector;
    altered(index) = controls(index).range(2);
    state = s12_v11_model_vehicle_state_step([altered; 1 + index], 1);
    verifyEqual(testCase, size(state), [21 1]);
end

rpmIndex = find(expected == "rpm", 1, "first");
upshift = controlVector;
upshift(rpmIndex) = profile.vehicle_state.upshift_rpm_threshold;
stateUp = s12_v11_model_vehicle_state_step([upshift; 20], 1);
verifyEqual(testCase, stateUp(7), 1); % upshift
downshift = controlVector;
downshift(rpmIndex) = profile.vehicle_state.downshift_rpm_threshold;
stateDown = s12_v11_model_vehicle_state_step([downshift; 40], 1);
verifyEqual(testCase, stateDown(7), 2); % downshift
ptrControls = s12_v11_model_ptr_controls_step(stateDown, 1);
verifyEqual(testCase, size(ptrControls), [4 1]);
gain = s12_v11_model_renderer_gain_step(stateDown, 1);
verifyGreaterThanOrEqual(testCase, gain, 0);
verifyLessThanOrEqual(testCase, gain, 0.2);
end

function verifyInterpretedFcnSingleInput(testCase, blockPath)
verifyEqual(testCase, string(get_param(blockPath, "BlockType")), "MATLABFcn");
ports = get_param(blockPath, "PortHandles");
verifyEqual(testCase, numel(ports.Inport), 1);
line = get_param(ports.Inport(1), "Line");
verifyNotEqual(testCase, line, -1);
destinations = get_param(line, "DstPortHandle");
verifyTrue(testCase, any(destinations == ports.Inport(1)));
end

function verifyMuxWidth(testCase, blockPath, expectedInputs)
verifyEqual(testCase, string(get_param(blockPath, "BlockType")), "Mux");
verifyEqual(testCase, str2double(get_param(blockPath, "Inputs")), expectedInputs);
end
