function profile = s12_engine_sound_load_profile(identifier)
%S12_ENGINE_SOUND_LOAD_PROFILE Compatibility entry point for canonical v1.1.
% Non-v1.1 identifiers fail closed instead of crossing a version boundary.

profile = s12_v11_load_profile(s12_v11_validate_canonical_vehicle_id(identifier));
end
