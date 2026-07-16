function [finalState,finalTime,stepCount,maxCourant,conservationResidual,qualificationDiagnostics,traceTime,tracePressure,traceVelocity,boundaryEnergyFlux] = s12_transient_wave_integrator_chart_source(initialState,gamma,dx,endTime,cfl,maxSteps,rhoFloor,pFloor,cflHardMaximum,leftBoundaryMode,rightBoundaryMode,ambientState,darcyFrictionFactor,hydraulicDiameter,activeCellCount)
%S12_TRANSIENT_WAVE_INTEGRATOR_CHART_SOURCE Stateflow chart source template.
%#codegen
traceCapacity = 4096;
maximumCellCount = 800;
cflTarget = 0.45;
maximumRetries = 8;
validateInputs(initialState, ambientState, gamma, dx, endTime, cfl, ...
    maxSteps, rhoFloor, pFloor, cflHardMaximum, leftBoundaryMode, ...
    rightBoundaryMode, darcyFrictionFactor, hydraulicDiameter, traceCapacity, ...
    maximumCellCount, activeCellCount);
U = initialState;
validateState(U, gamma, rhoFloor, pFloor);
time = 0;
stepCount = 0;
maxCourant = 0;
boundaryIntegral = zeros(3, 1);
qualificationDiagnostics = [inf, inf, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, ...
    0, 0, 0, 1, inf, inf, inf, inf, 0, 0, 0, 0, 0, inf(1, 24)];
traceTime = nan(1, traceCapacity);
tracePressure = nan(3, traceCapacity);
traceVelocity = nan(3, traceCapacity);
boundaryEnergyFlux = nan(1, traceCapacity);
probeIndices = probeIndicesFor(activeCellCount);
[tracePressure(:, 1), traceVelocity(:, 1)] = probeTrace(U, gamma, probeIndices);
traceTime(1) = 0;
boundaryEnergyFlux(1) = 0;
while time < endTime
    if stepCount >= maxSteps || stepCount + 1 > traceCapacity
        error('S12:TransientWave:MaxSteps', ...
            'Transient-wave model exhausted its explicit trace capacity.');
    end
    alphaBase = stageAlpha(U, gamma, activeCellCount);
    nominalDt = cfl * dx / alphaBase;
    dt = min(nominalDt, endTime - time);
    endClipped = dt < nominalDt;
    accepted = false;
    boundaryFlux = 0;
    for attempt = 0:maximumRetries
        alpha0 = stageAlpha(U, gamma, activeCellCount);
        if dt * alpha0 / dx > cflHardMaximum
            qualificationDiagnostics(24) = qualificationDiagnostics(24) + 1;
            qualificationDiagnostics(25) = qualificationDiagnostics(25) + 1;
            dt = cflTarget * dx / alpha0;
            continue
        end
        sourceStart = exactDarcyStep(U, gamma, darcyFrictionFactor, ...
            hydraulicDiameter, 0.5 * dt);
        [euler0, left0, right0, d0] = forwardEuler(sourceStart, activeCellCount, gamma, dx, dt, ...
            rhoFloor, pFloor, leftBoundaryMode, rightBoundaryMode, ambientState);
        U1 = euler0;
        validateState(U1, gamma, rhoFloor, pFloor);
        alpha1 = stageAlpha(U1, gamma, activeCellCount);
        if dt * alpha1 / dx > cflHardMaximum
            qualificationDiagnostics(24) = qualificationDiagnostics(24) + 1;
            qualificationDiagnostics(25) = qualificationDiagnostics(25) + 1;
            dt = cflTarget * dx / alpha1;
            continue
        end
        [euler1, left1, right1, d1] = forwardEuler(U1, activeCellCount, gamma, dx, dt, ...
            rhoFloor, pFloor, leftBoundaryMode, rightBoundaryMode, ambientState);
        U2 = 0.75 * sourceStart + 0.25 * euler1;
        validateState(U2, gamma, rhoFloor, pFloor);
        alpha2 = stageAlpha(U2, gamma, activeCellCount);
        if dt * alpha2 / dx > cflHardMaximum
            qualificationDiagnostics(24) = qualificationDiagnostics(24) + 1;
            qualificationDiagnostics(25) = qualificationDiagnostics(25) + 1;
            dt = cflTarget * dx / alpha2;
            continue
        end
        [euler2, left2, right2, d2] = forwardEuler(U2, activeCellCount, gamma, dx, dt, ...
            rhoFloor, pFloor, leftBoundaryMode, rightBoundaryMode, ambientState);
        hyperbolic = (1 / 3) * sourceStart + (2 / 3) * euler2;
        U3 = exactDarcyStep(hyperbolic, gamma, darcyFrictionFactor, ...
            hydraulicDiameter, 0.5 * dt);
        validateState(U3, gamma, rhoFloor, pFloor);
        qualificationDiagnostics = accumulateDiagnostics(qualificationDiagnostics, ...
            d0, d1, d2, U1, U2, U3, gamma, activeCellCount);
        U = U3;
        boundaryIntegral = boundaryIntegral + dt * ((right0 - left0) / 6 + ...
            (right1 - left1) / 6 + 2 * (right2 - left2) / 3);
        maxCourant = max(maxCourant, max([dt * alpha0 / dx, ...
            dt * alpha1 / dx, dt * alpha2 / dx]));
        boundaryFlux = (right0(3) - left0(3)) / 6 + ...
            (right1(3) - left1(3)) / 6 + ...
            2 * (right2(3) - left2(3)) / 3;
        accepted = true;
        break
    end
    if ~accepted
        error('S12:TransientWave:RetryLimit', ...
            'Transient-wave PP SSP-RK3 exceeded the retry limit.');
    end
    qualificationDiagnostics(8) = qualificationDiagnostics(8) + double(endClipped);
    time = time + dt;
    stepCount = stepCount + 1;
    traceTime(stepCount + 1) = time;
    [tracePressure(:, stepCount + 1), traceVelocity(:, stepCount + 1)] = ...
        probeTrace(U, gamma, probeIndices);
    boundaryEnergyFlux(stepCount + 1) = boundaryFlux;
end
if time ~= endTime
    error('S12:TransientWave:EndTime', ...
        'Transient-wave PP SSP-RK3 did not terminate exactly.');
end
finalState = U;
finalTime = time;
conservationResidual = (dx * sum(finalState - initialState, 2) + ...
    boundaryIntegral).';
end

function [stateNext, leftFlux, rightFlux, diagnostics] = forwardEuler( ...
        state, activeCellCount, gamma, dx, dt, rhoFloor, pFloor, leftBoundaryMode, ...
        rightBoundaryMode, ambientState)
cellCount = activeCellCount;
maximumCellCount = size(state, 2);
alphaStage = stageAlpha(state, gamma, cellCount);
lambda = dt / dx;
[rho, velocity, pressure] = recoverPrimitives(state, gamma);
slopeRho = minmodSlopes(rho, cellCount);
slopeVelocity = minmodSlopes(velocity, cellCount);
slopePressure = minmodSlopes(pressure, cellCount);
leftPrimitive = zeros(3, maximumCellCount);
rightPrimitive = zeros(3, maximumCellCount);
minmodActivationCount = 0;
minmodLimitedCellCount = 0;
reconstructionPPActivationCount = 0;
reconstructionPPLimitedCellCount = 0;
reconstructionPPMinTheta = 1;
minimumReconstructedDensity = inf;
minimumReconstructedPressure = inf;
for cellIndex = 1:cellCount
    slopes = [slopeRho(cellIndex); slopeVelocity(cellIndex); ...
        slopePressure(cellIndex)];
    if cellIndex > 1 && cellIndex < cellCount
        centered = 0.5 * [rho(cellIndex + 1) - rho(cellIndex - 1); ...
            velocity(cellIndex + 1) - velocity(cellIndex - 1); ...
            pressure(cellIndex + 1) - pressure(cellIndex - 1)];
        limited = abs(slopes - centered) > 32 * eps(max([1; abs(slopes); ...
            abs(centered)]));
        minmodActivationCount = minmodActivationCount + sum(limited);
        minmodLimitedCellCount = minmodLimitedCellCount + double(any(limited));
    end
    reconstruction = s12_pp_reconstruct_primitive( ...
        [rho(cellIndex); velocity(cellIndex); pressure(cellIndex)], ...
        slopes, rhoFloor, pFloor);
    leftPrimitive(:, cellIndex) = reconstruction.left;
    rightPrimitive(:, cellIndex) = reconstruction.right;
    reconstructionPPMinTheta = min(reconstructionPPMinTheta, reconstruction.theta);
    active = reconstruction.theta < 1 - 32 * eps;
    reconstructionPPActivationCount = reconstructionPPActivationCount + double(active);
    reconstructionPPLimitedCellCount = reconstructionPPLimitedCellCount + double(active);
    minimumReconstructedDensity = min(minimumReconstructedDensity, ...
        min(reconstruction.left(1), reconstruction.right(1)));
    minimumReconstructedPressure = min(minimumReconstructedPressure, ...
        min(reconstruction.left(3), reconstruction.right(3)));
end
interfaceFlux = zeros(3, maximumCellCount + 1);
fluxPPActivationCount = 0;
fluxPPLimitedInterfaceCount = 0;
fluxPPMinTheta = 1;
minimumAnchorDensity = inf;
minimumAnchorPressure = inf;
minimumFinalPartialDensity = inf;
minimumFinalPartialPressure = inf;
maximumFluxCorrectionNorm = 0;
for interfaceIndex = 1:(cellCount + 1)
    if interfaceIndex == 1
        leftIndex = 1;
        rightIndex = 1;
        leftState = boundaryState(state(:, 1), ambientState, gamma, 1, ...
            leftBoundaryMode);
        rightState = state(:, 1);
    elseif interfaceIndex == cellCount + 1
        leftIndex = cellCount;
        rightIndex = cellCount;
        leftState = state(:, cellCount);
        rightState = boundaryState(state(:, cellCount), ambientState, gamma, 2, ...
            rightBoundaryMode);
    else
        leftIndex = interfaceIndex - 1;
        rightIndex = interfaceIndex;
        leftState = conservativeFromPrimitives(rightPrimitive(1, leftIndex), ...
            rightPrimitive(2, leftIndex), rightPrimitive(3, leftIndex), gamma);
        rightState = conservativeFromPrimitives(leftPrimitive(1, rightIndex), ...
            leftPrimitive(2, rightIndex), leftPrimitive(3, rightIndex), gamma);
    end
    highFlux = hllcFlux(leftState, rightState, gamma);
    lowFlux = s12_pp_global_lf_flux(state(:, leftIndex), ...
        state(:, rightIndex), gamma, alphaStage);
    limitedFlux = s12_pp_limit_interface_flux(state(:, leftIndex), ...
        state(:, rightIndex), highFlux, lowFlux, lambda, gamma, rhoFloor, pFloor);
    interfaceFlux(:, interfaceIndex) = limitedFlux.flux;
    fluxPPMinTheta = min(fluxPPMinTheta, limitedFlux.theta);
    active = limitedFlux.theta < 1 - 32 * eps;
    fluxPPActivationCount = fluxPPActivationCount + double(active);
    fluxPPLimitedInterfaceCount = fluxPPLimitedInterfaceCount + double(active);
    minimumAnchorDensity = min(minimumAnchorDensity, ...
        min(limitedFlux.low_left_partial(1), limitedFlux.low_right_partial(1)));
    minimumAnchorPressure = min(minimumAnchorPressure, ...
        min(pressureOf(limitedFlux.low_left_partial, gamma), ...
        pressureOf(limitedFlux.low_right_partial, gamma)));
    minimumFinalPartialDensity = min(minimumFinalPartialDensity, ...
        min(limitedFlux.left_partial(1), limitedFlux.right_partial(1)));
    minimumFinalPartialPressure = min(minimumFinalPartialPressure, ...
        min(pressureOf(limitedFlux.left_partial, gamma), ...
        pressureOf(limitedFlux.right_partial, gamma)));
    maximumFluxCorrectionNorm = max(maximumFluxCorrectionNorm, ...
        limitedFlux.correction_norm);
end
stateNext = state;
for cellIndex = 1:cellCount
    stateNext(:, cellIndex) = state(:, cellIndex) - lambda * ...
        (interfaceFlux(:, cellIndex + 1) - interfaceFlux(:, cellIndex));
end
validateState(stateNext, gamma, rhoFloor, pFloor);
leftFlux = interfaceFlux(:, 1);
rightFlux = interfaceFlux(:, end);
diagnostics = [minmodActivationCount, minmodLimitedCellCount, ...
    max(cellCount - 2, 0), reconstructionPPActivationCount, ...
    reconstructionPPLimitedCellCount, reconstructionPPMinTheta, ...
    minimumReconstructedDensity, minimumReconstructedPressure, 0, ...
    fluxPPActivationCount, fluxPPLimitedInterfaceCount, cellCount + 1, ...
    fluxPPMinTheta, minimumAnchorDensity, minimumAnchorPressure, ...
    minimumFinalPartialDensity, minimumFinalPartialPressure, alphaStage, ...
    maximumFluxCorrectionNorm, 0];
end

function state = boundaryState(interiorState, ambientState, gamma, side, mode)
[rho, velocity, pressure, soundSpeed] = recoverScalar(interiorState, gamma);
[~, ambientVelocity, ambientPressure, ambientSoundSpeed] = ...
    recoverScalar(ambientState, gamma);
if mode ~= 1 && (abs(velocity) >= soundSpeed || abs(ambientVelocity) >= ambientSoundSpeed)
    error('S12:TransientWave:BoundaryRegime', ...
        'Validation-only open/nonreflecting boundaries require subsonic flow.');
end
if side == 2
    outgoing = velocity + 2 * soundSpeed / (gamma - 1);
    incomingAmbient = ambientVelocity - 2 * ambientSoundSpeed / (gamma - 1);
else
    outgoing = velocity - 2 * soundSpeed / (gamma - 1);
    incomingAmbient = ambientVelocity + 2 * ambientSoundSpeed / (gamma - 1);
end
if mode == 1
    state = conservativeFromPrimitives(rho, -velocity, pressure, gamma);
    return
end
entropyInvariant = pressure / rho^gamma;
if mode == 2
    boundaryDensity = (ambientPressure / entropyInvariant)^(1 / gamma);
    boundarySoundSpeed = sqrt(gamma * ambientPressure / boundaryDensity);
    if side == 2
        boundaryVelocity = outgoing - 2 * boundarySoundSpeed / (gamma - 1);
    else
        boundaryVelocity = outgoing + 2 * boundarySoundSpeed / (gamma - 1);
    end
    state = conservativeFromPrimitives(boundaryDensity, boundaryVelocity, ...
        ambientPressure, gamma);
elseif mode == 3
    boundaryVelocity = 0.5 * (outgoing + incomingAmbient);
    if side == 2
        boundarySoundSpeed = 0.25 * (gamma - 1) * ...
            (outgoing - incomingAmbient);
    else
        boundarySoundSpeed = 0.25 * (gamma - 1) * ...
            (incomingAmbient - outgoing);
    end
    if boundarySoundSpeed <= 0 || ~isfinite(boundarySoundSpeed)
        error('S12:TransientWave:BoundaryState', ...
            'Characteristic boundary construction is nonphysical.');
    end
    boundaryDensity = (boundarySoundSpeed^2 / ...
        (gamma * entropyInvariant))^(1 / (gamma - 1));
    boundaryPressure = entropyInvariant * boundaryDensity^gamma;
    state = conservativeFromPrimitives(boundaryDensity, boundaryVelocity, ...
        boundaryPressure, gamma);
else
    error('S12:TransientWave:BoundaryMode', ...
        'Unknown transient-wave boundary mode.');
end
if any(~isfinite(state)) || state(1) <= 0 || pressureOf(state, gamma) <= 0
    error('S12:TransientWave:BoundaryState', ...
        'Boundary construction produced an invalid state.');
end
end

function stateNext = exactDarcyStep(state, ~, fDarcy, diameter, dt)
if fDarcy == 0 || dt == 0
    stateNext = state;
    return
end
density = state(1, :);
velocity = state(2, :) ./ density;
k = fDarcy / (2 * diameter);
stateNext = state;
stateNext(2, :) = density .* velocity ./ (1 + k * abs(velocity) * dt);
end

function total = accumulateDiagnostics(total, d0, d1, d2, U1, U2, U3, gamma, cellCount)
for diagnostics = [d0(:), d1(:), d2(:)]
    total(1) = min(total(1), diagnostics(7));
    total(2) = min(total(2), diagnostics(8));
    total(3) = total(3) + diagnostics(9);
    total(4) = total(4) + diagnostics(1);
    total(5) = total(5) + diagnostics(2);
    total(6) = total(6) + diagnostics(3);
    total(7) = total(7) + 1;
    total(9) = total(9) + diagnostics(4);
    total(10) = total(10) + diagnostics(5);
    total(11) = total(11) + diagnostics(3);
    total(12) = min(total(12), diagnostics(6));
    total(13) = total(13) + diagnostics(10);
    total(14) = total(14) + diagnostics(11);
    total(15) = total(15) + diagnostics(12);
    total(16) = min(total(16), diagnostics(13));
    total(17) = min(total(17), diagnostics(14));
    total(18) = min(total(18), diagnostics(15));
    total(19) = min(total(19), diagnostics(16));
    total(20) = min(total(20), diagnostics(17));
    total(21) = max(total(21), diagnostics(18));
    total(22) = max(total(22), diagnostics(19));
    total(23) = total(23) + diagnostics(20);
end
[rho1, ~, p1] = recoverPrimitives(U1, gamma);
[rho2, ~, p2] = recoverPrimitives(U2, gamma);
[rho3, ~, p3] = recoverPrimitives(U3, gamma);
total(26) = min(total(26), minFirst(rho1, cellCount)); total(27) = min(total(27), minFirst(p1, cellCount));
total(28) = min(total(28), minFirst(rho2, cellCount)); total(29) = min(total(29), minFirst(p2, cellCount));
total(30) = min(total(30), minFirst(rho3, cellCount)); total(31) = min(total(31), minFirst(p3, cellCount));
stageDiagnostics = [d0(:), d1(:), d2(:)];
for stageIndex = 1:3
    total(31 + stageIndex) = min(total(31 + stageIndex), ...
        stageDiagnostics(7, stageIndex));
    total(34 + stageIndex) = min(total(34 + stageIndex), ...
        stageDiagnostics(8, stageIndex));
    total(37 + stageIndex) = min(total(37 + stageIndex), ...
        stageDiagnostics(14, stageIndex));
    total(40 + stageIndex) = min(total(40 + stageIndex), ...
        stageDiagnostics(15, stageIndex));
    total(43 + stageIndex) = min(total(43 + stageIndex), ...
        stageDiagnostics(16, stageIndex));
    total(46 + stageIndex) = min(total(46 + stageIndex), ...
        stageDiagnostics(17, stageIndex));
end
end

function [pressureValues, velocityValues] = probeTrace(state, gamma, indices)
[~, velocity, pressure] = recoverPrimitives(state, gamma);
pressureValues = pressure(indices).';
velocityValues = velocity(indices).';
end

function indices = probeIndicesFor(cellCount)
indices = [max(1, round(0.25 * (cellCount + 1))), ...
    max(1, round(0.50 * (cellCount + 1))), ...
    min(cellCount, max(1, round(0.75 * (cellCount + 1))))];
end

function alpha = stageAlpha(state, gamma, cellCount)
alpha = 0;
for cellIndex = 1:cellCount
    [~, velocity, ~, soundSpeed] = recoverScalar(state(:, cellIndex), gamma);
    alpha = max(alpha, abs(velocity) + soundSpeed);
end
end

function validateInputs(initialState, ambientState, gamma, dx, endTime, cfl, ...
        maxSteps, rhoFloor, pFloor, cflHardMaximum, leftBoundaryMode, ...
        rightBoundaryMode, fDarcy, diameter, traceCapacity, maximumCellCount, ...
        activeCellCount)
if ~isequal(size(initialState), [3, maximumCellCount]) || ...
        any(~isfinite(initialState(:)))
    error('S12:TransientWave:InitialStateInput', ...
        'Initial state must be a finite 3-by-maximum-cell buffer.');
end
if ~isequal(size(ambientState), [3, 1]) || any(~isfinite(ambientState(:)))
    error('S12:TransientWave:AmbientStateInput', ...
        'Ambient state must be a finite 3-by-1 conservative vector.');
end
if gamma <= 1
    error('S12:TransientWave:GammaInput', 'Gamma must exceed one.');
end
if dx <= 0
    error('S12:TransientWave:DxInput', 'Dx must be positive.');
end
if endTime < 0
    error('S12:TransientWave:EndTimeInput', 'End time must be nonnegative.');
end
if cfl <= 0
    error('S12:TransientWave:CFLInput', 'CFL must be positive.');
end
if maxSteps < 1 || maxSteps > traceCapacity - 1
    error('S12:TransientWave:StepCapacity', ...
        'The requested step count exceeds the fixed trace capacity.');
end
if activeCellCount < 3 || activeCellCount > maximumCellCount || ...
        activeCellCount ~= floor(activeCellCount)
    error('S12:TransientWave:ActiveCellInput', ...
        'Active cell count must be an integer in the fixed buffer range.');
end
if rhoFloor <= 0 || pFloor <= 0 || cflHardMaximum <= 0 || ...
        fDarcy < 0 || diameter <= 0
    error('S12:TransientWave:PositiveInput', ...
        'Floors, CFL bound, and Darcy geometry must be positive.');
end
if leftBoundaryMode < 1 || leftBoundaryMode > 3 || ...
        rightBoundaryMode < 1 || rightBoundaryMode > 3
    error('S12:TransientWave:BoundaryModeInput', ...
        'Boundary modes must be in the explicit validation-only enum.');
end
end

function validateState(state, gamma, rhoFloor, pFloor)
for cellIndex = 1:size(state, 2)
    [rho, ~, pressure] = recoverScalar(state(:, cellIndex), gamma);
    if ~isfinite(rho) || ~isfinite(pressure) || rho < rhoFloor || pressure < pFloor
        error('S12:Positivity:InvalidStage', ...
            'A PP stage violated the configured floors.');
    end
end
end

function [rho, velocity, pressure] = recoverPrimitives(state, gamma)
rho = state(1, :);
velocity = state(2, :) ./ rho;
pressure = (gamma - 1) * (state(3, :) - 0.5 * rho .* velocity.^2);
end

function [rho, velocity, pressure, soundSpeed] = recoverScalar(state, gamma)
[rhoVector, velocityVector, pressureVector] = recoverPrimitives(state, gamma);
rho = rhoVector(1); velocity = velocityVector(1); pressure = pressureVector(1);
soundSpeed = sqrt(gamma * pressure / rho);
end

function value = pressureOf(state, gamma)
[~, ~, pressure] = recoverPrimitives(state, gamma);
value = pressure(1);
end

function state = conservativeFromPrimitives(rho, velocity, pressure, gamma)
state = [rho; rho * velocity; pressure / (gamma - 1) + ...
    0.5 * rho * velocity^2];
end

function slopes = minmodSlopes(values, cellCount)
slopes = zeros(size(values));
for cellIndex = 2:(cellCount - 1)
    slopes(cellIndex) = minmod(values(cellIndex) - values(cellIndex - 1), ...
        values(cellIndex + 1) - values(cellIndex));
end
end

function value = minFirst(values, cellCount)
value = inf;
for cellIndex = 1:cellCount
    value = min(value, values(cellIndex));
end
end

function value = minmod(leftDelta, rightDelta)
if leftDelta * rightDelta <= 0
    value = 0;
elseif abs(leftDelta) <= abs(rightDelta)
    value = leftDelta;
else
    value = rightDelta;
end
end

function flux = hllcFlux(stateL, stateR, gamma)
rhoL = stateL(1); rhoR = stateR(1);
uL = stateL(2) / rhoL; uR = stateR(2) / rhoR;
energyL = stateL(3); energyR = stateR(3);
pL = (gamma - 1) * (energyL - 0.5 * rhoL * uL * uL);
pR = (gamma - 1) * (energyR - 0.5 * rhoR * uR * uR);
soundL = sqrt(gamma * pL / rhoL); soundR = sqrt(gamma * pR / rhoR);
sL = min(uL - soundL, uR - soundR);
sR = max(uL + soundL, uR + soundR);
sM = (pR - pL + rhoL * uL * (sL - uL) - rhoR * uR * (sR - uR)) / ...
    (rhoL * (sL - uL) - rhoR * (sR - uR));
fluxL = [rhoL * uL; rhoL * uL * uL + pL; uL * (energyL + pL)];
fluxR = [rhoR * uR; rhoR * uR * uR + pR; uR * (energyR + pR)];
if sL >= 0
    flux = fluxL;
elseif sM >= 0
    rhoStarL = rhoL * (sL - uL) / (sL - sM);
    energyStarL = rhoStarL * (energyL / rhoL + (sM - uL) * ...
        (sM + pL / (rhoL * (sL - uL))));
    flux = fluxL + sL * ([rhoStarL; rhoStarL * sM; energyStarL] - stateL);
elseif sR > 0
    rhoStarR = rhoR * (sR - uR) / (sR - sM);
    energyStarR = rhoStarR * (energyR / rhoR + (sM - uR) * ...
        (sM + pR / (rhoR * (sR - uR))));
    flux = fluxR + sR * ([rhoStarR; rhoStarR * sM; energyStarR] - stateR);
else
    flux = fluxR;
end
end
