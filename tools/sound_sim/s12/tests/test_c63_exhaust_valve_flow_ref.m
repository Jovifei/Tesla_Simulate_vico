function tests = test_c63_exhaust_valve_flow_ref
%TEST_C63_EXHAUST_VALVE_FLOW_REF Verify compressible exhaust-valve flow.
tests = functiontests(localfunctions);
end

function testChokedAndSubcriticalBranches(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "cylinder_ref", ...
    "c63_exhaust_valve_flow_ref.slx");
verifyEqual(testCase, exist(modelFile, "file"), 2, ...
    "The exhaust-valve flow reference model must exist.");

modelName = "c63_exhaust_valve_flow_ref";
load_system(modelFile);
cleanup = onCleanup(@() close_system(modelName, 0));

high = runAtPressure(modelName, 529000);
low = runAtPressure(modelName, 150000);

gamma = 1.31;
gasConstant = 287;
temperature = 1518;
downstreamPressure = 101325;
criticalRatio = (2 / (gamma + 1))^(gamma / (gamma - 1));

verifyTrue(testCase, logical(high.choked));
verifyLessThan(testCase, high.pressureRatio, criticalRatio);
expectedHigh = high.area * high.upstreamPressure / ...
    sqrt(gasConstant * temperature) * sqrt(gamma) * ...
    (2 / (gamma + 1))^((gamma + 1) / (2 * (gamma - 1)));
verifyEqual(testCase, high.massFlow, expectedHigh, "RelTol", 1e-8);

verifyFalse(testCase, logical(low.choked));
pressureRatio = downstreamPressure / low.upstreamPressure;
expectedLow = low.area * low.upstreamPressure / ...
    sqrt(gasConstant * temperature) * sqrt(2 * gamma / (gamma - 1) * ...
    (pressureRatio^(2 / gamma) - ...
    pressureRatio^((gamma + 1) / gamma)));
verifyEqual(testCase, low.massFlow, expectedLow, "RelTol", 1e-8);
verifyGreaterThan(testCase, high.massFlow, low.massFlow);
clear cleanup
end

function result = runAtPressure(modelName, pressurePa)
input = Simulink.SimulationInput(modelName);
input = input.setBlockParameter(modelName + "/UpstreamPressure", ...
    "Value", string(pressurePa));
input = input.setModelParameter("StopTime", "0");
output = sim(input);
result.area = output.S12_ValveEffectiveArea(end);
result.massFlow = output.S12_ValveMassFlow(end);
result.pressureRatio = output.S12_ValvePressureRatio(end);
result.choked = output.S12_ValveChoked(end);
result.upstreamPressure = pressurePa;
end
