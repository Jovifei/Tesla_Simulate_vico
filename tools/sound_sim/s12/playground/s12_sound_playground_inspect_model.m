function manifest = s12_sound_playground_inspect_model(artifact, plan, compileModel)
%S12_SOUND_PLAYGROUND_INSPECT_MODEL Inspect a temporary candidate only.
% compileModel=true is reserved for a separately approved Desktop session.

if nargin < 3
    compileModel = false;
end
if strcmp(s12_sound_playground_require_text_scalar(artifact.model_path, "artifact model path"), ...
        s12_sound_playground_require_text_scalar(plan.artifacts.workspace_unvalidated_intermediate.path, "workspace model path"))
    error("S12:Playground:EvidenceInspection", "Workspace unvalidated intermediate is never a candidate.");
end
model = string(artifact.model_name);
lease = s12_sound_playground_open_owned_model(model, artifact.model_path, ...
    fullfile(plan.temporary.root, "inspect_cleanup_failure.json"));
cleanup = onCleanup(@() s12_sound_playground_close_owned_model_without_save(lease));
manifest = struct("model_name", model, "model_path", string(artifact.model_path), ...
    "compile_requested", logical(compileModel), "status", "STRUCTURE_INSPECTED_NOT_COMPILED");
manifest.ports = inspectPorts(model, plan.port_contract);
s12_sound_playground_validate_ports(manifest.ports);
assertNoDefaultPorts(model);
manifest.signal_specifications = inspectSignalSpecifications(model);
if compileModel
    compileResult = s12_sound_playground_compile_and_inspect_dimensions(model, plan.signal_contract, ...
        fullfile(plan.runtime.transaction_root, "compile_cleanup_error.json"));
    manifest.dimensions = compileResult.dimensions;
    manifest.compile_gates = compileResult;
    manifest.status = "COMPILED_DIMENSIONS_INSPECTED";
end

function observed = inspectSignalSpecifications(model)
names = [ ...
    "Dashboard/Interactive Configuration [18x1]", ...
    "Dashboard/Qualification Configuration [18x1]", ...
    "Dashboard/Selected Configuration [18x1]", ...
    "Vehicle State/Vehicle State Fixed Packed [18x1]", ...
    "Engine Excitation/Engine Excitation Fixed Packed [18x1]"];
observed = repmat(struct("path", "", "Dimensions", "", "VarSizeSig", "", "OutDataTypeStr", ""), 1, numel(names));
for index = 1:numel(names)
    path = model + "/" + names(index);
    dimensions = string(get_param(path, "Dimensions"));
    variableSize = string(get_param(path, "VarSizeSig"));
    dataType = string(get_param(path, "OutDataTypeStr"));
    if ~strcmp(s12_sound_playground_require_text_scalar(dimensions, "Dimensions"), "[18 1]") || ...
            ~strcmp(s12_sound_playground_require_text_scalar(variableSize, "VarSizeSig"), "No") || ...
            ~strcmp(s12_sound_playground_require_text_scalar(dataType, "OutDataTypeStr"), "double")
        error("S12:Playground:SignalSpecification", "Signal Specification readback failed at %s.", path);
    end
    observed(index) = struct("path", path, "Dimensions", dimensions, ...
        "VarSizeSig", variableSize, "OutDataTypeStr", dataType);
end
end
end

function observed = inspectPorts(model, contract)
names = fieldnames(contract.subsystems);
observed = struct("subsystems", struct(), "top_level_connections", struct("source", {}, "destination", {}));
for index = 1:numel(names)
    name = names{index};
    path = model + "/" + subsystemBlockName(name);
    observed.subsystems.(name) = struct( ...
        "inputs", portCount(path, "Inport"), "outputs", portCount(path, "Outport"), ...
        "input_names", portNames(path, "Inport"), "output_names", portNames(path, "Outport"));
end
observed.top_level_connections = enumerateTopLevelLinks(model);
assertExactTopLevelLinks(observed.top_level_connections, contract.top_level_connections);
end

function count = portCount(path, kind)
count = numel(find_system(path, "SearchDepth", 1, "BlockType", kind));
end

function names = portNames(path, kind)
ports = string(find_system(path, "SearchDepth", 1, "BlockType", kind));
numbers = zeros(numel(ports), 1);
for index = 1:numel(ports)
    numbers(index) = str2double(get_param(ports(index), "Port"));
end
[~, order] = sort(numbers);
names = strings(1, numel(ports));
for index = 1:numel(ports)
    names(index) = string(get_param(ports(order(index)), "Name"));
end
end

function links = enumerateTopLevelLinks(model)
lines = get_param(model, "Lines");
links = struct("source", {}, "destination", {});
for index = 1:numel(lines)
    lineHandle = lines(index).Handle;
    sourcePort = get_param(lineHandle, "SrcPortHandle");
    destinationPorts = get_param(lineHandle, "DstPortHandle");
    if isempty(sourcePort) || sourcePort == -1 || isempty(destinationPorts) || any(destinationPorts == -1)
        error("S12:Playground:DanglingTopLevelLine", "Dangling top-level line handle %g.", lineHandle);
    end
    source = semanticEndpoint(model, sourcePort, "source");
    for destinationIndex = 1:numel(destinationPorts)
        destination = semanticEndpoint(model, destinationPorts(destinationIndex), "destination");
        links(end + 1) = struct("source", source, "destination", destination); %#ok<AGROW>
    end
end
end

function semantic = semanticEndpoint(model, portHandle, direction)
parent = get_param(portHandle, "Parent");
blockPath = string(getfullname(parent));
prefix = model + "/";
if ~startsWith(blockPath, prefix)
    error("S12:Playground:UnexpectedTopLevelEndpoint", "Endpoint %s is outside %s.", blockPath, model);
end
blockName = extractAfter(blockPath, prefix);
portNumber = get_param(portHandle, "PortNumber");
if strcmp(s12_sound_playground_require_text_scalar(direction, "endpoint direction"), "source")
    portName = internalPortName(blockPath, "Outport", portNumber);
else
    portName = internalPortName(blockPath, "Inport", portNumber);
end
semantic = blockName + "." + portName;
end

function name = internalPortName(blockPath, kind, portNumber)
if endsWith(blockPath, "/Qualification PCM Sink") || endsWith(blockPath, "/Optional Device Output")
    name = "PCM";
    return;
end
ports = string(find_system(blockPath, "SearchDepth", 1, "BlockType", kind));
for index = 1:numel(ports)
    if str2double(get_param(ports(index), "Port")) == portNumber
        name = string(get_param(ports(index), "Name"));
        return;
    end
end
error("S12:Playground:UnknownEndpointPort", "Cannot map %s port %d.", blockPath, portNumber);
end

function assertExactTopLevelLinks(observed, expected)
observedKeys = linkKeys(observed);
expectedKeys = linkKeys(expected);
if numel(unique(observedKeys)) ~= numel(observedKeys)
    error("S12:Playground:DuplicateTopLevelLink", "Duplicate top-level link observed.");
end
if ~isequal(sort(observedKeys), sort(expectedKeys))
    error("S12:Playground:TopLevelLinkSet", "Observed top-level link set does not exactly match the contract.");
end
for index = 1:numel(expected)
    assertTopLevelLink(observed, expected(index));
end
end

function assertTopLevelLink(observed, expected)
key = string(expected.source) + "->" + string(expected.destination);
if ~any(strcmp(linkKeys(observed), key))
    error("S12:Playground:MissingTopLevelLink", "Missing top-level link %s.", key);
end
end

function keys = linkKeys(links)
keys = strings(1, numel(links));
for index = 1:numel(links)
    keys(index) = string(links(index).source) + "->" + string(links(index).destination);
end
end

function block = subsystemBlockName(contractName)
map = struct("Dashboard", "Dashboard", "VehicleState", "Vehicle State", ...
    "EngineExcitation", "Engine Excitation", "PtrRadiationTuningAdapter", "PTR Radiation Tuning Adapter", ...
    "AudioRenderer", "Audio Renderer");
block = map.(contractName);
end

function assertNoDefaultPorts(model)
defaults = find_system(model, "Regexp", "on", "Name", "^(In1|Out1)$");
if ~isempty(defaults)
    error("S12:Playground:DefaultPortsRemain", "Default subsystem ports remain in candidate.");
end
end
