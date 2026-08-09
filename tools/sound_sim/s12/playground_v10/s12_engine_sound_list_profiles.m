function profiles = s12_engine_sound_list_profiles()
%S12_ENGINE_SOUND_LIST_PROFILES List built-in synthetic v1.0 profiles.

ids = ["inline3_turbo", "inline4_sport", "inline5_character", "inline6_smooth", ...
    "v6_sport", "hellcat_style_supercharged_v8", "ferrari_style_high_rev_v8"];
profiles = repmat(struct("id", "", "cylinders", 0, "synthetic", false), 1, numel(ids));
for index = 1:numel(ids)
    profile = s12_engine_sound_load_profile(ids(index));
    profiles(index) = struct("id", profile.profile_id.value, ...
        "cylinders", profile.engine.cylinder_count.value, ...
        "synthetic", logical(profile.synthetic.value));
end
end
