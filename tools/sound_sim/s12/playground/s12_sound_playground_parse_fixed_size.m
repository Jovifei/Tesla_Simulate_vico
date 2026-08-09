function shape = s12_sound_playground_parse_fixed_size(rawSize, blockPath, direction, dataName)
%S12_SOUND_PLAYGROUND_PARSE_FIXED_SIZE Parse fixed two-dimensional Stateflow size text.
% Accepted equivalent examples are [18,1], [18 1], and 18,1.

rawSize = string(rawSize);
context = "block=" + string(blockPath) + " direction=" + string(direction) + " data=" + string(dataName);
rawSize = s12_sound_playground_require_text_scalar(rawSize, "Stateflow fixed size");
if strlength(rawSize) == 0 || any(contains(lower(rawSize), ["dynamic", "inherit", "-1", ":"]))
    error("S12:Playground:DynamicSize", "Dynamic or incomplete size is not permitted: %s", context);
end
tokens = regexp(char(rawSize), "^\s*\[?\s*(\d+)\s*(?:,|\s+)\s*(\d+)\s*\]?\s*$", "tokens", "once");
if isempty(tokens)
    error("S12:Playground:StateflowSize", "Invalid fixed two-dimensional size %s: %s", rawSize, context);
end
shape = [str2double(tokens{1}), str2double(tokens{2})];
if any(~isfinite(shape)) || any(shape <= 0) || any(shape ~= floor(shape))
    error("S12:Playground:StateflowSize", "Invalid fixed two-dimensional size %s: %s", rawSize, context);
end
end
