function tests = test_s12_pp_benchmark_contract
%TEST_S12_PP_BENCHMARK_CONTRACT Specify the PP schema and suite integration.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testSchemaDeclaresBackwardCompatiblePpMetrics(testCase)
schema = readSchema;
required = ["positivity_mode", "rho_floor", "p_floor", "cfl_target", ...
    "cfl_pp_hard_max", "reconstruction_pp_activation_count", ...
    "reconstruction_pp_limited_cell_fraction", "reconstruction_pp_min_theta", ...
    "flux_pp_activation_count", "flux_pp_limited_interface_fraction", ...
    "flux_pp_min_theta", "low_order_anchor_id", "alpha_stage_max", ...
    "minimum_cell_density_by_stage", "minimum_cell_pressure_by_stage", ...
    "minimum_interface_density_by_stage", ...
    "minimum_interface_pressure_by_stage", ...
    "minimum_anchor_partial_density_by_stage", ...
    "minimum_anchor_partial_pressure_by_stage", ...
    "minimum_final_partial_density_by_stage", ...
    "minimum_final_partial_pressure_by_stage", ...
    "invalid_stage_count", "rejected_step_count", "retry_count", ...
    "maximum_flux_correction_norm"];

verifyGreaterThanOrEqual(testCase, schema.schema_minor, 2);
verifyTrue(testCase, all(ismember(required, string(schema.case_metric_fields))));
end

function testPpBenchmarkRegistersSmoothAndDoubleRarefaction(testCase)
output = tempname;
mkdir(output);
testCase.addTeardown(@() removeDirectory(output));

[result, available] = runPpBenchmark(testCase, "all", Profile="quick", ...
    Reconstruction="muscl_minmod_pp", OutputDirectory=output);
if ~available; return; end

caseIds = string({result.cases.id});
verifyTrue(testCase, any(caseIds == "smooth_periodic_entropy_wave_spatial"));
verifyTrue(testCase, any(caseIds == "double_rarefaction"));
acceptance = [result.cases.acceptance];
verifyTrue(testCase, all(string({acceptance.status}) == "passed"));
expected = ["positivity-diagnostics.csv", "double-rarefaction.png"];
for index = 1:numel(expected)
    verifyTrue(testCase, isfile(fullfile(output, expected(index))));
end
reportOnly = tempname;
mkdir(reportOnly);
testCase.addTeardown(@() removeDirectory(reportOnly));
run_s12_benchmarks("report-only", ...
    SourceManifest=fullfile(output, "benchmark-result.json"), ...
    OutputDirectory=reportOnly);
controlled = string({result.artifacts.path});
for index = 1:numel(controlled)
    verifyEqual(testCase, readBytes(fullfile(output, controlled(index))), ...
        readBytes(fullfile(reportOnly, controlled(index))));
end
end

function testPpResultRetainsFrozenHistoricalBaselines(testCase)
if ~requireProductionFunction(testCase, "s12_benchmark_verify_historical_baselines"); return; end
result = s12_benchmark_verify_historical_baselines;
verifyEqual(testCase, result.status, "passed");
verifyEqual(testCase, result.changed_file_count, 0);
end

function schema = readSchema
s12Root = fileparts(fileparts(mfilename("fullpath")));
schemaPath = fullfile(s12Root, "benchmark", "schema", "benchmark.schema.v1.json");
schema = jsondecode(fileread(schemaPath));
end

function exists = requireProductionFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyTrue(testCase, exists, ...
    "Sprint 3 production contract function must exist: " + name);
end

function [result, available] = runPpBenchmark(testCase, varargin)
available = true;
try
    result = run_s12_benchmarks(varargin{:});
catch exception
    verifyFail(testCase, "PP benchmark contract unavailable: " + ...
        string(exception.identifier));
    result = struct;
    available = false;
end
end

function removeDirectory(path)
if isfolder(path)
    rmdir(path, "s");
end
end

function bytes = readBytes(path)
fileId = fopen(path, "rb");
assert(fileId >= 0, "Cannot read controlled benchmark artifact.");
cleanup = onCleanup(@() fclose(fileId));
bytes = fread(fileId, Inf, "*uint8");
end
