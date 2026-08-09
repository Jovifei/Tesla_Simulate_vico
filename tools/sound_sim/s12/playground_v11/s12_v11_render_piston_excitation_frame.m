function [excitation, nextPhaseRad, firingPhase] = s12_v11_render_piston_excitation_frame( ...
        state, character, engineEventMap, startPhaseRad, sampleRateHz, frameSamples)
%S12_V11_RENDER_PISTON_EXCITATION_FRAME Render JSON-mapped piston events before PTR.
% The event map is synthetic C-level topology, never an OEM firing assertion.

validateInputs(state, character, engineEventMap, startPhaseRad, sampleRateHz, frameSamples);
sampleIndex = (0:frameSamples - 1).';
baseFrequency = double(state.rpm) / 60;
cycleOmega = pi * baseFrequency / sampleRateHz;
firingPhase = startPhaseRad + cycleOmega * sampleIndex;
eventCount = numel(engineEventMap.firing_order);
sharpness = max(0, min(1, double(character.pulse_sharpness)));
excitation = zeros(frameSamples, 1);
for eventIndex = 1:eventCount
    eventIdentifier = engineEventMap.firing_order(eventIndex);
    eventPhaseRad = 2 * pi * engineEventMap.firing_phases_deg(eventIndex) / 720;
    bank = engineEventMap.bank_map(eventIdentifier);
    relativePhase = firingPhase - eventPhaseRad;
    harmonic = sin(eventCount * relativePhase) + ...
        sharpness * sin(2 * eventCount * relativePhase);
    bankGeometry = 1 + 0.15 * bank * sin(relativePhase);
    excitation = excitation + bankGeometry .* ( ...
        character.firing_gain * harmonic + ...
        character.firing_harmonic_gain * sharpness * sin(3 * eventCount * relativePhase));
end
excitation = excitation / eventCount;
nextPhaseRad = mod(startPhaseRad + cycleOmega * frameSamples, 2 * pi);
if ~isequal(size(excitation), [frameSamples, 1]) || any(~isfinite(excitation), "all")
    error("S12:EngineSoundV11:PistonFrame", ...
        "Piston excitation must be one finite [frameSamples,1] pressure frame.");
end
end

function validateInputs(state, character, engineEventMap, startPhaseRad, sampleRateHz, frameSamples)
requiredState = ["rpm"];
requiredCharacter = ["cylinders", "firing_gain", "firing_harmonic_gain", "pulse_sharpness"];
requiredMap = ["configuration", "layout", "firing_order", "firing_phases_deg", "bank_map"];
if ~isstruct(state) || ~all(isfield(state, requiredState)) || ...
        ~isstruct(character) || ~all(isfield(character, requiredCharacter)) || ...
        ~isstruct(engineEventMap) || ~all(isfield(engineEventMap, requiredMap)) || ...
        string(engineEventMap.configuration) ~= "piston" || ...
        ~isnumeric(startPhaseRad) || ~isscalar(startPhaseRad) || ~isfinite(startPhaseRad) || ...
        ~isnumeric(sampleRateHz) || ~isscalar(sampleRateHz) || sampleRateHz <= 0 || ...
        ~isnumeric(frameSamples) || ~isscalar(frameSamples) || frameSamples <= 0 || frameSamples ~= floor(frameSamples)
    error("S12:EngineSoundV11:PistonFrame", "Piston frame inputs violate the scalar/map contract.");
end
firingOrder = reshape(double(engineEventMap.firing_order), 1, []);
firingPhases = reshape(double(engineEventMap.firing_phases_deg), 1, []);
bankMap = reshape(double(engineEventMap.bank_map), 1, []);
eventCount = double(character.cylinders);
if ~isnumeric(state.rpm) || ~isscalar(state.rpm) || ~isfinite(state.rpm) || ...
        ~isnumeric(eventCount) || ~isscalar(eventCount) || eventCount < 1 || eventCount ~= floor(eventCount) || ...
        numel(firingOrder) ~= eventCount || numel(firingPhases) ~= eventCount || numel(bankMap) ~= eventCount || ...
        any(firingOrder ~= floor(firingOrder)) || ~isequal(sort(firingOrder), 1:eventCount) || ...
        numel(unique(firingOrder)) ~= eventCount || any(firingPhases < 0 | firingPhases >= 720) || ...
        numel(unique(firingPhases)) ~= eventCount || any(~ismember(bankMap, [-1, 0, 1]))
    error("S12:EngineSoundV11:PistonFrame", "Piston event mapping is invalid.");
end
end
