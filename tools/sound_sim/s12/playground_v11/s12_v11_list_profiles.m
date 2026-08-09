function profiles = s12_v11_list_profiles()
%S12_V11_LIST_PROFILES List synthetic v1.1 packages and render readiness.

root = fileparts(mfilename("fullpath"));
common = fullfile(root, "common");
if isempty(which("s12_v11_validate_vehicle_package"))
    addpath(common);
end
vehicleRoot = fullfile(root, "vehicles");
ids = s12_v11_canonical_vehicle_ids();
pilots = ["hellcat_2022_stock", "c63_w204_facelift_stock", "ferrari_458_stock"];
template = struct("profile_id", "", "make", "", "model", "", ...
    "pilot", false, "render_supported", false, "synthetic", true);
profiles = repmat(template, 1, numel(ids));
for index = 1:numel(ids)
    packageRoot = fullfile(vehicleRoot, ids(index));
    if ~isfolder(packageRoot)
        error("S12:EngineSoundV11:ProfileNotFound", ...
            "Missing canonical v1.1 vehicle package: %s", ids(index));
    end
    s12_v11_validate_vehicle_package(packageRoot);
    metadata = jsondecode(fileread(fullfile(packageRoot, "profile.json")));
    pilot = ismember(ids(index), pilots);
    renderSupported = true;
    profiles(index) = struct( ...
        "profile_id", ids(index), ...
        "make", string(metadata.vehicle_identity.make), ...
        "model", string(metadata.vehicle_identity.model), ...
        "pilot", pilot, ...
        "render_supported", renderSupported, ...
        "synthetic", true);
end
end
