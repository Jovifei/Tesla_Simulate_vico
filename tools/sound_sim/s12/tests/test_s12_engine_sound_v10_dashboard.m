function tests = test_s12_engine_sound_v10_dashboard
%TEST_S12_ENGINE_SOUND_V10_DASHBOARD Contract for qualification/interactive controls.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
source = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground_v10");
testCase.TestData.source = source;
addpath(source);
end

function teardownOnce(testCase)
if isfolder(testCase.TestData.source)
    rmpath(testCase.TestData.source);
end
end

function testI3SeparatesQualificationAndInteractiveState(testCase)
models = topModels();
requiredBlocks = [ ...
    "Interactive Mode", "Manual RPM", "Manual Load", "Manual Acceleration", ...
    "Manual Throttle", "Manual Speed", "Manual Overrun", "Manual Vehicle State", ...
    "Vehicle State Mode Select"];
for model = models
    load_system(fullfile(testCase.TestData.source, model + ".slx"));
    for name = requiredBlocks
        verifyNotEmpty(testCase, find_system(model, "SearchDepth", 1, "Name", name));
    end
end
end

function testI3HasBoundDashboardControls(testCase)
models = topModels();
requiredControls = [ ...
    "RPM Dashboard", "Load Dashboard", "Acceleration Dashboard", "Throttle Dashboard", ...
    "Order Balance Dashboard", "Transient Dashboard", "Backfire Dashboard", ...
    "Pipe Length Dashboard", "Area Dashboard", "Reflection Dashboard", ...
    "Damping Dashboard", "Gain Dashboard"];
for model = models
    load_system(fullfile(testCase.TestData.source, model + ".slx"));
    for name = requiredControls
        block = model + "/" + name;
        verifyNotEmpty(testCase, find_system(model, "SearchDepth", 1, "Name", name));
        verifyNotEmpty(testCase, get_param(block, "Binding"));
    end
end
end

function models = topModels()
models = [ ...
    "S12_I3_Turbo_v10", "S12_I4_Sport_v10", "S12_I5_Character_v10", ...
    "S12_I6_Smooth_v10", "S12_V6_Sport_v10", "S12_V8_Muscle_v10", ...
    "S12_V8_HighRev_v10"];
end
