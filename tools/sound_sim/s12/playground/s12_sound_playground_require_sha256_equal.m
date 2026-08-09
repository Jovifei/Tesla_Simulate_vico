function s12_sound_playground_require_sha256_equal(actual, expected, context)
%S12_SOUND_PLAYGROUND_REQUIRE_SHA256_EQUAL Require equal, valid scalar SHA-256 values.

if nargin < 3
    context = "SHA-256 comparison";
end
[matches, actualInfo, expectedInfo] = s12_sound_playground_sha256_equal(actual, expected);
if ~actualInfo.is_scalar || ~expectedInfo.is_scalar
    error("S12:Playground:HashScalar", "%s requires scalar SHA-256 text. actual %s; expected %s.", ...
        context, describe(actual, actualInfo), describe(expected, expectedInfo));
end
if ~matches
    error("S12:Playground:HashMismatch", "%s failed. actual %s; expected %s.", ...
        context, describe(actual, actualInfo), describe(expected, expectedInfo));
end
end

function text = describe(value, info)
summary = contentSummary(value);
text = sprintf("class=%s size=%s valid=%d content=%s", ...
    info.class_name, mat2str(info.size), info.is_valid, summary);
end

function summary = contentSummary(value)
try
    if ischar(value)
        text = join(string(value), "|");
    elseif isstring(value)
        text = join(value(:).', "|");
    else
        text = string(value);
    end
catch
    text = "<unprintable>";
end
text = replace(replace(string(text), newline, "\\n"), char(13), "\\r");
quote = string(char(34));
if strlength(text) > 40
    summary = char(quote + extractBefore(text, 41) + "..." + quote);
else
    summary = char(quote + text + quote);
end
end
