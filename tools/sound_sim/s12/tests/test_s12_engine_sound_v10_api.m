function tests = test_s12_engine_sound_v10_api
%TEST_S12_ENGINE_SOUND_V10_API Public v1.0 audition API contracts.
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

function testProfileMapsToIndependentTopModel(testCase)
path = s12_engine_sound_model_path("inline5_character");
verifyTrue(testCase, isfile(path));
verifyEqual(testCase, string(erase(string(path), fileparts(path) + filesep)), ...
    "S12_I5_Character_v10.slx");
end

function testOpenModelSupportsLoadOnlyMode(testCase)
path = s12_engine_sound_open_model("v6_sport", "Open", false);
verifyTrue(testCase, bdIsLoaded("S12_V6_Sport_v10"));
verifyTrue(testCase, isfile(path));
end

function testRenderAllSupportsOneProfileDispatch(testCase)
runId = "api_contract_" + string(randi(1e9));
results = s12_engine_sound_render_all("ProfileIds", "inline3_turbo", ...
    "RunId", runId, "Play", false);
verifySize(testCase, results, [1, 1]);
verifyEqual(testCase, results.profile_id, "inline3_turbo");
verifyEqual(testCase, results.frame_count, 4500);
verifyTrue(testCase, isfile(fullfile(results.output_directory, "full_drive_cycle.wav")));
end
