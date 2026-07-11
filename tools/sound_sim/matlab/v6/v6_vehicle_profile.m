function profile = v6_vehicle_profile(profileName)
%V6_VEHICLE_PROFILE Dispatch to an isolated per-vehicle V6 profile.

arguments
    profileName (1,1) string
end

vehicleName = lower(profileName);
vehicleDir = fullfile(fileparts(mfilename("fullpath")), "vehicles", vehicleName);
profileFunction = vehicleName + "_v6_profile";
profilePath = fullfile(vehicleDir, profileFunction + ".m");
if ~isfile(profilePath)
    error("jovi:soundv6:UnsupportedProfile", ...
        "No independent V6 profile exists for %s.", profileName);
end

addpath(vehicleDir);
profile = feval(profileFunction);
end
