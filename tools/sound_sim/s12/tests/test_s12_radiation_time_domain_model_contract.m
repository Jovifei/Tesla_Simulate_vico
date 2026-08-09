function tests = test_s12_radiation_time_domain_model_contract
%TEST_S12_RADIATION_TIME_DOMAIN_MODEL_CONTRACT Reserve controlled 4D-B model.
tests = functiontests(localfunctions);
end

function testDedicatedModelExists(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
path = fullfile(s12Root, "models", "fvm_ref", ...
    "s12_euler_fvm_radiation_boundary_ref.slx");
verifyTrue(testCase, isfile(path), ...
    "Sprint 4D-B requires an independent controlled radiation-boundary model.");
end
