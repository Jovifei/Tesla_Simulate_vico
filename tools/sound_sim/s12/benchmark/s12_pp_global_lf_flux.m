function flux = s12_pp_global_lf_flux(leftState, rightState, gamma, alpha)
%S12_PP_GLOBAL_LF_FLUX Evaluate the stage-global Lax-Friedrichs flux.
if ~(isfinite(gamma) && gamma > 1 && isfinite(alpha) && alpha >= 0) || ...
        ~isequal(size(leftState), size(rightState)) || size(leftState, 1) ~= 3
    error("S12:Positivity:InvalidFluxInput", ...
        "Global LF inputs must have compatible states and finite parameters.");
end
flux = 0.5 * (physicalFlux(leftState, gamma) + ...
    physicalFlux(rightState, gamma) + alpha * (leftState - rightState));
end

function flux = physicalFlux(state, gamma)
rho = state(1, :);
velocity = state(2, :) ./ rho;
pressure = (gamma - 1) * (state(3, :) - 0.5 * rho .* velocity.^2);
if any(~isfinite(state), "all") || any(rho <= 0) || any(pressure <= 0)
    error("S12:Positivity:InvalidCellAverage", ...
        "Global LF inputs must have positive density and pressure.");
end
flux = [rho .* velocity; rho .* velocity.^2 + pressure; ...
    velocity .* (state(3, :) + pressure)];
end
