%RUN_C63_V6_AUTOFIT Fit C63 afterfire gains to derived public-reference features.

scriptDir = fileparts(mfilename("fullpath"));
addpath(scriptDir);
profile = v6_vehicle_profile("c63_w204");
referencePath = "E:\Claude_allow\Download\tesla-sound-research\c63_w204_headers_backfire.wav";
[profile, fitReport] = v6_fit_afterfire(profile, referencePath);
v6_render_c63_artifacts(profile, "iteration_03_afterfire_autofit_wideband", fitReport);
