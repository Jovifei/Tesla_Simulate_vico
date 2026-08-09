function record = s12_sound_playground_stage_record(runId, stage, status, artifact, cause)
%S12_SOUND_PLAYGROUND_STAGE_RECORD Create one fixed-schema Runtime Proof stage record.

if nargin < 4 || isempty(artifact)
    artifact = struct();
end
if nargin < 5
    cause = [];
end
record = s12_sound_playground_empty_progress();
record(1) = struct( ...
    "run_id", s12_sound_playground_require_text_scalar(runId, "run_id"), ...
    "stage", s12_sound_playground_require_text_scalar(stage, "stage"), ...
    "status", s12_sound_playground_require_text_scalar(status, "status"), ...
    "started_at", nowString(), "ended_at", "", "artifact", artifact, ...
    "error_identifier", "", "error_message", "", "error_stack", "");
if ~isempty(cause)
    record = s12_sound_playground_complete_stage_record(record, status, artifact, cause);
end
end

function value = nowString()
value = string(datetime("now", "Format", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"));
end
