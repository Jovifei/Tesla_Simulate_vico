function [ghostState, diagnostics] = s12_fanno_outlet_mdot_boundary( ...
        interiorState, gamma, targetMassFlux)
%S12_FANNO_OUTLET_MDOT_BOUNDARY Construct a forward subsonic mdot ghost.
validateInput(interiorState, gamma, targetMassFlux);
[densityInterior, velocityInterior, pressureInterior] = primitive(interiorState, gamma);
soundInterior = sqrt(gamma * pressureInterior / densityInterior);
requireForwardSubsonic(velocityInterior, soundInterior);
entropy = pressureInterior / densityInterior^gamma;
jPlus = velocityInterior + 2 * soundInterior / (gamma - 1);
soundSonic = jPlus * (gamma - 1) / (gamma + 1);
soundZeroVelocity = jPlus * (gamma - 1) / 2;
criticalMassFlux = massFluxForSound(soundSonic, entropy, jPlus, gamma);
if targetMassFlux >= criticalMassFlux
    error("S12:Fanno:BoundaryRegime", ...
        "Requested Fanno outlet mass flux is sonic or supercritical.");
end
lower = soundSonic * (1 + 64 * eps);
upper = soundZeroVelocity * (1 - 64 * eps);
for iteration = 1:96
    sound = 0.5 * (lower + upper);
    massFlux = massFluxForSound(sound, entropy, jPlus, gamma);
    if massFlux > targetMassFlux
        lower = sound;
    else
        upper = sound;
    end
end
sound = 0.5 * (lower + upper);
density = (sound^2 / (gamma * entropy))^(1 / (gamma - 1));
velocity = jPlus - 2 * sound / (gamma - 1);
pressure = entropy * density^gamma;
requireForwardSubsonic(velocity, sound);
ghostState = conservative(density, velocity, pressure, gamma);
diagnostics = struct( ...
    "boundary_id", "subsonic_inlet_pt_outlet_mdot.v1", ...
    "mass_flux", density * velocity, ...
    "target_mass_flux", targetMassFlux, ...
    "entropy", entropy, ...
    "outgoing_j_plus", jPlus, ...
    "critical_mass_flux", criticalMassFlux, ...
    "iteration_count", 96, ...
    "mach", velocity / sound);
end

function validateInput(state, gamma, targetMassFlux)
if ~isa(state, "double") || ~isequal(size(state), [3, 1]) || ...
        any(~isfinite(state), "all") || ~isscalar(gamma) || ...
        ~isfinite(gamma) || gamma <= 1 || ~isscalar(targetMassFlux) || ...
        ~isfinite(targetMassFlux) || targetMassFlux <= 0
    error("S12:Fanno:InvalidInput", "Invalid Fanno outlet boundary input.");
end
[density, ~, pressure] = primitive(state, gamma);
if density <= 0 || pressure <= 0
    error("S12:Fanno:InvalidInput", "Fanno boundary state must be physical.");
end
end

function massFlux = massFluxForSound(sound, entropy, jPlus, gamma)
density = (sound^2 / (gamma * entropy))^(1 / (gamma - 1));
velocity = jPlus - 2 * sound / (gamma - 1);
massFlux = density * velocity;
end

function requireForwardSubsonic(velocity, sound)
if ~(isfinite(velocity) && isfinite(sound) && sound > 0 && ...
        velocity > 0 && velocity < sound)
    error("S12:Fanno:BoundaryRegime", ...
        "Fanno validation outlet only supports forward subsonic flow.");
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
