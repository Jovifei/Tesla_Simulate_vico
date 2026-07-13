function state = s12_benchmark_primitive_to_conservative(rho, velocity, pressure, gamma)
%S12_BENCHMARK_PRIMITIVE_TO_CONSERVATIVE Convert ideal-gas primitives.
state = [rho; rho .* velocity; ...
    pressure / (gamma - 1) + 0.5 * rho .* velocity.^2];
end
