function tests = test_c63_primary_pipe_grid_convergence
%TEST_C63_PRIMARY_PIPE_GRID_CONVERGENCE Compare 4, 8, and 16 cell pipes.
tests = functiontests(localfunctions);
end

function testThreeGridPropagationConvergence(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFolder = fullfile(root, "models", "pipe_ref");
cellCounts = [4, 8, 16];
modelNames = ["c63_primary_pipe_wave_ref_4cell", ...
    "c63_primary_pipe_wave_ref", "c63_primary_pipe_wave_ref_16cell"];
delays = zeros(size(cellCounts));
outletPeaks = zeros(size(cellCounts));

for index = 1:numel(cellCounts)
    modelFile = fullfile(modelFolder, modelNames(index) + ".slx");
    assertEqual(testCase, exist(modelFile, "file"), 2, ...
        "All three grid models must exist before convergence is claimed.");
    load_system(modelFile);
    cleanup = onCleanup(@() close_system(modelNames(index), 0));

    pipes = find_system(modelNames(index), "FollowLinks", "on", ...
        "LookUnderMasks", "all", "ReferenceBlock", ...
        "fl_lib/Gas/Elements/Pipe (G)");
    verifyEqual(testCase, numel(pipes), cellCounts(index));

    output = sim(modelNames(index));
    time = output.S12_PipeTime;
    inletDelta = output.S12_PipeInletPressure - ...
        output.S12_PipeInletPressure(1);
    outletDelta = output.S12_PipeOutletPressure - ...
        output.S12_PipeOutletPressure(1);
    verifyTrue(testCase, all(isfinite([time; inletDelta; outletDelta])));

    inletIndex = firstThresholdCrossing(inletDelta);
    outletIndex = firstThresholdCrossing(outletDelta);
    verifyNotEmpty(testCase, inletIndex);
    verifyNotEmpty(testCase, outletIndex);
    delays(index) = time(outletIndex) - time(inletIndex);
    outletPeaks(index) = max(abs(outletDelta));
    clear cleanup
end

gamma = 1000 / (1000 - 287);
expectedDelay = 0.48 / sqrt(gamma * 287 * 700);
fprintf("Grid cells: %s; delays ms: %s; outlet peaks Pa: %s\n", ...
    mat2str(cellCounts), mat2str(1e3 * delays, 6), ...
    mat2str(outletPeaks, 6));
verifyLessThan(testCase, abs(delays - expectedDelay) / expectedDelay, 0.15);
verifyLessThan(testCase, abs(delays(3) - delays(2)) / delays(3), 0.05);
verifyLessThan(testCase, ...
    abs(outletPeaks(3) - outletPeaks(2)) / outletPeaks(3), 0.15);
end

function index = firstThresholdCrossing(signal)
threshold = 0.10 * max(abs(signal));
index = find(abs(signal) >= threshold, 1);
end
