function tests = test_s12_sound_playground_atomic_write_json_runtime
%TEST_S12_SOUND_PLAYGROUND_ATOMIC_WRITE_JSON_RUNTIME Exercise writer behavior in MATLAB.

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

function testSha256ReturnsScalarString(testCase)
root = string(tempname);
mkdir(root);
rootCleanup = onCleanup(@() removeRoot(root));
path = fullfile(root, "hash-input.txt");
file = fopen(path, "w", "n", "UTF-8");
fprintf(file, "synthetic");
fclose(file);

digest = s12_sound_playground_sha256(path);
verifyClass(testCase, digest, "string");
verifySize(testCase, digest, [1, 1]);
verifyTrue(testCase, s12_sound_playground_sha256_equal(digest, digest));
end

function testSha256EqualityIsScalarAndTypeChecked(testCase)
valid = string(repmat('A', 1, 64));
verifyTrue(testCase, s12_sound_playground_sha256_equal(valid, lower(char(valid))));
verifyFalse(testCase, s12_sound_playground_sha256_equal(valid, string(repmat('B', 1, 64))));
verifyError(testCase, @() s12_sound_playground_require_sha256_equal([valid, valid], valid, "runtime test"), ...
    "S12:Playground:HashScalar");
end

function testAtomicWriterSelftestRuns(testCase)
root = string(tempname);
mkdir(root);
rootCleanup = onCleanup(@() removeRoot(root));

result = s12_sound_playground_atomic_write_json_selftest(root, "matlab-runtime-test");
verifyEqual(testCase, string(result.status), "ATOMIC_WRITER_SELFTEST_PASSED");
verifyEqual(testCase, result.temporary_files, 0);
verifyEqual(testCase, result.owned_open_handles, 0);
verifyEqual(testCase, result.consecutive_writes, 100);
end

function removeRoot(root)
if isfolder(root)
    rmdir(root, "s");
end
end
