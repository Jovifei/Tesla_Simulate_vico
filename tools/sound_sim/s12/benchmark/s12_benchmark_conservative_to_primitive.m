function [rho, velocity, pressure] = s12_benchmark_conservative_to_primitive(state, gamma)
%S12_BENCHMARK_CONSERVATIVE_TO_PRIMITIVE Convert ideal-gas conserved state.
rho = state(1, :);
velocity = state(2, :) ./ rho;
pressure = (gamma - 1) * (state(3, :) - 0.5 * rho .* velocity.^2);
end
