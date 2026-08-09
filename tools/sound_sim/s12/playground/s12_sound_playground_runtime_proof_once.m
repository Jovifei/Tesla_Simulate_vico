% S12 Sound Playground Runtime Proof: the only manual MATLAB entry.
% Run only in one user-started, stable MATLAB Desktop session.

playground_root = string(fileparts(mfilename("fullpath")));
addpath(playground_root);
run_id = "runtime_proof_" + string(datetime("now", "Format", "yyyyMMdd_HHmmss_SSS"));
runtime_plan = s12_sound_playground_runtime_proof_plan(run_id);
runtime_preflight = s12_sound_playground_runtime_proof_preflight(runtime_plan);
s12_playground_runtime_proof_result = s12_sound_playground_runtime_proof( ...
    run_id, true, runtime_plan.runtime.case_output_root, runtime_preflight);
disp(s12_playground_runtime_proof_result);
