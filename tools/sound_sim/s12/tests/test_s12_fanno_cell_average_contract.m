function tests = test_s12_fanno_cell_average_contract
%TEST_S12_FANNO_CELL_AVERAGE_CONTRACT Specify conservative cell averages.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
addFannoPath(testCase);
end

function testConstantAndLinearProfilesAreAveragedExactly(testCase)
if ~requireFunction(testCase, "s12_fanno_cell_average"); return; end
edges = [0, 0.25, 0.75, 1.0];
constant = @(x) [2 + zeros(size(x)); 3 + zeros(size(x)); 5 + zeros(size(x))];
linear = @(x) [1 + 2 * x; 4 - x; 7 + 3 * x];
constantAverage = s12_fanno_cell_average(constant, edges, 4);
linearAverage = s12_fanno_cell_average(linear, edges, 4);
centers = 0.5 * (edges(1:end-1) + edges(2:end));
verifyEqual(testCase, constantAverage, repmat([2; 3; 5], 1, 3), ...
    "AbsTol", 32 * eps);
verifyEqual(testCase, linearAverage, [1 + 2 * centers; 4 - centers; 7 + 3 * centers], ...
    "AbsTol", 64 * eps);
end

function testSmoothProfileConvergesUnderQuadratureRefinement(testCase)
if ~requireFunction(testCase, "s12_fanno_cell_average"); return; end
edges = linspace(0, 1, 9);
profile = @(x) [1 + 0.2 * sin(2 * pi * x); ...
    2 + exp(x); 4 + 0.1 * cos(3 * pi * x)];
coarse = s12_fanno_cell_average(profile, edges, 4);
fine = s12_fanno_cell_average(profile, edges, 16);
reference = s12_fanno_cell_average(profile, edges, 64);
verifyLessThan(testCase, norm(fine - reference, inf), norm(coarse - reference, inf));
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
