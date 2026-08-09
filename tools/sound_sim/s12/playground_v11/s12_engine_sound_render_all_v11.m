function results = s12_engine_sound_render_all_v11(varargin)
%S12_ENGINE_SOUND_RENDER_ALL_V11 Render all requested canonical v1.1 profiles.
% The all-eight runtime path is authored here but remains NOT_RUNTIME_VERIFIED
% until it runs through the one safe, user-started shared MATLAB Desktop.

parser = inputParser;
parser.addParameter("ProfileIds", s12_v11_canonical_vehicle_ids());
parser.addParameter("BackfireLevel", "subtle");
parser.addParameter("Play", false, @(value)islogical(value) && isscalar(value));
parser.addParameter("RunId", "");
parser.addParameter("ScenarioKey", "s12-v11-render-all");
parser.parse(varargin{:});
ids = string(parser.Results.ProfileIds);
if ~isvector(ids) || isempty(ids) || any(strlength(ids) == 0)
    error("S12:EngineSoundV11:ProfileId", "ProfileIds must be a nonempty vector of canonical IDs.");
end
ids = reshape(ids, 1, []);
for index = 1:numel(ids)
    ids(index) = s12_v11_validate_canonical_vehicle_id(ids(index));
end
if numel(unique(ids)) ~= numel(ids)
    error("S12:EngineSoundV11:ProfileId", "ProfileIds must not contain duplicates.");
end
runId = string(parser.Results.RunId);
if strlength(runId) == 0
    runId = "run_" + string(datetime("now", Format="yyyyMMdd_HHmmss_SSS"));
end
template = struct("profile_id", "", "output_directory", "", "sample_rate_hz", 0, ...
    "frame_count", 0, "sample_count", 0, "pcm_sha256", "", "manifest_sha256", "", ...
    "variant", "", "perspective", "");
results = repmat(template, 1, numel(ids));
for index = 1:numel(ids)
    results(index) = s12_engine_sound_audition(ids(index), ...
        "BackfireLevel", parser.Results.BackfireLevel, ...
        "Play", parser.Results.Play, ...
        "RunId", runId, ...
        "ScenarioKey", string(parser.Results.ScenarioKey) + "|" + ids(index));
end
end
