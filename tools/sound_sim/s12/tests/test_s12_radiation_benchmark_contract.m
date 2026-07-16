function tests = test_s12_radiation_benchmark_contract
%TEST_S12_RADIATION_BENCHMARK_CONTRACT Specify shared 4D-A suite integration.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
radiationRoot = fullfile(s12Root, "validation", "radiation_impedance");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
if isfolder(radiationRoot)
    addpath(radiationRoot);
    testCase.addTeardown(@() rmpath(radiationRoot));
end
end

function testRegistryProfileAndSchemaExposeRadiationImpedance(testCase)
registry = s12_benchmark_registry();
ids = string({registry.id});
index = find(ids == "unflanged_open_end_radiation_impedance", 1);
verifyNotEmpty(testCase, index, ...
    "Sprint 4D-A must reuse the shared registry, not add a second runner.");
if isempty(index); return; end
verifyEqual(testCase, registry(index).category, "radiation_impedance");
quick = s12_benchmark_profile("quick");
full = s12_benchmark_profile("full");
verifyEqual(testCase, string(quick.radiation_impedance.validation_profile), "quick");
verifyEqual(testCase, string(full.radiation_impedance.validation_profile), "full");
schema = readSchema();
verifyEqual(testCase, schema.schema_minor, 7);
required = ["radiation_geometry", "flange_condition", "mean_flow_mach", ...
    "mode_id", "time_harmonic_convention", "impedance_definition", ...
    "normalization_id", "reference_plane", "pipe_radius_m", ...
    "cross_section_area_m2", "rho0", "c0", "frequency_hz", "ka", ...
    "reference_impedance_real", "reference_impedance_imag", ...
    "fit_impedance_real", "fit_impedance_imag", ...
    "reference_reflection_real", "reference_reflection_imag", ...
    "fit_reflection_real", "fit_reflection_imag", ...
    "impedance_relative_error", "reflection_complex_error", ...
    "reflection_magnitude_error", "reflection_phase_error", ...
    "passivity_margin", "maximum_reflection_magnitude", "fit_order", ...
    "fit_poles", "fit_stability_margin", "fit_band_ka", ...
    "end_correction_reference", "end_correction_fit", ...
    "reference_method_id", "fit_method_id"];
verifyTrue(testCase, all(ismember(required, string(schema.case_metric_fields))));
end

function testQuickRunUsesCanonicalSummaryCsvAndReportOnly(testCase)
registry = s12_benchmark_registry();
if ~any(string({registry.id}) == "unflanged_open_end_radiation_impedance")
    verifyTrue(testCase, false, ...
        "Sprint 4D-A registry entry must exist before the benchmark can run.");
    return
end
output = string(tempname);
rebuiltOutput = string(tempname);
testCase.addTeardown(@() removeDirectory(output));
testCase.addTeardown(@() removeDirectory(rebuiltOutput));
result = run_s12_benchmarks("case:unflanged_open_end_radiation_impedance", ...
    Profile="quick", OutputDirectory=output);
verifyEqual(testCase, result.cases.id, "unflanged_open_end_radiation_impedance");
verifyEqual(testCase, result.cases.category, "radiation_impedance");
verifyEqual(testCase, result.cases.metrics.radiation_geometry, ...
    "circular_unflanged");
verifyEqual(testCase, result.cases.metrics.reference_method_id, ...
    "levine_schwinger_direct_quadrature.v1");
verifyEqual(testCase, result.cases.metrics.fit_method_id, ...
    "silva_2009_causal_pade_1_2.v1");
verifyEqual(testCase, result.acceptance.status, "passed");
csvPath = fullfile(output, "radiation-impedance-frequency.csv");
verifyTrue(testCase, isfile(csvPath));
header = string(fileread(csvPath));
verifyTrue(testCase, contains(header, ...
    "frequency_hz,ka,reference_impedance_real,reference_impedance_imag"));
verifyTrue(testCase, isfile(fullfile(output, "radiation-impedance-comparison.png")));
verifyTrue(testCase, isfile(fullfile(output, "radiation-impedance-error.png")));
verifyTrue(testCase, isfile(fullfile(output, "radiation-impedance-stability.png")));
verifyTrue(testCase, isfile(fullfile(output, "radiation-boundary-package.json")));
manifest = jsondecode(fileread(fullfile(output, "benchmark-result.json")));
metrics = manifest.cases.metrics;
verifyFalse(testCase, isfield(metrics, "frequency_hz"), ...
    "Large frequency arrays must remain in CSV, indexed by the JSON result.");
verifyTrue(testCase, isfield(metrics, "frequency_csv_path"));
rebuilt = run_s12_benchmarks("report-only", ...
    SourceManifest=fullfile(output, "benchmark-result.json"), ...
    OutputDirectory=rebuiltOutput);
verifyEqual(testCase, rebuilt.acceptance.status, result.acceptance.status);
for artifactPath = string({result.artifacts.path})
    verifyEqual(testCase, readBytes(fullfile(output, artifactPath)), ...
        readBytes(fullfile(rebuiltOutput, artifactPath)), ...
        "Artifact differs after report-only: " + artifactPath);
end
verifyEqual(testCase, numel(result.artifacts), 12);
end

function testFrequencyOnlyCaseDoesNotInheritPpSolverContract(testCase)
output = string(tempname);
testCase.addTeardown(@() removeDirectory(output));
result = run_s12_benchmarks("case:unflanged_open_end_radiation_impedance", ...
    Profile="quick", Reconstruction="muscl_minmod_pp", OutputDirectory=output);
verifyEqual(testCase, result.acceptance.status, "passed", ...
    "A frequency-only radiation case must not inherit Euler PP checks.");
checkIds = string({result.cases.acceptance.checks.id});
verifyFalse(testCase, any(startsWith(checkIds, "pp_")), ...
    "PP checks belong only to Euler solver cases that use the PP operator.");
end

function schema = readSchema
s12Root = fileparts(fileparts(mfilename("fullpath")));
schema = jsondecode(fileread(fullfile(s12Root, "benchmark", ...
    "schema", "benchmark.schema.v1.json")));
end

function bytes = readBytes(path)
fileId = fopen(path, "rb");
cleanup = onCleanup(@() fclose(fileId));
bytes = fread(fileId, Inf, "*uint8");
end

function removeDirectory(path)
if isfolder(path); rmdir(path, "s"); end
end
