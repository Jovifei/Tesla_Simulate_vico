function tests = test_s12_fanno_fvm_contract
%TEST_S12_FANNO_FVM_CONTRACT Specify the independent Fanno FVM adapter.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
fannoRoot = fullfile(s12Root, "validation", "fanno");
addpath(benchmarkRoot, fannoRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot, fannoRoot));
end

function testDefinitionFreezesModeAndSourceIdentifiers(testCase)
if ~requireFunction(testCase, "s12_fanno_fvm_case_definition"); return; end
definition = s12_fanno_fvm_case_definition("quick");
verifyEqual(testCase, definition.spatial_scheme, "muscl_minmod_pp");
verifyEqual(testCase, definition.balance_law_mode, "fanno_constant_darcy");
verifyEqual(testCase, definition.friction_source_id, "darcy_wall_exact.v1");
verifyEqual(testCase, definition.source_integrator_id, ...
    "strang_exact_friction_ssprk3.v1");
verifyEqual(testCase, definition.boundary_id, "subsonic_fanno_validation.v1");
verifyEqual(testCase, definition.grid_cell_counts, [50, 100, 200, 400]);
end

function testUniformFrictionDecayUsesTheIndependentFannoAdapter(testCase)
if ~requireFunction(testCase, "s12_run_fanno_fvm"); return; end
gamma = 1.4;
rho = ones(1, 8);
velocity = 2 * ones(1, 8);
pressure = 3 * ones(1, 8);
state = [rho; rho .* velocity; pressure / (gamma - 1) + 0.5 * rho .* velocity.^2];
config = struct("gamma", gamma, "gas_constant", 287.05, "length_m", 1, ...
    "hydraulic_diameter_m", 0.1, "darcy_friction_factor", 0.02, ...
    "cfl", 0.2, "end_time_s", 0.01, "max_steps", 100, ...
    "boundary", "periodic_uniform_friction", "initial_state", state);
result = s12_run_fanno_fvm(config);
verifyEqual(testCase, result.balance_law_mode, "fanno_constant_darcy");
verifyEqual(testCase, result.source_integrator_id, "strang_exact_friction_ssprk3.v1");
verifyEqual(testCase, result.qualification.clipping_count, 0);
verifyEqual(testCase, result.qualification.flux_fallback_count, 0);
end

function testCharacteristicStepReturnsOneThreeStageResult(testCase)
if ~requireFunction(testCase, "s12_fanno_pp_characteristic_step"); return; end
gamma = 1.4;
gasConstant = 287.05;
staticPressure = 2e5;
staticTemperature = 300;
area = pi * 0.1^2 / 4;
massFlux = 1 / area;
density = staticPressure / (gasConstant * staticTemperature);
velocity = massFlux / density;
energy = staticPressure / (gamma - 1) + 0.5 * density * velocity^2;
state = repmat([density; density * velocity; energy], 1, 8);

result = s12_fanno_pp_characteristic_step(state, gamma, 1 / 8, 1e-5, ...
    GasConstant=gasConstant, InletStaticPressure=staticPressure, ...
    InletStaticTemperature=staticTemperature, OutletMassFlux=massFlux, Cfl=0.2);

verifyTrue(testCase, isscalar(result));
verifyEqual(testCase, result.stage_dt, repmat(1e-5, 1, 3), "AbsTol", 1e-14);
verifyEqual(testCase, numel(result.stage_states), 3);
verifyEqual(testCase, size(result.final_state), size(state));
verifyEqual(testCase, size(result.stage_diagnostics), [20, 3]);
end

function testCharacteristicBoundaryFvmUsesTheFannoAdapter(testCase)
if ~requireFunction(testCase, "s12_run_fanno_fvm"); return; end
gamma = 1.4;
gasConstant = 287.05;
staticPressure = 2e5;
staticTemperature = 300;
area = pi * 0.1^2 / 4;
massFlux = 1 / area;
density = staticPressure / (gasConstant * staticTemperature);
velocity = massFlux / density;
energy = staticPressure / (gamma - 1) + 0.5 * density * velocity^2;
state = repmat([density; density * velocity; energy], 1, 8);
config = struct("gamma", gamma, "gas_constant", gasConstant, "length_m", 1, ...
    "hydraulic_diameter_m", 0.1, "darcy_friction_factor", 0.02, ...
    "cfl", 0.2, "end_time_s", 1e-5, "max_steps", 100, ...
    "boundary", "subsonic_fanno_validation.v1", "initial_state", state, ...
    "inlet_static_pressure", staticPressure, ...
    "inlet_static_temperature", staticTemperature, "outlet_mass_flux", massFlux);

result = s12_run_fanno_fvm(config);

verifyEqual(testCase, result.qualification.boundary_id, ...
    "subsonic_fanno_validation.v1");
verifyEqual(testCase, result.final_time_s, 1e-5, "AbsTol", 1e-14);
verifyTrue(testCase, all(isfinite(result.final_state), "all"));
required = ["minimum_reconstructed_density", ...
    "minimum_reconstructed_pressure", "invalid_reconstruction_count", ...
    "reconstruction_pp_activation_count", "flux_pp_activation_count", ...
    "reconstruction_pp_min_theta", "flux_pp_min_theta", ...
    "minimum_anchor_partial_density", "minimum_anchor_partial_pressure", ...
    "minimum_final_partial_density", "minimum_final_partial_pressure", ...
    "invalid_stage_count"];
verifyTrue(testCase, all(isfield(result.qualification, required)));
verifyEqual(testCase, result.qualification.invalid_reconstruction_count, 0);
verifyEqual(testCase, result.qualification.invalid_stage_count, 0);
verifyGreaterThan(testCase, result.qualification.minimum_reconstructed_density, 0);
verifyGreaterThan(testCase, result.qualification.minimum_reconstructed_pressure, 0);
verifyEqual(testCase, result.balance_metric_id, ...
    "fanno_boundary_flux_interior_trim2.v1");
verifyEqual(testCase, result.balance_boundary_trim_cells_per_side, 2);
verifyEqual(testCase, result.outlet.mass_flux, massFlux, "RelTol", 2e-12);
end

function testZeroFrictionMatchesFrozenPeriodicPpStep(testCase)
gamma = 1.4;
cellCount = 8;
x = ((1:cellCount) - 0.5) / cellCount;
density = 1 + 0.05 * sin(2 * pi * x);
velocity = 0.2 * ones(size(x));
pressure = ones(size(x));
state = [density; density .* velocity; ...
    pressure / (gamma - 1) + 0.5 * density .* velocity.^2];
dt = 1e-5;
config = struct("gamma", gamma, "gas_constant", 287.05, "length_m", 1, ...
    "hydraulic_diameter_m", 0.1, "darcy_friction_factor", 0, ...
    "cfl", 0.2, "end_time_s", dt, "max_steps", 1, ...
    "boundary", "periodic_uniform_friction", "initial_state", state);

fanno = s12_run_fanno_fvm(config);
frozen = s12_run_periodic_ssprk3(state, gamma, 1 / cellCount, dt, 1, ...
    config.cfl, Reconstruction="muscl_minmod_pp");

verifyEqual(testCase, fanno.final_state, frozen.final_state, "AbsTol", 1e-13);
verifyEqual(testCase, fanno.qualification.source_density_change_max, 0);
verifyEqual(testCase, fanno.qualification.source_energy_change_max, 0);
end

function testFannoAdapterUsesGhostInclusiveCfl(testCase)
if ~requireFunction(testCase, "s12_fanno_analytical_profile"); return; end
definition = s12_fanno_case_definition("full");
profile = s12_fanno_analytical_profile(definition, 1, 50, 16);
config = struct("gamma", definition.gamma, ...
    "gas_constant", definition.gas_constant, "length_m", 1, ...
    "hydraulic_diameter_m", definition.diameter, ...
    "darcy_friction_factor", profile.darcy_friction_factor, ...
    "cfl", 0.2, "end_time_s", 2e-5, "max_steps", 20, ...
    "boundary", "subsonic_fanno_validation.v1", ...
    "initial_state", profile.cell_average_state, ...
    "inlet_static_pressure", definition.inlet_static_pressure, ...
    "inlet_static_temperature", definition.inlet_static_temperature, ...
    "outlet_mass_flux", definition.mass_flow / definition.area);

result = s12_run_fanno_fvm(config);

verifyLessThanOrEqual(testCase, result.maximum_cfl, config.cfl + 32 * eps);
verifyEqual(testCase, result.qualification.retry_count, 0);
verifyEqual(testCase, result.qualification.rejected_step_count, 0);
end

function testFannoAdapterReportsBalanceLawMetrics(testCase)
definition = s12_fanno_case_definition("full");
profile = s12_fanno_analytical_profile(definition, 1, 8, 16);
config = struct("gamma", definition.gamma, ...
    "gas_constant", definition.gas_constant, "length_m", 1, ...
    "hydraulic_diameter_m", definition.diameter, ...
    "darcy_friction_factor", profile.darcy_friction_factor, ...
    "cfl", 0.2, "end_time_s", 1e-5, "max_steps", 20, ...
    "boundary", "subsonic_fanno_validation.v1", ...
    "initial_state", profile.cell_average_state, ...
    "inlet_static_pressure", definition.inlet_static_pressure, ...
    "inlet_static_temperature", definition.inlet_static_temperature, ...
    "outlet_mass_flux", definition.mass_flow / definition.area);

result = s12_run_fanno_fvm(config);

required = ["mass_flow_uniformity", "mass_balance_residual", ...
    "energy_balance_residual", "source_balanced_momentum_residual", ...
    "stagnation_temperature_spread"];
verifyTrue(testCase, all(isfield(result.balance_metrics, required)));
verifyTrue(testCase, all(isfinite(struct2array(result.balance_metrics))));
verifyGreaterThan(testCase, result.sonic_margin, 0);
end

function testSteadyCriteriaUsesWholeStrangSteps(testCase)
definition = s12_fanno_case_definition("full");
profile = s12_fanno_analytical_profile(definition, 1, 8, 16);
criteria = struct("state_residual_limit", 1, ...
    "mass_flow_uniformity_limit", 1, "mass_balance_limit", 1, ...
    "energy_balance_limit", 1, "momentum_balance_limit", 1, ...
    "stagnation_temperature_spread_limit", 1, "required_windows", 2);
config = struct("gamma", definition.gamma, ...
    "gas_constant", definition.gas_constant, "length_m", 1, ...
    "hydraulic_diameter_m", definition.diameter, ...
    "darcy_friction_factor", profile.darcy_friction_factor, ...
    "cfl", 0.2, "end_time_s", 2e-4, "max_steps", 100, ...
    "boundary", "subsonic_fanno_validation.v1", ...
    "initial_state", profile.cell_average_state, ...
    "inlet_static_pressure", definition.inlet_static_pressure, ...
    "inlet_static_temperature", definition.inlet_static_temperature, ...
    "outlet_mass_flux", definition.mass_flow / definition.area, ...
    "steady_criteria", criteria);

result = s12_run_fanno_fvm(config);

verifyTrue(testCase, result.steady_state_reached);
verifyEqual(testCase, result.steady_window_count, 2);
verifyEqual(testCase, result.qualification.end_time_clipping_count, 0);
end

function testLongPipeCoarseGridUsesBoundaryFluxBalance(testCase)
definition = s12_fanno_case_definition("full");
profile = s12_fanno_analytical_profile(definition, 156, 50, 16);
settings = s12_benchmark_profile("full");
config = struct("gamma", definition.gamma, ...
    "gas_constant", definition.gas_constant, "length_m", 156, ...
    "hydraulic_diameter_m", definition.diameter, ...
    "darcy_friction_factor", profile.darcy_friction_factor, ...
    "cfl", settings.fanno_fvm.cfl, ...
    "cfl_safety_factor", settings.fanno_fvm.cfl_safety_factor, ...
    "end_time_s", settings.fanno_fvm.maximum_physical_time_s, ...
    "max_steps", 5, "boundary", "subsonic_fanno_validation.v1", ...
    "initial_state", profile.cell_average_state, ...
    "inlet_static_pressure", definition.inlet_static_pressure, ...
    "inlet_static_temperature", definition.inlet_static_temperature, ...
    "outlet_mass_flux", definition.mass_flow / definition.area, ...
    "steady_criteria", settings.fanno_fvm.steady_criteria);

result = s12_run_fanno_fvm(config);

verifyTrue(testCase, result.steady_state_reached);
verifyLessThanOrEqual(testCase, result.step_count, 5);
verifyEqual(testCase, result.balance_metric_id, ...
    "fanno_boundary_flux_interior_trim2.v1");
end

function exists = requireFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyTrue(testCase, exists, ...
    "Sprint 4B production function must exist: " + name);
end
