function tests = test_s12_pp_ssprk3_contract
%TEST_S12_PP_SSPRK3_CONTRACT Specify PP stages, rejection, and retry semantics.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testThreeStagesShareDtAndRecordPositiveDiagnostics(testCase)
state = uniformState(32, 1.4);
[result, available] = runPeriodicPp(testCase, state, 1.4, 1 / 32, ...
    1e-4, 3, 0.45, Reconstruction="muscl_minmod_pp");
if ~available; return; end

required = ["stage_dt", "stage_diagnostics", "rho_floor", "p_floor", ...
    "invalid_stage_count", "rejected_step_count", "retry_count"];
verifyTrue(testCase, all(isfield(result.qualification, required)));
verifyEqual(testCase, result.reconstruction, "muscl_minmod_pp");
verifyEqual(testCase, result.qualification.stage_dt(:, 1), ...
    result.qualification.stage_dt(:, 2), "AbsTol", 0, "RelTol", 0);
verifyEqual(testCase, result.qualification.stage_dt(:, 1), ...
    result.qualification.stage_dt(:, 3), "AbsTol", 0, "RelTol", 0);
verifyEqual(testCase, result.qualification.invalid_stage_count, 0);
end

function testHardCflViolationDiscardsWholeStepAndRestartsFromUn(testCase)
state = uniformState(32, 1.4);
[retried, available] = runPeriodicPp(testCase, state, 1.4, 1 / 32, ...
    2e-2, 1, 0.6, Reconstruction="muscl_minmod_pp");
if ~available; return; end
[direct, available] = runPeriodicPp(testCase, state, 1.4, 1 / 32, ...
    0.45 * (1 / 32) / sqrt(1.4), 1, 0.45, ...
    Reconstruction="muscl_minmod_pp");
if ~available; return; end

verifyGreaterThanOrEqual(testCase, retried.qualification.rejected_step_count, 1);
verifyGreaterThanOrEqual(testCase, retried.qualification.retry_count, 1);
verifyEqual(testCase, retried.final_state, direct.final_state, ...
    "AbsTol", 1e-12, "RelTol", 1e-12);
end

function testTransmissiveDoubleRarefactionRemainsFiniteWithoutFallback(testCase)
gamma = 1.4;
cellCount = 400;
x = ((1:cellCount) - 0.5) / cellCount;
left = x < 0.5;
state = primitiveToConservative(ones(size(x)), 2 * (2 * left - 1), ...
    0.1 * ones(size(x)), gamma);
[result, available] = runTransmissivePp(testCase, state, gamma, 1 / cellCount, ...
    0.1, 0.45, 20000, Reconstruction="muscl_minmod_pp");
if ~available; return; end

verifyTrue(testCase, all(isfinite(result.final_state), "all"));
verifyEqual(testCase, result.qualification.clipping_count, 0);
verifyEqual(testCase, result.qualification.flux_fallback_count, 0);
verifyEqual(testCase, result.qualification.invalid_stage_count, 0);
end

function state = uniformState(cellCount, gamma)
state = primitiveToConservative(ones(1, cellCount), zeros(1, cellCount), ...
    ones(1, cellCount), gamma);
end

function state = primitiveToConservative(rho, velocity, pressure, gamma)
state = [rho; rho .* velocity; ...
    pressure / (gamma - 1) + 0.5 * rho .* velocity.^2];
end

function [result, available] = runPeriodicPp(testCase, varargin)
available = true;
try
    result = s12_run_periodic_ssprk3(varargin{:});
catch exception
    verifyFail(testCase, "PP periodic runner contract unavailable: " + ...
        string(exception.identifier));
    result = struct;
    available = false;
end
end

function [result, available] = runTransmissivePp(testCase, varargin)
available = true;
try
    result = s12_run_transmissive_ssprk3(varargin{:});
catch exception
    verifyFail(testCase, "PP transmissive runner contract unavailable: " + ...
        string(exception.identifier));
    result = struct;
    available = false;
end
end
