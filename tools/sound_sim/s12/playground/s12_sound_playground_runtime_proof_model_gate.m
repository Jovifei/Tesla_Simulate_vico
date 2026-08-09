function result = s12_sound_playground_runtime_proof_model_gate(artifact, plan, gate)
%S12_SOUND_PLAYGROUND_RUNTIME_PROOF_MODEL_GATE Run one isolated model gate.

gate = string(gate);
model = string(artifact.model_name);
lease = s12_sound_playground_open_owned_model(model, artifact.model_path, ...
    fullfile(plan.runtime.transaction_root, gate + "_cleanup_failure.json"));
if ~lease.owned
    error("S12:Playground:CandidateCallerOwned", "Runtime Proof refuses a caller-owned candidate model.");
end
cleanup = onCleanup(@() s12_sound_playground_close_owned_model_without_save(lease));
result = struct("gate", gate, "model_path", string(artifact.model_path), ...
    "model_sha256_before", s12_sound_playground_sha256(artifact.model_path), "status", "RUNNING");

switch gate
    case "cold_reload"
        result.status = "COLD_RELOAD_PASSED";
    case "update_diagram"
        result.compile_scenario = s12_sound_playground_prepare_model_workspace_for_compile(model);
        set_param(model, "SimulationCommand", "update");
        result.status = "UPDATE_DIAGRAM_PASSED";
    case "active_compile_dimension_readback"
        result.compile_scenario = s12_sound_playground_prepare_model_workspace_for_compile(model);
        compiled = s12_sound_playground_compile_and_inspect_dimensions( ...
            model, plan.signal_contract, ...
            fullfile(plan.runtime.transaction_root, "compile_cleanup_error.json"), false);
        result.dimensions = compiled.dimensions;
        result.compile_gates = compiled;
        result.status = "ACTIVE_COMPILE_DIMENSION_READBACK_PASSED";
    otherwise
        error("S12:Playground:RuntimeProofGate", "Unknown Runtime Proof model gate: %s.", gate);
end

closeResult = s12_sound_playground_close_owned_model_without_save(lease);
clear cleanup
if ~strcmp(s12_sound_playground_require_text_scalar(closeResult.status, "model close status"), "CLOSED") || bdIsLoaded(char(model))
    error("S12:Playground:ModelClose", "Runtime Proof model gate did not close its owned model.");
end
result.model_sha256_after = s12_sound_playground_sha256(artifact.model_path);
s12_sound_playground_require_sha256_equal(result.model_sha256_before, result.model_sha256_after, ...
    "Runtime Proof model changed during " + string(gate));
end
