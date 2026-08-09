function s12_sound_playground_configure_function_interfaces(blockPath, interfaceName)
%S12_SOUND_PLAYGROUND_CONFIGURE_FUNCTION_INTERFACES Configure fixed chart I/O.
% R2026a Stateflow API behavior remains runtime-confirmation only.

interfaces = s12_sound_playground_function_interfaces();
expected = interfaces.(interfaceName);
chart = findChart(blockPath);
requiredProperties = ["SupportVariableSizing", "VectorOutputs1D", "TreatDimensionOfLengthOneAsFixedSize"];
for index = 1:numel(requiredProperties)
    if ~isprop(chart, requiredProperties(index))
        error("S12:Playground:StateflowProperty", "Missing chart property %s at %s.", requiredProperties(index), blockPath);
    end
end
chart.SupportVariableSizing = false;
chart.VectorOutputs1D = false;
chart.TreatDimensionOfLengthOneAsFixedSize = true;
configureCollection(chart.Inputs, expected.input_order, expected.inputs, blockPath, "input");
configureCollection(chart.Outputs, expected.output_order, expected.outputs, blockPath, "output");
end

function chart = findChart(blockPath)
chart = sfroot().find("-isa", "Stateflow.EMChart", "Path", blockPath);
if numel(chart) ~= 1
    error("S12:Playground:StateflowChart", "Expected one chart at %s.", blockPath);
end
end

function configureCollection(data, expectedNames, expectedShapes, blockPath, role)
expectedNames = string(expectedNames);
actualNames = strings(1, numel(data));
for index = 1:numel(data), actualNames(index) = string(data(index).Name); end
if numel(unique(actualNames)) ~= numel(actualNames) || numel(actualNames) ~= numel(expectedNames) || ...
        ~isequal(sort(actualNames), sort(expectedNames))
    interfaceError("S12:Playground:StateflowInterface", blockPath, role, "<collection>", ...
        "names=" + join(sort(expectedNames), ","), "names=" + join(sort(actualNames), ","));
end
for index = 1:numel(expectedNames)
    name = expectedNames(index);
    match = find(strcmp(actualNames, name));
    if numel(match) ~= 1 || ~isfield(expectedShapes, name)
        interfaceError("S12:Playground:StateflowInterface", blockPath, role, name, "exactly one expected name", ...
            "matches=" + string(numel(match)));
    end
    shape = expectedShapes.(name);
    configureData(data(match), shape, blockPath, name, role);
end
end

function configureData(data, shape, blockPath, name, role)
if ~isprop(data, "Props")
    interfaceError("S12:Playground:StateflowProperty", blockPath, role, name, "Props available", "Props missing");
end
expectedSize = sprintf("[%d,%d]", shape(1), shape(2));
data.Props.Array.Size = expectedSize;
if role == "output"
    data.Props.Array.IsDynamic = false;
end
data.Props.Type.Method = "Built-in";
data.DataType = "double";
verifyConfiguredData(data, shape, blockPath, name, role);
end

function verifyConfiguredData(data, shape, blockPath, name, role)
if role == "input"
    expectedScope = "Input";
elseif role == "output"
    expectedScope = "Output";
else
    interfaceError("S12:Playground:StateflowRole", blockPath, role, name, "input or output", role);
end
expected = struct("size", double(shape(:).'), "dynamic", false, "data_type", "double", "scope", expectedScope);
actual = struct("size", s12_sound_playground_parse_fixed_size(data.Props.Array.Size, blockPath, "Stateflow", name), ...
    "dynamic", logical(data.Props.Array.IsDynamic), ...
    "data_type", string(data.DataType), ...
    "scope", string(data.Scope));
if ~isequal(actual.size, expected.size)
    interfaceError("S12:Playground:StateflowShape", blockPath, role, name, mat2str(expected.size), mat2str(actual.size));
end
if role == "output" && ~isequal(actual.dynamic, expected.dynamic)
    interfaceError("S12:Playground:StateflowDynamic", blockPath, role, name, string(expected.dynamic), string(actual.dynamic));
end
if ~strcmp(actual.data_type, expected.data_type)
    interfaceError("S12:Playground:StateflowDataType", blockPath, role, name, expected.data_type, actual.data_type);
end
if ~strcmp(actual.scope, expected.scope)
    interfaceError("S12:Playground:StateflowScope", blockPath, role, name, expected.scope, actual.scope);
end
end

function interfaceError(identifier, blockPath, role, name, expected, actual)
error(identifier, "block=%s role=%s name=%s expected=%s actual=%s", blockPath, role, name, expected, actual);
end
