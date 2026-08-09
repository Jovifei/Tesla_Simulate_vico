function tests = test_s12_sound_playground_condition_contracts
%TEST_S12_SOUND_PLAYGROUND_CONDITION_CONTRACTS Exercise scalar condition helpers.

tests = functiontests(localfunctions);
end

function setupOnce(testCase)
playground = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground");
addpath(playground);
testCase.TestData.playground = playground;
end

function teardownOnce(testCase)
rmpath(testCase.TestData.playground);
end

function testTextScalarNormalizesCharAndString(testCase)
verifyEqual(testCase, s12_sound_playground_require_text_scalar('idle', "state"), "idle");
verifyEqual(testCase, s12_sound_playground_require_text_scalar("cruise", "state"), "cruise");
end

function testTextScalarRejectsVectorsMissingAndMultiRowChar(testCase)
for value = {["idle", "cruise"], missing, ['i', 'd'; 'l', 'e'], 42, ""}
    verifyError(testCase, @() s12_sound_playground_require_text_scalar(value{1}, "state"), ...
        "S12:Playground:TextScalar");
end
end

function testShaScalarHelpersNeverReturnLogicalVectors(testCase)
actual = string(repmat('A', 1, 64));
value = s12_sound_playground_sha256_equal(actual, lower(char(actual)));
verifyClass(testCase, value, "logical");
verifySize(testCase, value, [1, 1]);
end
