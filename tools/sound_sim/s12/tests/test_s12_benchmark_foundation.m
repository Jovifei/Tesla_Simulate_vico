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
    "smooth_periodic_entropy_wave_spatial", ...
    "lax_shock_tube", "shu_osher_shock_entropy", ...
    "woodward_colella_blast_wave", "double_rarefaction", ...
    "fanno_pipe_g_cross_validation", ...
    "fanno_fvm_three_way_cross_validation", ...
    "transient_pipe_wave_cross_validation"]);

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
verifyEqual(testCase, full.smooth_spatial.cell_counts.', [50, 100, 200, 400]);
verifyGreaterThan(testCase, quick.cfl_limit, 0);
verifyLessThanOrEqual(testCase, quick.cfl_limit, 1);
verifyGreaterThan(testCase, quick.pp_requested_cfl, 0);
verifyLessThan(testCase, quick.pp_requested_cfl, quick.cfl_limit);
verifyFalse(testCase, quick.double_rarefaction.require_pp_activation);
verifyTrue(testCase, full.double_rarefaction.require_pp_activation);
verifyEqual(testCase, quick.double_rarefaction.requested_cfl, 0.45);
verifyEqual(testCase, full.double_rarefaction.requested_cfl, 0.45);
verifyEqual(testCase, string(quick.fanno.validation_profile), "quick");
verifyEqual(testCase, string(full.fanno.validation_profile), "full");
end

function testSelectorsCoverCaseCategoryAndSuite(testCase)
registry = s12_benchmark_registry();
single = s12_benchmark_select(registry, "case:long_time_sod");
category = s12_benchmark_select(registry, "category:temporal_accuracy");
spatial = s12_benchmark_select(registry, "category:spatial_accuracy");
standard = s12_benchmark_select(registry, "category:standard_shock_tube");
suite = s12_benchmark_select(registry, "all");

verifyEqual(testCase, string({single.id}), "long_time_sod");
verifyEqual(testCase, string({category.id}), "smooth_periodic_entropy_wave");
verifyEqual(testCase, string({spatial.id}), "smooth_periodic_entropy_wave_spatial");
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
    "schema", "schema_minor", "suite", "environment", "cases", "artifacts", "acceptance"]);
verifyEqual(testCase, result.schema_minor, 6);
verifyEqual(testCase, result.suite.profile, "quick");
verifyEqual(testCase, result.suite.selector, "all");
verifyEmpty(testCase, result.cases);
verifyEqual(testCase, result.acceptance.status, "not_evaluated");
end

function testExecutedResultRecordsWorkingTreeProvenance(testCase)
outputDirectory = string(tempname);
testCase.addTeardown(@() removeOutputDirectory(outputDirectory));

result = run_s12_benchmarks("case:uniform_state", ...
    Profile="quick", OutputDirectory=outputDirectory);

hasProvenance = isfield(result.environment, "working_tree_dirty");
verifyTrue(testCase, hasProvenance);
if hasProvenance
    verifyClass(testCase, result.environment.working_tree_dirty, "logical");
end
end

function removeOutputDirectory(path)
if isfolder(path)
    rmdir(path, "s");
end
end
