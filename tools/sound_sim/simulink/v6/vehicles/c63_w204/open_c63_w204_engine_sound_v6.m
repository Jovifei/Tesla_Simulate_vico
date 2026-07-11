%OPEN_C63_W204_ENGINE_SOUND_V6 Open the model with its dictionary on path.

vehicleDir = fileparts(mfilename("fullpath"));
addpath(vehicleDir);
open_system(fullfile(vehicleDir, "c63_w204_engine_sound_v6.slx"));
