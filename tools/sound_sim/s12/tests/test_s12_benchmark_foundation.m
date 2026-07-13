function tests = test_s12_benchmark_foundation
%TEST_S12_BENCHMARK_FOUNDATION Verify the stable benchmark contracts.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
testCase.TestData.BenchmarkRoot = benchmarkRoot;
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testRegistryUsesFunctionalCaseContract(testCase)
registry = s12_benchmark_registry();
verifyEqual(testCase, string({registry.id}), ...
    ["uniform_state", "long_time_sod", "smooth_periodic_entropy_wave", ...
    "lax_shock_tube", "shu_osher_shock_entropy", ...
    "woodward_colella_blast_wave"]);

requiredFields = ["id", "category", "factory"];
verifyTrue(testCase, all(ismember(requiredFields, string(fieldnames(registry)))));
for caseIndex = 1:numel(registry)
    verifyClass(testCase, registry(caseIndex).factory, "function_handle");
    definition = registry(caseIndex).factory();
    verifyEqual(testCase, string(fieldnames(definition)).', ...
        ["configure", "run", "analyze", "accept"]);
    verifyTrue(testCase, all(structfun( ...
        @(value) isa(value, "function_handle"), definition)));
end
end

function testProfilesAreConfigDrivenAndDeterministic(testCase)
quick = s12_benchmark_profile("quick");
full = s12_benchmark_profile("full");

verifyEqual(testCase, quick.id, "quick");
verifyEqual(testCase, full.id, "full");
verifyLessThan(testCase, quick.smooth.cell_count, full.smooth.cell_count);
verifyEqual(testCase, quick.smooth.dt_divisors, [1, 2, 4, 8]);
verifyEqual(testCase, full.smooth.dt_divisors, [1, 2, 4, 8]);
verifyGreaterThan(testCase, quick.cfl_limit, 0);
verifyLessThanOrEqual(testCase, quick.cfl_limit, 1);
end

function testSelectorsCoverCaseCategoryAndSuite(testCase)
registry = s12_benchmark_registry();
single = s12_benchmark_select(registry, "case:long_time_sod");
category = s12_benchmark_select(registry, "category:temporal_accuracy");
standard = s12_benchmark_select(registry, "category:standard_shock_tube");
suite = s12_benchmark_select(registry, "all");

verifyEqual(testCase, string({single.id}), "long_time_sod");
verifyEqual(testCase, string({category.id}), "smooth_periodic_entropy_wave");
verifyEqual(testCase, string({standard.id}), "lax_shock_tube");
verifyEqual(testCase, string({suite.id}), string({registry.id}));
verifyError(testCase, @() s12_benchmark_select(registry, "case:missing"), ...
    "S12:Benchmark:UnknownSelector");
end

function testCanonicalResultStartsWithVersionedStableSchema(testCase)
environment = struct("git_commit", "deadbeef", ...
    "matlab_release", "R2026a", "platform", "win64");
result = s12_benchmark_new_result("quick", "all", environment);

verifyEqual(testCase, result.schema, "benchmark.schema.v1");
verifyEqual(testCase, string(fieldnames(result)).', [ ...
    "schema", "suite", "environment", "cases", "artifacts", "acceptance"]);
verifyEqual(testCase, result.suite.profile, "quick");
verifyEqual(testCase, result.suite.selector, "all");
verifyEmpty(testCase, result.cases);
verifyEqual(testCase, result.acceptance.status, "not_evaluated");
end
