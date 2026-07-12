%OPEN_HELLCAT_ENGINE_SOUND_V6 Open the model with its dictionary on path.

vehicleDir = fileparts(mfilename("fullpath"));
addpath(vehicleDir);
open_system(fullfile(vehicleDir, "hellcat_engine_sound_v6.slx"));
