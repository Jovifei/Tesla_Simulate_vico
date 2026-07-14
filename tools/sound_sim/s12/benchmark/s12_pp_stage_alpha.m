function alpha = s12_pp_stage_alpha(state, gamma)
%S12_PP_STAGE_ALPHA Return max(abs(u)+c) from stage cell averages.
arguments
    state (3,:) double
    gamma (1,1) double {mustBeGreaterThan(gamma, 1)}
end
rho = state(1, :);
velocity = state(2, :) ./ rho;
pressure = (gamma - 1) * (state(3, :) - 0.5 * rho .* velocity.^2);
if any(~isfinite(state), "all") || any(rho <= 0) || any(pressure <= 0)
    error("S12:Positivity:InvalidCellAverage", ...
        "Stage cell averages must have positive density and pressure.");
end
alpha = max(abs(velocity) + sqrt(gamma * pressure ./ rho));
end
