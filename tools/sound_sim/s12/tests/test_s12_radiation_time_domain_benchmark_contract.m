function tests = test_s12_radiation_time_domain_benchmark_contract
%TEST_S12_RADIATION_TIME_DOMAIN_BENCHMARK_CONTRACT Specify 4D-B suite wiring.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
radiationRoot = fullfile(s12Root, "validation", "radiation_impedance");
addpath(benchmarkRoot);
addpath(radiationRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
testCase.addTeardown(@() rmpath(radiationRoot));
end

function testRegistryProfilesAndSchemaExposeTheShared4DBSuite(testCase)
requiredIds = ["radiation_single_tone", "radiation_multisine", "radiation_chirp", ...
    "radiation_pulse", "radiation_limit_open", "radiation_limit_matched", ...
    "radiation_limit_rigid", "radiation_amplitude_linearity", ...
    "radiation_grid_convergence", "radiation_time_convergence", ...
    "radiation_zero_input_decay", "radiation_retry_rollback"];
registry = s12_benchmark_registry();
ids = string({registry.id});
verifyTrue(testCase, all(ismember(requiredIds, ids)), ...
    "Sprint 4D-B cases must use the shared benchmark registry.");
if all(ismember(requiredIds, ids))
    selected = registry(ismember(ids, requiredIds));
    categories = string({selected.category});
    verifyTrue(testCase, any(categories == "radiation_boundary_time_domain"));
    verifyTrue(testCase, any(categories == "transient_open_end_impedance"));
end
quick = s12_benchmark_profile("quick");
full = s12_benchmark_profile("full");
verifyTrue(testCase, isfield(quick, "radiation_boundary_time_domain"));
verifyTrue(testCase, isfield(full, "radiation_boundary_time_domain"));
if isfield(quick, "radiation_boundary_time_domain") && ...
        isfield(full, "radiation_boundary_time_domain")
    verifyEqual(testCase, reshape(quick.radiation_boundary_time_domain.grid_cell_counts,1,[]), [50, 100]);
    verifyEqual(testCase, reshape(full.radiation_boundary_time_domain.grid_cell_counts,1,[]), [100, 200, 400, 800]);
    verifyEqual(testCase, reshape(full.radiation_boundary_time_domain.cfl_scan,1,[]), [0.45, 0.30, 0.20, 0.10]);
    verifyGreaterThanOrEqual(testCase, quick.radiation_boundary_time_domain.max_steps, 2048);
    verifyGreaterThanOrEqual(testCase, full.radiation_boundary_time_domain.max_steps, 16384);
end
schema = readSchema();
requiredFields = ["boundary_type", "radiation_package_schema", ...
    "radiation_package_sha256", "radiation_package_source_commit", ...
    "radiation_reference_plane", "radiation_state_dimension", ...
    "radiation_state_initialization", "radiation_integration_id", ...
    "radiation_poles", "radiation_time_step_margin", ...
    "input_waveform_id", "input_amplitude_pa", "input_frequency_hz", ...
    "input_ka", "reference_reflection_real", "reference_reflection_imag", ...
    "measured_reflection_real", "measured_reflection_imag", ...
    "reflection_real_error", "reflection_imag_error", ...
    "prearrival_energy_fraction", "radiation_retry_count", ...
    "radiation_rollback_count", "unsupported_case_count"];
verifyGreaterThanOrEqual(testCase, schema.schema_minor, 10);
verifyTrue(testCase, all(ismember(requiredFields, string(schema.case_metric_fields))));
end

function testEachRegistryFactorySharesOneCaseDefinitionContract(testCase)
registry = s12_benchmark_registry();
ids = string({registry.id});
indices = find(string({registry.category}) == "radiation_boundary_time_domain");
indices = [indices, find(string({registry.category}) == ...
    "transient_open_end_impedance")];
verifyGreaterThanOrEqual(testCase, numel(indices), 12);
for index = reshape(indices, 1, [])
    definition = registry(index).factory();
    config = definition.configure(s12_benchmark_profile("quick"));
    verifyEqual(testCase, config.case_id, registry(index).id);
    verifyEqual(testCase, config.category, registry(index).category);
    verifyTrue(testCase, isfield(config, "physical_definition"));
    verifyTrue(testCase, isfield(config, "acceptance_limits"));
    verifyTrue(testCase, isfield(config, "measurement_windows"));
    verifyTrue(testCase, isfield(config, "radiation_package_sha256"));
end
end

function testFullProfileFreezesQualificationThresholds(testCase)
quick = s12_benchmark_profile("quick");
full = s12_benchmark_profile("full");
verifyFalse(testCase, quick.radiation_boundary_time_domain.acceptance.frozen);
verifyTrue(testCase, full.radiation_boundary_time_domain.acceptance.frozen);
required = ["maximum_reflection_magnitude_error", ...
    "maximum_reflection_phase_error", "maximum_complex_reflection_error", ...
    "maximum_waveform_l1", "maximum_waveform_linf", ...
    "maximum_arrival_time_error_s", "maximum_prearrival_reflection", ...
    "maximum_energy_residual", "maximum_amplitude_linearity_error", ...
    "minimum_time_step_margin", "minimum_density", "minimum_pressure", ...
    "maximum_retry_count", "minimum_grid_order", "minimum_time_order"];
verifyTrue(testCase, all(isfield(full.radiation_boundary_time_domain.acceptance, required)));
end

function testQuickZeroInputCaseUsesTheCanonicalRunner(testCase)
output = string(tempname);
testCase.addTeardown(@() removeDirectory(output));
result = run_s12_benchmarks("case:radiation_zero_input_decay", ...
    Profile="quick", Reconstruction="muscl_minmod_pp", OutputDirectory=output);
verifyEqual(testCase, result.cases.id, "radiation_zero_input_decay");
verifyEqual(testCase, result.cases.category, "radiation_boundary_time_domain");
verifyTrue(testCase, result.cases.metrics.zero_input_decay_observed);
verifyEqual(testCase, result.acceptance.status, "passed");
verifyTrue(testCase, isfile(fullfile(output, "benchmark-result.json")));
end

function testRetryRollbackEvidenceDoesNotRequireSyntheticTrace(testCase)
output = string(tempname);
testCase.addTeardown(@() removeDirectory(output));
result = run_s12_benchmarks("case:radiation_retry_rollback", ...
    Profile="quick", Reconstruction="muscl_minmod_pp", OutputDirectory=output);
verifyEqual(testCase, result.acceptance.status, "passed");
verifyFalse(testCase, isfile(fullfile(output, "radiation-time-domain-traces.csv")));
end

function testTimeTraceUsesCausalIndependentIntegrator(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
source = fileread(fullfile(s12Root, "benchmark", ...
    "s12_benchmark_case_radiation_time_domain.m"));
verifyTrue(testCase, contains(source, "s12_radiation_time_domain_reference"));
verifyFalse(testCase, contains(source, "s12_radiation_independent_time_reference"));
end

function testGridStudyUsesTemporalResolutionForObservedTimeOrder(testCase)
definition = s12_benchmark_case_radiation_time_domain("radiation_grid_convergence");
config = definition.configure(s12_benchmark_profile("quick"));
analysis = definition.analyze(definition.run(config));
verifyGreaterThanOrEqual(testCase, min(analysis.metrics.observed_time_order), 0);
end

function testFullTimeScanFitsFixedDriverCapacity(testCase)
definition = s12_benchmark_case_radiation_time_domain("radiation_time_convergence");
config = definition.configure(s12_benchmark_profile("full"));
minimumCfl = min([config.run_plan.cfl]);
maximumGrid = max([config.run_plan.grid_cell_count]);
requiredSteps = ceil(config.case_definition.end_time_s * ...
    config.physical_definition.c0 * maximumGrid / ...
    (minimumCfl * config.case_definition.pipe_length_m));
verifyGreaterThanOrEqual(testCase, config.max_steps, requiredSteps);
end

function schema = readSchema
s12Root = fileparts(fileparts(mfilename("fullpath")));
schema = jsondecode(fileread(fullfile(s12Root, "benchmark", ...
    "schema", "benchmark.schema.v1.json")));
end

function removeDirectory(path)
if isfolder(path), rmdir(path, "s"); end
end
