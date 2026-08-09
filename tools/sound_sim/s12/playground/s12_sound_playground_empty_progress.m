function progress = s12_sound_playground_empty_progress()
%S12_SOUND_PLAYGROUND_EMPTY_PROGRESS Return the only permitted stage-record schema.

template = struct("run_id", "", "stage", "", "status", "", ...
    "started_at", "", "ended_at", "", "artifact", struct(), ...
    "error_identifier", "", "error_message", "", "error_stack", "");
progress = repmat(template, 0, 1);
end
