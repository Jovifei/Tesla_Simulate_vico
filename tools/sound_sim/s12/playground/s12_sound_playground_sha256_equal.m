function [result, actualInfo, expectedInfo] = s12_sound_playground_sha256_equal(actualInput, expectedInput)
%S12_SOUND_PLAYGROUND_SHA256_EQUAL Compare two normalized scalar SHA-256 values.

actualInfo = normalizeSha256(actualInput);
expectedInfo = normalizeSha256(expectedInput);
result = false;
if ~(actualInfo.is_valid && expectedInfo.is_valid)
    return;
end
actual = actualInfo.value;
expected = expectedInfo.value;
result = strcmp(actual, expected);
end

function info = normalizeSha256(value)
info = struct("class_name", string(class(value)), "size", size(value), "value", "", ...
    "is_scalar", false, "is_valid", false);
if ischar(value)
    if size(value, 1) ~= 1
        return;
    end
    normalized = string(value);
elseif isstring(value)
    if ~isscalar(value) || ismissing(value)
        return;
    end
    normalized = value;
else
    return;
end
info.is_scalar = true;
info.value = upper(strtrim(normalized));
info.is_valid = strlength(info.value) == 64 && ...
    ~isempty(regexp(char(info.value), "^[0-9A-F]{64}$", "once"));
end
