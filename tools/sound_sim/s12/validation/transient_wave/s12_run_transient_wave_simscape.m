function result = s12_run_transient_wave_simscape(config)
%S12_RUN_TRANSIENT_WAVE_SIMSCAPE Run controlled multi-Pipe(G) reference.
arguments
    config (1,1) struct
end
validateConfig(config);
root = fileparts(fileparts(fileparts(mfilename("fullpath"))));
modelName = modelForBoundary(config.boundary);
modelPath = fullfile(root, "models", "pipe_ref", modelName + ".slx");
if ~isfile(modelPath)
    error("S12:TransientWave:MissingModel", "Transient Pipe(G) reference is missing.");
end
wasLoaded = bdIsLoaded(modelName);
load_system(modelPath);
cleanup = onCleanup(@() closeIfOwned(modelName, wasLoaded));
workspace = get_param(modelName, "ModelWorkspace");
setValue(workspace, "S12_PipeCellLengthM", config.pipe_length_m / 8);
setValue(workspace, "S12_PipeInitialPressurePa", config.ambient_pressure_pa);
setValue(workspace, "S12_PipeInitialTemperatureK", config.temperature_k);
setValue(workspace, "S12_PressurePulsePa", config.pulse_amplitude_pa);
setValue(workspace, "S12_PrimaryAreaM2", config.area_m2);
setValue(workspace, "S12_PrimaryDiameterM", config.hydraulic_diameter_m);
setValue(workspace, "S12_PrimaryRoughnessM", config.roughness_m);
setValue(workspace, "S12_PulseStartS", config.pulse_start_s);
setValue(workspace, "S12_PulseEndS", config.pulse_end_s);
waveSpeed = sqrt(config.gamma * config.gas_constant * config.temperature_k);
sourceTime = linspace(0, config.end_time_s, 2001).';
sourceCenter = config.source_center_s;
sourceSigma = config.pulse_sigma_m / waveSpeed;
sourcePressure = config.pulse_amplitude_pa * exp(-0.5 * ...
    ((sourceTime - sourceCenter) / sourceSigma).^2);
setValue(workspace, "S12_GaussianPressureCommand", ...
    [sourceTime, sourcePressure]);
output = sim(modelName, "StopTime", num2str(config.end_time_s, "%.17g"));
time = column(output.get("S12_PipeTime"));
probe = column(output.get("S12_PipeFvmComparisonPressure"));
if numel(time) ~= numel(probe) || isempty(time) || any(~isfinite(probe))
    error("S12:TransientWave:SimscapeTrace", ...
        "Pipe(G) probe trace is incomplete or nonfinite.");
end
result = struct( ...
    "reference_id", simscapeReferenceId(config.boundary), ...
    "boundary_type", string(config.boundary), ...
    "model_path", modelPath, ...
    "time_s", time, "pressure_pa", probe, ...
    "probe_location_m", config.pipe_length_m / 2, ...
    "sample_count", numel(time), "final_time_s", time(end), ...
    "fvm_time_origin_s", config.fvm_time_origin_s);
clear cleanup
end

function validateConfig(config)
required = ["boundary", "gamma", "gas_constant", "pipe_length_m", "ambient_pressure_pa", ...
    "temperature_k", "pulse_amplitude_pa", "pulse_start_s", "pulse_end_s", ...
    "pulse_center_m", "pulse_sigma_m", "source_center_s", "fvm_time_origin_s", ...
    "end_time_s", "area_m2", ...
    "hydraulic_diameter_m", "roughness_m"];
if ~isstruct(config) || ~all(isfield(config, required)) || ...
        config.gamma <= 1 || config.gas_constant <= 0 || config.pipe_length_m <= 0 || ...
        config.ambient_pressure_pa <= 0 || ...
        config.temperature_k <= 0 || config.pulse_amplitude_pa <= 0 || ...
        config.pulse_start_s < 0 || config.pulse_end_s <= config.pulse_start_s || ...
        config.pulse_center_m < 0 || config.pulse_sigma_m <= 0 || ...
        config.source_center_s < 0 || config.fvm_time_origin_s < config.source_center_s || ...
        config.end_time_s <= config.pulse_end_s || config.area_m2 <= 0 || ...
        config.hydraulic_diameter_m <= 0 || config.roughness_m < 0
    error("S12:TransientWave:InvalidInput", "Invalid Pipe(G) transient configuration.");
end
modelForBoundary(config.boundary);
end

function value = modelForBoundary(boundary)
switch string(boundary)
    case "closed_rigid_end"
        value = "s12_transient_pipe_g_closed_ref";
    case "ideal_pressure_release_open_end"
        value = "s12_transient_pipe_g_open_ref";
    otherwise
        error("S12:TransientWave:InvalidBoundary", ...
            "Pipe(G) reference supports only controlled closed/open ends.");
end
end

function value = simscapeReferenceId(boundary)
if string(boundary) == "closed_rigid_end"
    value = "pipe_g_multisegment_zero_mdot_rigid.v1";
else
    value = "pipe_g_multisegment_pressure_reservoir_release.v1";
end
end

function setValue(workspace, name, value)
if ~any(strcmp({workspace.whos.name}, name))
    workspace.assignin(name, value);
    return
end
parameter = workspace.getVariable(name);
if isa(parameter, "Simulink.Parameter")
    parameter.Value = value;
    workspace.assignin(name, parameter);
else
    workspace.assignin(name, value);
end
end

function value = column(raw)
value = reshape(raw, [], 1);
end

function closeIfOwned(modelName, wasLoaded)
if ~wasLoaded && bdIsLoaded(modelName)
    close_system(modelName, 0);
end
end
