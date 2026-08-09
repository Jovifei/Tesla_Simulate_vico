function tests = test_s12_sound_playground_sha256_contracts
%TEST_S12_SOUND_PLAYGROUND_SHA256_CONTRACTS Validate scalar SHA comparison contracts.

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

function testAcceptedNormalizedForms(testCase)
[upperHash, lowerHash] = validHashes();
verifyTrue(testCase, s12_sound_playground_sha256_equal(upperHash, lowerHash));
verifyTrue(testCase, s12_sound_playground_sha256_equal(char(lowerHash), upperHash));
verifyTrue(testCase, s12_sound_playground_sha256_equal(lowerHash + newline, upperHash));
end

function testMalformedInputsReturnFalse(testCase)
[upperHash, ~] = validHashes();
cases = {"", missing, [upperHash, upperHash], ['A', 'B'; 'C', 'D'], ...
    string(repmat('A', 1, 63)), string(repmat('A', 1, 65)), string(repmat('G', 1, 64)), 42};
for index = 1:numel(cases)
    verifyFalse(testCase, s12_sound_playground_sha256_equal(cases{index}, upperHash));
end
end

function testRequireReportsScalarDiagnostics(testCase)
[upperHash, ~] = validHashes();
verifyError(testCase, @() s12_sound_playground_require_sha256_equal("", upperHash, "empty actual"), ...
    "S12:Playground:HashMismatch");
try
    s12_sound_playground_require_sha256_equal("", upperHash, "empty actual");
catch cause
    verifySubstring(testCase, cause.message, "actual class=");
    verifySubstring(testCase, cause.message, "expected class=");
    verifySubstring(testCase, cause.message, "size=");
end
end

function [upperHash, lowerHash] = validHashes()
upperHash = string(repmat('A', 1, 64));
lowerHash = lower(upperHash);
end
