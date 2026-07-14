function tests = test_s12_pp_global_lf_contract
%TEST_S12_PP_GLOBAL_LF_CONTRACT Specify the frozen global LF anchor.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
addBenchmarkPath(testCase);
end

function testStageAlphaUsesGlobalCellAverageMaximum(testCase)
if ~requireProductionFunction(testCase, "s12_pp_stage_alpha"); return; end
gamma = 1.4;
state = primitiveToConservative([1, 2, 0.5], [0, -0.5, 1], ...
    [1, 0.5, 2], gamma);
expected = max(abs([0, -0.5, 1]) + sqrt(gamma * [1, 0.5, 2] ./ [1, 2, 0.5]));

alpha = s12_pp_stage_alpha(state, gamma);

verifyEqual(testCase, alpha, expected, "RelTol", 64 * eps);
end

function testEqualStatesReturnPhysicalFlux(testCase)
if ~requireProductionFunction(testCase, "s12_pp_global_lf_flux"); return; end
gamma = 1.4;
state = primitiveToConservative(2, 0.3, 1.5, gamma);
expected = physicalFlux(state, gamma);

flux = s12_pp_global_lf_flux(state, state, gamma, 2);

verifyEqual(testCase, flux, expected, "RelTol", 64 * eps);
end

function testCflHardLimitRejectsWholeForwardEulerStep(testCase)
if ~requireProductionFunction(testCase, "s12_pp_validate_stage_cfl"); return; end
f = s12_pp_contract_fixture;
verifyError(testCase, @() s12_pp_validate_stage_cfl(0.51, 1, 1, ...
    f.cfl_hard_max), "S12:Positivity:CflHardLimit");
verifyEqual(testCase, s12_pp_validate_stage_cfl(0.5, 1, 1, ...
    f.cfl_hard_max), 0.5, "AbsTol", 32 * eps);
end

function testUniformAndLowPressureLegalStatesRemainAdmissible(testCase)
if ~requireProductionFunction(testCase, "s12_pp_global_lf_anchor"); return; end
f = s12_pp_contract_fixture;
gamma = f.gamma;
state = primitiveToConservative(1, 0, 2e-6, gamma);

result = s12_pp_global_lf_anchor(state, state, gamma, 1, 0.45, ...
    f.rho_floor, f.p_floor);

verifyEqual(testCase, result.left_partial + result.right_partial, ...
    2 * state, "AbsTol", 32 * eps);
verifyGreaterThanOrEqual(testCase, result.left_partial(1), f.rho_floor);
verifyGreaterThanOrEqual(testCase, result.right_partial(1), f.rho_floor);
verifyGreaterThanOrEqual(testCase, pressureOf(result.left_partial, gamma), f.p_floor);
verifyGreaterThanOrEqual(testCase, pressureOf(result.right_partial, gamma), f.p_floor);
verifyTrue(testCase, all(isfinite(result.flux)));
end

function addBenchmarkPath(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
fixtureRoot = fullfile(fileparts(mfilename("fullpath")), "fixtures");
addpath(benchmarkRoot, fixtureRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot, fixtureRoot));
end

function exists = requireProductionFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyTrue(testCase, exists, ...
    "Sprint 3 production contract function must exist: " + name);
end

function state = primitiveToConservative(rho, velocity, pressure, gamma)
state = [rho; rho .* velocity; ...
    pressure / (gamma - 1) + 0.5 * rho .* velocity.^2];
end

function flux = physicalFlux(state, gamma)
rho = state(1);
velocity = state(2) / rho;
pressure = (gamma - 1) * (state(3) - 0.5 * rho * velocity^2);
flux = [rho * velocity; rho * velocity^2 + pressure; ...
    velocity * (state(3) + pressure)];
end

function value = pressureOf(state, gamma)
rho = state(1);
velocity = state(2) / rho;
value = (gamma - 1) * (state(3) - 0.5 * rho * velocity^2);
end
