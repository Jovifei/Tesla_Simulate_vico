function result = s12_pp_limit_interface_flux(leftState, rightState, ...
        highFlux, lowFlux, lambda, gamma, rhoFloor, pFloor)
%S12_PP_LIMIT_INTERFACE_FLUX Limit one shared conservative interface flux.
lowLeft = leftState - 2 * lambda * lowFlux;
lowRight = rightState + 2 * lambda * lowFlux;
if ~isAdmissible(lowLeft, gamma, rhoFloor, pFloor) || ...
        ~isAdmissible(lowRight, gamma, rhoFloor, pFloor)
    error("S12:Positivity:InvalidLowOrderAnchor", ...
        "The low-order anchor must be admissible before flux limiting.");
end
highLeft = leftState - 2 * lambda * highFlux;
highRight = rightState + 2 * lambda * highFlux;
theta = min(densityTheta(lowLeft(1), highLeft(1), rhoFloor), ...
    densityTheta(lowRight(1), highRight(1), rhoFloor));
theta = pressureTheta(leftState, rightState, highFlux, lowFlux, ...
    lambda, gamma, rhoFloor, pFloor, theta);
flux = lowFlux + theta * (highFlux - lowFlux);
leftPartial = leftState - 2 * lambda * flux;
rightPartial = rightState + 2 * lambda * flux;
if ~isAdmissible(leftPartial, gamma, rhoFloor, pFloor) || ...
        ~isAdmissible(rightPartial, gamma, rhoFloor, pFloor)
    error("S12:Positivity:FluxLimitFailure", ...
        "The limited shared flux did not produce admissible partial states.");
end
result = struct("flux", flux, "theta", theta, ...
    "left_partial", leftPartial, "right_partial", rightPartial, ...
    "low_left_partial", lowLeft, "low_right_partial", lowRight, ...
    "correction_norm", norm(flux - highFlux));
end

function theta = densityTheta(lowDensity, highDensity, floorValue)
theta = 1;
if highDensity < floorValue
    theta = (lowDensity - floorValue) / (lowDensity - highDensity);
end
theta = min(max(theta, 0), 1);
end

function theta = pressureTheta(leftState, rightState, highFlux, lowFlux, ...
        lambda, gamma, rhoFloor, pFloor, upperTheta)
theta = upperTheta;
if pairAdmissible(leftState, rightState, highFlux, lowFlux, lambda, ...
        gamma, rhoFloor, pFloor, theta)
    return
end
lower = 0;
upper = upperTheta;
for iteration = 1:60
    middle = 0.5 * (lower + upper);
    if pairAdmissible(leftState, rightState, highFlux, lowFlux, lambda, ...
            gamma, rhoFloor, pFloor, middle)
        lower = middle;
    else
        upper = middle;
    end
end
theta = lower;
end

function valid = pairAdmissible(leftState, rightState, highFlux, lowFlux, ...
        lambda, gamma, rhoFloor, pFloor, theta)
flux = lowFlux + theta * (highFlux - lowFlux);
valid = isAdmissible(leftState - 2 * lambda * flux, ...
    gamma, rhoFloor, pFloor) && ...
    isAdmissible(rightState + 2 * lambda * flux, ...
    gamma, rhoFloor, pFloor);
end

function valid = isAdmissible(state, gamma, rhoFloor, pFloor)
rho = state(1);
velocity = state(2) / rho;
pressure = (gamma - 1) * (state(3) - 0.5 * rho * velocity^2);
valid = all(isfinite(state)) && rho >= rhoFloor && pressure >= pFloor;
end
