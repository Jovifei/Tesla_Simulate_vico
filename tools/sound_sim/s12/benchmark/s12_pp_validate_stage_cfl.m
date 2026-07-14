function courant = s12_pp_validate_stage_cfl(dt, dx, alpha, hardMaximum)
%S12_PP_VALIDATE_STAGE_CFL Enforce the frozen global-LF CFL hard limit.
arguments
    dt (1,1) double {mustBePositive}
    dx (1,1) double {mustBePositive}
    alpha (1,1) double {mustBePositive}
    hardMaximum (1,1) double {mustBePositive}
end
courant = dt * alpha / dx;
if courant > hardMaximum + 32 * eps(max(1, hardMaximum))
    error("S12:Positivity:CflHardLimit", ...
        "The full SSP step must be rejected above the PP CFL hard limit.");
end
end
