function modelPath = s12_engine_sound_open_model(profileInput, varargin)
%S12_ENGINE_SOUND_OPEN_MODEL Load or open one independent v1.0 top model.

parser = inputParser;
parser.addParameter("Open", true, @(value)islogical(value) && isscalar(value));
parser.parse(varargin{:});
modelPath = s12_engine_sound_model_path(profileInput);
[~, model] = fileparts(modelPath);
load_system(char(modelPath));
if parser.Results.Open
    open_system(char(model));
end
end
