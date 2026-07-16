function tests = test_s12_transient_wave_benchmark_contract
%TEST_S12_TRANSIENT_WAVE_BENCHMARK_CONTRACT Specify unified suite entry.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
transientRoot = fullfile(s12Root, "validation", "transient_wave");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
if isfolder(transientRoot)
    addpath(transientRoot);
    testCase.addTeardown(@() rmpath(transientRoot));
end
end

function testRegistryProfilesAndSchemaExposeTransientWave(testCase)
registry = s12_benchmark_registry();
ids = string({registry.id});
index = find(ids == "transient_pipe_wave_cross_validation", 1);
verifyNotEmpty(testCase, index, ...
    "Sprint 4C must use the shared registry rather than a separate runner.");
if isempty(index); return; end
verifyEqual(testCase, registry(index).category, "transient_wave");
full = s12_benchmark_profile("full");
verifyEqual(testCase, reshape(full.transient_wave.grid_cell_counts, 1, []), ...
    [50, 100, 200, 400, 800]);
schemaPath = fullfile(fileparts(fileparts(mfilename("fullpath"))), ...
    "benchmark", "schema", "benchmark.schema.v1.json");
schema = jsondecode(fileread(schemaPath));
required = ["transient_case_id", "boundary_type", "reference_wave_speed", ...
    "measured_wave_speed", "arrival_time_error", ...
    "pressure_reflection_coefficient", "velocity_reflection_coefficient", ...
    "boundary_energy_residual", "probe_locations", "sample_rate"];
verifyTrue(testCase, all(ismember(required, string(schema.case_metric_fields))));
end

function testQuickRunUsesCanonicalResultAndReportOnly(testCase)
registry = s12_benchmark_registry();
if ~any(string({registry.id}) == "transient_pipe_wave_cross_validation")
    verifyTrue(testCase, false, ...
        "Sprint 4C registry entry must exist before the benchmark can run.");
    return
end
output = tempname;
rebuiltOutput = tempname;
testCase.addTeardown(@() removeDirectory(output));
testCase.addTeardown(@() removeDirectory(rebuiltOutput));
result = run_s12_benchmarks("case:transient_pipe_wave_cross_validation", ...
    Profile="quick", OutputDirectory=output, Reconstruction="muscl_minmod_pp");
verifyEqual(testCase, result.cases.id, "transient_pipe_wave_cross_validation");
verifyEqual(testCase, result.cases.metrics.reference_type, ...
    "linear_acoustics_primary_simscape_secondary");
metrics = result.cases.metrics;
required = ["reference_applicability", "minimum_reconstructed_density", ...
    "minimum_reconstructed_pressure", "invalid_reconstruction_count", ...
    "reconstruction_pp_activation_count", "flux_pp_activation_count", ...
    "minimum_anchor_partial_density", "minimum_anchor_partial_pressure", ...
    "minimum_final_partial_density", "minimum_final_partial_pressure", ...
    "invalid_stage_count", "clipping_count", "flux_fallback_count", ...
    "probe_sampling_id", "sample_rate", "time_resolution", "conservation_error"];
verifyTrue(testCase, all(isfield(metrics, required)));
finiteIndex = find(metrics.transient_case_id == "finite_amplitude_pulse", 1);
verifyFalse(testCase, metrics.reference_applicability(finiteIndex));
verifyTrue(testCase, all(isnan(metrics.waveform_l1_error(finiteIndex, :))));
verifyEqual(testCase, max(metrics.clipping_count, [], "all"), 0);
verifyEqual(testCase, max(metrics.flux_fallback_count, [], "all"), 0);
verifyEqual(testCase, result.acceptance.status, "passed");
verifyTrue(testCase, isfile(fullfile(output, "transient-wave-probes.csv")));
rebuilt = run_s12_benchmarks("report-only", ...
    SourceManifest=fullfile(output, "benchmark-result.json"), ...
    OutputDirectory=rebuiltOutput);
verifyEqual(testCase, rebuilt.acceptance.status, result.acceptance.status);
for artifactPath = string({result.artifacts.path})
    verifyEqual(testCase, readBytes(fullfile(output, artifactPath)), ...
        readBytes(fullfile(rebuiltOutput, artifactPath)), ...
        "Artifact differs after report-only: " + artifactPath);
end
end

function bytes = readBytes(path)
fileId = fopen(path, "rb");
cleanup = onCleanup(@() fclose(fileId));
bytes = fread(fileId, Inf, "*uint8");
end

function removeDirectory(path)
if isfolder(path); rmdir(path, "s"); end
end
