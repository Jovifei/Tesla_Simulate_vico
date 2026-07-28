function root = s12_engine_sound_runtime_root()
%S12_ENGINE_SOUND_RUNTIME_ROOT Return the non-source v1.0 runtime artifact root.

workspace = mfilename("fullpath");
for index = 1:6
    workspace = fileparts(workspace);
end
root = fullfile(workspace, "tasks", "reports", "runtime", "s12-engine-sound-v10");
end
