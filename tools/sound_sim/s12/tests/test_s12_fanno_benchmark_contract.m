function tests = test_s12_fanno_benchmark_contract
%TEST_S12_FANNO_BENCHMARK_CONTRACT Specify the Sprint 4B benchmark entry.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
fannoRoot = fullfile(s12Root, "validation", "fanno");
addpath(benchmarkRoot, fannoRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot, fannoRoot));
end

function testRegistryProfilesAndSchemaExposeFannoFvm(testCase)
registry = s12_benchmark_registry();
ids = string({registry.id});
index = find(ids == "fanno_fvm_three_way_cross_validation", 1);
verifyNotEmpty(testCase, index);
if isempty(index); return; end
verifyEqual(testCase, registry(index).category, "cross_validation");

quick = s12_benchmark_profile("quick");
full = s12_benchmark_profile("full");
verifyEqual(testCase, reshape(full.fanno_fvm.grid_cell_counts, 1, []), ...
    [50, 100, 200, 400]);
verifyLessThan(testCase, quick.fanno_fvm.grid_cell_counts(end), ...
    full.fanno_fvm.grid_cell_counts(end));
verifyEqual(testCase, reshape(full.fanno_fvm.lengths_m, 1, []), [1, 76, 156]);

schemaPath = fullfile(fileparts(fileparts(mfilename("fullpath"))), ...
    "benchmark", "schema", "benchmark.schema.v1.json");
schema = jsondecode(fileread(schemaPath));
verifyGreaterThanOrEqual(testCase, schema.schema_minor, 4);
verifyTrue(testCase, all(ismember(["balance_law_mode", ...
    "source_balanced_momentum_residual", "steady_state_reached"], ...
    string(schema.case_metric_fields))));
end

function testQuickCaseUsesCanonicalThreeWayContract(testCase)
output = tempname;
reportOutput = tempname;
testCase.addTeardown(@() removeDirectory(output));
testCase.addTeardown(@() removeDirectory(reportOutput));
result = run_s12_benchmarks("case:fanno_fvm_three_way_cross_validation", ...
    Profile="quick", OutputDirectory=output, Reconstruction="muscl_minmod_pp");

verifyEqual(testCase, result.cases.id, "fanno_fvm_three_way_cross_validation");
verifyEqual(testCase, result.cases.metrics.balance_law_mode, ...
    "fanno_constant_darcy");
verifyEqual(testCase, result.cases.metrics.boundary_id, ...
    "subsonic_fanno_validation.v1");
verifyTrue(testCase, all(result.cases.metrics.steady_state_reached));
required = ["minimum_reconstructed_density", ...
    "minimum_reconstructed_pressure", "invalid_reconstruction_count", ...
    "reconstruction_pp_activation_count", "flux_pp_activation_count", ...
    "reconstruction_pp_min_theta", "flux_pp_min_theta", ...
    "minimum_anchor_partial_density", "minimum_anchor_partial_pressure", ...
    "invalid_stage_count"];
verifyTrue(testCase, all(isfield(result.cases.metrics, required)));
verifyEqual(testCase, result.cases.metrics.uniform_friction_decay_id, ...
    "periodic_uniform_exact.v1");
verifyLessThan(testCase, ...
    max(result.cases.metrics.uniform_friction_decay_relative_error), 1e-11);
verifyEqual(testCase, result.cases.metrics.cold_start_initialization_id, ...
    "linear_endpoint_primitive.v1");
verifyTrue(testCase, result.cases.metrics.cold_start_steady_state_reached);
verifyEqual(testCase, size(result.cases.metrics.fvm_simscape_station_relative_difference), ...
    [1, 5, 4]);
verifyEqual(testCase, result.acceptance.status, "passed");
verifyTrue(testCase, isfile(fullfile(output, "fanno-fvm-grid-matrix.csv")));
verifyTrue(testCase, isfile(fullfile(output, ...
    "fanno-uniform-friction-decay.csv")));
verifyTrue(testCase, isfile(fullfile(output, "fanno-cold-start.csv")));
verifyTrue(testCase, isfile(fullfile(output, ...
    "fanno-five-station-comparison.csv")));
rebuilt = run_s12_benchmarks("report-only", ...
    SourceManifest=fullfile(output, "benchmark-result.json"), ...
    OutputDirectory=reportOutput);
verifyEqual(testCase, rebuilt.acceptance.status, result.acceptance.status);
for artifactPath = string({result.artifacts.path})
    verifyEqual(testCase, readBytes(fullfile(output, artifactPath)), ...
        readBytes(fullfile(reportOutput, artifactPath)), ...
        "Artifact differs after report-only: " + artifactPath);
end
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
