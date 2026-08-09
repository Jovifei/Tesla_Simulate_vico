function result = s12_sound_playground_compile_and_inspect_dimensions(model, contract, cleanupErrorPath, performUpdate)
%S12_SOUND_PLAYGROUND_COMPILE_AND_INSPECT_DIMENSIONS Keep compiled reads in one active lifecycle.

if nargin < 4
    performUpdate = true;
end
result = struct("update_diagram_gate", "NOT_RUN", "compiled_dimensions_gate", "NOT_RUN", "dimensions", struct());
if performUpdate
    try
        set_param(model, "SimulationCommand", "update");
        result.update_diagram_gate = "UPDATE_DIAGRAM_PASSED";
    catch cause
        persistCleanupError(cleanupErrorPath, "update_diagram", cause);
        rethrow(cause);
    end
end
compiled = false;
try
    feval(model, [], [], [], "compile");
    compiled = true;
    result.dimensions = inspectCompiledDimensions(model);
    s12_sound_playground_validate_dimensions(result.dimensions, contract);
    result.compiled_dimensions_gate = "COMPILED_DIMENSIONS_PASSED";
    feval(model, [], [], [], "term");
catch cause
    if compiled
        try
            feval(model, [], [], [], "term");
        catch cleanupCause
            persistCleanupError(cleanupErrorPath, "compile_term", cleanupCause);
        end
    end
    rethrow(cause);
end
end

function observed = inspectCompiledDimensions(model)
observed = struct( ...
    "configuration", portDimension(model + "/Dashboard", "Outport", 1, "Dashboard.Configuration"), ...
    "configuration_vehicle_input", portDimension(model + "/Vehicle State", "Inport", 1, "Vehicle State.Configuration"), ...
    "configuration_vehicle_output", portDimension(model + "/Vehicle State", "Outport", 1, "Vehicle State.Packed"), ...
    "configuration_engine_input", portDimension(model + "/Engine Excitation", "Inport", 1, "Engine Excitation.Packed"), ...
    "excitation", portDimension(model + "/Engine Excitation", "Outport", 1, "Engine Excitation.Excitation"), ...
    "pressure", portDimension(model + "/PTR Radiation Tuning Adapter", "Outport", 1, "PTR Radiation Tuning Adapter.Pressure"), ...
    "pcm", portDimension(model + "/Audio Renderer", "Outport", 1, "Audio Renderer.PCM"));
end

function dimension = portDimension(blockPath, direction, portIndex, portName)
handles = get_param(blockPath, "PortHandles");
port = handles.(char(direction))(portIndex);
raw = get_param(port, "CompiledPortDimensions");
dimensionsMode = get_param(port, "CompiledPortDimensionsMode");
busType = get_param(port, "CompiledBusType");
dimension = s12_sound_playground_decode_compiled_dimensions(raw, dimensionsMode, busType, blockPath, portName);
end

function persistCleanupError(path, phase, cause)
if strlength(string(path)) == 0
    return;
end
folder = fileparts(path);
if ~isfolder(folder)
    mkdir(folder);
end
record = struct("phase", string(phase), "identifier", string(cause.identifier), ...
    "message", string(cause.message), "report", string(getReport(cause, "extended", "hyperlinks", "off")));
try
    s12_sound_playground_atomic_write_json(path, record);
catch
    return;
end
end
