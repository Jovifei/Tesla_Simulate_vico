function progress = s12_sound_playground_append_stage_record(progress, record)
%S12_SOUND_PLAYGROUND_APPEND_STAGE_RECORD Append only an exact stage-record schema.

template = s12_sound_playground_empty_progress();
if ~isstruct(progress) || ~isequal(string(fieldnames(progress)).', string(fieldnames(template)).')
    error("S12:Playground:ProgressSchema", "Progress must start from s12_sound_playground_empty_progress.");
end
if ~isstruct(record) || ~isscalar(record) || ~isequal(string(fieldnames(record)).', string(fieldnames(template)).')
    error("S12:Playground:ProgressRecordSchema", "Cannot append a stage record with a different schema.");
end
progress(end + 1) = record;
end
