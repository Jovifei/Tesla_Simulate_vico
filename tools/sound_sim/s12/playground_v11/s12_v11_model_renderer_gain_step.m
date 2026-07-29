function gain = s12_v11_model_renderer_gain_step(stateVector, profileIndex)
%S12_V11_MODEL_RENDERER_GAIN_STEP Extract the JSON-ranged renderer gain.

profile = profileForIndex(profileIndex);
if ~isnumeric(stateVector) || ~isequal(size(stateVector), [21, 1]) || ...
        any(~isfinite(stateVector), "all")
    error("S12:EngineSoundV11:ModelRenderer", ...
        "Vehicle State must expose a finite [21,1] model-control vector.");
end
controls = s12_v11_model_dashboard_controls(profile);
index = find(string({controls.field}) == "gain", 1, "first");
if isempty(index)
    error("S12:EngineSoundV11:ModelRenderer", "Dashboard gain control is unavailable.");
end
bounds = controls(index).range;
gain = max(bounds(1), min(bounds(2), double(stateVector(18))));
end

function profile = profileForIndex(profileIndex)
ids = s12_v11_canonical_vehicle_ids();
if ~isnumeric(profileIndex) || ~isscalar(profileIndex) || ~isfinite(profileIndex) || ...
        profileIndex ~= floor(profileIndex) || profileIndex < 1 || profileIndex > numel(ids)
    error("S12:EngineSoundV11:ModelRenderer", "profileIndex is outside the canonical vehicle list.");
end
profile = s12_v11_load_profile(ids(profileIndex));
end
