function tests = test_s12_ssprk3_sod_ref
%TEST_S12_SSPRK3_SOD_REF Verify long-time SSP-RK3 Euler integration.
tests = functiontests(localfunctions);
end

function testUniformStateIsPreservedOverManySteps(testCase)
modelName = openSspRk3Model(testCase);
gamma = 1.4;
cellCount = 200;
dx = 0.005;
endTime = 0.2;
cfl = 0.45;
maxSteps = 10000;
rho = 1.1 * ones(1, cellCount);
velocity = 0.2 * ones(1, cellCount);
pressure = 1.0 * ones(1, cellCount);
initialState = primitiveToConservative(rho, velocity, pressure, gamma);

result = runSspRk3Case(modelName, initialState, gamma, dx, endTime, ...
    cfl, maxSteps);

verifyGreaterThan(testCase, result.stepCount, 1);
verifyEqual(testCase, result.finalState, initialState, ...
    "RelTol", 1e-12, "AbsTol", 1e-10);
end

function testLongTimeSodMatchesExactRiemannSolution(testCase)
modelName = openSspRk3Model(testCase);
gamma = 1.4;
cellCount = 200;
dx = 0.005;
cfl = 0.45;
endTime = 0.2;
maxSteps = 10000;
x0 = 0.5;
x = ((1:cellCount) - 0.5) * dx;
left = [1, 0, 1];
right = [0.125, 0, 0.1];
isLeft = x < x0;
rho = left(1) * isLeft + right(1) * ~isLeft;
velocity = left(2) * isLeft + right(2) * ~isLeft;
pressure = left(3) * isLeft + right(3) * ~isLeft;
initialState = primitiveToConservative(rho, velocity, pressure, gamma);

result = runSspRk3Case(modelName, initialState, gamma, dx, endTime, ...
    cfl, maxSteps);
[exactRho, exactVelocity, exactPressure, wave] = exactSodSolution( ...
    x, x0, endTime, gamma, left, right);
finalRho = result.finalState(1, :);
finalVelocity = result.finalState(2, :) ./ finalRho;
finalPressure = (gamma - 1) * (result.finalState(3, :) - ...
    0.5 * finalRho .* finalVelocity.^2);

verifyGreaterThan(testCase, result.stepCount, 1);
verifyLessThanOrEqual(testCase, abs(result.finalTime - endTime), 1e-12);
verifyTrue(testCase, all(isfinite(result.finalState), "all"));
verifyTrue(testCase, all(isfinite(finalVelocity)));
verifyTrue(testCase, all(isfinite(finalPressure)));
verifyGreaterThan(testCase, min(finalRho), 0);
verifyGreaterThan(testCase, min(finalPressure), 0);
verifyLessThanOrEqual(testCase, result.maxCourant, cfl * (1 + 1e-12));

conservationScale = max(abs(dx * sum(initialState, 2)).', 1);
scaledResidual = abs(result.conservationResidual) ./ conservationScale;
verifyLessThanOrEqual(testCase, scaledResidual, 1e-10 * ones(1, 3));

verifyLessThanOrEqual(testCase, mean(abs(finalRho - exactRho)), 0.03);
verifyLessThanOrEqual(testCase, ...
    mean(abs(finalVelocity - exactVelocity)), 0.04);
verifyLessThanOrEqual(testCase, ...
    mean(abs(finalPressure - exactPressure)), 0.03);

edgeX = 0.5 * (x(1:end - 1) + x(2:end));
pressureJump = abs(diff(finalPressure));
shockMask = edgeX > 0.75;
shockEdges = edgeX(shockMask);
shockJumps = pressureJump(shockMask);
[~, shockIndex] = max(shockJumps);
numericalShockPosition = shockEdges(shockIndex);
exactShockPosition = x0 + wave.rightShockSpeed * endTime;
verifyLessThanOrEqual(testCase, ...
    abs(numericalShockPosition - exactShockPosition), 0.01);

densityJump = abs(diff(finalRho));
contactMask = edgeX > 0.58 & edgeX < 0.78;
contactEdges = edgeX(contactMask);
contactJumps = densityJump(contactMask);
[~, contactIndex] = max(contactJumps);
numericalContactPosition = contactEdges(contactIndex);
exactContactPosition = x0 + wave.contactSpeed * endTime;
verifyLessThanOrEqual(testCase, ...
    abs(numericalContactPosition - exactContactPosition), 0.02);
end

function modelName = openSspRk3Model(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "fvm_ref", ...
    "s12_euler_ssprk3_sod_ref.slx");
assertEqual(testCase, exist(modelFile, "file"), 2, ...
    "The SSP-RK3 long-time Sod reference model must exist.");
modelName = "s12_euler_ssprk3_sod_ref";
load_system(modelFile);
testCase.addTeardown(@() close_system(modelName, 0));
end

function result = runSspRk3Case(modelName, state, gamma, dx, endTime, ...
        cfl, maxSteps)
workspace = get_param(modelName, "ModelWorkspace");
setParameterValue(workspace, "S12_RK3_State", state);
setParameterValue(workspace, "S12_RK3_Gamma", gamma);
setParameterValue(workspace, "S12_RK3_Dx", dx);
setParameterValue(workspace, "S12_RK3_EndTime", endTime);
setParameterValue(workspace, "S12_RK3_CFL", cfl);
setParameterValue(workspace, "S12_RK3_MaxSteps", maxSteps);
output = sim(modelName);
result.finalState = squeeze(output.S12_RK3FinalState);
result.finalTime = output.S12_RK3FinalTime(end);
result.stepCount = output.S12_RK3StepCount(end);
result.maxCourant = output.S12_RK3MaxCourant(end);
result.conservationResidual = ...
    squeeze(output.S12_RK3ConservationResidual);
result.conservationResidual = result.conservationResidual(:).';
end

function state = primitiveToConservative(rho, velocity, pressure, gamma)
state = [rho; rho .* velocity; ...
    pressure / (gamma - 1) + 0.5 * rho .* velocity.^2];
end

function [rho, velocity, pressure, wave] = exactSodSolution( ...
        x, x0, time, gamma, left, right)
[starPressure, starVelocity] = solveStarRegion(gamma, left, right);
leftSoundSpeed = sqrt(gamma * left(3) / left(1));
rightSoundSpeed = sqrt(gamma * right(3) / right(1));
leftStarDensity = starDensity(left, starPressure, gamma);
rightStarDensity = starDensity(right, starPressure, gamma);
leftStarSoundSpeed = leftSoundSpeed * ...
    (starPressure / left(3))^((gamma - 1) / (2 * gamma));
rightStarSoundSpeed = rightSoundSpeed * ...
    (starPressure / right(3))^((gamma - 1) / (2 * gamma));

wave.contactSpeed = starVelocity;
wave.rightShockSpeed = right(2) + rightSoundSpeed * sqrt( ...
    (gamma + 1) / (2 * gamma) * starPressure / right(3) + ...
    (gamma - 1) / (2 * gamma));
similarity = (x - x0) / time;
rho = zeros(size(x));
velocity = zeros(size(x));
pressure = zeros(size(x));

for index = 1:numel(x)
    speed = similarity(index);
    if speed <= starVelocity
        [rho(index), velocity(index), pressure(index)] = sampleLeft( ...
            speed, gamma, left, starPressure, starVelocity, ...
            leftSoundSpeed, leftStarSoundSpeed, leftStarDensity);
    else
        [rho(index), velocity(index), pressure(index)] = sampleRight( ...
            speed, gamma, right, starPressure, starVelocity, ...
            rightSoundSpeed, rightStarSoundSpeed, rightStarDensity);
    end
end
end

function [starPressure, starVelocity] = solveStarRegion(gamma, left, right)
leftSoundSpeed = sqrt(gamma * left(3) / left(1));
rightSoundSpeed = sqrt(gamma * right(3) / right(1));
pressureGuess = 0.5 * (left(3) + right(3)) - ...
    0.125 * (right(2) - left(2)) * (left(1) + right(1)) * ...
    (leftSoundSpeed + rightSoundSpeed);
starPressure = max(pressureGuess, eps);

for iteration = 1:100
    [leftFunction, leftDerivative] = pressureFunction( ...
        starPressure, left, gamma, leftSoundSpeed);
    [rightFunction, rightDerivative] = pressureFunction( ...
        starPressure, right, gamma, rightSoundSpeed);
    nextPressure = starPressure - ...
        (leftFunction + rightFunction + right(2) - left(2)) / ...
        (leftDerivative + rightDerivative);
    nextPressure = max(nextPressure, eps);
    if abs(nextPressure - starPressure) <= ...
            1e-12 * max(1, nextPressure)
        starPressure = nextPressure;
        break
    end
    starPressure = nextPressure;
end

[leftFunction, ~] = pressureFunction( ...
    starPressure, left, gamma, leftSoundSpeed);
[rightFunction, ~] = pressureFunction( ...
    starPressure, right, gamma, rightSoundSpeed);
starVelocity = 0.5 * (left(2) + right(2) + ...
    rightFunction - leftFunction);
end

function [value, derivative] = pressureFunction( ...
        pressure, state, gamma, soundSpeed)
if pressure > state(3)
    coefficientA = 2 / ((gamma + 1) * state(1));
    coefficientB = (gamma - 1) / (gamma + 1) * state(3);
    rootTerm = sqrt(coefficientA / (pressure + coefficientB));
    value = (pressure - state(3)) * rootTerm;
    derivative = rootTerm * (1 - ...
        0.5 * (pressure - state(3)) / (pressure + coefficientB));
else
    pressureRatio = pressure / state(3);
    exponent = (gamma - 1) / (2 * gamma);
    value = 2 * soundSpeed / (gamma - 1) * ...
        (pressureRatio^exponent - 1);
    derivative = pressureRatio^(-(gamma + 1) / (2 * gamma)) / ...
        (state(1) * soundSpeed);
end
end

function density = starDensity(state, starPressure, gamma)
pressureRatio = starPressure / state(3);
if starPressure > state(3)
    gammaRatio = (gamma - 1) / (gamma + 1);
    density = state(1) * (pressureRatio + gammaRatio) / ...
        (gammaRatio * pressureRatio + 1);
else
    density = state(1) * pressureRatio^(1 / gamma);
end
end

function [rho, velocity, pressure] = sampleLeft( ...
        speed, gamma, state, starPressure, starVelocity, soundSpeed, ...
        starSoundSpeed, starDensityValue)
if starPressure > state(3)
    shockSpeed = state(2) - soundSpeed * sqrt( ...
        (gamma + 1) / (2 * gamma) * starPressure / state(3) + ...
        (gamma - 1) / (2 * gamma));
    if speed <= shockSpeed
        [rho, velocity, pressure] = unpackPrimitive(state);
    else
        rho = starDensityValue;
        velocity = starVelocity;
        pressure = starPressure;
    end
else
    headSpeed = state(2) - soundSpeed;
    tailSpeed = starVelocity - starSoundSpeed;
    if speed <= headSpeed
        [rho, velocity, pressure] = unpackPrimitive(state);
    elseif speed >= tailSpeed
        rho = starDensityValue;
        velocity = starVelocity;
        pressure = starPressure;
    else
        velocity = 2 / (gamma + 1) * (soundSpeed + ...
            0.5 * (gamma - 1) * state(2) + speed);
        localSoundSpeed = 2 / (gamma + 1) * (soundSpeed + ...
            0.5 * (gamma - 1) * (state(2) - speed));
        [rho, pressure] = fanDensityPressure( ...
            state, localSoundSpeed, soundSpeed, gamma);
    end
end
end

function [rho, velocity, pressure] = sampleRight( ...
        speed, gamma, state, starPressure, starVelocity, soundSpeed, ...
        starSoundSpeed, starDensityValue)
if starPressure > state(3)
    shockSpeed = state(2) + soundSpeed * sqrt( ...
        (gamma + 1) / (2 * gamma) * starPressure / state(3) + ...
        (gamma - 1) / (2 * gamma));
    if speed >= shockSpeed
        [rho, velocity, pressure] = unpackPrimitive(state);
    else
        rho = starDensityValue;
        velocity = starVelocity;
        pressure = starPressure;
    end
else
    headSpeed = state(2) + soundSpeed;
    tailSpeed = starVelocity + starSoundSpeed;
    if speed >= headSpeed
        [rho, velocity, pressure] = unpackPrimitive(state);
    elseif speed <= tailSpeed
        rho = starDensityValue;
        velocity = starVelocity;
        pressure = starPressure;
    else
        velocity = 2 / (gamma + 1) * (-soundSpeed + ...
            0.5 * (gamma - 1) * state(2) + speed);
        localSoundSpeed = 2 / (gamma + 1) * (soundSpeed - ...
            0.5 * (gamma - 1) * (state(2) - speed));
        [rho, pressure] = fanDensityPressure( ...
            state, localSoundSpeed, soundSpeed, gamma);
    end
end
end

function [rho, pressure] = fanDensityPressure( ...
        state, localSoundSpeed, soundSpeed, gamma)
soundSpeedRatio = localSoundSpeed / soundSpeed;
rho = state(1) * soundSpeedRatio^(2 / (gamma - 1));
pressure = state(3) * soundSpeedRatio^(2 * gamma / (gamma - 1));
end

function [rho, velocity, pressure] = unpackPrimitive(state)
rho = state(1);
velocity = state(2);
pressure = state(3);
end

function setParameterValue(workspace, name, value)
parameter = workspace.getVariable(name);
parameter.Value = value;
workspace.assignin(name, parameter);
end
