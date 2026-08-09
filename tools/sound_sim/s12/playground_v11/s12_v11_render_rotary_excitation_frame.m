function [excitation, nextPhaseRad, firingPhase] = s12_v11_render_rotary_excitation_frame( ...
        state, character, engineEventMap, startPhaseRad, sampleRateHz, frameSamples)
%S12_V11_RENDER_ROTARY_EXCITATION_FRAME Render a deterministic rotary source.
% This is a pre-PTR pressure excitation component, not a post-render effect.

schedule = s12_v11_rotary_event_frequency(character, double(state.rpm));
if ~isstruct(engineEventMap) || ~all(isfield(engineEventMap, ...
        ["configuration", "layout", "firing_order", "firing_phases_deg", "bank_map"])) || ...
        string(engineEventMap.configuration) ~= "rotary" || string(engineEventMap.layout) ~= "rotary" || ...
        ~isnumeric(startPhaseRad) || ~isscalar(startPhaseRad) || ~isfinite(startPhaseRad) || ...
        ~isnumeric(sampleRateHz) || ~isscalar(sampleRateHz) || sampleRateHz <= 0 || ...
        ~isnumeric(frameSamples) || ~isscalar(frameSamples) || frameSamples ~= floor(frameSamples) || frameSamples <= 0
    error("S12:EngineSoundV11:RotaryFrame", "Rotary frame inputs violate the scalar contract.");
end
sampleIndex = (0:frameSamples - 1).';
eventOmega = 2 * pi * schedule.combustion_event_hz / sampleRateHz;
firingPhase = startPhaseRad + eventOmega * sampleIndex;
validateRotaryEventMap(engineEventMap, character.rotor_count);
eventCount = numel(engineEventMap.firing_order);
eventGeometry = zeros(frameSamples, 1);
for eventIndex = 1:eventCount
    eventIdentifier = engineEventMap.firing_order(eventIndex);
    eventPhaseRad = 2 * pi * engineEventMap.firing_phases_deg(eventIndex) / 720;
    bank = engineEventMap.bank_map(eventIdentifier);
    relativePhase = firingPhase - eventPhaseRad;
    eventGeometry = eventGeometry + (1 + 0.15 * bank * sin(relativePhase)) .* ...
        sin(eventCount * relativePhase);
end
eventGeometry = eventGeometry / eventCount;
apexRatio = schedule.apex_pass_hz / max(schedule.combustion_event_hz, eps);
apexPhase = firingPhase * apexRatio;
sharpness = max(0, min(1, double(character.pulse_sharpness)));
excitation = character.firing_gain * sin(firingPhase) + ...
    character.firing_harmonic_gain * sharpness * sin(3 * firingPhase) + ...
    character.rotary_apex_gain * sin(apexPhase + pi / 5);
excitation = excitation .* (1 + sharpness * eventGeometry / 4);
nextPhaseRad = mod(startPhaseRad + eventOmega * frameSamples, 2 * pi);
if ~isequal(size(excitation), [frameSamples, 1]) || any(~isfinite(excitation), "all")
    error("S12:EngineSoundV11:RotaryFrame", ...
        "Rotary excitation must be one finite [frameSamples,1] pressure frame.");
end

function validateRotaryEventMap(engineEventMap, rotorCount)
firingOrder = reshape(double(engineEventMap.firing_order), 1, []);
firingPhases = reshape(double(engineEventMap.firing_phases_deg), 1, []);
bankMap = reshape(double(engineEventMap.bank_map), 1, []);
if ~isnumeric(rotorCount) || ~isscalar(rotorCount) || rotorCount ~= 2 || ...
        numel(firingOrder) ~= rotorCount || numel(firingPhases) ~= rotorCount || ...
        numel(bankMap) ~= rotorCount || any(firingOrder ~= floor(firingOrder)) || ...
        ~isequal(sort(firingOrder), 1:rotorCount) || numel(unique(firingOrder)) ~= rotorCount || ...
        any(firingPhases < 0 | firingPhases >= 720) || ...
        numel(unique(firingPhases)) ~= rotorCount || ~isequal(sort(bankMap), [-1, 1])
    error("S12:EngineSoundV11:RotaryFrame", "Synthetic rotary event mapping is invalid.");
end
end
end
