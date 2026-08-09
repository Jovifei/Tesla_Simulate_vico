function value = s12_engine_sound_normalize_profile_text(value)
%S12_ENGINE_SOUND_NORMALIZE_PROFILE_TEXT Convert JSON char values to string values.

if ischar(value)
    value = string(value);
elseif iscell(value)
    for index = 1:numel(value)
        value{index} = s12_engine_sound_normalize_profile_text(value{index});
    end
elseif isstruct(value)
    names = fieldnames(value);
    for element = 1:numel(value)
        for index = 1:numel(names)
            name = names{index};
            value(element).(name) = s12_engine_sound_normalize_profile_text(value(element).(name));
        end
    end
end
end
