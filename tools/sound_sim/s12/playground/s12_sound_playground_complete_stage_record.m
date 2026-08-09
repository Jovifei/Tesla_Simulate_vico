function record = s12_sound_playground_complete_stage_record(record, status, artifact, cause)
%S12_SOUND_PLAYGROUND_COMPLETE_STAGE_RECORD Finalize one fixed-schema stage record.

validateRecord(record);
record.status = s12_sound_playground_require_text_scalar(status, "status");
if nargin >= 3 && ~isempty(artifact)
    record.artifact = artifact;
end
record.ended_at = string(datetime("now", "Format", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"));
record.error_identifier = "";
record.error_message = "";
record.error_stack = "";
if nargin >= 4 && ~isempty(cause)
    if ~isa(cause, "MException")
        error("S12:Playground:StageCause", "Stage cause must be an MException.");
    end
    record.error_identifier = string(cause.identifier);
    record.error_message = string(cause.message);
    record.error_stack = string(getReport(cause, "extended", "hyperlinks", "off"));
end
end

function validateRecord(record)
required = ["run_id", "stage", "status", "started_at", "ended_at", "artifact", ...
    "error_identifier", "error_message", "error_stack"];
if ~isstruct(record) || ~isscalar(record) || ~isequal(string(fieldnames(record)).', required)
    error("S12:Playground:StageRecordSchema", "Stage record must use the fixed Runtime Proof schema.");
end
end
