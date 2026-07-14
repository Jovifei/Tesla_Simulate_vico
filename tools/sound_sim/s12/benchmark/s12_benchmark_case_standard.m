function definition = s12_benchmark_case_standard(caseId)
%S12_BENCHMARK_CASE_STANDARD Share the Sprint 1 case contract and adapter.
arguments
    caseId (1,1) string
end
definition = struct( ...
    "configure", @configureCase, ...
    "run", @runCase, ...
    "analyze", @analyzeCase, ...
    "accept", @acceptCase);

    function config = configureCase(profile)
        config = makeConfig(caseId, profile);
    end

    function raw = runCase(config)
        switch config.case_id
            case "lax"
                raw = runLax(config);
            case "shu_osher"
                raw = runShuOsher(config);
            case "woodward_colella"
                raw = runWoodwardColella(config);
            otherwise
                error("S12:Benchmark:UnknownStandardCase", ...
                    "Unknown standard case '%s'.", config.case_id);
        end
    end

    function analysis = analyzeCase(raw)
        switch raw.config.case_id
            case "lax"
                analysis = analyzeLax(raw);
            case "shu_osher"
                analysis = analyzeShuOsher(raw);
            case "woodward_colella"
                analysis = analyzeWoodwardColella(raw);
            otherwise
                error("S12:Benchmark:UnknownStandardCase", ...
                    "Unknown standard case '%s'.", raw.config.case_id);
        end
    end

    function acceptance = acceptCase(metrics)
        switch caseId
            case "lax"
                acceptance = acceptLax(metrics);
            case "shu_osher"
                acceptance = acceptShuOsher(metrics);
            case "woodward_colella"
                acceptance = acceptWoodwardColella(metrics);
            otherwise
                error("S12:Benchmark:UnknownStandardCase", ...
                    "Unknown standard case '%s'.", caseId);
        end
    end
end

function config = makeConfig(caseId, profile)
base = struct( ...
    "case_id", caseId, ...
    "model", "s12_euler_ssprk3_sod_ref.slx", ...
    "gamma", 1.4, ...
    "cfl", profile.cfl_limit, ...
    "reconstruction", profile.reconstruction, ...
    "max_steps", 100000);
switch caseId
    case "lax"
        config = merge(base, struct( ...
            "domain", [-5, 5], "discontinuity", 0, ...
            "left", [0.445, 0.698, 3.528], ...
            "right", [0.5, 0, 0.571], "end_time", 1.3, ...
            "cell_counts", profile.lax.cell_counts, ...
            "reference_type", "exact_riemann", ...
            "boundary_strategy", "transmissive_domain_separated"));
    case "shu_osher"
        config = merge(base, struct( ...
            "domain", [-5, 5], "discontinuity", -4, ...
            "left", [3.857143, 2.629369, 10.333333], ...
            "end_time", 1.8, "cell_counts", profile.shu_osher.cell_counts, ...
            "reference_type", "literature_definition_self_convergence", ...
            "boundary_strategy", "transmissive_domain_separated"));
    case "woodward_colella"
        config = merge(base, struct( ...
            "physical_domain", [0, 1], "extended_domain", [-2, 3], ...
            "end_time", 0.038, ...
            "cell_counts", profile.woodward_colella.cell_counts, ...
            "reference_type", "literature_definition_self_convergence", ...
            "boundary_strategy", "mirror_extension_transmissive_solver"));
    otherwise
        error("S12:Benchmark:UnknownStandardCase", ...
            "Unknown standard case '%s'.", caseId);
end
end

function raw = runLax(config)
samples = repmat(emptySample(), 1, numel(config.cell_counts));
for gridIndex = 1:numel(config.cell_counts)
    count = config.cell_counts(gridIndex);
    dx = diff(config.domain) / count;
    x = config.domain(1) + ((1:count) - 0.5) * dx;
    leftMask = x < config.discontinuity;
    rho = config.left(1) * leftMask + config.right(1) * ~leftMask;
    velocity = config.left(2) * leftMask + config.right(2) * ~leftMask;
    pressure = config.left(3) * leftMask + config.right(3) * ~leftMask;
    initialState = s12_benchmark_primitive_to_conservative( ...
        rho, velocity, pressure, config.gamma);
    sample = executeSample(x, initialState, dx, config);
    [sample.exact_density, sample.exact_velocity, sample.exact_pressure] = ...
        s12_exact_sod(x, config.discontinuity, config.end_time, config.gamma, ...
        config.left, config.right);
    samples(gridIndex) = sample;
end
raw = struct("config", config, "samples", samples);
end

function raw = runShuOsher(config)
samples = repmat(emptySample(), 1, numel(config.cell_counts));
for gridIndex = 1:numel(config.cell_counts)
    count = config.cell_counts(gridIndex);
    dx = diff(config.domain) / count;
    x = config.domain(1) + ((1:count) - 0.5) * dx;
    leftMask = x < config.discontinuity;
    rho = (1 + 0.2 * sin(5 * x));
    rho(leftMask) = config.left(1);
    velocity = zeros(size(x));
    velocity(leftMask) = config.left(2);
    pressure = ones(size(x));
    pressure(leftMask) = config.left(3);
    initialState = s12_benchmark_primitive_to_conservative( ...
        rho, velocity, pressure, config.gamma);
    samples(gridIndex) = executeSample(x, initialState, dx, config);
end
raw = struct("config", config, "samples", samples);
end

function raw = runWoodwardColella(config)
samples = repmat(emptySample(), 1, numel(config.cell_counts));
for gridIndex = 1:numel(config.cell_counts)
    physicalCount = config.cell_counts(gridIndex);
    dx = diff(config.physical_domain) / physicalCount;
    count = round(diff(config.extended_domain) / dx);
    x = config.extended_domain(1) + ((1:count) - 0.5) * dx;
    physicalX = reflectedCoordinate(x);
    pressure = 0.01 * ones(size(x));
    pressure(physicalX < 0.1) = 1000;
    pressure(physicalX >= 0.9) = 100;
    rho = ones(size(x));
    velocity = zeros(size(x));
    initialState = s12_benchmark_primitive_to_conservative( ...
        rho, velocity, pressure, config.gamma);
    sample = executeSample(x, initialState, dx, config);
    sample.physical_mask = x > config.physical_domain(1) & ...
        x < config.physical_domain(2);
    samples(gridIndex) = sample;
end
raw = struct("config", config, "samples", samples);
end

function sample = executeSample(x, initialState, dx, config)
sample = emptySample();
sample.x = x;
sample.dx = dx;
sample.initial_state = initialState;
started = tic;
try
    sample.solver = s12_run_transmissive_ssprk3(initialState, config.gamma, ...
        dx, config.end_time, config.cfl, config.max_steps, ...
        Reconstruction=config.reconstruction);
    sample.success = true;
catch exception
    sample.success = false;
    sample.error_id = string(exception.identifier);
    sample.error_message = string(exception.message);
end
sample.runtime_seconds = toc(started);
end

function analysis = analyzeLax(raw)
count = numel(raw.samples);
densityError = NaN(1, count);
velocityError = NaN(1, count);
pressureError = NaN(1, count);
shockError = NaN(1, count);
contactError = NaN(1, count);
rarefactionError = NaN(1, count);
shockPosition = NaN(1, count);
contactPosition = NaN(1, count);
rarefactionHeadPosition = NaN(1, count);
minDensity = NaN(1, count);
minPressure = NaN(1, count);
conservation = NaN(1, count);
courant = NaN(1, count);
runtime = [raw.samples.runtime_seconds];
hasNonfinite = false;
exactFeatures = laxExactFeatures(raw.config);
for index = 1:count
    sample = raw.samples(index);
    if ~sample.success
        hasNonfinite = true;
        continue
    end
    [rho, velocity, pressure] = s12_benchmark_conservative_to_primitive( ...
        sample.solver.final_state, raw.config.gamma);
    hasNonfinite = hasNonfinite || any(~isfinite([rho, velocity, pressure]), "all");
    densityError(index) = mean(abs(rho - sample.exact_density));
    velocityError(index) = mean(abs(velocity - sample.exact_velocity));
    pressureError(index) = mean(abs(pressure - sample.exact_pressure));
    headMask = sample.x >= exactFeatures.rarefaction_head - 0.75 & ...
        sample.x <= exactFeatures.rarefaction_head + 0.75;
    rarefactionHeadPosition(index) = s12_benchmark_leading_level_location( ...
        sample.x(headMask), rho(headMask), raw.config.left(1), ...
        exactFeatures.rarefaction_fan_amplitude, 0.05);
    contactPosition(index) = featureLocationNear( ...
        sample.x, rho, exactFeatures.contact, 0.60);
    shockPosition(index) = featureLocationNear( ...
        sample.x, rho, exactFeatures.shock, 0.75);
    rarefactionError(index) = abs(rarefactionHeadPosition(index) - ...
        exactFeatures.rarefaction_head);
    contactError(index) = abs(contactPosition(index) - exactFeatures.contact);
    shockError(index) = abs(shockPosition(index) - exactFeatures.shock);
    minDensity(index) = min(rho);
    minPressure(index) = min(pressure);
    conservation(index) = scaledConservation(sample);
    courant(index) = sample.solver.max_courant;
end
finest = raw.samples(end);
[rho, ~, ~] = finalPrimitive(finest, raw.config.gamma);
analysis = struct("metrics", struct( ...
    "density_l1_error", densityError(end), ...
    "velocity_l1_error", velocityError(end), ...
    "pressure_l1_error", pressureError(end), ...
    "density_l1_by_grid", densityError, ...
    "velocity_l1_by_grid", velocityError, ...
    "pressure_l1_by_grid", pressureError, ...
    "shock_position_error", shockError(end), ...
    "contact_position_error", contactError(end), ...
    "rarefaction_head_position_error", rarefactionError(end), ...
    "shock_position", shockPosition(end), ...
    "contact_position", contactPosition(end), ...
    "rarefaction_head_position", rarefactionHeadPosition(end), ...
    "rarefaction_head_locator", "five_percent_fan_amplitude", ...
    "exact_shock_position", exactFeatures.shock, ...
    "exact_contact_position", exactFeatures.contact, ...
    "exact_rarefaction_head_position", exactFeatures.rarefaction_head, ...
    "min_density", min(minDensity), "min_pressure", min(minPressure), ...
    "density_total_variation", sum(abs(diff(rho))), ...
    "conservation_error", max(conservation), "max_courant", max(courant), ...
    "step_count", sum(stepCounts(raw.samples)), ...
    "grid_cell_counts", raw.config.cell_counts, ...
    "grid_error_nonincreasing", nonincreasing(densityError), ...
    "has_nonfinite", hasNonfinite, "runtime_seconds", sum(runtime), ...
    "failure_diagnostics", failureDiagnostics(raw.samples)), ...
    "plot", struct("x", finest.x, "numerical_density", rho, ...
        "exact_density", finest.exact_density));
analysis.metrics = merge(analysis.metrics, qualificationSummary(raw.samples));
end

function analysis = analyzeShuOsher(raw)
count = numel(raw.samples);
shock = NaN(1, count);
amplitude = NaN(1, count);
variation = NaN(1, count);
minDensity = NaN(1, count);
minPressure = NaN(1, count);
conservation = NaN(1, count);
courant = NaN(1, count);
hasNonfinite = false;
runtime = [raw.samples.runtime_seconds];
for index = 1:count
    sample = raw.samples(index);
    if ~sample.success
        hasNonfinite = true;
        continue
    end
    [rho, velocity, pressure] = s12_benchmark_conservative_to_primitive( ...
        sample.solver.final_state, raw.config.gamma);
    hasNonfinite = hasNonfinite || any(~isfinite([rho, velocity, pressure]), "all");
    shock(index) = s12_benchmark_gradient_locations( ...
        sample.x, rho, 1, 0);
    window = entropyWindow(raw.config, shock(index), sample.dx);
    mask = sample.x >= window(1) & sample.x <= window(2);
    if any(mask)
        amplitude(index) = max(rho(mask)) - min(rho(mask));
        variation(index) = sum(abs(diff(rho(mask))));
    end
    minDensity(index) = min(rho);
    minPressure(index) = min(pressure);
    conservation(index) = scaledConservation(sample);
    courant(index) = sample.solver.max_courant;
end
finest = raw.samples(end);
[rho, ~, ~] = finalPrimitive(finest, raw.config.gamma);
window = entropyWindow(raw.config, shock(end), finest.dx);
analysis = struct("metrics", struct( ...
    "shock_position", shock(end), "shock_position_by_grid", shock, ...
    "post_shock_window", window, ...
    "density_peak_to_trough", amplitude(end), ...
    "density_peak_to_trough_by_grid", amplitude, ...
    "density_total_variation", variation(end), ...
    "density_total_variation_by_grid", variation, ...
    "min_density", min(minDensity), "min_pressure", min(minPressure), ...
    "conservation_error", max(conservation), "max_courant", max(courant), ...
    "step_count", sum(stepCounts(raw.samples)), ...
    "grid_cell_counts", raw.config.cell_counts, ...
    "has_nonfinite", hasNonfinite, "runtime_seconds", sum(runtime), ...
    "failure_diagnostics", failureDiagnostics(raw.samples)), ...
    "plot", struct("x", finest.x, "numerical_density", rho));
analysis.metrics = merge(analysis.metrics, qualificationSummary(raw.samples));
end

function analysis = analyzeWoodwardColella(raw)
count = numel(raw.samples);
minDensity = NaN(1, count);
minPressure = NaN(1, count);
conservation = NaN(1, count);
physicalMass = NaN(1, count);
physicalEnergy = NaN(1, count);
courant = NaN(1, count);
locations = NaN(count, 3);
hasNonfinite = false;
runtime = [raw.samples.runtime_seconds];
for index = 1:count
    sample = raw.samples(index);
    if ~sample.success
        hasNonfinite = true;
        continue
    end
    [rho, velocity, pressure] = s12_benchmark_conservative_to_primitive( ...
        sample.solver.final_state, raw.config.gamma);
    hasNonfinite = hasNonfinite || any(~isfinite([rho, velocity, pressure]), "all");
    mask = sample.physical_mask;
    minDensity(index) = min(rho);
    minPressure(index) = min(pressure);
    conservation(index) = scaledConservation(sample);
    courant(index) = sample.solver.max_courant;
    locations(index, :) = s12_benchmark_gradient_locations( ...
        sample.x(mask), rho(mask), 3, 4 * sample.dx);
    initial = sample.initial_state(:, mask);
    final = sample.solver.final_state(:, mask);
    physicalMass(index) = normalizedDifference(initial(1, :), final(1, :));
    physicalEnergy(index) = normalizedDifference(initial(3, :), final(3, :));
end
finest = raw.samples(end);
[rho, ~, ~] = finalPrimitive(finest, raw.config.gamma);
mask = finest.physical_mask;
analysis = struct("metrics", struct( ...
    "min_density", min(minDensity), "min_pressure", min(minPressure), ...
    "density_total_variation", sum(abs(diff(rho(mask)))), ...
    "has_nonfinite", hasNonfinite, "conservation_error", max(conservation), ...
    "physical_mass_residual", physicalMass(end), ...
    "physical_energy_residual", physicalEnergy(end), ...
    "max_courant", max(courant), ...
    "step_count", sum(stepCounts(raw.samples)), ...
    "major_gradient_positions", locations(end, :), ...
    "major_gradient_positions_by_grid", locations, ...
    "grid_cell_counts", raw.config.cell_counts, ...
    "runtime_seconds", sum(runtime), ...
    "failure_diagnostics", failureDiagnostics(raw.samples)), ...
    "plot", struct("x", finest.x(mask), "numerical_density", rho(mask)));
analysis.metrics = merge(analysis.metrics, qualificationSummary(raw.samples));
end

function acceptance = acceptLax(metrics)
checks = [ ...
    check("lax_finite", ~metrics.has_nonfinite, double(metrics.has_nonfinite), 0), ...
    positiveCheck("lax_positive_density", metrics.min_density), ...
    positiveCheck("lax_positive_pressure", metrics.min_pressure), ...
    check("lax_conservation", metrics.conservation_error <= 1e-10, ...
        metrics.conservation_error, 1e-10), ...
    check("lax_cfl", metrics.max_courant <= 0.45 * (1 + 1e-12), ...
        metrics.max_courant, 0.45 * (1 + 1e-12)), ...
    check("lax_grid_error_trend", metrics.grid_error_nonincreasing, ...
        double(~metrics.grid_error_nonincreasing), 0)];
acceptance = acceptanceFromChecks(checks);
end

function acceptance = acceptShuOsher(metrics)
checks = [ ...
    check("shu_osher_finite", ~metrics.has_nonfinite, ...
        double(metrics.has_nonfinite), 0), ...
    positiveCheck("shu_osher_positive_density", metrics.min_density), ...
    positiveCheck("shu_osher_positive_pressure", metrics.min_pressure), ...
    check("shu_osher_conservation", metrics.conservation_error <= 1e-10, ...
        metrics.conservation_error, 1e-10), ...
    check("shu_osher_cfl", metrics.max_courant <= 0.45 * (1 + 1e-12), ...
        metrics.max_courant, 0.45 * (1 + 1e-12)), ...
    check("shu_osher_shock_in_domain", isfinite(metrics.shock_position) && ...
        metrics.shock_position > -5 && metrics.shock_position < 5, ...
        metrics.shock_position, 5)];
acceptance = acceptanceFromChecks(checks);
end

function acceptance = acceptWoodwardColella(metrics)
checks = [ ...
    check("woodward_colella_finite", ~metrics.has_nonfinite, ...
        double(metrics.has_nonfinite), 0), ...
    positiveCheck("woodward_colella_positive_density", metrics.min_density), ...
    positiveCheck("woodward_colella_positive_pressure", metrics.min_pressure), ...
    check("woodward_colella_conservation", metrics.conservation_error <= 1e-10, ...
        metrics.conservation_error, 1e-10), ...
    check("woodward_colella_physical_mass", ...
        metrics.physical_mass_residual <= 1e-8, ...
        metrics.physical_mass_residual, 1e-8), ...
    check("woodward_colella_physical_energy", ...
        metrics.physical_energy_residual <= 1e-8, ...
        metrics.physical_energy_residual, 1e-8), ...
    check("woodward_colella_cfl", ...
        metrics.max_courant <= 0.45 * (1 + 1e-12), ...
        metrics.max_courant, 0.45 * (1 + 1e-12))];
acceptance = acceptanceFromChecks(checks);
end

function result = acceptanceFromChecks(checks)
if all([checks.passed])
    status = "passed";
else
    status = "failed";
end
result = struct("status", status, "checks", checks);
end

function result = check(id, passed, actual, limit)
result = struct("id", id, "passed", logical(passed), ...
    "actual", actual, "limit", limit);
end

function result = positiveCheck(id, value)
result = check(id, isfinite(value) && value > 0, -value, 0);
end

function sample = emptySample
sample = struct( ...
    "x", zeros(1, 0), "dx", NaN, "initial_state", zeros(3, 0), ...
    "solver", struct(), "success", false, "error_id", "", ...
    "error_message", "", "runtime_seconds", NaN, ...
    "exact_density", zeros(1, 0), "exact_velocity", zeros(1, 0), ...
    "exact_pressure", zeros(1, 0), "physical_mask", false(1, 0));
end

function [rho, velocity, pressure] = finalPrimitive(sample, gamma)
if sample.success
    [rho, velocity, pressure] = s12_benchmark_conservative_to_primitive( ...
        sample.solver.final_state, gamma);
else
    rho = NaN(size(sample.x));
    velocity = rho;
    pressure = rho;
end
end

function features = laxExactFeatures(config)
[~, ~, ~, features] = s12_exact_sod(0, config.discontinuity, ...
    config.end_time, config.gamma, config.left, config.right);
[fanTailDensity, ~, ~] = s12_exact_sod(features.rarefaction_tail, ...
    config.discontinuity, config.end_time, config.gamma, config.left, ...
    config.right);
features.rarefaction_fan_amplitude = abs(config.left(1) - fanTailDensity);
end

function location = featureLocationNear(x, rho, expected, halfWidth)
mask = x >= expected - halfWidth & x <= expected + halfWidth;
if ~isfinite(expected) || ~any(mask)
    location = NaN;
    return
end
location = s12_benchmark_gradient_locations(x(mask), rho(mask), 1, 0);
end

function window = entropyWindow(config, shockPosition, dx)
window = [max(config.discontinuity, shockPosition - 2), shockPosition - 4 * dx];
if ~isfinite(shockPosition) || window(2) <= window(1)
    window = [NaN, NaN];
end
end

function value = scaledConservation(sample)
scale = max(abs(sample.dx * sum(sample.initial_state, 2)).', 1);
value = max(abs(sample.solver.conservation_residual) ./ scale);
end

function value = normalizedDifference(initial, final)
value = abs(sum(final) - sum(initial)) / max(abs(sum(initial)), 1);
end

function value = nonincreasing(values)
finite = values(isfinite(values));
value = ~isempty(finite) && all(diff(finite) <= 1e-12);
end

function text = failureDiagnostics(samples)
messages = string({samples.error_message});
messages = messages(messages ~= "");
if isempty(messages)
    text = "";
else
    text = strjoin(messages, " | ");
end
end

function summary = qualificationSummary(samples)
successful = samples([samples.success]);
if isempty(successful)
    error("S12:Benchmark:QualificationMissing", ...
        "No successful standard-case samples contain qualification diagnostics.");
end
summary = s12_benchmark_aggregate_qualification([successful.solver]);
end

function values = stepCounts(samples)
values = zeros(1, numel(samples));
for index = 1:numel(samples)
    if samples(index).success
        values(index) = samples(index).solver.step_count;
    end
end
end

function physicalX = reflectedCoordinate(x)
physicalX = mod(x, 2);
rightHalf = physicalX > 1;
physicalX(rightHalf) = 2 - physicalX(rightHalf);
end

function result = merge(left, right)
result = left;
fields = fieldnames(right);
for index = 1:numel(fields)
    result.(fields{index}) = right.(fields{index});
end
end
