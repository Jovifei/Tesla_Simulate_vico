function result = s12_sound_playground_prepare_model_workspace_for_compile(model)
%S12_SOUND_PLAYGROUND_PREPARE_MODEL_WORKSPACE_FOR_COMPILE Publish fixed idle frames.

model = s12_sound_playground_require_text_scalar(model, "compile model");
if ~bdIsLoaded(char(model))
    error("S12:Playground:CompileModelNotLoaded", "Compile model is not loaded: %s.", model);
end

scenario = s12_sound_playground_scenario_source("idle");
workspace = get_param(char(model), "ModelWorkspace");
assignin(workspace, "s12_playground_scenario_frames", scenario.workspace_signal);
published = evalin(workspace, "s12_playground_scenario_frames");

expectedSize = [18, 1, scenario.frame_count];
if ~isequal(published.signals.dimensions, [18, 1]) || ...
        ~isequal(size(published.signals.values), expectedSize) || ...
        any(~isfinite(published.signals.values), "all")
    error("S12:Playground:CompileScenario", "Compile scenario model-workspace contract failed.");
end

result = struct("status", "COMPILE_SCENARIO_PREPARED", "scenario", scenario.name, ...
    "frame_count", scenario.frame_count, "scenario_sha256", scenario.scenario_sha256);
end
