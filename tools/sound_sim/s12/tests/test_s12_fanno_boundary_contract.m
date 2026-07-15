function tests = test_s12_fanno_boundary_contract
%TEST_S12_FANNO_BOUNDARY_CONTRACT Specify validation-only Fanno boundaries.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
addFannoPath(testCase);
end

function testInletPrescribesStaticPressureTemperatureAndKeepsJminus(testCase)
if ~requireFunction(testCase, "s12_fanno_inlet_pt_boundary"); return; end
gamma = 1.4;
gasConstant = 287.05;
pressure = 100e3;
temperature = 300;
soundSpeed = sqrt(gamma * gasConstant * temperature);
interior = primitiveToConservative(pressure / (gasConstant * temperature), ...
    0.35 * soundSpeed, pressure, gamma);
[ghost, diagnostics] = s12_fanno_inlet_pt_boundary( ...
    interior, gamma, gasConstant, pressure, temperature);
[rho, velocity, resultPressure] = primitive(ghost, gamma);
resultSoundSpeed = sqrt(gamma * resultPressure / rho);
[~, interiorVelocity, interiorPressure] = primitive(interior, gamma);
interiorSoundSpeed = sqrt(gamma * interiorPressure / interior(1));
verifyEqual(testCase, resultPressure, pressure, "RelTol", 32 * eps);
verifyEqual(testCase, resultPressure / (rho * gasConstant), temperature, ...
    "RelTol", 32 * eps);
verifyEqual(testCase, velocity - 2 * resultSoundSpeed / (gamma - 1), ...
    interiorVelocity - 2 * interiorSoundSpeed / (gamma - 1), "AbsTol", 2e-12);
verifyGreaterThan(testCase, velocity, 0);
verifyLessThan(testCase, velocity, resultSoundSpeed);
verifyEqual(testCase, diagnostics.boundary_id, "subsonic_inlet_pt_outlet_mdot.v1");
end

function testOutletPrescribesMassFluxAndKeepsEntropyAndJplus(testCase)
if ~requireFunction(testCase, "s12_fanno_outlet_mdot_boundary"); return; end
gamma = 1.4;
rho = 1.1;
velocity = 90;
pressure = 120e3;
interior = primitiveToConservative(rho, velocity, pressure, gamma);
massFlux = rho * velocity;
[ghost, diagnostics] = s12_fanno_outlet_mdot_boundary( ...
    interior, gamma, massFlux);
[outRho, outVelocity, outPressure] = primitive(ghost, gamma);
interiorSoundSpeed = sqrt(gamma * pressure / rho);
outSoundSpeed = sqrt(gamma * outPressure / outRho);
verifyEqual(testCase, outRho * outVelocity, massFlux, "RelTol", 2e-12);
verifyEqual(testCase, outPressure / outRho^gamma, pressure / rho^gamma, ...
    "RelTol", 2e-12);
verifyEqual(testCase, outVelocity + 2 * outSoundSpeed / (gamma - 1), ...
    velocity + 2 * interiorSoundSpeed / (gamma - 1), "RelTol", 2e-12);
verifyGreaterThan(testCase, outVelocity, 0);
verifyLessThan(testCase, outVelocity, outSoundSpeed);
verifyEqual(testCase, diagnostics.mass_flux, massFlux, "RelTol", 32 * eps);
end

function testBoundariesRejectReverseAndSonicStates(testCase)
if ~requireFunction(testCase, "s12_fanno_inlet_pt_boundary"); return; end
if ~requireFunction(testCase, "s12_fanno_outlet_mdot_boundary"); return; end
gamma = 1.4;
gasConstant = 287.05;
pressure = 100e3;
temperature = 300;
rho = pressure / (gasConstant * temperature);
soundSpeed = sqrt(gamma * gasConstant * temperature);
reverse = primitiveToConservative(rho, -0.2 * soundSpeed, pressure, gamma);
sonic = primitiveToConservative(rho, soundSpeed, pressure, gamma);
verifyError(testCase, @() s12_fanno_inlet_pt_boundary( ...
    reverse, gamma, gasConstant, pressure, temperature), "S12:Fanno:BoundaryRegime");
verifyError(testCase, @() s12_fanno_inlet_pt_boundary( ...
    sonic, gamma, gasConstant, pressure, temperature), "S12:Fanno:BoundaryRegime");
verifyError(testCase, @() s12_fanno_outlet_mdot_boundary( ...
    reverse, gamma, rho * 0.1 * soundSpeed), "S12:Fanno:BoundaryRegime");
verifyError(testCase, @() s12_fanno_outlet_mdot_boundary( ...
    sonic, gamma, rho * soundSpeed), "S12:Fanno:BoundaryRegime");
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

function state = primitiveToConservative(rho, velocity, pressure, gamma)
state = [rho; rho * velocity; pressure / (gamma - 1) + 0.5 * rho * velocity^2];
end

function [rho, velocity, pressure] = primitive(state, gamma)
rho = state(1, :);
velocity = state(2, :) ./ rho;
pressure = (gamma - 1) * (state(3, :) - 0.5 * rho .* velocity.^2);
end
