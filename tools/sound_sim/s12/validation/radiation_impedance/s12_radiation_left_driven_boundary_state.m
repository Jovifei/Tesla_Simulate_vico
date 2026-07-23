function result = s12_radiation_left_driven_boundary_state(interiorState, ambientState, ...
        gamma, incomingPressurePa, smallSignalLimit)
%S12_RADIATION_LEFT_DRIVEN_BOUNDARY_STATE Small-signal characteristic source.
arguments
    interiorState (3,1) double {mustBeFinite}
    ambientState (3,1) double {mustBeFinite}
    gamma (1,1) double {mustBeFinite, mustBeGreaterThan(gamma, 1)}
    incomingPressurePa (1,1) double {mustBeFinite}
    smallSignalLimit (1,1) double {mustBeFinite, mustBeGreaterThan(smallSignalLimit, 0)}
end
[rho0, ~, p0, c0] = primitive(ambientState, gamma);
[rho, velocity, pressure] = primitive(interiorState, gamma);
if rho0 <= 0 || p0 <= 0 || rho <= 0 || pressure <= 0
    error("S12:Radiation:InvalidState", "Driven boundary requires positive states.");
end
if abs(incomingPressurePa) > smallSignalLimit * p0
    error("S12:Radiation:SmallSignalLimit", ...
        "Driven characteristic exceeds the frozen small-signal envelope.");
end
impedance = rho0 * c0;
outgoingPressure = 0.5 * ((pressure - p0) - impedance * velocity);
boundaryPressure = p0 + incomingPressurePa + outgoingPressure;
boundaryVelocity = (incomingPressurePa - outgoingPressure) / impedance;
boundaryDensity = rho0 * (boundaryPressure / p0)^(1 / gamma);
state = conservative(boundaryDensity, boundaryVelocity, boundaryPressure, gamma);
if ~all(isfinite(state)) || state(1) <= 0 || pressureOf(state, gamma) <= 0
    error("S12:Radiation:InvalidState", "Driven boundary produced a nonphysical state.");
end
result = struct("state", state, ...
    "boundary_type", "small_signal_characteristic_drive.v1", ...
    "incoming_pressure_pa", incomingPressurePa, ...
    "outgoing_pressure_pa", outgoingPressure, ...
    "outgoing_characteristic", outgoingPressure, ...
    "boundary_pressure_pa", boundaryPressure, ...
    "boundary_velocity_mps", boundaryVelocity, ...
    "reference_impedance_pa_s_m", impedance);
end

function [rho, velocity, pressure, soundSpeed] = primitive(state, gamma)
rho = state(1);
velocity = state(2) / rho;
pressure = pressureOf(state, gamma);
soundSpeed = sqrt(gamma * pressure / rho);
end

function pressure = pressureOf(state, gamma)
rho = state(1);
velocity = state(2) / rho;
pressure = (gamma - 1) * (state(3) - 0.5 * rho * velocity^2);
end

function state = conservative(rho, velocity, pressure, gamma)
state = [rho; rho * velocity; pressure / (gamma - 1) + 0.5 * rho * velocity^2];
end
