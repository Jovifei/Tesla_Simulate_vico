%BUILD_HELLCAT_SIMULINK_ASSETS Create the isolated Hellcat model and dictionary.

scriptDir = fileparts(mfilename("fullpath"));
soundRoot = fileparts(fileparts(fileparts(fileparts(scriptDir))));
matlabRoot = fullfile(soundRoot, "matlab");
v6Root = fullfile(matlabRoot, "v6");
addpath(matlabRoot, v6Root);

profile = v6_vehicle_profile("hellcat");
dictionaryPath = fullfile(scriptDir, "hellcat_v6_params.sldd");
if isfile(dictionaryPath)
    dictionary = Simulink.data.dictionary.open(dictionaryPath);
else
    dictionary = Simulink.data.dictionary.create(dictionaryPath);
end
designData = getSection(dictionary, "Design Data");
try
    entry = getEntry(designData, "HELLCAT_V6");
    setValue(entry, profile);
catch
    addEntry(designData, "HELLCAT_V6", profile);
end
saveChanges(dictionary);
close(dictionary);

sourceModel = fullfile(soundRoot, "simulink", "engine_sound_v6.slx");
targetModel = fullfile(scriptDir, "hellcat_engine_sound_v6.slx");
if bdIsLoaded("hellcat_engine_sound_v6")
    close_system("hellcat_engine_sound_v6", 0);
end
load_system(sourceModel);
save_system("engine_sound_v6", targetModel);
set_param("hellcat_engine_sound_v6", "DataDictionary", ...
    "hellcat_v6_params.sldd");
save_system("hellcat_engine_sound_v6");
close_system("hellcat_engine_sound_v6");
close_system("engine_sound_v6", 0);
fprintf("Hellcat V6 Simulink assets: %s\n", scriptDir);
