function tests = test_s12_v12_source_core_matlab
%TEST_S12_V12_SOURCE_CORE_MATLAB Runtime contracts for the v1.2 pre-PTR source.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
testFolder = fileparts(mfilename("fullpath"));
s12Folder = fileparts(testFolder);
commonFolder = fullfile(s12Folder, "playground_v12", "common");
testCase.TestData.commonFolder = commonFolder;
testCase.TestData.vehicleFolder = fullfile(s12Folder, "playground_v12", "vehicles");
addpath(commonFolder);
testCase.addTeardown(@() rmpath(commonFolder));
end

function testPilotProfilesRenderFiniteDeterministicPrePtrFrames(testCase)
profileIds = ["hellcat_2022_stock", "ferrari_458_stock", "rx7_fd_1991_stock"];
state = struct( ...
    "rpm", 3200, ...
    "load", 0.55, ...
    "throttle", 0.60, ...
    "acceleration", 1.2, ...
    "shift_event", 0, ...
    "shift_progress", 0, ...
    "afterfire_kind", "none", ...
    "afterfire_progress", 0);

for profileId = profileIds
    profile = loadProfile(testCase, profileId);
    normalized = s12_v12_validate_source_profile(profile);
    verifyEqual(testCase, normalized.engine_kind, string(profile.source.engine_kind.value));

    [firstFrame, firstContext, diagnostics] = s12_v12_render_pre_ptr_frame( ...
        state, profile, [], 48000, 960);
    [repeatFrame, repeatContext] = s12_v12_render_pre_ptr_frame( ...
        state, profile, [], 48000, 960);
    [nextFrame, nextContext] = s12_v12_render_pre_ptr_frame( ...
        state, profile, firstContext, 48000, 960);

    verifySize(testCase, firstFrame, [960, 1]);
    verifyTrue(testCase, all(isfinite(firstFrame), "all"));
    verifyEqual(testCase, repeatFrame, firstFrame);
    verifyEqual(testCase, repeatContext, firstContext);
    verifyEqual(testCase, diagnostics.pre_ptr_adapter, ...
        "bank_excitation_to_one_port_ptr_input");
    verifyEqual(testCase, firstContext.frame_index, 1);
    verifyEqual(testCase, nextContext.frame_index, 2);
    verifyNotEqual(testCase, nextFrame, firstFrame);
end
end

function testHeldAccelerationProducesOnlyDecayingOnset(testCase)
profile = loadProfile(testCase, "hellcat_2022_stock");
idle = struct( ...
    "rpm", 3200, "load", 0.55, "throttle", 0.60, "acceleration", 0, ...
    "shift_event", 0, "shift_progress", 0, ...
    "afterfire_kind", "none", "afterfire_progress", 0);
accelerating = idle;
accelerating.acceleration = 4;

[~, context] = s12_v12_render_pre_ptr_frame(idle, profile, [], 48000, 960);
[~, context, onset] = s12_v12_render_pre_ptr_frame( ...
    accelerating, profile, context, 48000, 960);
for frameIndex = 1:4
    [~, context, held] = s12_v12_render_pre_ptr_frame( ...
        accelerating, profile, context, 48000, 960);
end

verifyGreaterThan(testCase, onset.layer_energy.transient, 0);
verifyLessThan(testCase, held.layer_energy.transient, ...
    0.01 * onset.layer_energy.transient);

accelerating.acceleration = 5;
[~, ~, retriggered] = s12_v12_render_pre_ptr_frame( ...
    accelerating, profile, context, 48000, 960);
verifyGreaterThan(testCase, retriggered.layer_energy.transient, ...
    100 * held.layer_energy.transient);
end

function testSteadySourceLevelIsNotRpmDriven(testCase)
profile = loadProfile(testCase, "ferrari_458_stock");
state = struct( ...
    "rpm", 2500, "load", 0.55, "throttle", 0.60, "acceleration", 0, ...
    "shift_event", 0, "shift_progress", 0, ...
    "afterfire_kind", "none", "afterfire_progress", 0);

[~, context] = s12_v12_render_pre_ptr_frame(state, profile, [], 48000, 960);
[lowRpmFrame, context] = s12_v12_render_pre_ptr_frame( ...
    state, profile, context, 48000, 960);
state.rpm = 8000;
[~, context] = s12_v12_render_pre_ptr_frame(state, profile, context, 48000, 960);
[highRpmFrame, ~] = s12_v12_render_pre_ptr_frame( ...
    state, profile, context, 48000, 960);

sourceLevelDeltaDb = abs(20 * log10( ...
    sqrt(mean(highRpmFrame .^ 2)) / sqrt(mean(lowRpmFrame .^ 2))));
verifyLessThan(testCase, sourceLevelDeltaDb, 1.5);
end

function testMatlabValidatorRejectsNonscalarGain(testCase)
profile = loadProfile(testCase, "hellcat_2022_stock");
profile.source.flow_gain.value = [0.1, 0.2];
verifyError(testCase, @() s12_v12_validate_source_profile(profile), ...
    "S12:EngineSoundV12:SourceProfile");
end

function testMatlabValidatorRejectsWrongRotaryRatio(testCase)
profile = loadProfile(testCase, "rx7_fd_1991_stock");
profile.source.shaft_turns_per_rotor_turn.value = 1;
verifyError(testCase, @() s12_v12_validate_source_profile(profile), ...
    "S12:EngineSoundV12:SourceProfile");
end

function testFrozenRadiationAdapterIsDeterministicAndChunkInvariant(testCase)
sampleRate = 48000;
input = sin(2 * pi * (1:1920)' * 137 / sampleRate);

[whole, wholeContext, diagnostics] = ...
    s12_v12_apply_frozen_radiation_frame(input, [], sampleRate);
[first, firstContext] = ...
    s12_v12_apply_frozen_radiation_frame(input(1:960), [], sampleRate);
[second, secondContext] = ...
    s12_v12_apply_frozen_radiation_frame(input(961:end), firstContext, sampleRate);
[repeat, repeatContext] = ...
    s12_v12_apply_frozen_radiation_frame(input, [], sampleRate);

verifySize(testCase, whole, [1920, 1]);
verifyTrue(testCase, all(isfinite(whole), "all"));
verifyEqual(testCase, [first; second], whole, "AbsTol", 1e-14);
verifyEqual(testCase, repeat, whole);
verifyEqual(testCase, repeatContext, wholeContext);
verifyEqual(testCase, secondContext.frame_index, 2);
verifyEqual(testCase, diagnostics.configuration, ...
    "frozen_4d_b_radiation_audio_adapter");
verifyFalse(testCase, diagnostics.full_fvm_ptr_network);
verifyEqual(testCase, diagnostics.radiation_package_sha256, ...
    "0f4b2ca494cd44f79d05968513759578d04e6ab38b1ee37f7621158abb0d2d6f");
verifyEqual(testCase, diagnostics.radiation_source_commit, ...
    "4afe65a67ed21822422f1eb6dbf43fdd627072d3");
end

function testFrozenRadiationAdapterRejectsInvalidContext(testCase)
badContext = struct("frame_index", 1);
verifyError(testCase, @() s12_v12_apply_frozen_radiation_frame( ...
    zeros(960, 1), badContext, 48000), ...
    "S12:EngineSoundV12:RadiationAdapter");
end

function testSourceToRadiationFramePreservesCausalLayering(testCase)
profile = loadProfile(testCase, "hellcat_2022_stock");
state = struct( ...
    "rpm", 4200, ...
    "load", 0.8, ...
    "throttle", 0.9, ...
    "acceleration", 2.5, ...
    "shift_event", 0, ...
    "shift_progress", 0, ...
    "afterfire_kind", "none", ...
    "afterfire_progress", 0);

[pressure, context, diagnostics] = ...
    s12_v12_render_radiated_frame(state, profile, [], 48000, 960);

verifySize(testCase, pressure, [960, 1]);
verifyTrue(testCase, all(isfinite(pressure), "all"));
verifyEqual(testCase, context.source.frame_index, 1);
verifyEqual(testCase, context.radiation.frame_index, 1);
verifyEqual(testCase, diagnostics.topology, ...
    "source_to_bank_mixer_to_frozen_radiation_adapter");
verifyFalse(testCase, diagnostics.full_fvm_ptr_network);
verifyEqual(testCase, diagnostics.source.pre_ptr_adapter, ...
    "bank_excitation_to_one_port_ptr_input");
end

function testSimulinkStepAdaptersHaveFixedFrameContracts(testCase)
sourceInput = [3200; 0.55; 0.60; 1.2; 0; 0; 0; 0; 0];
source = s12_v12_model_source_step(sourceInput, "hellcat_2022_stock");
radiation = s12_v12_model_radiation_step([source; 0]);
stereo = s12_v12_model_stereo_renderer_step([radiation; 0.10]);

verifySize(testCase, source, [960, 1]);
verifySize(testCase, radiation, [960, 1]);
verifySize(testCase, stereo, [960, 2]);
verifyTrue(testCase, all(isfinite(stereo), "all"));
verifyLessThan(testCase, max(abs(stereo), [], "all"), 1);
end

function testNinetySecondVehicleCycleHasContinuousBoundedPhases(testCase)
times = (0:0.02:89.98).';
states = zeros(numel(times), 8);
for index = 1:numel(times)
    states(index, :) = s12_v12_vehicle_cycle_state( ...
        times(index), "hellcat_2022_stock").';
end

verifySize(testCase, states, [4500, 8]);
verifyTrue(testCase, all(isfinite(states), "all"));
verifyGreaterThanOrEqual(testCase, min(states(:, 1)), 0);
verifyLessThanOrEqual(testCase, max(states(:, 1)), 6500);
verifyLessThan(testCase, max(abs(diff(states(:, 1)))), 80);
verifyEqual(testCase, unique(states(times >= 2 & times < 12, 7)), 0);
verifyEqual(testCase, unique(states(times >= 22 & times < 32, 7)), 0);
verifyTrue(testCase, all(states(times >= 54 & times < 66, 7) == 3));
verifyTrue(testCase, all(states(times >= 82 & times < 88, 7) == 3));
end

function testFullCycleCanTraverseEveryDiscreteTransient(testCase)
profile = loadProfile(testCase, "hellcat_2022_stock");
context = [];
for frameIndex = 1:4500
    time = (frameIndex - 1) * 0.02;
    packed = s12_v12_vehicle_cycle_state(time, "hellcat_2022_stock");
    kinds = ["none", "upshift_bark", ...
        "downshift_blip_pop", "overrun_crackle"];
    state = struct( ...
        "rpm", packed(1), "load", packed(2), ...
        "throttle", packed(3), "acceleration", packed(4), ...
        "shift_event", packed(5), "shift_progress", packed(6), ...
        "afterfire_kind", kinds(packed(7) + 1), ...
        "afterfire_progress", packed(8));
    [frame, context] = s12_v12_render_pre_ptr_frame( ...
        state, profile, context, 48000, 960);
    verifyTrue(testCase, all(isfinite(frame), "all"));
end
verifyEqual(testCase, context.frame_index, 4500);
end

function profile = loadProfile(testCase, profileId)
profilePath = fullfile(testCase.TestData.vehicleFolder, profileId, "source_profile.json");
profile = jsondecode(fileread(profilePath));
end
