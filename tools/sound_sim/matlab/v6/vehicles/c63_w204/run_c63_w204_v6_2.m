%RUN_C63_W204_V6_2 Render balanced and aggressive combustion-rasp candidates.

vehicleDir = fileparts(mfilename("fullpath"));
v6Root = fileparts(fileparts(vehicleDir));
addpath(v6Root, fileparts(v6Root), vehicleDir);

balanced = c63_w204_v6_profile();
v6_render_c63_artifacts(balanced, "iteration_05_v6_2_rasp_balanced");

aggressive = balanced;
aggressive.audio.master_gain = 0.93;
aggressive.rasp.nonlinear_gain = 0.42;
aggressive.rasp.texture_gain = 0.14;
aggressive.rasp.jitter_gain = 0.45;
v6_render_c63_artifacts(aggressive, "iteration_06_v6_2_rasp_aggressive");
