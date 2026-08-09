function s12_sound_playground_clear_default_subsystem_contents(subsystemPath)
%S12_SOUND_PLAYGROUND_CLEAR_DEFAULT_SUBSYSTEM_CONTENTS Remove only default graph.

blocks = find_system(subsystemPath, "SearchDepth", 1, "Type", "Block");
blocks = setdiff(string(blocks), string(subsystemPath), "stable");
lines = get_param(subsystemPath, "Lines");
for index = 1:numel(lines)
    delete_line(lines(index).Handle);
end
if isempty(blocks)
    return;
end
expected = sort([string(subsystemPath) + "/In1"; string(subsystemPath) + "/Out1"]);
types = strings(numel(blocks), 1);
for index = 1:numel(blocks)
    types(index) = string(get_param(blocks(index), "BlockType"));
end
if ~isequal(sort(blocks), expected) || ~isequal(sort(types), ["Inport"; "Outport"])
    error("S12:Playground:UnexpectedSubsystemContents", ...
        "Only the default In1-to-Out1 graph may be removed from %s.", subsystemPath);
end
for index = 1:numel(blocks)
    delete_block(blocks(index));
end
remaining = find_system(subsystemPath, "SearchDepth", 1, "Type", "Block");
remaining = setdiff(string(remaining), string(subsystemPath), "stable");
if ~isempty(remaining) || ~isempty(get_param(subsystemPath, "Lines"))
    error("S12:Playground:SubsystemNotEmpty", "Unable to empty %s.", subsystemPath);
end
end
