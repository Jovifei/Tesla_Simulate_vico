function [pressureFrame, diagnostics] = s12_v11_render_afterfire_pressure_frame(events, frameStartS, sampleRateHz, frameSamples, scenarioKey)
%S12_V11_RENDER_AFTERFIRE_PRESSURE_FRAME Render synthetic pressure before PTR.
% The source combines a non-resonant pressure body with a short,
% deterministically band-limited crack. Vehicle ringing remains downstream.

validateFrameContract(events, frameStartS, sampleRateHz, frameSamples, scenarioKey);
pressureFrame = zeros(frameSamples, 1);
contributionTemplate = struct("event_time_s", 0, "kind", "", ...
    "energy", 0, "body_peak", 0, "crack_peak", 0);
contributions = repmat(contributionTemplate, 0, 1);
bodyLength = max(8, round(0.012 * sampleRateHz));
crackLength = max(8, round(0.006 * sampleRateHz));
componentLength = max(bodyLength, crackLength);

for eventIndex = 1:numel(events)
    event = events(eventIndex);
    validateEvent(event);
    eventSample = round((double(event.time_s) - frameStartS) * sampleRateHz) + 1;
    sourceFirst = max(1, 2 - eventSample);
    sourceLast = min(componentLength, frameSamples - eventSample + 1);
    if sourceFirst > sourceLast
        continue;
    end

    bodyTime = (0:bodyLength - 1).' / sampleRateHz;
    pressureBody = exp(-bodyTime / 0.0014) - 0.34 * exp(-bodyTime / 0.0048);
    pressureBody = pressureBody / max(max(abs(pressureBody)), eps);
    pressureBody = [pressureBody; zeros(componentLength - bodyLength, 1)];

    crack = deterministicNoise(crackLength, string(event.cluster_id) + "|" + ...
        string(event.kind) + "|" + string(event.time_s));
    crack = [crack(1); diff(crack)];
    crack = conv(crack, ones(7, 1) / 7, "same");
    crackTime = (0:crackLength - 1).' / sampleRateHz;
    crack = crack .* exp(-crackTime / 0.0018);
    crack = crack / max(max(abs(crack)), eps);
    crack = [crack; zeros(componentLength - crackLength, 1)];

    variation = max(-1, min(1, double(event.variation)));
    crackMix = 0.27 + 0.06 * variation;
    bodyMix = 1 - crackMix;
    component = double(event.energy) * (bodyMix * pressureBody + crackMix * crack);
    target = eventSample + (sourceFirst:sourceLast) - 1;
    pressureFrame(target) = pressureFrame(target) + component(sourceFirst:sourceLast);

    contribution = contributionTemplate;
    contribution.event_time_s = double(event.time_s);
    contribution.kind = string(event.kind);
    contribution.energy = double(event.energy);
    contribution.body_peak = double(event.energy) * bodyMix;
    contribution.crack_peak = double(event.energy) * crackMix;
    contributions(end + 1, 1) = contribution; %#ok<AGROW>
end

if any(~isfinite(pressureFrame))
    error("S12:EngineSoundV11:PressureFrame", "Afterfire pressure frame became nonfinite.");
end
diagnostics = struct( ...
    "insertion_stage", "before_ptr_radiation", ...
    "post_pcm_append", false, ...
    "source_event_count", numel(events), ...
    "rendered_event_count", numel(contributions), ...
    "frame_start_s", double(frameStartS), ...
    "sample_rate_hz", double(sampleRateHz), ...
    "frame_samples", double(frameSamples), ...
    "body_model", "nonresonant_pressure_impulse", ...
    "crack_model", "short_deterministic_band_limited_noise", ...
    "contributions", contributions, ...
    "causality_chain", ["state", "eligibility", "events", ...
        "pre_ptr_pressure_excitation", "ptr_radiation"]);
end

function validateFrameContract(events, frameStartS, sampleRateHz, frameSamples, scenarioKey)
if ~(isstruct(events) || isempty(events))
    error("S12:EngineSoundV11:PressureFrame", "events must be a struct array.");
end
if ~isnumeric(frameStartS) || ~isscalar(frameStartS) || ~isfinite(frameStartS)
    error("S12:EngineSoundV11:PressureFrame", "frameStartS must be finite.");
end
if ~isnumeric(sampleRateHz) || ~isscalar(sampleRateHz) || ~isfinite(sampleRateHz) || sampleRateHz <= 0
    error("S12:EngineSoundV11:PressureFrame", "sampleRateHz must be positive and finite.");
end
if ~isnumeric(frameSamples) || ~isscalar(frameSamples) || ~isfinite(frameSamples) || ...
        frameSamples < 1 || frameSamples ~= floor(frameSamples)
    error("S12:EngineSoundV11:PressureFrame", "frameSamples must be a positive integer.");
end
if ~((ischar(scenarioKey) && isrow(scenarioKey)) || (isstring(scenarioKey) && isscalar(scenarioKey)))
    error("S12:EngineSoundV11:ScenarioKey", "scenarioKey must be one text scalar.");
end
end

function validateEvent(event)
required = ["time_s", "kind", "location", "energy", "cluster_id", ...
    "variation", "eligibility_explanation"];
if ~isstruct(event) || ~isscalar(event) || ~all(isfield(event, cellstr(required)))
    error("S12:EngineSoundV11:PressureFrame", "Each event must satisfy the afterfire event contract.");
end
if ~isnumeric(event.time_s) || ~isscalar(event.time_s) || ~isfinite(event.time_s) || ...
        ~isnumeric(event.energy) || ~isscalar(event.energy) || ~isfinite(event.energy) || event.energy < 0 || ...
        ~isnumeric(event.variation) || ~isscalar(event.variation) || ~isfinite(event.variation)
    error("S12:EngineSoundV11:PressureFrame", "Event time, energy, and variation must be finite.");
end
if string(event.location) ~= "pre_ptr_exhaust_source"
    error("S12:EngineSoundV11:PressureFrame", "Afterfire events must target the pre-PTR source.");
end
end

function values = deterministicNoise(count, key)
seed = deterministicSeed(key);
values = zeros(count, 1);
for index = 1:count
    seed = mod(1664525 * seed + 1013904223, 2 ^ 32);
    values(index) = 2 * (seed / (2 ^ 32 - 1)) - 1;
end
end

function seed = deterministicSeed(key)
codes = double(char(string(key)));
seed = 216613;
for index = 1:numel(codes)
    seed = mod(seed * 131 + codes(index), 2147483647);
end
end
