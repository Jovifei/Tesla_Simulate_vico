function tests = test_s12_muscl_qualification
%TEST_S12_MUSCL_QUALIFICATION Verify Sprint 2 final-qualification evidence.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testSpatialCaseUsesCellAverageFourGridContract(testCase)
config = struct( ...
    "cell_counts", [50, 100, 200, 400], ...
    "end_time", 0.01, ...
    "time_cfl", 0.05, ...
    "reconstruction", "muscl_minmod");
exists = exist("s12_benchmark_smooth_spatial", "file") == 2;
verifyTrue(testCase, exists);
if ~exists
    return
end
result = s12_benchmark_smooth_spatial(config, 0.45);

verifyEqual(testCase, result.cell_counts, [50, 100, 200, 400]);
verifyTrue(testCase, result.uses_cell_averages);
verifyFalse(testCase, any(result.cfl_clipped));
verifyFalse(testCase, any(result.end_time_clipped));
verifyEqual(testCase, result.reconstruction, "muscl_minmod");
verifySize(testCase, result.rho_l1_error, [1, 4]);
verifySize(testCase, result.observed_order.rho, [1, 3]);
verifyTrue(testCase, isfield(result, "qualification"));
verifyEqual(testCase, result.qualification.limiter, "minmod");
definition = s12_benchmark_case_smooth_spatial;
analysis = definition.analyze(result);
acceptance = definition.accept(analysis.metrics);
verifyEqual(testCase, acceptance.status, "passed");
end

function testSpatialCaseRegistersSecondOrderGate(testCase)
definition = s12_benchmark_case_smooth_spatial;
profile = s12_benchmark_profile("full");
profile.reconstruction = "muscl_minmod";
config = definition.configure(profile);

verifyEqual(testCase, config.cell_counts, [50, 100, 200, 400]);
verifyEqual(testCase, config.reconstruction, "muscl_minmod");
end

function testMusclRunnerReportsReconstructionDiagnostics(testCase)
cellCount = 32;
dx = 1 / cellCount;
x = ((1:cellCount) - 0.5) * dx;
state = s12_benchmark_primitive_to_conservative( ...
    1 + 0.1 * sin(2 * pi * x), ones(size(x)), ones(size(x)), 1.4);
result = s12_run_periodic_ssprk3(state, 1.4, dx, 5e-4, 4, 0.45, ...
    Reconstruction="muscl_minmod");

hasQualification = isfield(result, "qualification");
verifyTrue(testCase, hasQualification);
if ~hasQualification
    return
end
required = ["spatial_scheme", "reconstruction_variables", "limiter", ...
    "limiter_activation_count", "limited_cell_fraction", ...
    "minimum_reconstructed_density", "minimum_reconstructed_pressure", ...
    "invalid_reconstruction_count", "invalid_stage_count", ...
    "clipping_count", "flux_fallback_count", "automatic_retry_count"];
verifyTrue(testCase, all(isfield(result.qualification, required)));
verifyEqual(testCase, result.qualification.limiter, "minmod");
verifyGreaterThan(testCase, result.qualification.minimum_reconstructed_density, 0);
verifyGreaterThan(testCase, result.qualification.minimum_reconstructed_pressure, 0);
verifyEqual(testCase, result.qualification.invalid_reconstruction_count, 0);
end

function testSchemaDeclaresBackwardCompatibleQualificationMetrics(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
schema = jsondecode(fileread(fullfile(root, "benchmark", "schema", ...
    "benchmark.schema.v1.json")));
required = ["spatial_scheme", "reconstruction_variables", "limiter", ...
    "limiter_activation_count", "limited_cell_fraction", ...
    "minimum_reconstructed_density", "minimum_reconstructed_pressure", ...
    "invalid_reconstruction_count"];

verifyEqual(testCase, string(schema.schema), "benchmark.schema.v1");
hasMetricDeclaration = isfield(schema, "case_metric_fields");
verifyTrue(testCase, hasMetricDeclaration);
if ~hasMetricDeclaration
    return
end
verifyTrue(testCase, all(ismember(required, string(schema.case_metric_fields))));
end
