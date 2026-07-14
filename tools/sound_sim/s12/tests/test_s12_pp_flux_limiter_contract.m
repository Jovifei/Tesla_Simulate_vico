function tests = test_s12_pp_flux_limiter_contract
%TEST_S12_PP_FLUX_LIMITER_CONTRACT Specify shared-interface flux limiting.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testLegalHighOrderCandidateUsesThetaOne(testCase)
if ~requireProductionFunction(testCase, "s12_pp_limit_interface_flux"); return; end
gamma = 1.4;
state = primitiveToConservative(1, 0, 1, gamma);
flux = [0; 1; 0];

result = s12_pp_limit_interface_flux(state, state, flux, flux, ...
    0.05, gamma, 1e-6, 1e-6);

verifyEqual(testCase, result.theta, 1, "AbsTol", 32 * eps);
verifyEqual(testCase, result.flux, flux, "AbsTol", 32 * eps);
verifyEqual(testCase, result.left_partial + result.right_partial, ...
    2 * state, "AbsTol", 32 * eps);
end

function testDensityAndPressureConstraintsShareTheStricterTheta(testCase)
if ~requireProductionFunction(testCase, "s12_pp_limit_interface_flux"); return; end
gamma = 1.4;
state = primitiveToConservative(1, 0, 1, gamma);
highFlux = [10; 0; 10];
lowFlux = zeros(3, 1);
lambda = 0.1;

result = s12_pp_limit_interface_flux(state, state, highFlux, lowFlux, ...
    lambda, gamma, 0.1, 0.5);

expectedDensityTheta = 0.45;
expectedPressureTheta = 0.625;
verifyEqual(testCase, result.theta, min(expectedDensityTheta, expectedPressureTheta), ...
    "AbsTol", 32 * eps);
verifyGreaterThanOrEqual(testCase, result.left_partial(1), 0.1);
verifyGreaterThanOrEqual(testCase, pressure(result.left_partial, gamma), 0.5);
verifyEqual(testCase, result.left_partial + result.right_partial, ...
    2 * state, "AbsTol", 32 * eps);
end

function testAnchorFailureIsRejectedWithoutNanOrRepair(testCase)
if ~requireProductionFunction(testCase, "s12_pp_limit_interface_flux"); return; end
gamma = 1.4;
state = primitiveToConservative(1, 0, 1, gamma);
badAnchor = [10; 0; 0];

verifyError(testCase, @() s12_pp_limit_interface_flux( ...
    state, state, zeros(3, 1), badAnchor, 0.1, gamma, 0.1, 0.1), ...
    "S12:Positivity:InvalidLowOrderAnchor");
end

function testResultIsFiniteAndDeterministic(testCase)
if ~requireProductionFunction(testCase, "s12_pp_limit_interface_flux"); return; end
gamma = 1.4;
left = primitiveToConservative(1, 0.2, 1, gamma);
right = primitiveToConservative(0.8, -0.1, 0.8, gamma);
highFlux = [2; 0.3; 1.5];
lowFlux = [0.1; 0.2; 0.3];

first = s12_pp_limit_interface_flux(left, right, highFlux, lowFlux, ...
    0.02, gamma, 1e-6, 1e-6);
second = s12_pp_limit_interface_flux(left, right, highFlux, lowFlux, ...
    0.02, gamma, 1e-6, 1e-6);

verifyTrue(testCase, all(isfinite([first.flux; first.left_partial; ...
    first.right_partial])));
verifyEqual(testCase, first, second, "AbsTol", 0, "RelTol", 0);
end

function exists = requireProductionFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyTrue(testCase, exists, ...
    "Sprint 3 production contract function must exist: " + name);
end

function state = primitiveToConservative(rho, velocity, pressureValue, gamma)
state = [rho; rho * velocity; ...
    pressureValue / (gamma - 1) + 0.5 * rho * velocity^2];
end

function pressureValue = pressure(state, gamma)
rho = state(1);
velocity = state(2) / rho;
pressureValue = (gamma - 1) * (state(3) - 0.5 * rho * velocity^2);
end
