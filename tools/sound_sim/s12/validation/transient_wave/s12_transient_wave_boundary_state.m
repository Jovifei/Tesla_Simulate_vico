function result = s12_transient_wave_boundary_state(interiorState, ambientState, ...
        gamma, side, boundaryType)
%S12_TRANSIENT_WAVE_BOUNDARY_STATE Build validation-only boundary states.
arguments
    interiorState (3,1) double {mustBeFinite}
    ambientState (3,1) double {mustBeFinite}
    gamma (1,1) double {mustBeGreaterThan(gamma, 1), mustBeFinite}
    side (1,1) string
    boundaryType (1,1) string
end
[validSide, validBoundary] = validateBoundaryRequest(side, boundaryType);
if ~validSide || ~validBoundary
    error("S12:TransientWave:InvalidBoundary", ...
        "Boundary side or type is outside the validation-only contract.");
end
if isequal(interiorState, ambientState)
    result = fixedPointResult(interiorState, gamma, side, boundaryType);
    return
end
[rho, velocity, pressure, soundSpeed] = primitive(interiorState, gamma);
[ambientDensity, ambientVelocity, ambientPressure, ambientSoundSpeed] = ...
    primitive(ambientState, gamma);
if rho <= 0 || pressure <= 0 || ambientDensity <= 0 || ambientPressure <= 0
    error("S12:TransientWave:InvalidState", ...
        "Boundary states must have positive density and pressure.");
end
[outgoing, incomingAmbient] = characteristics(velocity, soundSpeed, ...
    ambientVelocity, ambientSoundSpeed, gamma, side);
switch boundaryType
    case "closed_rigid_end"
        state = conservative(rho, -velocity, pressure, gamma);
        incoming = -outgoing;
    case "ideal_pressure_release_open_end"
        entropyInvariant = pressure / rho^gamma;
        boundaryDensity = (ambientPressure / entropyInvariant)^(1 / gamma);
        boundarySoundSpeed = sqrt(gamma * ambientPressure / boundaryDensity);
        if side == "right"
            boundaryVelocity = outgoing - 2 * boundarySoundSpeed / (gamma - 1);
            incoming = boundaryVelocity - 2 * boundarySoundSpeed / (gamma - 1);
        else
            boundaryVelocity = outgoing + 2 * boundarySoundSpeed / (gamma - 1);
            incoming = boundaryVelocity + 2 * boundarySoundSpeed / (gamma - 1);
        end
        state = conservative(boundaryDensity, boundaryVelocity, ...
            ambientPressure, gamma);
    case "nonreflecting_reference_boundary"
        [boundaryVelocity, boundarySoundSpeed] = combineCharacteristics( ...
            outgoing, incomingAmbient, gamma, side);
        entropyInvariant = pressure / rho^gamma;
        boundaryDensity = (boundarySoundSpeed^2 / ...
            (gamma * entropyInvariant))^(1 / (gamma - 1));
        boundaryPressure = entropyInvariant * boundaryDensity^gamma;
        state = conservative(boundaryDensity, boundaryVelocity, ...
            boundaryPressure, gamma);
        incoming = incomingAmbient;
end
if any(~isfinite(state)) || state(1) <= 0 || pressureOf(state, gamma) <= 0
    error("S12:TransientWave:InvalidState", ...
        "Boundary construction produced an invalid state.");
end
result = struct( ...
    "state", state, ...
    "boundary_type", boundaryType, ...
    "side", side, ...
    "outgoing_characteristic", outgoing, ...
    "incoming_characteristic", incoming, ...
    "boundary_pressure", pressureOf(state, gamma));
end

function [validSide, validBoundary] = validateBoundaryRequest(side, boundaryType)
validSide = any(side == ["left", "right"]);
validBoundary = any(boundaryType == ["closed_rigid_end", ...
    "ideal_pressure_release_open_end", "nonreflecting_reference_boundary"]);
end

function result = fixedPointResult(state, gamma, side, boundaryType)
[~, velocity, ~, soundSpeed] = primitive(state, gamma);
if side == "right"
    outgoing = velocity + 2 * soundSpeed / (gamma - 1);
    incoming = velocity - 2 * soundSpeed / (gamma - 1);
else
    outgoing = velocity - 2 * soundSpeed / (gamma - 1);
    incoming = velocity + 2 * soundSpeed / (gamma - 1);
end
result = struct( ...
    "state", state, ...
    "boundary_type", boundaryType, ...
    "side", side, ...
    "outgoing_characteristic", outgoing, ...
    "incoming_characteristic", incoming, ...
    "boundary_pressure", pressureOf(state, gamma));
end

function [outgoing, incomingAmbient] = characteristics(u, c, ambientU, ambientC, gamma, side)
if side == "right"
    outgoing = u + 2 * c / (gamma - 1);
    incomingAmbient = ambientU - 2 * ambientC / (gamma - 1);
else
    outgoing = u - 2 * c / (gamma - 1);
    incomingAmbient = ambientU + 2 * ambientC / (gamma - 1);
end
end

function [u, c] = combineCharacteristics(outgoing, incoming, gamma, side)
if side == "right"
    u = 0.5 * (outgoing + incoming);
    c = 0.25 * (gamma - 1) * (outgoing - incoming);
else
    u = 0.5 * (outgoing + incoming);
    c = 0.25 * (gamma - 1) * (incoming - outgoing);
end
if c <= 0 || ~isfinite(c)
    error("S12:TransientWave:InvalidState", ...
        "Characteristic boundary reconstruction produced invalid sound speed.");
end
end

function [rho, u, p, c] = primitive(state, gamma)
rho = state(1);
u = state(2) / rho;
p = pressureOf(state, gamma);
c = sqrt(gamma * p / rho);
end

function p = pressureOf(state, gamma)
rho = state(1);
u = state(2) / rho;
p = (gamma - 1) * (state(3) - 0.5 * rho * u^2);
end

function state = conservative(rho, velocity, pressure, gamma)
state = [rho; rho * velocity; pressure / (gamma - 1) + ...
    0.5 * rho * velocity^2];
end
