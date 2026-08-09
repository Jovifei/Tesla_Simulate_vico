function tests = test_s12_engine_sound_v10_model_excitation
%TEST_S12_ENGINE_SOUND_V10_MODEL_EXCITATION Contract tests for top-model source.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
source = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground_v10");
testCase.TestData.source = source;
addpath(source);
end

function teardownOnce(testCase)
if isfolder(testCase.TestData.source)
    rmpath(testCase.TestData.source);
end
end

function testModelExcitationHasFixedAudioFrameShape(testCase)
profile = s12_engine_sound_load_profile("inline4_sport");
output = runStep(profile, [3000; 0.5; 1.2; 0.6; 80; 0], true, 0);
verifySize(testCase, output, [960, 1]);
verifyTrue(testCase, all(isfinite(output)));
end

function testAccelerationAndBackfireInputsAffectExcitation(testCase)
profile = s12_engine_sound_load_profile("hellcat_style_supercharged_v8");
steady = runStep(profile, [3500; 0.6; 0.0; 0.6; 80; 0], true, 0);
accelerating = runStep(profile, [3500; 0.6; 3.0; 0.6; 80; 0], true, 0);
backfire = runStep(profile, [3500; 0.1; -2.0; 0.0; 80; 1], true, 0.30);
verifyGreaterThan(testCase, rms(accelerating - steady), 1e-4);
verifyGreaterThan(testCase, rms(backfire - steady), 1e-4);
end

function testCylinderLayoutProfilesHaveDistinctExcitation(testCase)
inlineFive = s12_engine_sound_load_profile("inline5_character");
highRev = s12_engine_sound_load_profile("ferrari_style_high_rev_v8");
state = [4200; 0.7; 1.0; 0.7; 95; 0];
first = runStep(inlineFive, state, true, 0);
second = runStep(highRev, state, true, 0);
verifyGreaterThan(testCase, norm(first - second), 1e-3);
end

function output = runStep(profile, state, reset, backfireEnergy)
output = s12_engine_sound_model_excitation_step(state, reset, ...
    profile.engine.cylinder_count.value, profile.engine.firing_order.value, ...
    profile.engine.firing_phase_deg.value, profile.engine.bank_map.value, ...
    profile.synthesis.order_gains.value, profile.synthesis.pulse_sharpness.value, ...
    profile.synthesis.harmonic_tilt.value, profile.synthesis.intake_tone.value, ...
    profile.synthesis.supercharger_tone.value, profile.transient.attack.value, ...
    profile.transient.decay.value, profile.transient.acceleration_gain.value, ...
    profile.transient.lift_gain.value, backfireEnergy);
end
