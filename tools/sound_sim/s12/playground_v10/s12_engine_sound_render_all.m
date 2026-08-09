function results = s12_engine_sound_render_all(varargin)
%S12_ENGINE_SOUND_RENDER_ALL Render deterministic offline auditions by profile.

parser = inputParser;
parser.addParameter("ProfileIds", strings(1, 0));
parser.addParameter("BackfireLevel", "");
parser.addParameter("Play", false, @(value)islogical(value) && isscalar(value));
parser.addParameter("RunId", "");
parser.parse(varargin{:});
ids = string(parser.Results.ProfileIds);
if isempty(ids)
    listed = s12_engine_sound_list_profiles();
    ids = string({listed.id});
end
if ~isvector(ids) || any(strlength(ids) == 0)
    error("S12:EngineSoundV10:ProfileIds", "ProfileIds must be a nonempty string vector.");
end
results = repmat(struct("profile_id", "", "backfire_level", "", "output_directory", "", ...
    "sample_rate_hz", 0, "frame_count", 0, "pcm_sha256", ""), 1, numel(ids));
for index = 1:numel(ids)
    results(index) = s12_engine_sound_audition(ids(index), ...
        "BackfireLevel", parser.Results.BackfireLevel, "Play", parser.Results.Play, ...
        "RunId", parser.Results.RunId);
end
end
