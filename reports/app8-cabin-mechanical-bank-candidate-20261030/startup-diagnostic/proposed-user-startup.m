% Keep MATLAB startup side-effect free unless explicitly requested.
toolkitRoot = fullfile(getenv("USERPROFILE"), ".matlab", "agentic-toolkits", "simulink");
if isfolder(toolkitRoot)
    addpath(toolkitRoot);
end
if strcmp(getenv("TESLA_SPEED_ENABLE_SATK_STARTUP"), "1") && isfolder(toolkitRoot)
    try
        satk_initialize;
    catch exception
        warning("Jovi:SimulinkAgenticToolkit:Startup", "%s", exception.message);
    end
end
