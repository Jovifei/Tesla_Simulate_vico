function tests = test_s12_fanno_pipe_g_cross_validation
%TEST_S12_FANNO_PIPE_G_CROSS_VALIDATION Verify matched Fanno/Pipe(G) reference.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
validationRoot = fullfile(s12Root, "validation", "fanno");
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(validationRoot);
addpath(benchmarkRoot);
testCase.TestData.s12Root = s12Root;
testCase.addTeardown(@() rmpath(validationRoot, benchmarkRoot));
end

function testControlledModelsExist(testCase)
singleModel = fullfile(testCase.TestData.s12Root, "models", "pipe_ref", ...
    "s12_fanno_pipe_g_ref.slx");
segmentedModel = fullfile(testCase.TestData.s12Root, "models", "pipe_ref", ...
    "s12_fanno_pipe_g_segmented_ref.slx");

verifyTrue(testCase, isfile(singleModel));
verifyTrue(testCase, isfile(segmentedModel));
end

function testQuickCaseMatchesAnalyticalReference(testCase)
result = s12_run_fanno_pipe_g(s12_fanno_case_definition("quick"));

verifyEqual(testCase, result.status, "passed");
verifyEqual(testCase, result.friction_convention, "darcy_f_D_L_over_D");
verifyEqual(testCase, result.physical_assumptions, ...
    "steady_1d_constant_area_adiabatic_calorically_perfect_subsonic");
verifyLessThan(testCase, result.single.maximum_relative_error, 5e-4);
verifyLessThan(testCase, result.segmented.maximum_relative_error, 5e-4);
verifyTrue(testCase, result.single.all_finite);
verifyTrue(testCase, result.segmented.all_finite);
end

function testFullCaseCapturesLumpedAndSegmentedAccuracy(testCase)
result = s12_run_fanno_pipe_g(s12_fanno_case_definition("full"));

verifyEqual(testCase, result.case_definition.lengths, [1, 76, 156]);
verifyLessThan(testCase, result.single.maximum_relative_error, 0.02);
verifyLessThan(testCase, result.segmented.maximum_relative_error, 0.002);
verifyLessThan(testCase, result.segmented.maximum_relative_error, ...
    result.single.maximum_relative_error);
verifyGreaterThan(testCase, result.minimum_choke_margin, 0);
verifyEqual(testCase, result.retry_count, 0);
end

function testMatchedAssumptionsAreExplicit(testCase)
definition = s12_fanno_case_definition("full");

verifyEqual(testCase, definition.gamma, definition.cp / ...
    (definition.cp - definition.gas_constant), "AbsTol", 2e-15);
verifyEqual(testCase, definition.additional_equivalent_length, 0);
verifyEqual(testCase, definition.wall_boundary, "perfect_insulator");
verifyEqual(testCase, definition.inlet_boundary, "fixed_static_p_T");
verifyEqual(testCase, definition.outlet_boundary, "fixed_mass_flow");
verifyEqual(testCase, definition.segment_counts, [1, 5]);
end

function testBenchmarkRegistryAndSchemaExposeCrossValidation(testCase)
registry = s12_benchmark_registry();
index = find(string({registry.id}) == "fanno_pipe_g_cross_validation", 1);
verifyNotEmpty(testCase, index);
verifyEqual(testCase, registry(index).category, "cross_validation");

schema = jsondecode(fileread(fullfile(testCase.TestData.s12Root, ...
    "benchmark", "schema", "benchmark.schema.v1.json")));
verifyGreaterThanOrEqual(testCase, schema.schema_minor, 3);
required = ["reference_type", "friction_convention", ...
    "single_maximum_relative_error", "segmented_maximum_relative_error", ...
    "minimum_choke_margin", "retry_count"];
verifyTrue(testCase, all(ismember(required, string(schema.case_metric_fields))));
end

function testBenchmarkEntryPointAndReportOnlyAreDeterministic(testCase)
runDirectory = tempname;
reportDirectory = tempname;
testCase.addTeardown(@() removeDirectory(runDirectory));
testCase.addTeardown(@() removeDirectory(reportDirectory));

executed = run_s12_benchmarks("case:fanno_pipe_g_cross_validation", ...
    Profile="quick", OutputDirectory=runDirectory);
manifest = fullfile(runDirectory, "benchmark-result.json");
rebuilt = run_s12_benchmarks("report-only", SourceManifest=manifest, ...
    OutputDirectory=reportDirectory);

verifyEqual(testCase, executed.acceptance.status, "passed");
verifyEqual(testCase, executed.cases.metrics.reference_type, ...
    "analytical_fanno_exact_relation");
controlled = string({executed.artifacts.path});
for index = 1:numel(controlled)
    verifyEqual(testCase, readBytes(fullfile(runDirectory, controlled(index))), ...
        readBytes(fullfile(reportDirectory, controlled(index))));
end
verifyEqual(testCase, rebuilt.acceptance.status, "passed");
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
