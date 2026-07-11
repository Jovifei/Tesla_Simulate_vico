%RUN_C63_W204_V6_1 Render the reviewed C63 V6.1 listening artifacts.

vehicleDir = fileparts(mfilename("fullpath"));
v6Root = fileparts(fileparts(vehicleDir));
addpath(v6Root, fileparts(v6Root), vehicleDir);
profile = c63_w204_v6_profile();
v6_render_c63_artifacts(profile, "iteration_04_v6_1_reviewed");
