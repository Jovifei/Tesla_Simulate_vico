function value = s12_sound_playground_require_text_scalar(input, name)
%S12_SOUND_PLAYGROUND_REQUIRE_TEXT_SCALAR Normalize one nonempty text value.

if nargin < 2
    name = "text";
end
if ischar(input)
    valid = size(input, 1) == 1;
    if valid
        value = string(input);
    else
        value = "";
    end
elseif isstring(input)
    valid = isscalar(input) && ~ismissing(input);
    if valid
        value = input;
    else
        value = "";
    end
else
    valid = false;
    value = "";
end
if ~valid || strlength(value) == 0
    error("S12:Playground:TextScalar", "%s must be nonempty scalar text; class=%s size=%s.", ...
        string(name), class(input), mat2str(size(input)));
end
end
