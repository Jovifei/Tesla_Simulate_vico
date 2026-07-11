% Parameters used by classic_sound_tuner.slx.

scriptDir = fileparts(mfilename("fullpath"));
addpath(fullfile(fileparts(scriptDir), "matlab"));

TunerProfileName = "c63_w204";
profile = vehicle_profile(TunerProfileName);
SpeedKmh = 80;
ThrottleCmd = 0.65;
GearCmd = 2;
ShiftGainCmd = 1.0;
WheelRadiusM = profile.wheel_radius_m;
GearRatios = profile.gear_ratios;
FinalDrive = profile.final_drive;
OverallRatio = GearRatios(GearCmd) * FinalDrive;
RedlineRPM = profile.redline_rpm;
