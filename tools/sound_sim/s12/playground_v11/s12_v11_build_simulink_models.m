function results = s12_v11_build_simulink_models(varargin)
%S12_V11_BUILD_SIMULINK_MODELS Build v1.1 wrappers in one visible Desktop.
% This is intentionally opt-in: never call it through batch/nodesktop or an
% unapproved MCP control plane.  The caller must have the one user-started
% visible MATLAB Desktop already stable.

parser = inputParser;
parser.addParameter("AllowModelCreation", false, @(value)islogical(value) && isscalar(value));
parser.addParameter("ExpectedFrozenPtrAdapterSha256", ...
    "3ce53f44883686ed2fa10a6c5b20cfe15d11b813ff75fb164489c62a241020e1");
parser.parse(varargin{:});
if ~parser.Results.AllowModelCreation
    error("S12:EngineSoundV11:DesktopGate", ...
        "Set AllowModelCreation=true only in the approved existing visible Desktop.");
end
if ~usejava("desktop")
    error("S12:EngineSoundV11:DesktopGate", ...
        "v1.1 model creation requires the existing visible MATLAB Desktop.");
end

contracts = s12_v11_model_contracts();
frozenAdapter = s12_v11_resolve_frozen_ptr_adapter( ...
    parser.Results.ExpectedFrozenPtrAdapterSha256);
ensureCanonicalAdapterOnPath(frozenAdapter);
for contract = contracts
    s12_v11_validate_model_topology(contract, contract.required_chain);
end
buildSharedCore(contracts(1));
results = repmat(struct("vehicle_id", "", "model_name", "", "model_path", "", ...
    "core_model_name", "", "core_model_path", "", "pcm_size", [960,2], ...
    "frozen_ptr_adapter_path", "", "frozen_ptr_adapter_sha256", ""), 1, numel(contracts));
for index = 1:numel(contracts)
    contract = contracts(index);
    buildVehicleWrapper(contract);
    results(index) = struct( ...
        "vehicle_id", contract.vehicle_id, ...
        "model_name", contract.model_name, ...
        "model_path", contract.model_path, ...
        "core_model_name", contract.core_model_name, ...
        "core_model_path", contract.core_model_path, ...
        "pcm_size", contract.pcm_size, ...
        "frozen_ptr_adapter_path", frozenAdapter.source_path, ...
        "frozen_ptr_adapter_sha256", frozenAdapter.sha256);
end
end

function buildSharedCore(contract)
coreFolder = fileparts(contract.core_model_path);
if ~isfolder(coreFolder)
    mkdir(coreFolder);
end
addpath(coreFolder);
prepareModel(contract.core_model_name, contract.core_model_path);
model = contract.core_model_name;
configureDiscreteFrameTiming(model);
add_block("simulink/Ports & Subsystems/In1", model + "/Excitation", ...
    "PortDimensions", "[960 1]", "Position", [40, 80, 70, 100]);
add_block("simulink/Ports & Subsystems/In1", model + "/Profile Index", ...
    "PortDimensions", "1", "Position", [40, 140, 70, 160]);
add_block("simulink/Ports & Subsystems/In1", model + "/PTR Controls", ...
    "PortDimensions", "[4 1]", "Position", [40, 200, 70, 220]);
addMuxBlock(model + "/PTR Input Mux", 3, [115, 70, 120, 190]);
addMatlabFcnBlock(model + "/PTR Radiation Adapter", ...
    "s12_v11_model_ptr_radiation_step(u)", "[960 1]", [170, 58, 340, 122]);
add_block("simulink/Ports & Subsystems/Out1", model + "/Pressure", ...
    "Position", [410, 80, 440, 100]);
add_line(model, "Excitation/1", "PTR Input Mux/1", "autorouting", "on");
add_line(model, "Profile Index/1", "PTR Input Mux/2", "autorouting", "on");
add_line(model, "PTR Controls/1", "PTR Input Mux/3", "autorouting", "on");
add_line(model, "PTR Input Mux/1", "PTR Radiation Adapter/1", "autorouting", "on");
add_line(model, "PTR Radiation Adapter/1", "Pressure/1", "autorouting", "on");
validateSharedCore(model);
save_system(model, contract.core_model_path);
end

function buildVehicleWrapper(contract)
modelFolder = fileparts(contract.model_path);
if ~isfolder(modelFolder)
    error("S12:EngineSoundV11:ModelBuild", "Vehicle package folder is missing: %s", modelFolder);
end
addpath(fileparts(contract.core_model_path));
prepareModel(contract.model_name, contract.model_path);
model = contract.model_name;
configureDiscreteFrameTiming(model);
profile = s12_v11_load_profile(contract.vehicle_id);
profileIndex = find(s12_v11_canonical_vehicle_ids() == contract.vehicle_id, 1, "first");
[controls, controlNames, stateMux] = addDashboardControls(model, contract, profile);
add_block("simulink/Sources/Clock", model + "/Timeline Clock", ...
    "Position", [35, 860, 95, 880]);
addMatlabFcnBlock(model + "/Vehicle State", ...
    "s12_v11_model_vehicle_state_step(u, " + string(profileIndex) + ")", "[21 1]", [220, 90, 380, 130]);
addMuxBlock(model + "/Excitation Clock Mux", 2, [405, 68, 410, 140]);
addMatlabFcnBlock(model + "/Vehicle Excitation Afterfire", ...
    "s12_v11_model_excitation_afterfire_step(u, '" + contract.vehicle_id + "')", ...
    "[960 1]", [450, 76, 650, 144]);
add_block("simulink/Ports & Subsystems/Model", ...
    model + "/PTR Radiation Model Reference", "Position", [725, 76, 925, 144]);
set_param(model + "/PTR Radiation Model Reference", "ModelName", contract.core_model_name);
addMatlabFcnBlock(model + "/PTR Control Selector", ...
    "s12_v11_model_ptr_controls_step(u, " + string(profileIndex) + ")", "[4 1]", [470, 200, 650, 240]);
addMatlabFcnBlock(model + "/Renderer Gain Selector", ...
    "s12_v11_model_renderer_gain_step(u, " + string(profileIndex) + ")", "[1 1]", [740, 200, 900, 240]);
addMuxBlock(model + "/Renderer Input Mux", 2, [950, 72, 955, 144]);
add_block("simulink/Sources/Constant", model + "/Vehicle Profile Index", ...
    "Value", num2str(profileIndex), "SampleTime", "0.02", "Position", [675, 175, 710, 195]);
addStereoRenderer(model + "/Stereo Renderer", profileIndex);
add_block("simulink/Ports & Subsystems/Out1", model + "/PCM Output", ...
    "Position", [1190, 95, 1220, 115]);
for index = 1:numel(controlNames)
    add_line(model, controlNames(index) + "/1", stateMux + "/" + string(index), "autorouting", "on");
end
add_line(model, "Timeline Clock/1", stateMux + "/" + string(numel(controlNames) + 1), "autorouting", "on");
add_line(model, stateMux + "/1", "Vehicle State/1", "autorouting", "on");
add_line(model, "Vehicle State/1", "Excitation Clock Mux/1", "autorouting", "on");
add_line(model, "Timeline Clock/1", "Excitation Clock Mux/2", "autorouting", "on");
add_line(model, "Excitation Clock Mux/1", "Vehicle Excitation Afterfire/1", "autorouting", "on");
add_line(model, "Vehicle State/1", "PTR Control Selector/1", "autorouting", "on");
add_line(model, "Vehicle State/1", "Renderer Gain Selector/1", "autorouting", "on");
add_line(model, "Vehicle Excitation Afterfire/1", "PTR Radiation Model Reference/1", "autorouting", "on");
add_line(model, "Vehicle Profile Index/1", "PTR Radiation Model Reference/2", "autorouting", "on");
add_line(model, "PTR Control Selector/1", "PTR Radiation Model Reference/3", "autorouting", "on");
add_line(model, "PTR Radiation Model Reference/1", "Renderer Input Mux/1", "autorouting", "on");
add_line(model, "Renderer Gain Selector/1", "Renderer Input Mux/2", "autorouting", "on");
add_line(model, "Renderer Input Mux/1", "Stereo Renderer/1", "autorouting", "on");
add_line(model, "Stereo Renderer/1", "PCM Output/1", "autorouting", "on");
validateWrapperTopology(model, contract, controls, controlNames, stateMux);
s12_v11_validate_model_topology(contract, contract.required_chain);
save_system(model, contract.model_path);
end

function [controls, controlNames, stateMux] = addDashboardControls(model, contract, profile)
controls = s12_v11_model_dashboard_controls(profile);
controlNames = string({controls.control_name});
if ~isequal(string({controls.dashboard_name}), string(contract.dashboard_blocks))
    error("S12:EngineSoundV11:ModelBuild", "Dashboard contract differs from validated JSON controls.");
end
for index = 1:numel(controlNames)
    top = 55 + 65 * (index - 1);
    add_block("simulink/Sources/Constant", model + "/" + controlNames(index), ...
        "Value", num2str(controls(index).default, 16), "SampleTime", "0.02", ...
        "Position", [35, top, 95, top + 25]);
    knobPath = model + "/" + controls(index).dashboard_name;
    add_block("simulink_hmi_blocks/Knob", knobPath, ...
        "Position", [35, top - 45, 105, top - 5]);
    binding = Simulink.HMI.ParamSourceInfo;
    binding.BlockPath = Simulink.BlockPath(char(model + "/" + controlNames(index)));
    binding.ParamName = 'Value';
    set_param(knobPath, "Binding", binding);
    set_param(knobPath, "Limits", controls(index).hmi_limits);
end
stateMux = "Dashboard State Mux";
add_block("simulink/Signal Routing/Mux", model + "/" + stateMux, ...
    "Inputs", num2str(numel(controls) + 1), "Position", [150, 90, 155, 155]);
end

function addStereoRenderer(rendererPath, profileIndex)
addMatlabFcnBlock(rendererPath, ...
    "s12_v11_model_stereo_renderer_step(u, " + string(profileIndex) + ")", ...
    "[960 2]", [1000, 76, 1140, 144]);
end

function addMuxBlock(blockPath, inputs, position)
add_block("simulink/Signal Routing/Mux", blockPath, "Inputs", num2str(inputs), ...
    "Position", position);
end

function addMatlabFcnBlock(blockPath, expression, outputDimensions, position)
add_block("simulink/User-Defined Functions/MATLAB Fcn", blockPath, ...
    "MATLABFcn", expression, "Output1D", "off", ...
    "OutputDimensions", outputDimensions, ...
    "Position", position);
end

function prepareModel(modelName, modelPath)
if bdIsLoaded(modelName)
    close_system(modelName, 0);
end
if isfile(modelPath)
    load_system(modelPath);
else
    new_system(modelName);
end
lines = find_system(modelName, "FindAll", "on", "SearchDepth", 1, "Type", "line");
if ~isempty(lines)
    delete_line(lines);
end
blocks = find_system(modelName, "SearchDepth", 1, "Type", "Block");
for index = 1:numel(blocks)
    delete_block(blocks{index});
end
end

function configureDiscreteFrameTiming(model)
set_param(model, "SolverType", "Fixed-step", "Solver", "FixedStepDiscrete", ...
    "FixedStep", "0.02", "StopTime", "90");
end

function validateSharedCore(model)
expected = ["Excitation", "Profile Index", "PTR Controls", "PTR Input Mux", "PTR Radiation Adapter", "Pressure"];
validateRequiredBlocks(model, expected, ["Inport", "Inport", "Inport", "Mux", "MATLABFcn", "Outport"]);
validateMuxWidth(model, "PTR Input Mux", 3);
validateSingleInputInterpretedFcn(model, "PTR Radiation Adapter");
if ~hasConnection(model, "Excitation", "PTR Input Mux") || ...
        ~hasConnection(model, "Profile Index", "PTR Input Mux") || ...
        ~hasConnection(model, "PTR Controls", "PTR Input Mux") || ...
        ~hasConnection(model, "PTR Input Mux", "PTR Radiation Adapter") || ...
        ~hasConnection(model, "PTR Radiation Adapter", "Pressure")
    error("S12:EngineSoundV11:ModelTopology", ...
        "Shared PTR/Radiation core failed its physical adapter connection contract.");
end
end

function validateWrapperTopology(model, contract, controls, controlNames, stateMux)
validateRequiredBlocks(model, contract.required_chain, ...
    ["MATLABFcn", "MATLABFcn", "ModelReference", "MATLABFcn", "Outport"]);
validateRequiredBlocks(model, controlNames, repmat("Constant", 1, numel(controlNames)));
validateRequiredBlocks(model, stateMux, "Mux");
validateRequiredBlocks(model, ["Timeline Clock", "Excitation Clock Mux", "PTR Control Selector", ...
    "Renderer Gain Selector", "Renderer Input Mux"], ...
    ["Clock", "Mux", "MATLABFcn", "MATLABFcn", "Mux"]);
validateMuxWidth(model, "Excitation Clock Mux", 2);
validateMuxWidth(model, "Renderer Input Mux", 2);
for blockName = ["Vehicle State", "Vehicle Excitation Afterfire", ...
        "PTR Control Selector", "Renderer Gain Selector", "Stereo Renderer"]
    validateSingleInputInterpretedFcn(model, blockName);
end
for index = 1:numel(contract.dashboard_blocks)
    dashboardPath = model + "/" + contract.dashboard_blocks(index);
    expectedControlPath = model + "/" + controlNames(index);
    validateDashboardBinding(dashboardPath, expectedControlPath);
end
for index = 1:numel(contract.required_chain) - 1
    sourceName = contract.required_chain(index);
    destinationName = contract.required_chain(index + 1);
    if sourceName == "Vehicle State" && destinationName == "Vehicle Excitation Afterfire"
        connected = hasConnection(model, sourceName, "Excitation Clock Mux") && ...
            hasConnection(model, "Excitation Clock Mux", destinationName);
    elseif sourceName == "PTR Radiation Model Reference" && destinationName == "Stereo Renderer"
        connected = hasConnection(model, sourceName, "Renderer Input Mux") && ...
            hasConnection(model, "Renderer Input Mux", destinationName);
    else
        connected = hasConnection(model, sourceName, destinationName);
    end
    if ~connected
        error("S12:EngineSoundV11:ModelTopology", ...
            "Top-level wrapper chain differs from the before-PTR afterfire contract.");
    end
end
for index = 1:numel(controlNames)
    if ~hasConnection(model, controlNames(index), stateMux)
        error("S12:EngineSoundV11:ModelTopology", ...
            "Each bound Dashboard control must feed Vehicle State through the state mux.");
    end
end
if ~hasConnection(model, stateMux, "Vehicle State")
    error("S12:EngineSoundV11:ModelTopology", ...
        "Dashboard State Mux must feed the Vehicle State model function.");
end
if ~hasConnection(model, "Timeline Clock", stateMux) || ...
        ~hasConnection(model, "Timeline Clock", "Excitation Clock Mux") || ...
        ~hasConnection(model, "Vehicle State", "Excitation Clock Mux") || ...
        ~hasConnection(model, "Excitation Clock Mux", "Vehicle Excitation Afterfire") || ...
        ~hasConnection(model, "Vehicle State", "PTR Control Selector") || ...
        ~hasConnection(model, "PTR Control Selector", "PTR Radiation Model Reference") || ...
        ~hasConnection(model, "Vehicle State", "Renderer Gain Selector") || ...
        ~hasConnection(model, "Renderer Gain Selector", "Renderer Input Mux") || ...
        ~hasConnection(model, "Renderer Input Mux", "Stereo Renderer")
    error("S12:EngineSoundV11:ModelTopology", ...
        "Dashboard-derived state must reach the PTR and renderer control consumers.");
end
if numel(controls) ~= numel(contract.dashboard_blocks)
    error("S12:EngineSoundV11:ModelTopology", "Dashboard control count does not match the contract.");
end
end

function validateMuxWidth(model, blockName, expectedInputs)
actual = str2double(string(get_param(model + "/" + blockName, "Inputs")));
if ~isscalar(actual) || actual ~= expectedInputs
    error("S12:EngineSoundV11:ModelTopology", ...
        "Mux %s must expose exactly %d inputs.", blockName, expectedInputs);
end
end

function validateSingleInputInterpretedFcn(model, blockName)
blockPath = model + "/" + blockName;
if string(get_param(blockPath, "BlockType")) ~= "MATLABFcn"
    error("S12:EngineSoundV11:ModelTopology", ...
        "Interpreted function %s has the wrong block type.", blockName);
end
ports = get_param(blockPath, "PortHandles");
if numel(ports.Inport) ~= 1
    error("S12:EngineSoundV11:ModelTopology", ...
        "Interpreted function %s must expose exactly one input port.", blockName);
end
line = get_param(ports.Inport(1), "Line");
if isequal(line, -1)
    error("S12:EngineSoundV11:ModelTopology", ...
        "Interpreted function %s must have its one input connected.", blockName);
end
destinations = get_param(line, "DstPortHandle");
if ~any(destinations == ports.Inport(1))
    error("S12:EngineSoundV11:ModelTopology", ...
        "Interpreted function %s input line does not terminate at its only input port.", blockName);
end
end

function validateDashboardBinding(dashboardPath, expectedControlPath)
if string(get_param(dashboardPath, "BlockType")) ~= "KnobBlock"
    error("S12:EngineSoundV11:ModelTopology", "Dashboard block must be a Knob.");
end
binding = get_param(dashboardPath, "Binding");
if isempty(binding) || ~isa(binding, "Simulink.HMI.ParamSourceInfo") || ...
        string(binding.ParamName) ~= "Value"
    error("S12:EngineSoundV11:ModelTopology", ...
        "Dashboard binding must target a tunable Constant Value parameter.");
end
boundBlockPath = string(getBlock(binding.BlockPath, 1));
if boundBlockPath ~= string(expectedControlPath)
    error("S12:EngineSoundV11:ModelTopology", ...
        "Dashboard binding does not resolve to its corresponding control Constant.");
end
end

function ensureCanonicalAdapterOnPath(frozenAdapter)
addpath(frozenAdapter.source_folder, "-begin");
resolvedPath = string(which(frozenAdapter.function_name));
if resolvedPath ~= frozenAdapter.source_path
    error("S12:EngineSoundV11:FrozenPtrAdapter", ...
        "MATLAB path does not resolve the verified canonical frozen PTR adapter.");
end
end

function validateRequiredBlocks(model, names, expectedTypes)
names = string(names);
expectedTypes = string(expectedTypes);
if isscalar(expectedTypes)
    expectedTypes = repmat(expectedTypes, size(names));
end
if numel(names) ~= numel(expectedTypes)
    error("S12:EngineSoundV11:ModelTopology", "Block-type validation contract is inconsistent.");
end
for index = 1:numel(names)
    blockPath = model + "/" + names(index);
    if ~isValidSimulinkBlock(blockPath, expectedTypes(index))
        error("S12:EngineSoundV11:ModelTopology", ...
            "Required block %s is absent or has the wrong Simulink BlockType.", names(index));
    end
end
end

function valid = isValidSimulinkBlock(blockPath, expectedType)
valid = ishandle(get_param(blockPath, "Handle")) && ...
    string(get_param(blockPath, "BlockType")) == string(expectedType);
end

function connected = hasConnection(model, sourceName, destinationName)
sourcePorts = get_param(model + "/" + sourceName, "PortHandles");
destinationPorts = get_param(model + "/" + destinationName, "PortHandles");
if isempty(sourcePorts.Outport) || isempty(destinationPorts.Inport)
    connected = false;
    return;
end
line = get_param(sourcePorts.Outport(1), "Line");
if isequal(line, -1)
    connected = false;
    return;
end
destinations = get_param(line, "DstPortHandle");
connected = any(ismember(destinations, destinationPorts.Inport));
end
