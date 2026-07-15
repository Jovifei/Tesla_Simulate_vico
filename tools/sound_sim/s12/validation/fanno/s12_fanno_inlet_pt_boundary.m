function [ghostState, diagnostics] = s12_fanno_inlet_pt_boundary( ...
        interiorState, gamma, gasConstant, staticPressure, staticTemperature)
%S12_FANNO_INLET_PT_BOUNDARY Construct a forward subsonic p/T inlet ghost.
validateCommon(interiorState, gamma);
if ~isscalar(gasConstant) || ~isfinite(gasConstant) || gasConstant <= 0 || ...
        ~isscalar(staticPressure) || ~isfinite(staticPressure) || staticPressure <= 0 || ...
        ~isscalar(staticTemperature) || ~isfinite(staticTemperature) || staticTemperature <= 0
    error("S12:Fanno:InvalidInput", "Invalid Fanno inlet pressure/temperature data.");
end
[rhoInterior, velocityInterior, pressureInterior] = primitive(interiorState, gamma);
soundInterior = sqrt(gamma * pressureInterior / rhoInterior);
requireForwardSubsonic(velocityInterior, soundInterior);
density = staticPressure / (gasConstant * staticTemperature);
sound = sqrt(gamma * gasConstant * staticTemperature);
jMinus = velocityInterior - 2 * soundInterior / (gamma - 1);
velocity = jMinus + 2 * sound / (gamma - 1);
requireForwardSubsonic(velocity, sound);
ghostState = conservative(density, velocity, staticPressure, gamma);
diagnostics = struct( ...
    "boundary_id", "subsonic_inlet_pt_outlet_mdot.v1", ...
    "static_pressure", staticPressure, ...
    "static_temperature", staticTemperature, ...
    "outgoing_j_minus", jMinus, ...
    "incoming_density", density, ...
    "incoming_velocity", velocity, ...
    "mach", velocity / sound);
end

function validateCommon(state, gamma)
if ~isa(state, "double") || ~isequal(size(state), [3, 1]) || ...
        any(~isfinite(state), "all") || ~isscalar(gamma) || ...
        ~isfinite(gamma) || gamma <= 1
    error("S12:Fanno:InvalidInput", "Invalid Fanno boundary state.");
end
[density, ~, pressure] = primitive(state, gamma);
if density <= 0 || pressure <= 0
    error("S12:Fanno:InvalidInput", "Fanno boundary state must be physical.");
end
end

function requireForwardSubsonic(velocity, sound)
if ~(isfinite(velocity) && isfinite(sound) && sound > 0 && ...
        velocity > 0 && velocity < sound)
    error("S12:Fanno:BoundaryRegime", ...
        "Fanno validation inlet only supports forward subsonic flow.");
end
end

function [density, velocity, pressure] = primitive(state, gamma)
density = state(1);
velocity = state(2) / density;
pressure = (gamma - 1) * (state(3) - 0.5 * density * velocity^2);
end

function state = conservative(density, velocity, pressure, gamma)
state = [density; density * velocity; ...
    pressure / (gamma - 1) + 0.5 * density * velocity^2];
end
