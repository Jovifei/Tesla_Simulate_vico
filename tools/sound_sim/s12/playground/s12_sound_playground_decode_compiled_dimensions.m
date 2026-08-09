function dimensions = s12_sound_playground_decode_compiled_dimensions(raw, dimensionsMode, busType, blockPath, portName)
%S12_SOUND_PLAYGROUND_DECODE_COMPILED_DIMENSIONS Decode fixed nonbus dimensions.

context = sprintf("block=%s port=%s raw=%s", string(blockPath), string(portName), mat2str(raw));
if isempty(raw) || ~isnumeric(raw)
    error("S12:Playground:CompiledDimensions", "Invalid dimensions: %s", context);
end
raw = double(raw(:).');
if any(~isfinite(raw)) || any(raw ~= floor(raw)) || any(raw <= 0)
    error("S12:Playground:CompiledDimensions", "Invalid dimensions: %s", context);
end
if ~(isequal(dimensionsMode, 0) || isequal(string(dimensionsMode), "0"))
    error("S12:Playground:CompiledDimensionsMode", "Unsupported dimensions mode: %s", context);
end
if ~strcmp(string(busType), "NOT_BUS")
    error("S12:Playground:CompiledBusType", "Unsupported bus type: %s", context);
end
rank = raw(1);
if rank <= 0 || numel(raw) ~= rank + 1
    error("S12:Playground:CompiledDimensions", "Invalid dimensions: %s", context);
end
dimensions = raw(2:end);
end
