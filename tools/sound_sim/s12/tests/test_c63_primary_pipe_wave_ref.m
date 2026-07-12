function tests = test_c63_primary_pipe_wave_ref
%TEST_C63_PRIMARY_PIPE_WAVE_REF Verify a segmented Simscape Gas primary.
tests = functiontests(localfunctions);
end

function testPressurePulsePropagation(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "pipe_ref", ...
    "c63_primary_pipe_wave_ref.slx");
verifyEqual(testCase, exist(modelFile, "file"), 2, ...
    "The segmented primary-pipe reference model must exist.");

modelName = "c63_primary_pipe_wave_ref";
load_system(modelFile);
cleanup = onCleanup(@() close_system(modelName, 0));

pipes = find_system(modelName, "FollowLinks", "on", ...
    "LookUnderMasks", "all", "ReferenceBlock", ...
    "fl_lib/Gas/Elements/Pipe (G)");
verifyEqual(testCase, numel(pipes), 8);

output = sim(modelName);
time = output.S12_PipeTime;
inlet = output.S12_PipeInletPressure;
outlet = output.S12_PipeOutletPressure;
verifyTrue(testCase, all(isfinite([time; inlet; outlet])));

inletDelta = inlet - inlet(1);
outletDelta = outlet - outlet(1);
inletThreshold = 0.10 * max(abs(inletDelta));
outletThreshold = 0.10 * max(abs(outletDelta));
inletIndex = find(abs(inletDelta) >= inletThreshold, 1);
outletIndex = find(abs(outletDelta) >= outletThreshold, 1);
verifyNotEmpty(testCase, inletIndex);
verifyNotEmpty(testCase, outletIndex);

delay = time(outletIndex) - time(inletIndex);
verifyGreaterThan(testCase, delay, 4e-4);
verifyLessThan(testCase, delay, 1.6e-3);
verifyGreaterThan(testCase, max(abs(outletDelta)), 50);
verifyLessThan(testCase, max(abs(outletDelta)), ...
    1.25 * max(abs(inletDelta)));
clear cleanup
end
