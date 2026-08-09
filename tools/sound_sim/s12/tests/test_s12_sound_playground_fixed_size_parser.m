function tests = test_s12_sound_playground_fixed_size_parser
%TEST_S12_SOUND_PLAYGROUND_FIXED_SIZE_PARSER Exercise Stateflow size parsing.

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

function testAcceptsDeclaredFixedTwoDimensionalFormats(testCase)
for rawSize = ["[18,1]", "[18 1]", "18,1"]
    errorIdentifier = "";
    shape = [];
    try
        shape = s12_sound_playground_parse_fixed_size(rawSize, "Chart", "Stateflow", "packed");
    catch cause
        errorIdentifier = string(cause.identifier);
    end
    verifyEqual(testCase, errorIdentifier, "");
    if strlength(errorIdentifier) == 0
        verifyEqual(testCase, shape, [18, 1]);
    end
end
end
