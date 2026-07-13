function tests = test_s12_benchmark_standard_cases
%TEST_S12_BENCHMARK_STANDARD_CASES Verify Sprint 1 benchmark contracts.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testRegistryAndProfilesExposeThreeStandardCases(testCase)
registry = s12_benchmark_registry();
ids = string({registry.id});
verifyTrue(testCase, all(ismember(["lax_shock_tube", ...
    "shu_osher_shock_entropy", "woodward_colella_blast_wave"], ids)));

quick = s12_benchmark_profile("quick");
full = s12_benchmark_profile("full");
for field = ["lax", "shu_osher", "woodward_colella"]
    verifyTrue(testCase, isfield(quick, field));
    verifyTrue(testCase, isfield(full, field));
    verifyLessThan(testCase, quick.(field).cell_counts(end), ...
        full.(field).cell_counts(end));
end
end

function testLaxQuickUsesExactRiemannMetrics(testCase)
result = runSingleCase(testCase, "lax_shock_tube");
metrics = result.cases.metrics;

verifyEqual(testCase, result.cases.config.reference_type, "exact_riemann");
verifyTrue(testCase, all(isfield(metrics, ["density_l1_error", ...
    "velocity_l1_error", "pressure_l1_error", "shock_position_error", ...
    "contact_position_error", "rarefaction_head_position_error", ...
    "shock_position", "contact_position", "rarefaction_head_position", ...
    "exact_shock_position", "exact_contact_position", ...
    "exact_rarefaction_head_position", "rarefaction_head_locator", ...
    "min_density", "min_pressure", "conservation_error", "max_courant", ...
    "grid_cell_counts"])));
verifyTrue(testCase, all(isfinite([metrics.density_l1_error, ...
    metrics.velocity_l1_error, metrics.pressure_l1_error])));
verifyGreaterThan(testCase, metrics.min_density, 0);
verifyGreaterThan(testCase, metrics.min_pressure, 0);
verifyEqual(testCase, metrics.rarefaction_head_locator, ...
    "five_percent_fan_amplitude");
end

function testExactRiemannSamplerExposesLaxWaveLocations(testCase)
[~, ~, ~, waves] = s12_exact_sod(0, 0, 1.3, 1.4, ...
    [0.445, 0.698, 3.528], [0.5, 0, 0.571]);

verifyLessThan(testCase, waves.rarefaction_head, waves.contact);
verifyLessThan(testCase, waves.contact, waves.shock);
verifyEqual(testCase, waves.rarefaction_head, ...
    1.3 * (0.698 - sqrt(1.4 * 3.528 / 0.445)), AbsTol=1e-12);
end

function testLeadingLevelLocatorUsesFirstResolvedDeparture(testCase)
x = [-1, -0.5, 0, 0.5, 1];
signal = [1, 1, 0.98, 0.8, 0.5];

location = s12_benchmark_leading_level_location( ...
    x, signal, 1, 0.4, 0.05);

verifyEqual(testCase, location, 0);
end

function testShuOsherQuickReportsLiteratureDefinedSelfConvergence(testCase)
result = runSingleCase(testCase, "shu_osher_shock_entropy");
metrics = result.cases.metrics;

verifyEqual(testCase, result.cases.config.reference_type, ...
    "literature_definition_self_convergence");
verifyTrue(testCase, all(isfield(metrics, ["shock_position", ...
    "post_shock_window", "density_peak_to_trough", "density_total_variation", ...
    "min_density", "min_pressure", "conservation_error", "max_courant", ...
    "grid_cell_counts"])));
verifyGreaterThan(testCase, metrics.min_density, 0);
verifyGreaterThan(testCase, metrics.min_pressure, 0);
verifyTrue(testCase, all(isfinite(metrics.shock_position)));
end

function testWoodwardColellaQuickUsesMirrorBoundaryAndDiagnostics(testCase)
result = runSingleCase(testCase, "woodward_colella_blast_wave");
metrics = result.cases.metrics;

verifyEqual(testCase, result.cases.config.boundary_strategy, ...
    "mirror_extension_transmissive_solver");
verifyEqual(testCase, result.cases.config.reference_type, ...
    "literature_definition_self_convergence");
verifyTrue(testCase, all(isfield(metrics, ["min_density", "min_pressure", ...
    "has_nonfinite", "conservation_error", "physical_mass_residual", ...
    "physical_energy_residual", "max_courant", "major_gradient_positions", ...
    "grid_cell_counts"])));
verifyFalse(testCase, metrics.has_nonfinite);
verifyGreaterThan(testCase, metrics.min_density, 0);
verifyGreaterThan(testCase, metrics.min_pressure, 0);
end

function testStandardCaseReportOnlyRebuildsAdditionalArtifacts(testCase)
environment = struct("git_commit", "deadbeef", ...
    "matlab_release", "R2026a", "platform", "win64");
canonical = s12_benchmark_new_result("quick", "case:lax_shock_tube", environment);
canonical.cases = sampleLaxCase();
canonical.acceptance = struct("status", "passed", ...
    "checks", struct("id", "sentinel", "passed", true));
outA = tempname;
outB = tempname;
mkdir(outA);
mkdir(outB);
testCase.addTeardown(@() removeDirectory(outA));
testCase.addTeardown(@() removeDirectory(outB));

s12_write_benchmark_artifacts(canonical, outA);
s12_write_benchmark_artifacts(canonical, outB);
path = fullfile(outA, "lax-analytic-comparison.png");
assertTrue(testCase, isfile(path));
verifyEqual(testCase, readBytes(path), readBytes(fullfile( ...
    outB, "lax-analytic-comparison.png")));
end

function result = runSingleCase(testCase, caseId)
output = tempname;
testCase.addTeardown(@() removeDirectory(output));
result = run_s12_benchmarks("case:" + caseId, ...
    Profile="quick", OutputDirectory=output);
verifyEqual(testCase, result.acceptance.status, "passed");
verifyEqual(testCase, numel(result.cases), 1);
end

function benchmarkCase = sampleLaxCase
benchmarkCase = struct( ...
    "id", "lax_shock_tube", ...
    "category", "standard_shock_tube", ...
    "status", "passed", ...
    "config", struct("reference_type", "exact_riemann", "cfl", 0.45), ...
    "metrics", struct("density_l1_error", 0.1, "velocity_l1_error", 0.1, ...
        "pressure_l1_error", 0.1, "shock_position", 0.7, ...
        "grid_cell_counts", 16, "min_density", 0.4, ...
        "min_pressure", 0.5, "conservation_error", 1e-12, ...
        "max_courant", 0.45, "runtime_seconds", 1), ...
    "acceptance", struct("status", "passed", "checks", struct([])), ...
    "plot", struct("x", [0, 0.5, 1], ...
        "numerical_density", [0.45, 0.7, 0.5], ...
        "exact_density", [0.445, 0.69, 0.5]));
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
