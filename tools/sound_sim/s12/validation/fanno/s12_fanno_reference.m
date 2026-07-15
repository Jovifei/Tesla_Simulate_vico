function result = s12_fanno_reference(input)
%S12_FANNO_REFERENCE Evaluate steady subsonic ideal-gas Fanno flow.
% The friction parameter uses the Darcy convention f_D*L/D (equivalent
% to 4*f_Fanning*L/D). The duct is constant-area and adiabatic.

arguments
    input (1, 1) struct
end

required = ["static_pressure", "static_temperature", "mach", "gamma", ...
    "gas_constant", "area", "diameter", "length", ...
    "darcy_friction_factor"];
if ~all(isfield(input, required))
    error("S12:Fanno:InvalidInput", "The Fanno input is missing a required field.");
end
for index = 1:numel(required)
    value = input.(required(index));
    if ~(isnumeric(value) && isreal(value) && isscalar(value) && isfinite(value))
        error("S12:Fanno:InvalidInput", ...
            "Every Fanno input field must be a finite real numeric scalar.");
    end
end

positive = [input.static_pressure, input.static_temperature, ...
    input.gas_constant, input.area, input.diameter];
nonnegative = [input.length, input.darcy_friction_factor];
if any(positive <= 0) || any(nonnegative < 0) || ...
        input.mach <= 0 || input.mach >= 1 || input.gamma <= 1
    error("S12:Fanno:InvalidInput", ...
        "Inputs must define finite positive properties and 0 < Mach < 1.");
end

fannoInlet = fannoFunction(input.mach, input.gamma);
usedParameter = input.darcy_friction_factor * input.length / input.diameter;
if input.darcy_friction_factor > 0 && ...
        usedParameter >= fannoInlet * (1 - 64 * eps)
    error("S12:Fanno:ChokedLength", ...
        "Duct length must be strictly less than the length to sonic choking.");
end

if usedParameter == 0
    outletMach = input.mach;
else
    target = fannoInlet - usedParameter;
    outletMach = solveSubsonicMach(input.mach, target, input.gamma);
end

inlet = makeState(input.static_pressure, input.static_temperature, ...
    input.mach, input.gamma, input.gas_constant, input.area);
temperatureRatio = (2 + (input.gamma - 1) * input.mach^2) / ...
    (2 + (input.gamma - 1) * outletMach^2);
outletTemperature = input.static_temperature * temperatureRatio;
outletPressure = input.static_pressure * input.mach / outletMach * ...
    sqrt(temperatureRatio);
outlet = makeState(outletPressure, outletTemperature, outletMach, ...
    input.gamma, input.gas_constant, input.area);

fannoOutlet = fannoFunction(outletMach, input.gamma);
if input.darcy_friction_factor == 0
    remainingLength = Inf;
else
    remainingLength = input.diameter * fannoOutlet / ...
        input.darcy_friction_factor;
end


result = struct( ...
    "status", "ok", ...
    "friction_convention", "darcy_f_D_L_over_D", ...
    "inlet", inlet, ...
    "outlet", outlet, ...
    "mass_flow", inlet.mass_flow, ...
    "fanno", struct( ...
        "inlet", fannoInlet, ...
        "outlet", fannoOutlet, ...
        "used_parameter", usedParameter, ...
        "residual", fannoInlet - fannoOutlet - usedParameter), ...
    "remaining_length_to_choke", remainingLength);
end

function state = makeState(pressure, temperature, mach, gamma, gasConstant, area)
soundSpeed = sqrt(gamma * gasConstant * temperature);
velocity = mach * soundSpeed;
density = pressure / (gasConstant * temperature);
massFlow = density * velocity * area;
totalTemperature = temperature * (1 + 0.5 * (gamma - 1) * mach^2);
totalPressure = pressure * (1 + 0.5 * (gamma - 1) * mach^2)^(gamma / (gamma - 1));
state = struct( ...
    "mach", mach, ...
    "static_pressure", pressure, ...
    "static_temperature", temperature, ...
    "static_density", density, ...
    "sound_speed", soundSpeed, ...
    "velocity", velocity, ...
    "total_pressure", totalPressure, ...
    "total_temperature", totalTemperature, ...
    "mass_flow", massFlow);
end

function value = fannoFunction(mach, gamma)
machSquared = mach^2;
value = (1 - machSquared) / (gamma * machSquared) + ...
    (gamma + 1) / (2 * gamma) * log( ...
    (gamma + 1) * machSquared / (2 + (gamma - 1) * machSquared));
end

function mach = solveSubsonicMach(inletMach, target, gamma)
lower = inletMach;
upper = 1;
for iteration = 1:80
    mach = 0.5 * (lower + upper);
    if fannoFunction(mach, gamma) > target
        lower = mach;
    else
        upper = mach;
    end
end
mach = 0.5 * (lower + upper);
end
