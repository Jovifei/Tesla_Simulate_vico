function tests = test_s12_benchmark_smooth_periodic
%TEST_S12_BENCHMARK_SMOOTH_PERIODIC Verify third-order time convergence.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
end

function testRichardsonSelfConvergenceIsThirdOrder(testCase)
config = struct( ...
    "cell_count", 16, ...
    "end_time", 0.01, ...
    "base_dt", 0.005, ...
    "dt_divisors", [1, 2, 4, 8]);

result = s12_benchmark_smooth_periodic(config, 0.45);

verifyEqual(testCase, result.dt_requested, ...
    config.base_dt ./ config.dt_divisors, "AbsTol", 0);
verifyFalse(testCase, any(result.cfl_clipped));
verifyEqual(testCase, result.boundary, "periodic");
verifyEqual(testCase, result.stage_dt_ratio, ones(1, 4), ...
    "RelTol", 1e-12, "AbsTol", 1e-14);
verifySize(testCase, result.observed_order, [1, 2]);
verifyGreaterThanOrEqual(testCase, result.observed_order(end), 2.7);
verifyLessThanOrEqual(testCase, result.observed_order(end), 3.3);
verifyLessThanOrEqual(testCase, ...
    max(result.scaled_conservation_error, [], "all"), 1e-11);
end
