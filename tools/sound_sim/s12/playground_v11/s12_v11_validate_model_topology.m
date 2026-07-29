function s12_v11_validate_model_topology(contract, actualChain)
%S12_V11_VALIDATE_MODEL_TOPOLOGY Fail closed on an invalid wrapper contract.

if ~isstruct(contract) || ~isscalar(contract) || ...
        ~isfield(contract, "required_chain") || ~isfield(contract, "port_contract") || ...
        ~isfield(contract, "pcm_size") || ~isfield(contract, "dashboard_blocks") || ...
        ~isfield(contract, "vehicle_id")
    error("S12:EngineSoundV11:ModelTopology", "Model contract is incomplete.");
end
requiredChain = string(contract.required_chain);
expectedChain = ["Vehicle State", "Vehicle Excitation Afterfire", ...
    "PTR Radiation Model Reference", "Stereo Renderer", "PCM Output"];
if ~isequal(requiredChain, expectedChain)
    error("S12:EngineSoundV11:ModelTopology", ...
        "required_chain must be Vehicle State -> Excitation/Afterfire -> PTR/Radiation -> Renderer -> PCM.");
end
profile = s12_v11_load_profile(contract.vehicle_id);
dashboardControls = s12_v11_model_dashboard_controls(profile);
expectedDashboard = string({dashboardControls.dashboard_name});
if numel(expectedDashboard) ~= 12 || numel(unique(expectedDashboard)) ~= 12
    error("S12:EngineSoundV11:ModelTopology", ...
        "The JSON-backed Dashboard contract must define exactly twelve unique controls.");
end
if ~isequal(string(contract.dashboard_blocks), expectedDashboard)
    error("S12:EngineSoundV11:ModelTopology", ...
        "The dashboard control contract must match the JSON-backed twelve-control contract.");
end
if nargin < 2
    actualChain = requiredChain;
end
if ~isequal(string(actualChain), requiredChain)
    error("S12:EngineSoundV11:ModelTopology", ...
        "The root source-to-PCM topology differs from required_chain.");
end
if ~isequal(contract.pcm_size, [960,2]) || ...
        string(contract.port_contract.pcm_output) ~= "[960,2]" || ...
        string(contract.port_contract.afterfire_insertion_stage) ~= "before_ptr_radiation" || ...
        logical(contract.port_contract.post_ptr_design_permitted)
    error("S12:EngineSoundV11:ModelTopology", ...
        "The [960,2] PCM and before_ptr_radiation port contract is invalid.");
end
end
