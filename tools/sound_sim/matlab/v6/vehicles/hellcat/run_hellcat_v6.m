%RUN_HELLCAT_V6 Render the independent Hellcat physical-acoustics candidate.

vehicleDir = fileparts(mfilename("fullpath"));
v6Root = fileparts(fileparts(vehicleDir));
addpath(v6Root, fileparts(v6Root), vehicleDir);
profile = hellcat_v6_profile();
v6_render_vehicle_artifacts(profile, "iteration_01_reference_calibrated");
