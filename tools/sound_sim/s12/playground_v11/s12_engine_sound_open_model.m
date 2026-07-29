function modelPath = s12_engine_sound_open_model(profileInput, varargin)
%S12_ENGINE_SOUND_OPEN_MODEL Open one v1.1 wrapper only after it exists.
% The function never creates a model and fails closed when no built SLX exists.

parser = inputParser;
parser.addParameter("Open", true, @(value)islogical(value) && isscalar(value));
parser.parse(varargin{:});
profileId = s12_v11_validate_canonical_vehicle_id(profileInput);
contracts = s12_v11_model_contracts();
match = string({contracts.vehicle_id}) == profileId;
if nnz(match) ~= 1
    error("S12:EngineSoundV11:Model", "Expected exactly one v1.1 model contract.");
end
modelPath = string(contracts(match).model_path);
if parser.Results.Open
    if ~isfile(modelPath)
        error("S12:EngineSoundV11:ModelNotBuilt", ...
            "The v1.1 wrapper has not been generated: %s", modelPath);
    end
    [~, modelName] = fileparts(modelPath);
    load_system(char(modelPath));
    open_system(char(modelName));
end
end
