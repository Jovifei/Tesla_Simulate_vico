function tests = test_s12_benchmark_report
%TEST_S12_BENCHMARK_REPORT Verify deterministic report-only rendering.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testReportOnlyPreservesAcceptanceAndIsDeterministic(testCase)
environment = struct("git_commit", "deadbeef", ...
    "matlab_release", "R2026a", "platform", "win64");
canonical = s12_benchmark_new_result("quick", ...
    "case:smooth_periodic_entropy_wave", environment);
canonical.cases = sampleSmoothCase();
canonical.acceptance = struct("status", "failed", ...
    "checks", struct("id", "manual_sentinel", "passed", false));
outA = tempname;
outB = tempname;
mkdir(outA);
mkdir(outB);
testCase.addTeardown(@() removeDirectory(outA));
testCase.addTeardown(@() removeDirectory(outB));

writtenA = s12_write_benchmark_artifacts(canonical, outA);
writtenB = s12_write_benchmark_artifacts(canonical, outB);

expected = ["benchmark-report.md", "benchmark-result.json", ...
    "benchmark-summary.csv", "smooth-convergence.png"];
for fileIndex = 1:numel(expected)
    verifyTrue(testCase, isfile(fullfile(outA, expected(fileIndex))));
    verifyEqual(testCase, readBytes(fullfile(outA, expected(fileIndex))), ...
        readBytes(fullfile(outB, expected(fileIndex))));
end
verifyEqual(testCase, writtenA.acceptance.status, "failed");
verifyEqual(testCase, writtenB.acceptance.status, "failed");
decoded = jsondecode(fileread(fullfile(outA, "benchmark-result.json")));
verifyEqual(testCase, string(decoded.acceptance.status), "failed");
verifyEqual(testCase, string(decoded.schema), "benchmark.schema.v1");
end

function benchmarkCase = sampleSmoothCase
benchmarkCase = struct( ...
    "id", "smooth_periodic_entropy_wave", ...
    "category", "temporal_accuracy", ...
    "status", "passed", ...
    "config", struct("cell_count", 16, "cfl", 0.45), ...
    "metrics", struct( ...
        "dt_requested", [0.01, 0.005, 0.0025, 0.00125], ...
        "self_error", [8e-5, 1e-5, 1.25e-6], ...
        "observed_order", [3, 3], ...
        "conservation_error", 1e-14, ...
        "runtime_seconds", 1.25), ...
    "acceptance", struct("status", "passed", "checks", struct([])), ...
    "plot", struct("x", [1, 2, 4, 8], ...
        "error", [8e-5, 1e-5, 1.25e-6, 1.5625e-7]));
end

function bytes = readBytes(path)
fileId = fopen(path, "rb");
cleanup = onCleanup(@() fclose(fileId));
bytes = fread(fileId, Inf, "*uint8");
end

function removeDirectory(path)
if isfolder(path)
    rmdir(path, "s");
end
end
