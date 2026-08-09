function ptrControls = s12_v11_model_ptr_controls_step(stateVector, profileIndex)
%S12_V11_MODEL_PTR_CONTROLS_STEP Extract JSON-ranged controls before PTR.

profile = profileForIndex(profileIndex);
values = validateState(stateVector, profile.renderer.frame_samples);
controls = s12_v11_model_dashboard_controls(profile);
ptrControls = [ ...
    clampToControl(values(14), controls, "ptr_pipe_length_m"); ...
    clampToControl(values(15), controls, "ptr_area_m2"); ...
    clampToControl(values(16), controls, "ptr_reflection"); ...
    clampToControl(values(17), controls, "ptr_damping")];
end

function values = validateState(stateVector, frameSamples)
if ~isnumeric(stateVector) || ~isequal(size(stateVector), [21, 1]) || ...
        any(~isfinite(stateVector), "all") || frameSamples ~= 960
    error("S12:EngineSoundV11:ModelPTR", ...
        "Vehicle State must expose a finite [21,1] model-control vector.");
end
values = double(stateVector(:));
end

function value = clampToControl(value, controls, field)
index = find(string({controls.field}) == string(field), 1, "first");
if isempty(index)
    error("S12:EngineSoundV11:ModelPTR", "Dashboard control %s is unavailable.", field);
end
bounds = controls(index).range;
value = max(bounds(1), min(bounds(2), value));
end

function profile = profileForIndex(profileIndex)
ids = s12_v11_canonical_vehicle_ids();
if ~isnumeric(profileIndex) || ~isscalar(profileIndex) || ~isfinite(profileIndex) || ...
        profileIndex ~= floor(profileIndex) || profileIndex < 1 || profileIndex > numel(ids)
    error("S12:EngineSoundV11:ModelPTR", "profileIndex is outside the canonical vehicle list.");
end
profile = s12_v11_load_profile(ids(profileIndex));
end
