function tests = test_s12_pp_model_semantic_contract
%TEST_S12_PP_MODEL_SEMANTIC_CONTRACT Freeze approved PP chart interface semantics.
tests = functiontests(localfunctions);
end

function testApprovedChartAndDataContract(testCase)
[modelName, chart] = openPpModel(testCase);
verifyEqual(testCase, string(get_param(modelName, "FileName")), string(modelPath(testCase)));
verifyTrue(testCase, chart.SupportVariableSizing);
verifyTrue(testCase, chart.TreatDimensionOfLengthOneAsFixedSize);
verifyEqual(testCase, string(sha256Text(chart.Script)), ...
    "1b76cd6779c236fc42068326e26986e16f50c1825945ecafa2add15e81a09400");

data = chart.find("-isa", "Stateflow.Data");
[~, order] = sort(string({data.Name}));
data = data(order);
expectedNames = ["cfl", "diagnostics", "dtRequest", "dtUsed", "dx", ...
    "gamma", "pFloor", "residual", "rhoFloor", "state", "stateNext"];
expectedScopes = ["Input", "Output", "Input", "Output", "Input", ...
    "Input", "Input", "Output", "Input", "Input", "Output"];
expectedDynamic = [true, false, true, false, true, true, true, false, true, true, false].';
verifyEqual(testCase, string({data.Name}), expectedNames);
verifyEqual(testCase, string({data.Scope}), expectedScopes);
verifyEqual(testCase, string(arrayfun(@(item) item.Props.Array.Size, data, ...
    "UniformOutput", false)), repmat("-1", numel(expectedNames), 1));
verifyEqual(testCase, logical(arrayfun(@(item) item.Props.Array.IsDynamic, data)), ...
    expectedDynamic);
end

function testApprovedModelBinaryContract(testCase)
verifyEqual(testCase, string(sha256File(modelPath(testCase))), ...
    "dcd32d9c5f4d805afdea96cef9320d874924ad59736e874758aabc67e784d70d");
end

function [modelName, chart] = openPpModel(testCase)
modelName = "s12_euler_fvm_periodic_step_muscl_minmod_pp_ref";
root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(root, "benchmark");
addedBenchmark = ~any(string(strsplit(path, pathsep)) == benchmarkRoot);
if addedBenchmark
    addpath(benchmarkRoot);
    testCase.addTeardown(@() rmpath(benchmarkRoot));
end
load_system(modelPath(testCase));
testCase.addTeardown(@() close_system(modelName, 0));
set_param(modelName, "SimulationCommand", "update");
root = sfroot;
chart = root.find("-isa", "Stateflow.EMChart", ...
    "Path", modelName + "/PeriodicFVMStep");
verifyEqual(testCase, numel(chart), 1);
end

function path = modelPath(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
path = fullfile(root, "models", "fvm_ref", ...
    "s12_euler_fvm_periodic_step_muscl_minmod_pp_ref.slx");
verifyTrue(testCase, isfile(path));
end

function value = sha256Text(text)
value = sha256Bytes(uint8(char(text)));
end

function value = sha256File(path)
fileId = fopen(path, "r");
verify = onCleanup(@() fclose(fileId));
value = sha256Bytes(fread(fileId, "*uint8"));
end

function value = sha256Bytes(bytes)
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(bytes);
raw = typecast(digest.digest(), "uint8");
value = lower(reshape(dec2hex(raw, 2).', 1, []));
end
