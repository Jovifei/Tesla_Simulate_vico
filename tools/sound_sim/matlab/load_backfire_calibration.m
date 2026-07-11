function calibration = load_backfire_calibration(profileName)
%LOAD_BACKFIRE_CALIBRATION Read derived, non-audio backfire parameters.

persistent payload
if isempty(payload)
    scriptDir = fileparts(mfilename("fullpath"));
    jsonPath = fullfile(scriptDir, "calibration", "backfire_calibration.json");
    payload = jsondecode(fileread(jsonPath));
end

names = string({payload.profiles.name});
index = find(names == string(profileName), 1);
if isempty(index)
    error("jovi:sound:MissingBackfireCalibration", ...
        "No backfire calibration for %s", profileName);
end
calibration = payload.profiles(index);
end
