function tests = test_s12_muscl_minmod
%TEST_S12_MUSCL_MINMOD Verify the Sprint 2 reconstruction-mode contract.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testFirstOrderFallbackMatchesFrozenTransmissiveResult(testCase)
[initialState, gamma, dx, endTime, cfl, maxSteps] = sodInputs;

legacy = s12_run_transmissive_ssprk3( ...
    initialState, gamma, dx, endTime, cfl, maxSteps);
fallback = s12_run_transmissive_ssprk3( ...
    initialState, gamma, dx, endTime, cfl, maxSteps, ...
    Reconstruction="first_order");

verifyEqual(testCase, fallback.reconstruction, "first_order");
verifyEqual(testCase, fallback.final_state, legacy.final_state, ...
    "AbsTol", 0, "RelTol", 0);
verifyEqual(testCase, fallback.conservation_residual, ...
    legacy.conservation_residual, "AbsTol", 0, "RelTol", 0);
end

function testMusclMinmodImprovesSodDensityL1Error(testCase)
[initialState, gamma, dx, endTime, cfl, maxSteps] = sodInputs;
x = ((1:size(initialState, 2)) - 0.5) * dx;
[exactDensity, ~, ~] = s12_exact_sod( ...
    x, 0.5, endTime, gamma, [1, 0, 1], [0.125, 0, 0.1]);

firstOrder = s12_run_transmissive_ssprk3( ...
    initialState, gamma, dx, endTime, cfl, maxSteps, ...
    Reconstruction="first_order");
muscl = s12_run_transmissive_ssprk3( ...
    initialState, gamma, dx, endTime, cfl, maxSteps, ...
    Reconstruction="muscl_minmod");

firstOrderError = mean(abs(firstOrder.final_state(1, :) - exactDensity));
musclError = mean(abs(muscl.final_state(1, :) - exactDensity));
verifyEqual(testCase, muscl.reconstruction, "muscl_minmod");
verifyLessThan(testCase, musclError, firstOrderError);
end

function testPeriodicMusclPreservesUniformStateAndUsesOneStageDt(testCase)
gamma = 1.4;
cellCount = 16;
initialState = primitiveToConservative( ...
    1.1 * ones(1, cellCount), 0.2 * ones(1, cellCount), ...
    ones(1, cellCount), gamma);

result = s12_run_periodic_ssprk3(initialState, gamma, 1 / cellCount, ...
    1e-3, 5, 0.45, Reconstruction="muscl_minmod");

verifyEqual(testCase, result.reconstruction, "muscl_minmod");
verifyEqual(testCase, result.final_state, initialState, ...
    "RelTol", 1e-12, "AbsTol", 1e-12);
verifyEqual(testCase, result.used_dt, result.requested_dt, ...
    "AbsTol", 32 * eps(1e-3));
end

function testBenchmarkEntryPointRecordsMusclMode(testCase)
output = tempname;
mkdir(output);
testCase.addTeardown(@() removeDirectory(output));

result = run_s12_benchmarks("case:lax_shock_tube", ...
    Profile="quick", Reconstruction="muscl_minmod", ...
    OutputDirectory=output);

verifyEqual(testCase, result.acceptance.status, "passed");
verifyEqual(testCase, result.cases.config.reconstruction, "muscl_minmod");
end

function [state, gamma, dx, endTime, cfl, maxSteps] = sodInputs
gamma = 1.4;
cellCount = 200;
dx = 1 / cellCount;
endTime = 0.2;
cfl = 0.45;
maxSteps = 10000;
x = ((1:cellCount) - 0.5) * dx;
left = x < 0.5;
state = primitiveToConservative( ...
    1.0 * left + 0.125 * ~left, zeros(size(x)), ...
    1.0 * left + 0.1 * ~left, gamma);
end

function state = primitiveToConservative(rho, velocity, pressure, gamma)
state = [rho; rho .* velocity; ...
    pressure / (gamma - 1) + 0.5 * rho .* velocity.^2];
end

function removeDirectory(path)
if isfolder(path)
    rmdir(path, "s");
end
end
