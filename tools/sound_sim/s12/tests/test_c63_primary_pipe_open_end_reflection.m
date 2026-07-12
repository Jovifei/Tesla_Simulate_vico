function tests = test_c63_primary_pipe_open_end_reflection
%TEST_C63_PRIMARY_PIPE_OPEN_END_REFLECTION Verify pressure-release reflection.
tests = functiontests(localfunctions);
end

function testOpenEndReturnsNegativePressureWave(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "pipe_ref", ...
    "c63_primary_pipe_open_end_ref.slx");
assertEqual(testCase, exist(modelFile, "file"), 2, ...
    "The open-end reflection reference model must exist.");

modelName = "c63_primary_pipe_open_end_ref";
load_system(modelFile);
cleanup = onCleanup(@() close_system(modelName, 0));

pipes = find_system(modelName, "FollowLinks", "on", ...
    "LookUnderMasks", "all", "ReferenceBlock", ...
    "fl_lib/Gas/Elements/Pipe (G)");
verifyEqual(testCase, numel(pipes), 8);

output = sim(modelName);
time = output.S12_PipeTime;
probe = output.S12_PipeProbePressure;
probeDelta = probe - probe(1);
outlet = output.S12_PipeOutletPressure;
outletDelta = outlet - outlet(1);
verifyTrue(testCase, all(isfinite([time; probeDelta; outletDelta])));
verifyLessThan(testCase, max(abs(outletDelta)), 1);

gamma = 1000 / (1000 - 287);
soundSpeed = sqrt(gamma * 287 * 700);
pipeLength = 0.48;
probePosition = 0.06;
pulseStart = 5e-4;
pulseDuration = 5e-4;
incidentArrival = pulseStart + probePosition / soundSpeed;
reflectionArrival = pulseStart + ...
    (2 * pipeLength - probePosition) / soundSpeed;

incidentWindow = time >= incidentArrival - 1e-4 & ...
    time <= incidentArrival + pulseDuration + 2e-4;
reflectionWindow = time >= reflectionArrival - 2e-4 & ...
    time <= reflectionArrival + pulseDuration + 3e-4;
incidentPeak = max(probeDelta(incidentWindow));
reflectedPeak = min(probeDelta(reflectionWindow));
verifyGreaterThan(testCase, incidentPeak, 500);
verifyLessThan(testCase, reflectedPeak, -100);

reflectionRatio = abs(reflectedPeak) / incidentPeak;
verifyGreaterThan(testCase, reflectionRatio, 0.20);
verifyLessThan(testCase, reflectionRatio, 1.20);

reflectionThreshold = 0.10 * abs(reflectedPeak);
reflectionIndex = find(reflectionWindow & ...
    probeDelta <= -reflectionThreshold, 1);
verifyNotEmpty(testCase, reflectionIndex);
arrivalError = abs(time(reflectionIndex) - reflectionArrival);
verifyLessThan(testCase, arrivalError, 2.5e-4);

fprintf("Open-end incident/reflected Pa: %.3f / %.3f; ratio: %.4f; " + ...
    "reflection arrival ms: %.6f\n", incidentPeak, reflectedPeak, ...
    reflectionRatio, 1e3 * time(reflectionIndex));
clear cleanup
end
