%RUN_C63_V6 Render the C63 V6 physical-acoustics baseline artifacts.

scriptDir = fileparts(mfilename("fullpath"));
addpath(scriptDir);
profile = v6_vehicle_profile("c63_w204");
v6_render_c63_artifacts(profile, "iteration_00_physical_baseline");
