function tests = test_s12_benchmark_baseline_promotion
%TEST_S12_BENCHMARK_BASELINE_PROMOTION Verify explicit baseline gating.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testPromotionRequiresExplicitTokenAndPassingManifest(testCase)
source = tempname;
destination = tempname;
mkdir(source);
testCase.addTeardown(@() removeDirectory(source));
testCase.addTeardown(@() removeDirectory(destination));
writeFile(fullfile(source, "benchmark-report.md"), "stable report");
manifest = struct( ...
    "schema", "benchmark.schema.v1", ...
    "environment", struct("git_commit", "deadbeef"), ...
    "acceptance", struct("status", "passed"), ...
    "artifacts", struct("id", "report", "type", "markdown", ...
        "path", "benchmark-report.md"));
manifestPath = fullfile(source, "benchmark-result.json");
writeFile(manifestPath, string(jsonencode(manifest)));

verifyError(testCase, @() promote_s12_benchmark_baseline( ...
    manifestPath, destination), "S12:Benchmark:PromotionNotAuthorized");
promoted = promote_s12_benchmark_baseline(manifestPath, destination, ...
    ApprovalToken="PROMOTE_ACCEPTED_BASELINE");

verifyTrue(testCase, isfile(fullfile(destination, "benchmark-report.md")));
verifyTrue(testCase, isfile(fullfile(destination, "baseline-approval.json")));
verifyEqual(testCase, promoted.source_git_commit, "deadbeef");
end

function writeFile(path, content)
fileId = fopen(path, "wt", "n", "UTF-8");
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, "%s", char(content));
end

function removeDirectory(path)
if isfolder(path)
    rmdir(path, "s");
end
end
