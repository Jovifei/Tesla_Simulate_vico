function tests = test_s12_sound_playground_stateflow_root_access
%TEST_S12_SOUND_PLAYGROUND_STATEFLOW_ROOT_ACCESS Guard Stateflow root lookup syntax.

tests = functiontests(localfunctions);
end

function testBuilderAndInterfaceUseInvokedStateflowRoot(testCase)
playground = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground");
files = ["s12_sound_playground_build_temp.m", ...
    "s12_sound_playground_configure_function_interfaces.m"];
for name = files
    source = string(fileread(fullfile(playground, name)));
    verifyFalse(testCase, contains(source, "sfroot.find("));
    verifyGreaterThanOrEqual(testCase, count(source, "sfroot().find("), 1);
end

root = sfroot();
verifyClass(testCase, root, "Simulink.Root");
charts = root.find("-isa", "Stateflow.EMChart"); %#ok<NASGU>
end

function testInputVariabilityIsInheritedAndOutputsRemainFixed(testCase)
playground = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground");
originalPath = path;
pathLease = onCleanup(@() path(originalPath));
addpath(playground);

model = "S12_Stateflow_Dynamic_Policy_Test";
if bdIsLoaded(model)
    close_system(model, 0);
end
modelLease = onCleanup(@() closeIfLoaded(model));
new_system(model);
block = model + "/Engine";
add_block("simulink/User-Defined Functions/MATLAB Function", block);
chart = sfroot().find("-isa", "Stateflow.EMChart", "Path", block);
verifyNumElements(testCase, chart, 1);
chart.Script = s12_sound_playground_function_scripts().engine;

s12_sound_playground_configure_function_interfaces(block, "EngineExcitation");

packed = chart.Inputs(strcmp(string({chart.Inputs.Name}), "packed"));
verifyNumElements(testCase, packed, 1);
verifyTrue(testCase, logical(packed.Props.Array.IsDynamic), ...
    "MATLAB Function inputs inherit variability from their connected Simulink signals.");
verifyTrue(testCase, all(~arrayfun(@(item) logical(item.Props.Array.IsDynamic), chart.Outputs)), ...
    "MATLAB Function outputs must remain explicitly fixed-size.");
end

function closeIfLoaded(model)
if bdIsLoaded(model)
    close_system(model, 0);
end
end
