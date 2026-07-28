function tests = test_s12_engine_sound_v10_profiles
%TEST_S12_ENGINE_SOUND_V10_PROFILES Contract tests for v1.0 JSON profiles.
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

function testBuiltinProfilesHaveExactSyntheticIdentity(testCase)
profiles = s12_engine_sound_list_profiles();
expected = ["inline3_turbo", "inline4_sport", "inline5_character", "inline6_smooth", ...
    "v6_sport", "hellcat_style_supercharged_v8", "ferrari_style_high_rev_v8"];
verifyEqual(testCase, string({profiles.id}), expected);
verifyEqual(testCase, [profiles.cylinders], [3, 4, 5, 6, 6, 8, 8]);
verifyTrue(testCase, all([profiles.synthetic]));
end

function testProfileLoaderPreservesApprovedEngineDefinitions(testCase)
profile = s12_engine_sound_load_profile("inline5_character");
verifyEqual(testCase, profile.profile_id.value, "inline5_character");
verifyEqual(testCase, profile.engine.cylinder_count.value, 5);
verifyEqual(testCase, profile.engine.firing_order.value, [1, 2, 4, 5, 3]);
verifyEqual(testCase, profile.engine.idle_rpm.value, 850);
verifyEqual(testCase, profile.engine.redline_rpm.value, 7200);
verifyEqual(testCase, profile.backfire.default_level.value, "subtle");
end

function testEveryProfileParameterHasSyntheticProvenance(testCase)
profile = s12_engine_sound_load_profile("ferrari_style_high_rev_v8");
result = s12_engine_sound_validate_profile(profile);
verifyTrue(testCase, result.valid);
verifyEqual(testCase, result.provenance_coverage, 1);
verifyGreaterThan(testCase, result.parameter_count, 20);
end

function testValidatorRejectsInvalidCylinderCount(testCase)
profile = s12_engine_sound_load_profile("inline3_turbo");
profile.engine.cylinder_count.value = 2;
verifyError(testCase, @()s12_engine_sound_validate_profile(profile), ...
    "S12:EngineSoundV10:CylinderCount");
end

function testValidatorRejectsInvalidFiringPermutation(testCase)
profile = s12_engine_sound_load_profile("inline4_sport");
profile.engine.firing_order.value = [1, 3, 3, 2];
verifyError(testCase, @()s12_engine_sound_validate_profile(profile), ...
    "S12:EngineSoundV10:FiringOrder");
end

function testValidatorRejectsInvalidRpmRange(testCase)
profile = s12_engine_sound_load_profile("v6_sport");
profile.engine.idle_rpm.value = 7600;
verifyError(testCase, @()s12_engine_sound_validate_profile(profile), ...
    "S12:EngineSoundV10:RpmRange");
end

function testValidatorRejectsWrongOrderGainLength(testCase)
profile = s12_engine_sound_load_profile("inline6_smooth");
profile.synthesis.order_gains.value = [1, 0.7, 0.4];
verifyError(testCase, @()s12_engine_sound_validate_profile(profile), ...
    "S12:EngineSoundV10:OrderGainLength");
end

function testValidatorRejectsMissingProvenance(testCase)
profile = s12_engine_sound_load_profile("v6_sport");
profile.engine.layout = rmfield(profile.engine.layout, "source_level");
verifyError(testCase, @()s12_engine_sound_validate_profile(profile), ...
    "S12:EngineSoundV10:Provenance");
end

function testValidatorRejectsUnknownFields(testCase)
profile = s12_engine_sound_load_profile("inline4_sport");
profile.unreviewed_parameter = struct("value", 1, "unit", "", "range", [0, 1], ...
    "source_level", "C", "source", "synthetic");
verifyError(testCase, @()s12_engine_sound_validate_profile(profile), ...
    "S12:EngineSoundV10:UnknownField");
end
