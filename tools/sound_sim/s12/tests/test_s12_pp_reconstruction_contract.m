function tests = test_s12_pp_reconstruction_contract
%TEST_S12_PP_RECONSTRUCTION_CONTRACT Specify primitive slope-scaling behavior.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
addBenchmarkPath(testCase);
end

function testLegalSlopesPreserveMinmodReconstruction(testCase)
if ~requireProductionFunction(testCase, "s12_pp_reconstruct_primitive"); return; end
f = s12_pp_contract_fixture;
primitive = [2; 0.3; 3];
slopes = [0.4; -0.2; 0.6];

result = s12_pp_reconstruct_primitive(primitive, slopes, ...
    f.rho_floor, f.p_floor);

verifyEqual(testCase, result.theta, 1, "AbsTol", 32 * eps);
verifyEqual(testCase, result.left, primitive - 0.5 * slopes, ...
    "AbsTol", 32 * eps);
verifyEqual(testCase, result.right, primitive + 0.5 * slopes, ...
    "AbsTol", 32 * eps);
verifyEqual(testCase, 0.5 * (result.left + result.right), primitive, ...
    "AbsTol", 32 * eps);
end

function testDensityAndPressureUseOneSharedTheta(testCase)
if ~requireProductionFunction(testCase, "s12_pp_reconstruct_primitive"); return; end
primitive = [1; 0.2; 1];
slopes = [1.8; 0.8; 1.6];

result = s12_pp_reconstruct_primitive(primitive, slopes, 0.55, 0.7);

expectedTheta = min([1, 2 * (1 - 0.55) / 1.8, ...
    2 * (1 - 0.7) / 1.6]);
verifyEqual(testCase, result.theta, expectedTheta, "AbsTol", 32 * eps);
verifyGreaterThanOrEqual(testCase, min(result.left(1), result.right(1)), 0.55);
verifyGreaterThanOrEqual(testCase, min(result.left(3), result.right(3)), 0.7);
verifyEqual(testCase, result.left(2), ...
    primitive(2) - 0.5 * expectedTheta * slopes(2), "AbsTol", 32 * eps);
verifyEqual(testCase, result.right(2), ...
    primitive(2) + 0.5 * expectedTheta * slopes(2), "AbsTol", 32 * eps);
end

function testLeftRightAndBothSidesAreBounded(testCase)
if ~requireProductionFunction(testCase, "s12_pp_reconstruct_primitive"); return; end
cases = [ ...
    1, 0, 1,  1.6, 0, 0; ...
    1, 0, 1, -1.6, 0, 0; ...
    1, 0, 1,  1.6, 0, 1.6].';
for caseIndex = 1:size(cases, 2)
    primitive = cases(1:3, caseIndex);
    slopes = cases(4:6, caseIndex);
    result = s12_pp_reconstruct_primitive(primitive, slopes, 0.4, 0.4);
    verifyGreaterThanOrEqual(testCase, min(result.left([1, 3])), 0.4);
    verifyGreaterThanOrEqual(testCase, min(result.right([1, 3])), 0.4);
    verifyGreaterThanOrEqual(testCase, result.theta, 0);
    verifyLessThanOrEqual(testCase, result.theta, 1);
    verifyTrue(testCase, isfinite(result.theta));
end
end

function testPeriodicAndTransmissiveStencilsAreExplicit(testCase)
if ~requireProductionFunction(testCase, "s12_pp_minmod_primitive_slopes"); return; end
primitive = [1, 2, 4, 8; 0, 1, 1, 0; 1, 2, 4, 8];

periodic = s12_pp_minmod_primitive_slopes(primitive, Boundary="periodic");
transmissive = s12_pp_minmod_primitive_slopes(primitive, ...
    Boundary="transmissive");

verifyEqual(testCase, periodic, [0, 1, 2, 0; 0, 0, 0, 0; 0, 1, 2, 0]);
verifyEqual(testCase, transmissive(:, [1, end]), zeros(3, 2));
end

function testIllegalCellCenterFailsInsteadOfBeingScaled(testCase)
if ~requireProductionFunction(testCase, "s12_pp_reconstruct_primitive"); return; end
verifyError(testCase, @() s12_pp_reconstruct_primitive( ...
    [0.5; 0; 1], [0; 0; 0], 0.6, 0.1), ...
    "S12:Positivity:InvalidCellAverage");
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
