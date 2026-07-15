function tests = test_s12_fanno_balance_law_contract
%TEST_S12_FANNO_BALANCE_LAW_CONTRACT Specify Fanno steady balance metrics.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
addFannoPath(testCase);
end

function testSourceBalancedMomentumUsesBoundaryFluxAndWallIntegral(testCase)
if ~requireFunction(testCase, "s12_fanno_balance_metrics"); return; end
input = struct( ...
    "mass_flux", [2, 2, 2], ...
    "total_enthalpy", [4, 4, 4], ...
    "stagnation_temperature", [300, 300, 300], ...
    "momentum_flux_in", 12, ...
    "momentum_flux_out", 9, ...
    "wall_momentum_source_integral", -3, ...
    "state_change_residual", 1e-9);
metrics = s12_fanno_balance_metrics(input);
verifyEqual(testCase, metrics.mass_flow_uniformity, 0, "AbsTol", 0);
verifyEqual(testCase, metrics.energy_balance_residual, 0, "AbsTol", 0);
verifyEqual(testCase, metrics.stagnation_temperature_spread, 0, "AbsTol", 0);
verifyEqual(testCase, metrics.source_balanced_momentum_residual, 0, "AbsTol", 0);
verifyEqual(testCase, metrics.normalized_state_residual, 1e-9, "AbsTol", 0);
end

function testNoFrictionIsTheZeroSourceLimit(testCase)
if ~requireFunction(testCase, "s12_fanno_balance_metrics"); return; end
input = struct( ...
    "mass_flux", [3, 3], ...
    "total_enthalpy", [9, 9], ...
    "stagnation_temperature", [310, 310], ...
    "momentum_flux_in", 15, ...
    "momentum_flux_out", 15, ...
    "wall_momentum_source_integral", 0, ...
    "state_change_residual", 0);
metrics = s12_fanno_balance_metrics(input);
verifyEqual(testCase, metrics.source_balanced_momentum_residual, 0, "AbsTol", 0);
verifyEqual(testCase, metrics.mass_balance_residual, 0, "AbsTol", 0);
end

function addFannoPath(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
fannoRoot = fullfile(s12Root, "validation", "fanno");
addpath(fannoRoot);
testCase.addTeardown(@() rmpath(fannoRoot));
end

function exists = requireFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyTrue(testCase, exists, ...
    "Sprint 4B production function must exist: " + name);
end
