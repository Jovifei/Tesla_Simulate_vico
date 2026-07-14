function result = run_s12_positivity_final_qualification(mode, options)
%RUN_S12_POSITIVITY_FINAL_QUALIFICATION Qualify PP against frozen Sprint 2.
arguments
    mode (1,1) string {mustBeMember(mode, ["run", "report-only"])} = "run"
    options.Profile (1,1) string = "full"
    options.OutputDirectory (1,1) string = ""
    options.SourceManifest (1,1) string = ""
end
root = fileparts(mfilename("fullpath"));
if options.OutputDirectory == ""
    options.OutputDirectory = fullfile(root, "out", ...
        "sprint3-qualification", options.Profile);
end
if mode == "report-only"
    if options.SourceManifest == "" || ~isfile(options.SourceManifest)
        error("S12:Benchmark:MissingManifest", ...
            "Qualification report-only requires an existing SourceManifest.");
    end
    result = normalize(jsondecode(fileread(options.SourceManifest)));
    result = s12_write_sprint3_qualification_artifacts(result, ...
        options.OutputDirectory);
    copyfile(options.SourceManifest, fullfile(options.OutputDirectory, ...
        "benchmark-result.json"));
    return
end

ppDirectory = fullfile(options.OutputDirectory, "muscl_minmod_pp");
pp = run_s12_benchmarks("all", Profile=options.Profile, ...
    OutputDirectory=ppDirectory, Reconstruction="muscl_minmod_pp");
sprint2Path = fullfile(root, "baselines", "sprint-2", ...
    "benchmark-result.json");
sprint2 = jsondecode(fileread(sprint2Path));
result = buildResult(pp, sprint2, options.Profile);
result = s12_write_sprint3_qualification_artifacts(result, ...
    options.OutputDirectory);
end

function result = buildResult(pp, sprint2, profile)
count = numel(pp.cases);
emptyComparison = struct("id", "", "category", "", ...
    "muscl_minmod", struct(), "muscl_minmod_pp", struct(), ...
    "rho_error_ratio", NaN, "plot", struct());
cases = repmat(emptyComparison, 1, count);
for index = 1:count
    id = string(pp.cases(index).id);
    oldIndex = find(string({sprint2.cases.id}) == id, 1);
    if isempty(oldIndex)
        oldMetrics = struct();
    else
        oldMetrics = sprint2.cases(oldIndex).muscl_minmod;
    end
    ppMetrics = pp.cases(index).metrics;
    cases(index) = struct("id", id, ...
        "category", string(pp.cases(index).category), ...
        "muscl_minmod", oldMetrics, ...
        "muscl_minmod_pp", ppMetrics, ...
        "rho_error_ratio", rhoErrorRatio(oldMetrics, ppMetrics), ...
        "plot", pp.cases(index).plot);
end
checks = qualificationChecks(pp, cases);
if all([checks.passed])
    status = "passed";
else
    status = "failed";
end
result = struct( ...
    "schema", "benchmark.schema.v1", ...
    "schema_minor", 2, ...
    "suite", struct("profile", profile, ...
        "selector", "sprint3_positivity_final_qualification"), ...
    "environment", pp.environment, ...
    "source_results", struct( ...
        "sprint2_accepted_commit", ...
            "eaf629532d937584b8992f0de5ca86410c3ba9e6", ...
        "muscl_minmod_source", "accepted_sprint2_baseline", ...
        "muscl_minmod_pp_acceptance", pp.acceptance.status), ...
    "cases", cases, ...
    "artifacts", struct([]), ...
    "acceptance", struct("status", status, "checks", checks));
end

function checks = qualificationChecks(pp, cases)
historical = s12_benchmark_verify_historical_baselines;
spatial = selectCase(cases, "smooth_periodic_entropy_wave_spatial");
stress = selectCase(cases, "double_rarefaction");
checks = [ ...
    check("historical_baselines_unchanged", historical.status == "passed"), ...
    check("pp_full_suite", pp.acceptance.status == "passed"), ...
    check("smooth_pp_second_order", ...
        spatial.muscl_minmod_pp.rho_observed_order(end) >= 1.7 && ...
        spatial.muscl_minmod_pp.rho_observed_order(end) <= 2.3), ...
    check("smooth_pp_no_time_clip", ...
        ~any(spatial.muscl_minmod_pp.cfl_clipped) && ...
        ~any(spatial.muscl_minmod_pp.end_time_clipped)), ...
    check("smooth_pp_error_no_regression", ...
        smoothErrorNoRegression(spatial)), ...
    check("analytic_cases_no_regression", analyticCasesNoRegression(cases)), ...
    check("all_pp_evidence_healthy", allPpEvidenceHealthy(cases)), ...
    check("nominal_retries_zero", nominalRetriesZero(cases)), ...
    check("stress_pp_activated", stressActivated(stress)), ...
    check("stress_conservative_and_finite", stressHealthy(stress))];
end

function value = smoothErrorNoRegression(spatial)
oldError = row(spatial.muscl_minmod.rho_l1_error);
ppError = row(spatial.muscl_minmod_pp.rho_l1_error);
value = numel(oldError) == numel(ppError) && ...
    all(ppError <= 1.05 * oldError);
end

function value = analyticCasesNoRegression(cases)
value = true;
for id = ["long_time_sod", "lax_shock_tube"]
    comparison = selectCase(cases, id);
    oldError = densityError(comparison.muscl_minmod);
    ppError = densityError(comparison.muscl_minmod_pp);
    value = value && isfinite(oldError) && isfinite(ppError) && ...
        ppError <= 1.10 * oldError;
end
end

function value = allPpEvidenceHealthy(cases)
value = true;
for index = 1:numel(cases)
    metrics = cases(index).muscl_minmod_pp;
    required = ["rho_floor", "p_floor", "minimum_cell_density_by_stage", ...
        "minimum_cell_pressure_by_stage", ...
        "minimum_interface_density_by_stage", ...
        "minimum_interface_pressure_by_stage", ...
        "minimum_anchor_partial_density_by_stage", ...
        "minimum_anchor_partial_pressure_by_stage", ...
        "minimum_final_partial_density_by_stage", ...
        "minimum_final_partial_pressure_by_stage"];
    if ~all(isfield(metrics, required)) || metrics.invalid_stage_count ~= 0 || ...
            metrics.invalid_reconstruction_count ~= 0 || ...
            metrics.clipping_count ~= 0 || metrics.flux_fallback_count ~= 0 || ...
            any(metrics.minimum_cell_density_by_stage < metrics.rho_floor) || ...
            any(metrics.minimum_cell_pressure_by_stage < metrics.p_floor) || ...
            any(metrics.minimum_interface_density_by_stage < metrics.rho_floor) || ...
            any(metrics.minimum_interface_pressure_by_stage < metrics.p_floor) || ...
            any(metrics.minimum_anchor_partial_density_by_stage < metrics.rho_floor) || ...
            any(metrics.minimum_anchor_partial_pressure_by_stage < metrics.p_floor) || ...
            any(metrics.minimum_final_partial_density_by_stage < metrics.rho_floor) || ...
            any(metrics.minimum_final_partial_pressure_by_stage < metrics.p_floor) || ...
            (isfield(metrics, "has_nonfinite") && metrics.has_nonfinite)
        value = false;
        return
    end
end
end

function value = nominalRetriesZero(cases)
value = true;
for index = 1:numel(cases)
    metrics = cases(index).muscl_minmod_pp;
    value = value && metrics.rejected_step_count == 0 && metrics.retry_count == 0;
end
end

function value = stressActivated(stress)
metrics = stress.muscl_minmod_pp;
value = metrics.reconstruction_pp_activation_count > 0 || ...
    metrics.flux_pp_activation_count > 0;
end

function value = stressHealthy(stress)
metrics = stress.muscl_minmod_pp;
value = ~metrics.has_nonfinite && metrics.conservation_error <= 1e-10 && ...
    metrics.clipping_count == 0 && metrics.flux_fallback_count == 0 && ...
    metrics.invalid_stage_count == 0;
end

function value = rhoErrorRatio(old, pp)
oldError = densityError(old);
ppError = densityError(pp);
if isfinite(oldError) && oldError ~= 0
    value = ppError / oldError;
else
    value = NaN;
end
end

function value = densityError(metrics)
if isfield(metrics, "rho_l1_error")
    candidate = metrics.rho_l1_error;
elseif isfield(metrics, "density_l1_error")
    candidate = metrics.density_l1_error;
else
    value = NaN;
    return
end
value = candidate(end);
end

function selected = selectCase(cases, id)
selected = cases(string({cases.id}) == id);
if numel(selected) ~= 1
    error("S12:Benchmark:QualificationCaseMissing", ...
        "Sprint 3 qualification requires case '%s'.", id);
end
end

function value = row(value)
value = reshape(value, 1, []);
end

function value = check(id, passed)
value = struct("id", id, "passed", logical(passed));
end

function result = normalize(result)
result.schema = string(result.schema);
result.suite.profile = string(result.suite.profile);
result.suite.selector = string(result.suite.selector);
result.acceptance.status = string(result.acceptance.status);
for index = 1:numel(result.cases)
    result.cases(index).id = string(result.cases(index).id);
    result.cases(index).category = string(result.cases(index).category);
    if isempty(result.cases(index).rho_error_ratio)
        result.cases(index).rho_error_ratio = NaN;
    end
end
end
