function result = s12_pp_global_lf_anchor(leftState, rightState, gamma, ...
        alpha, lambda, rhoFloor, pFloor)
%S12_PP_GLOBAL_LF_ANCHOR Form admissible one-sided low-order partial states.
flux = s12_pp_global_lf_flux(leftState, rightState, gamma, alpha);
leftPartial = leftState - 2 * lambda * flux;
rightPartial = rightState + 2 * lambda * flux;
if ~isAdmissible(leftPartial, gamma, rhoFloor, pFloor) || ...
        ~isAdmissible(rightPartial, gamma, rhoFloor, pFloor)
    error("S12:Positivity:InvalidLowOrderAnchor", ...
        "Global LF one-sided partial states must satisfy both floors.");
end
result = struct("flux", flux, "left_partial", leftPartial, ...
    "right_partial", rightPartial);
end

function valid = isAdmissible(state, gamma, rhoFloor, pFloor)
rho = state(1);
velocity = state(2) / rho;
pressure = (gamma - 1) * (state(3) - 0.5 * rho * velocity^2);
valid = all(isfinite(state)) && rho >= rhoFloor && pressure >= pFloor;
end
