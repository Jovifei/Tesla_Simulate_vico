function tests = test_nasa_mixture_properties
%TEST_NASA_MIXTURE_PROPERTIES Verify S12 semiperfect-gas tables.
tests = functiontests(localfunctions);
end

function testFreshAndBurnedMixtures(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
propertyPath = fullfile(root, "library", "properties");
addpath(propertyPath);
cleanup = onCleanup(@() rmpath(propertyPath));

tables = s12_nasa_mixture_tables();

verifyEqual(testCase, tables.temperature_k([1 end]), [300 3500]);
verifyGreaterThan(testCase, min(tables.fresh.cp_j_kgk), 950);
verifyLessThan(testCase, max(tables.fresh.cp_j_kgk), 1400);
verifyGreaterThan(testCase, min(tables.burned.cp_j_kgk), 1000);
verifyLessThan(testCase, max(tables.burned.cp_j_kgk), 1700);

verifyEqual(testCase, tables.fresh.cv_j_kgk, ...
    tables.fresh.cp_j_kgk - tables.fresh.gas_constant_j_kgk, ...
    "AbsTol", 1e-10);
verifyEqual(testCase, tables.burned.cv_j_kgk, ...
    tables.burned.cp_j_kgk - tables.burned.gas_constant_j_kgk, ...
    "AbsTol", 1e-10);
verifyEqual(testCase, tables.fresh.gamma, ...
    tables.fresh.cp_j_kgk ./ tables.fresh.cv_j_kgk, ...
    "AbsTol", 1e-12);
verifyEqual(testCase, tables.burned.gamma, ...
    tables.burned.cp_j_kgk ./ tables.burned.cv_j_kgk, ...
    "AbsTol", 1e-12);

verifyGreaterThan(testCase, tables.fresh.gamma(1), ...
    tables.fresh.gamma(end));
verifyGreaterThan(testCase, tables.burned.gamma(1), ...
    tables.burned.gamma(end));
verifyGreaterThan(testCase, tables.burned.gas_constant_j_kgk, 285);
verifyLessThan(testCase, tables.burned.gas_constant_j_kgk, 295);
clear cleanup
end
