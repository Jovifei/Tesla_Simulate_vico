function tests = test_c63_exhaust_valve_flow_ref
%TEST_C63_EXHAUST_VALVE_FLOW_REF Verify compressible exhaust-valve flow.
tests = functiontests(localfunctions);
end

function testBidirectionalFlowAndLiftDependentCd(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "cylinder_ref", ...
    "c63_exhaust_valve_flow_ref.slx");
verifyEqual(testCase, exist(modelFile, "file"), 2, ...
    "The exhaust-valve flow reference model must exist.");

modelName = "c63_exhaust_valve_flow_ref";
load_system(modelFile);
cleanup = onCleanup(@() close_system(modelName, 0));

midAngle = 130 + 220 / 2;
quarterAngle = 130 + 220 / 4;
high = runAtBoundary(modelName, 529000, 101325, midAngle);
low = runAtBoundary(modelName, 150000, 101325, midAngle);
reverse = runAtBoundary(modelName, 101325, 200000, midAngle);
quarter = runAtBoundary(modelName, 529000, 101325, quarterAngle);

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
verifyLessThan(testCase, reverse.massFlow, 0);
verifyTrue(testCase, logical(reverse.choked));
expectedReverse = expectedMassFlow(reverse.area, 200000, 330, ...
    1.4, 287, 101325 / 200000, true);
verifyEqual(testCase, reverse.massFlow, -expectedReverse, "RelTol", 1e-8);

verifyGreaterThan(testCase, high.cd, quarter.cd);
verifyGreaterThan(testCase, quarter.cd, 0);
verifyLessThanOrEqual(testCase, high.cd, 1);
verifyLessThan(testCase, high.enthalpyFlow, 0);
verifyGreaterThan(testCase, reverse.enthalpyFlow, 0);
verifyEqual(testCase, high.enthalpyFlow, ...
    -high.massFlow * (gamma * gasConstant / (gamma - 1)) * temperature, ...
    "RelTol", 1e-8);
verifyEqual(testCase, reverse.enthalpyFlow, ...
    -reverse.massFlow * (1.4 * 287 / (1.4 - 1)) * 330, ...
    "RelTol", 1e-8);
clear cleanup
end

function result = runAtBoundary(modelName, upstreamPa, downstreamPa, angleDeg)
input = Simulink.SimulationInput(modelName);
input = input.setBlockParameter(modelName + "/UpstreamPressure", ...
    "Value", string(upstreamPa));
input = input.setBlockParameter(modelName + "/DownstreamPressure", ...
    "Value", string(downstreamPa));
input = input.setBlockParameter(modelName + "/CrankAngleDeg", ...
    "Value", string(angleDeg));
input = input.setModelParameter("StopTime", "0");
output = sim(input);
result.area = output.S12_ValveEffectiveArea(end);
result.massFlow = output.S12_ValveMassFlow(end);
result.pressureRatio = output.S12_ValvePressureRatio(end);
result.choked = output.S12_ValveChoked(end);
result.cd = output.S12_ValveCd(end);
result.enthalpyFlow = output.S12_ValveEnthalpyFlow(end);
result.upstreamPressure = upstreamPa;
end

function massFlow = expectedMassFlow(area, pressure, temperature, gamma, ...
    gasConstant, pressureRatio, choked)
base = area * pressure / sqrt(gasConstant * temperature);
if choked
    massFlow = base * sqrt(gamma) * ...
        (2 / (gamma + 1))^((gamma + 1) / (2 * (gamma - 1)));
else
    massFlow = base * sqrt(2 * gamma / (gamma - 1) * ...
        (pressureRatio^(2 / gamma) - ...
        pressureRatio^((gamma + 1) / gamma)));
end
end
