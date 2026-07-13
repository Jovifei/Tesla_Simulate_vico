function tests = test_s12_benchmark_entrypoints
%TEST_S12_BENCHMARK_ENTRYPOINTS Verify run and report-only entry points.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testSingleCaseAndReportOnlyUseSameCanonicalResult(testCase)
runDirectory = tempname;
reportDirectory = tempname;
testCase.addTeardown(@() removeDirectory(runDirectory));
testCase.addTeardown(@() removeDirectory(reportDirectory));

executed = run_s12_benchmarks("case:uniform_state", ...
    Profile="quick", OutputDirectory=runDirectory);
manifest = fullfile(runDirectory, "benchmark-result.json");
rebuilt = run_s12_benchmarks("report-only", ...
    SourceManifest=manifest, OutputDirectory=reportDirectory);

verifyEqual(testCase, numel(executed.cases), 1);
verifyEqual(testCase, executed.cases.id, "uniform_state");
verifyEqual(testCase, executed.acceptance.status, "passed");
verifyEqual(testCase, rebuilt.acceptance.status, executed.acceptance.status);
verifyEqual(testCase, readBytes(manifest), readBytes(fullfile( ...
    reportDirectory, "benchmark-result.json")));
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
