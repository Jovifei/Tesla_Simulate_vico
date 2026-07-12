function tests = test_c63_cylinder_ref
%TEST_C63_CYLINDER_REF Verify C63 crank geometry and adiabatic reference.
tests = functiontests(localfunctions);
end

function testTdcBdcGeometryAndPressure(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "cylinder_ref", ...
    "c63_cylinder_adiabatic_ref.slx");
verifyEqual(testCase, exist(modelFile, "file"), 2, ...
    "The S12 reference model must exist before it can be verified.");

modelName = "c63_cylinder_adiabatic_ref";
load_system(modelFile);
cleanup = onCleanup(@() close_system(modelName, 0));

bore = 0.1022;
stroke = 0.0946;
compressionRatio = 11.3;
sweptVolume = pi * bore^2 * stroke / 4;
clearanceVolume = sweptVolume / (compressionRatio - 1);

tdc = runAtAngle(modelName, 0);
bdc = runAtAngle(modelName, 180);

verifyEqual(testCase, tdc.volume, clearanceVolume, "RelTol", 1e-8);
verifyEqual(testCase, bdc.volume, clearanceVolume + sweptVolume, ...
    "RelTol", 1e-8);
verifyEqual(testCase, tdc.pressure / bdc.pressure, ...
    compressionRatio^1.35, "RelTol", 1e-8);
clear cleanup
end

function result = runAtAngle(modelName, crankAngleDeg)
input = Simulink.SimulationInput(modelName);
input = input.setBlockParameter(modelName + "/CrankAngleDeg", ...
    "Value", string(crankAngleDeg));
input = input.setModelParameter("StopTime", "0");
output = sim(input);
result.volume = output.S12_CylinderVolume(end);
result.pressure = output.S12_CylinderPressure(end);
end
