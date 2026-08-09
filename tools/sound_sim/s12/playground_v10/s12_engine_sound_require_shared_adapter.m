function s12_engine_sound_require_shared_adapter()
%S12_ENGINE_SOUND_REQUIRE_SHARED_ADAPTER Expose the frozen v0.9 PTR adapter.

shared = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground");
if ~isfile(fullfile(shared, "s12_sound_playground_ptr_tuning_step.m"))
    error("S12:EngineSoundV10:SharedAdapter", "The shared v0.9 PTR adapter is unavailable.");
end
if isempty(which("s12_sound_playground_ptr_tuning_step"))
    addpath(shared);
end
end
