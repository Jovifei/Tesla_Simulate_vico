function tests = test_s12_transient_wave_model_contract
%TEST_S12_TRANSIENT_WAVE_MODEL_CONTRACT Specify independent model paths.
tests = functiontests(localfunctions);
end

function testControlledModelsExistAndAreSeparateFromFanno(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
expected = [ ...
    fullfile(s12Root, "models", "fvm_ref", "s12_euler_fvm_transient_wave_ref.slx"); ...
    fullfile(s12Root, "models", "pipe_ref", "s12_transient_pipe_g_closed_ref.slx"); ...
    fullfile(s12Root, "models", "pipe_ref", "s12_transient_pipe_g_open_ref.slx")];
for path = expected.'
    verifyEqual(testCase, exist(path, "file"), 2, ...
        "Sprint 4C controlled model must exist: " + path);
end
verifyNotEqual(testCase, expected(1), fullfile(s12Root, "models", "fvm_ref", ...
    "s12_euler_fvm_fanno_ref.slx"));
end
