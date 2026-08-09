function tests = test_s12_sound_playground_function_scripts
%TEST_S12_SOUND_PLAYGROUND_FUNCTION_SCRIPTS Exercise generated MATLAB Function text.

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

function testGeneratedScriptsAreScalarAndContainCodegenDirective(testCase)
scripts = s12_sound_playground_function_scripts();
for name = ["engine", "ptr", "renderer"]
    script = scripts.(char(name));
    verifyClass(testCase, script, "string");
    verifySize(testCase, script, [1, 1]);
    verifyTrue(testCase, contains(script, "%#codegen"));
    verifyTrue(testCase, contains(script, "function"));
end
end
