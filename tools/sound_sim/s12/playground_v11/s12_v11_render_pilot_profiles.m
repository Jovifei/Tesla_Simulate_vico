function results = s12_v11_render_pilot_profiles(varargin)
%S12_V11_RENDER_PILOT_PROFILES Render or publish the three v1.1 pilots.

parser = inputParser;
parser.addParameter("Publish", false, @(value)islogical(value) && isscalar(value));
parser.addParameter("Play", false, @(value)islogical(value) && isscalar(value));
parser.addParameter("AfterfireLevel", "subtle");
parser.addParameter("RunId", "");
parser.addParameter("FrameIndices", []);
parser.addParameter("ScenarioKey", "s12-v11-pilots");
parser.parse(varargin{:});
pilots = ["hellcat_2022_stock", "c63_w204_facelift_stock", "ferrari_458_stock"];
if parser.Results.Publish
    runId = string(parser.Results.RunId);
    if strlength(runId) == 0
        runId = "run_" + string(datetime("now", Format="yyyyMMdd_HHmmss_SSS"));
    end
    first = s12_v11_audition_profile(pilots(1), ...
        "AfterfireLevel", parser.Results.AfterfireLevel, ...
        "Play", parser.Results.Play, "RunId", runId, ...
        "ScenarioKey", string(parser.Results.ScenarioKey) + "|" + pilots(1));
    results = repmat(first, 1, numel(pilots));
    for index = 2:numel(pilots)
        results(index) = s12_v11_audition_profile(pilots(index), ...
            "AfterfireLevel", parser.Results.AfterfireLevel, ...
            "Play", parser.Results.Play, "RunId", runId, ...
            "ScenarioKey", string(parser.Results.ScenarioKey) + "|" + pilots(index));
    end
else
    first = s12_v11_render_profile(pilots(1), ...
        "AfterfireLevel", parser.Results.AfterfireLevel, ...
        "FrameIndices", parser.Results.FrameIndices, ...
        "ScenarioKey", string(parser.Results.ScenarioKey) + "|" + pilots(1));
    results = repmat(first, 1, numel(pilots));
    for index = 2:numel(pilots)
        results(index) = s12_v11_render_profile(pilots(index), ...
            "AfterfireLevel", parser.Results.AfterfireLevel, ...
            "FrameIndices", parser.Results.FrameIndices, ...
            "ScenarioKey", string(parser.Results.ScenarioKey) + "|" + pilots(index));
    end
end
end
