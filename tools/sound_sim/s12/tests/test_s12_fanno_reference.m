function tests = test_s12_fanno_reference
%TEST_S12_FANNO_REFERENCE Verify the analytical subsonic Fanno reference.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
fannoRoot = fullfile(s12Root, "validation", "fanno");
addpath(fannoRoot);
testCase.addTeardown(@() rmpath(fannoRoot));
end

function testZeroLengthPreservesInletState(testCase)
input = nominalInput();
input.length = 0;
result = s12_fanno_reference(input);

verifyEqual(testCase, result.outlet.mach, input.mach, "AbsTol", 1e-14);
verifyEqual(testCase, result.outlet.static_pressure, input.static_pressure, "AbsTol", 1e-8);
verifyEqual(testCase, result.outlet.static_temperature, input.static_temperature, "AbsTol", 1e-12);
verifyEqual(testCase, result.fanno.residual, 0, "AbsTol", 1e-14);
verifyEqual(testCase, result.status, "ok");
end

function testSubsonicFrictionAcceleratesFlowAndReducesStaticState(testCase)
result = s12_fanno_reference(nominalInput());

verifyGreaterThan(testCase, result.outlet.mach, result.inlet.mach);
verifyLessThan(testCase, result.outlet.static_pressure, result.inlet.static_pressure);
verifyLessThan(testCase, result.outlet.static_temperature, result.inlet.static_temperature);
verifyGreaterThan(testCase, result.outlet.mach, 0);
verifyLessThan(testCase, result.outlet.mach, 1);
end

function testIndependentConservationIdentitiesHold(testCase)
input = nominalInput();
result = s12_fanno_reference(input);
inletMassFlow = input.static_pressure * input.mach * input.area * ...
    sqrt(input.gamma / (input.gas_constant * input.static_temperature));

verifyEqual(testCase, result.mass_flow, inletMassFlow, "RelTol", 2e-13);
verifyEqual(testCase, result.outlet.mass_flow, result.inlet.mass_flow, "RelTol", 2e-12);
verifyEqual(testCase, result.outlet.total_temperature, ...
    result.inlet.total_temperature, "RelTol", 2e-13);
verifyLessThanOrEqual(testCase, abs(result.fanno.residual), 1e-11);
end

function testTotalPressureFallsAcrossFriction(testCase)
result = s12_fanno_reference(nominalInput());

verifyLessThan(testCase, result.outlet.total_pressure, result.inlet.total_pressure);
verifyGreaterThan(testCase, result.inlet.total_pressure, result.inlet.static_pressure);
verifyGreaterThan(testCase, result.outlet.total_pressure, result.outlet.static_pressure);
end

function testDarcyLengthBudgetIsAccountedExactly(testCase)
input = nominalInput();
result = s12_fanno_reference(input);
usedParameter = input.darcy_friction_factor * input.length / input.diameter;

verifyEqual(testCase, result.fanno.inlet - result.fanno.outlet, ...
    usedParameter, "AbsTol", 1e-11);
verifyEqual(testCase, result.remaining_length_to_choke, ...
    input.diameter * result.fanno.outlet / input.darcy_friction_factor, ...
    "RelTol", 2e-12);
verifyEqual(testCase, result.friction_convention, "darcy_f_D_L_over_D");
end

function testZeroFrictionHasInfiniteChokingLength(testCase)
input = nominalInput();
input.darcy_friction_factor = 0;
result = s12_fanno_reference(input);

verifyEqual(testCase, result.outlet.mach, input.mach, "AbsTol", 1e-14);
verifyEqual(testCase, result.remaining_length_to_choke, Inf);
end

function testRejectsInvalidInputs(testCase)
base = nominalInput();
invalid = {
    withField(base, "static_pressure", 0)
    withField(base, "static_temperature", -1)
    withField(base, "mach", 1)
    withField(base, "gamma", 1)
    withField(base, "gas_constant", NaN)
    withField(base, "area", 0)
    withField(base, "diameter", -1)
    withField(base, "length", -1)
    withField(base, "darcy_friction_factor", -0.01)
    withField(base, "static_pressure", [100e3, 200e3])
    };

for index = 1:numel(invalid)
    verifyError(testCase, @() s12_fanno_reference(invalid{index}), ...
        "S12:Fanno:InvalidInput");
end
end

function testRejectsLengthAtOrBeyondChoking(testCase)
input = nominalInput();
unit = s12_fanno_reference(withField(input, "length", 0));
chokingLength = input.diameter * unit.fanno.inlet / input.darcy_friction_factor;

verifyError(testCase, @() s12_fanno_reference( ...
    withField(input, "length", chokingLength)), "S12:Fanno:ChokedLength");
verifyError(testCase, @() s12_fanno_reference( ...
    withField(input, "length", 1.01 * chokingLength)), "S12:Fanno:ChokedLength");
end

function input = nominalInput()
input = struct( ...
    "static_pressure", 200e3, ...
    "static_temperature", 350, ...
    "mach", 0.30, ...
    "gamma", 1.4, ...
    "gas_constant", 287.05, ...
    "area", 0.01, ...
    "diameter", 0.10, ...
    "length", 1.0, ...
    "darcy_friction_factor", 0.02);
end

function output = withField(input, name, value)
output = input;
output.(name) = value;
end
