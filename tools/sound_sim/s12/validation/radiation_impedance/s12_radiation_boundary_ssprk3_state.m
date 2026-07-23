function result = s12_radiation_boundary_ssprk3_state(package, state0, outgoing, dt)
%S12_RADIATION_BOUNDARY_SSPRK3_STATE Advance the explicit boundary state.
arguments
    package (1,1) struct
    state0 (2,1) double {mustBeFinite}
    outgoing (1,3) double {mustBeFinite}
    dt (1,1) double {mustBeFinite, mustBeGreaterThan(dt, 0)}
end
if ~all(isfield(package, ["state_space_A", "state_space_B"])) || ...
        ~isequal(size(package.state_space_A), [2, 2]) || ...
        ~isequal(size(package.state_space_B), [2, 1])
    error("S12:Radiation:InvalidState", ...
        "Radiation package must provide finite two-state dynamics.");
end
derivative0 = package.state_space_A * state0 + package.state_space_B * outgoing(1);
state1 = state0 + dt * derivative0;
derivative1 = package.state_space_A * state1 + package.state_space_B * outgoing(2);
state2 = 0.75 * state0 + 0.25 * (state1 + dt * derivative1);
derivative2 = package.state_space_A * state2 + package.state_space_B * outgoing(3);
state3 = (1 / 3) * state0 + (2 / 3) * (state2 + dt * derivative2);
if any(~isfinite([state1; state2; state3]))
    error("S12:Radiation:InvalidState", ...
        "Radiation SSP-RK3 update produced a non-finite state.");
end
result = struct("initial_state", state0, "stage_state", [state1, state2], ...
    "final_state", state3, "stage_dt_s", [dt, dt, dt], ...
    "outgoing_pressure_pa", outgoing, "integrator_id", "augmented_ssprk3.v1");
end
