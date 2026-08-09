function tests = test_s12_engine_identity_v014
%TEST_S12_ENGINE_IDENTITY_V014 Contracts for synthetic pre-PTR identities.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
testFolder = fileparts(mfilename("fullpath"));
s12Folder = fileparts(testFolder);
testCase.TestData.commonFolder = fullfile(s12Folder, "playground_v12", "common");
testCase.TestData.vehicleFolder = fullfile(s12Folder, "playground_v12", "vehicles");
addpath(testCase.TestData.commonFolder);
testCase.addTeardown(@() rmpath(testCase.TestData.commonFolder));
end

function testIdentityProfilesLoadWithSyntheticProvenance(testCase)
profileIds = ["hellcat_2022_stock", "ferrari_458_stock", "rx7_fd_1991_stock"];
engineTypes = ["supercharged_cross_plane_v8", ...
    "naturally_aspirated_flat_plane_v8", "twin_rotor_turbo"];
cylinderCounts = [8, 8, 2];
rpmLimits = [6500, 9000, 8000];
for index = 1:numel(profileIds)
    identity = s12_v12_load_engine_identity_profile(profileIds(index));
    verifyEqual(testCase, identity.engine_type, engineTypes(index));
    verifyEqual(testCase, identity.cylinder_count, cylinderCounts(index));
    verifyEqual(testCase, identity.rpm_limit, rpmLimits(index));
    verifyEqual(testCase, identity.provenance, "C/synthetic/uncalibrated");
end
end

function testIdentityValidatorRejectsMissingProvenance(testCase)
path = fullfile(testCase.TestData.vehicleFolder, "hellcat_2022_stock", ...
    "engine_identity_profile.json");
profile = jsondecode(fileread(path));
profile.turbo_or_supercharger_profile.whine_gain = rmfield( ...
    profile.turbo_or_supercharger_profile.whine_gain, "source_level");
verifyError(testCase, @() s12_v12_validate_engine_identity_profile(profile), ...
    "S12:EngineIdentity:Profile");
end

function testFerrariHighFrequencyIdentityEnergyRisesWithRpm(testCase)
identity = s12_v12_load_engine_identity_profile("ferrari_458_stock");
rpms = [2000, 4500, 7000, 9000];
energies = zeros(size(rpms));
for index = 1:numel(rpms)
    [~, ~, diagnostics] = renderIdentityAt(identity, rpms(index), 0.75, 0.75);
    energies(index) = diagnostics.high_frequency_energy;
end
verifyTrue(testCase, all(diff(energies) > 0));
end

function testHellcatSuperchargerWhineRisesWithLoad(testCase)
identity = s12_v12_load_engine_identity_profile("hellcat_2022_stock");
[~, ~, lowLoad] = renderIdentityAt(identity, 3000, 0.15, 0.25);
[~, ~, highLoad] = renderIdentityAt(identity, 3000, 0.85, 0.85);
verifyGreaterThan(testCase, highLoad.supercharger_whine_energy, ...
    2 * lowLoad.supercharger_whine_energy);
verifyGreaterThan(testCase, highLoad.v8_exhaust_energy, 0);
end

function testRx7IdentityUsesRotaryPulseAndTurboTimeStructure(testCase)
identity = s12_v12_load_engine_identity_profile("rx7_fd_1991_stock");
[frame, ~, diagnostics] = renderIdentityAt(identity, 5000, 0.75, 0.75);
verifySize(testCase, frame, [960, 2]);
verifyGreaterThan(testCase, diagnostics.rotary_event_count, 0);
verifyGreaterThan(testCase, diagnostics.rotary_gate_variance, 1e-6);
verifyGreaterThan(testCase, diagnostics.turbo_spool, 0);
verifyGreaterThan(testCase, diagnostics.turbine_energy, 0);
end

function testIdentityLevelIsNotRpmDrivenAtConstantLoad(testCase)
profileIds = ["hellcat_2022_stock", "ferrari_458_stock", "rx7_fd_1991_stock"];
for index = 1:numel(profileIds)
    identity = s12_v12_load_engine_identity_profile(profileIds(index));
    [lowRpm, ~, ~] = renderIdentityAt(identity, 2500, 0.55, 0.60);
    [highRpm, ~, ~] = renderIdentityAt(identity, ...
        min(8000, identity.rpm_limit), 0.55, 0.60);
    deltaDb = abs(20 * log10( ...
        sqrt(mean(highRpm(:) .^ 2)) / sqrt(mean(lowRpm(:) .^ 2))));
    verifyLessThan(testCase, deltaDb, 1.0);
end
end

function testIdentityDemoNamesCoverRequiredListeningSegments(testCase)
names = s12_v12_identity_demo_names("ferrari_458_stock");
verifyEqual(testCase, names, [ ...
    "ferrari_identity_v01.wav", ...
    "ferrari_identity_v01_idle.wav", ...
    "ferrari_identity_v01_acceleration.wav", ...
    "ferrari_identity_v01_lift.wav", ...
    "ferrari_identity_v01_full_pull.wav"]);
end

function testIdentitySeparationAtThreeThousandRpm(testCase)
profileIds = ["hellcat_2022_stock", "ferrari_458_stock", "rx7_fd_1991_stock"];
features = zeros(numel(profileIds), 3);
state = stateAt(3000, 0.65, 0.65);
for index = 1:numel(profileIds)
    source = loadSourceProfile(testCase, profileIds(index));
    [~, context] = s12_v12_render_pre_ptr_frame(state, source, [], 48000, 960);
    [frame, ~, diagnostics] = s12_v12_render_pre_ptr_frame( ...
        state, source, context, 48000, 960);
    verifyTrue(testCase, isfield(diagnostics, "identity"));
    features(index, :) = identityFeatures(frame, 3000);
end
verifyGreaterThan(testCase, abs(features(1, 1) - features(2, 1)), 100);
verifyGreaterThan(testCase, abs(features(1, 1) - features(3, 1)), 100);
verifyGreaterThan(testCase, abs(features(2, 2) - features(3, 2)), 1e-4);
verifyGreaterThan(testCase, abs(features(1, 3) - features(2, 3)), 0.01);
end

function [frame, context, diagnostics] = renderIdentityAt(identity, rpm, load, throttle)
sampleRate = 48000;
frameSamples = 960;
crankPhase = 2 * pi * (rpm / 60) * (0:frameSamples - 1)' / sampleRate;
[frame, context, diagnostics] = s12_v12_render_engine_identity_frame( ...
    identity, crankPhase, rpm * ones(frameSamples, 1), ...
    load * ones(frameSamples, 1), throttle * ones(frameSamples, 1), ...
    zeros(frameSamples, 1), [], sampleRate, frameSamples);
end

function state = stateAt(rpm, load, throttle)
state = struct("rpm", rpm, "load", load, "throttle", throttle, ...
    "acceleration", 0, "shift_event", 0, "shift_progress", 0, ...
    "afterfire_kind", "none", "afterfire_progress", 0);
end

function features = identityFeatures(frame, rpm)
frame = frame(:, 1);
power = abs(fft(frame)) .^ 2;
frequencies = (0:numel(frame) - 1)' * 48000 / numel(frame);
keep = frequencies <= 12000;
power = power(keep);
frequencies = frequencies(keep);
centroid = sum(frequencies .* power) / sum(power);
orderBand = abs(frequencies - 4 * rpm / 60) <= 100;
orderEnergy = sum(power(orderBand));
lowBand = frequencies >= 100 & frequencies <= 1000;
highBand = frequencies >= 2500 & frequencies <= 10000;
harmonicRatio = sum(power(highBand)) / max(sum(power(lowBand)), eps);
features = [centroid, orderEnergy, harmonicRatio];
end

function profile = loadSourceProfile(testCase, profileId)
path = fullfile(testCase.TestData.vehicleFolder, profileId, "source_profile.json");
profile = jsondecode(fileread(path));
end
