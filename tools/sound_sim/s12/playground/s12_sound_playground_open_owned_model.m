function lease = s12_sound_playground_open_owned_model(modelName, modelPath, cleanupErrorPath)
%S12_SOUND_PLAYGROUND_OPEN_OWNED_MODEL Load only when the caller has not.

lease = struct("model_name", string(modelName), "owned", false, "cleanup_error_path", string(cleanupErrorPath));
if ~bdIsLoaded(char(lease.model_name))
    load_system(modelPath);
    lease.owned = true;
end
if ~bdIsLoaded(char(lease.model_name))
    error("S12:Playground:ModelLoad", "Model %s was not loaded.", lease.model_name);
end
end
