toolkitRoot = fullfile(getenv("USERPROFILE"), ".matlab", "agentic-toolkits", "simulink");
if isfolder(toolkitRoot)
    addpath(toolkitRoot);
    try
        satk_initialize;
    catch exception
        warning("Jovi:SimulinkAgenticToolkit:Startup", "%s", exception.message);
    end
end
