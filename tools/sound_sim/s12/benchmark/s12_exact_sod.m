function [rho, velocity, pressure, waves] = s12_exact_sod( ...
        x, x0, time, gamma, left, right)
%S12_EXACT_SOD Sample the exact ideal-gas Sod Riemann solution.
[starPressure, starVelocity] = solveStarRegion(gamma, left, right);
aLeft = sqrt(gamma * left(3) / left(1));
aRight = sqrt(gamma * right(3) / right(1));
rhoLeftStar = starDensity(left, starPressure, gamma);
rhoRightStar = starDensity(right, starPressure, gamma);
aLeftStar = aLeft * (starPressure / left(3))^((gamma - 1) / (2 * gamma));
aRightStar = aRight * (starPressure / right(3))^((gamma - 1) / (2 * gamma));
waves = waveLocations(x0, time, gamma, left, right, starPressure, ...
    starVelocity, aLeft, aRight, aLeftStar, aRightStar);
similarity = (x - x0) / time;
rho = zeros(size(x));
velocity = rho;
pressure = rho;
for index = 1:numel(x)
    if similarity(index) <= starVelocity
        [rho(index), velocity(index), pressure(index)] = sampleLeft( ...
            similarity(index), gamma, left, starPressure, starVelocity, ...
            aLeft, aLeftStar, rhoLeftStar);
    else
        [rho(index), velocity(index), pressure(index)] = sampleRight( ...
            similarity(index), gamma, right, starPressure, starVelocity, ...
            aRight, aRightStar, rhoRightStar);
    end
end

function waves = waveLocations(x0, time, gamma, left, right, starPressure, ...
        starVelocity, aLeft, aRight, aLeftStar, aRightStar)
waves = struct( ...
    "left_wave_type", "", "right_wave_type", "", ...
    "rarefaction_head", NaN, "rarefaction_tail", NaN, ...
    "contact", x0 + starVelocity * time, "shock", NaN);
if starPressure > left(3)
    waves.left_wave_type = "shock";
    waves.shock = x0 + time * (left(2) - aLeft * sqrt((gamma + 1) / ...
        (2 * gamma) * starPressure / left(3) + (gamma - 1) / (2 * gamma)));
else
    waves.left_wave_type = "rarefaction";
    waves.rarefaction_head = x0 + time * (left(2) - aLeft);
    waves.rarefaction_tail = x0 + time * (starVelocity - aLeftStar);
end
if starPressure > right(3)
    waves.right_wave_type = "shock";
    waves.shock = x0 + time * (right(2) + aRight * sqrt((gamma + 1) / ...
        (2 * gamma) * starPressure / right(3) + (gamma - 1) / (2 * gamma)));
else
    waves.right_wave_type = "rarefaction";
    if isnan(waves.rarefaction_head)
        waves.rarefaction_head = x0 + time * (right(2) + aRight);
        waves.rarefaction_tail = x0 + time * (starVelocity + aRightStar);
    end
end
end
end

function [starPressure, starVelocity] = solveStarRegion(gamma, left, right)
aLeft = sqrt(gamma * left(3) / left(1));
aRight = sqrt(gamma * right(3) / right(1));
starPressure = max(0.5 * (left(3) + right(3)) - ...
    0.125 * (right(2) - left(2)) * (left(1) + right(1)) * ...
    (aLeft + aRight), eps);
for iteration = 1:100
    [fLeft, dLeft] = pressureFunction(starPressure, left, gamma, aLeft);
    [fRight, dRight] = pressureFunction(starPressure, right, gamma, aRight);
    next = max(starPressure - (fLeft + fRight + right(2) - left(2)) / ...
        (dLeft + dRight), eps);
    if abs(next - starPressure) <= 1e-12 * max(1, next)
        starPressure = next;
        break
    end
    starPressure = next;
end
[fLeft, ~] = pressureFunction(starPressure, left, gamma, aLeft);
[fRight, ~] = pressureFunction(starPressure, right, gamma, aRight);
starVelocity = 0.5 * (left(2) + right(2) + fRight - fLeft);
end

function [value, derivative] = pressureFunction(p, state, gamma, soundSpeed)
if p > state(3)
    coefficientA = 2 / ((gamma + 1) * state(1));
    coefficientB = (gamma - 1) / (gamma + 1) * state(3);
    root = sqrt(coefficientA / (p + coefficientB));
    value = (p - state(3)) * root;
    derivative = root * (1 - 0.5 * (p - state(3)) / (p + coefficientB));
else
    ratio = p / state(3);
    value = 2 * soundSpeed / (gamma - 1) * ...
        (ratio^((gamma - 1) / (2 * gamma)) - 1);
    derivative = ratio^(-(gamma + 1) / (2 * gamma)) / ...
        (state(1) * soundSpeed);
end
end

function density = starDensity(state, starPressure, gamma)
ratio = starPressure / state(3);
if starPressure > state(3)
    gammaRatio = (gamma - 1) / (gamma + 1);
    density = state(1) * (ratio + gammaRatio) / (gammaRatio * ratio + 1);
else
    density = state(1) * ratio^(1 / gamma);
end
end

function [rho, velocity, pressure] = sampleLeft( ...
        speed, gamma, state, starPressure, starVelocity, soundSpeed, ...
        starSoundSpeed, starDensityValue)
if starPressure > state(3)
    shockSpeed = state(2) - soundSpeed * sqrt((gamma + 1) / ...
        (2 * gamma) * starPressure / state(3) + (gamma - 1) / (2 * gamma));
    if speed <= shockSpeed
        [rho, velocity, pressure] = unpack(state);
    else
        [rho, velocity, pressure] = deal(starDensityValue, starVelocity, starPressure);
    end
else
    head = state(2) - soundSpeed;
    tail = starVelocity - starSoundSpeed;
    if speed <= head
        [rho, velocity, pressure] = unpack(state);
    elseif speed >= tail
        [rho, velocity, pressure] = deal(starDensityValue, starVelocity, starPressure);
    else
        velocity = 2 / (gamma + 1) * (soundSpeed + ...
            0.5 * (gamma - 1) * state(2) + speed);
        localSound = 2 / (gamma + 1) * (soundSpeed + ...
            0.5 * (gamma - 1) * (state(2) - speed));
        [rho, pressure] = fanState(state, localSound / soundSpeed, gamma);
    end
end
end

function [rho, velocity, pressure] = sampleRight( ...
        speed, gamma, state, starPressure, starVelocity, soundSpeed, ...
        starSoundSpeed, starDensityValue)
if starPressure > state(3)
    shockSpeed = state(2) + soundSpeed * sqrt((gamma + 1) / ...
        (2 * gamma) * starPressure / state(3) + (gamma - 1) / (2 * gamma));
    if speed >= shockSpeed
        [rho, velocity, pressure] = unpack(state);
    else
        [rho, velocity, pressure] = deal(starDensityValue, starVelocity, starPressure);
    end
else
    head = state(2) + soundSpeed;
    tail = starVelocity + starSoundSpeed;
    if speed >= head
        [rho, velocity, pressure] = unpack(state);
    elseif speed <= tail
        [rho, velocity, pressure] = deal(starDensityValue, starVelocity, starPressure);
    else
        velocity = 2 / (gamma + 1) * (-soundSpeed + ...
            0.5 * (gamma - 1) * state(2) + speed);
        localSound = 2 / (gamma + 1) * (soundSpeed - ...
            0.5 * (gamma - 1) * (state(2) - speed));
        [rho, pressure] = fanState(state, localSound / soundSpeed, gamma);
    end
end
end

function [rho, pressure] = fanState(state, soundRatio, gamma)
rho = state(1) * soundRatio^(2 / (gamma - 1));
pressure = state(3) * soundRatio^(2 * gamma / (gamma - 1));
end

function [rho, velocity, pressure] = unpack(state)
rho = state(1);
velocity = state(2);
pressure = state(3);
end
