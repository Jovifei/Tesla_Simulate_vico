function tests = test_s12_fanno_analytical_profile_contract
%TEST_S12_FANNO_ANALYTICAL_PROFILE_CONTRACT Specify Fanno cell-average data.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
fannoRoot = fullfile(s12Root, "validation", "fanno");
addpath(fannoRoot);
testCase.addTeardown(@() rmpath(fannoRoot));
end

function testProfileUsesFiniteConservativeCellAverages(testCase)
if ~requireFunction(testCase, "s12_fanno_analytical_profile"); return; end
definition = s12_fanno_case_definition("full");
profile = s12_fanno_analytical_profile(definition, 1, 8, 16);

verifyEqual(testCase, size(profile.cell_average_state), [3, 8]);
verifyEqual(testCase, numel(profile.cell_centers_m), 8);
verifyTrue(testCase, all(isfinite(profile.cell_average_state), "all"));
verifyGreaterThan(testCase, min(profile.cell_average_state(1, :)), 0);
verifyGreaterThan(testCase, profile.minimum_sonic_margin, 0);
verifyEqual(testCase, profile.cell_average_reference_id, ...
    "gauss_legendre_conservative.v1");
end

function testCellAverageConvergesUnderQuadratureRefinement(testCase)
if ~requireFunction(testCase, "s12_fanno_analytical_profile"); return; end
definition = s12_fanno_case_definition("full");
coarse = s12_fanno_analytical_profile(definition, 76, 16, 1);
fine = s12_fanno_analytical_profile(definition, 76, 16, 2);
reference = s12_fanno_analytical_profile(definition, 76, 16, 32);

verifyLessThan(testCase, norm(fine.cell_average_state - reference.cell_average_state, inf), ...
    norm(coarse.cell_average_state - reference.cell_average_state, inf));
end

function exists = requireFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyTrue(testCase, exists, ...
    "Sprint 4B production function must exist: " + name);
end
