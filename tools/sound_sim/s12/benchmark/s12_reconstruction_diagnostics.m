function diagnostics = s12_reconstruction_diagnostics(state, gamma, reconstruction)
%S12_RECONSTRUCTION_DIAGNOSTICS Observe reconstruction without changing fluxes.
arguments
    state (3,:) double
    gamma (1,1) double {mustBeGreaterThan(gamma, 1)}
    reconstruction (1,1) string {mustBeMember(reconstruction, ...
        ["first_order", "muscl_minmod"])}
end

rho = state(1, :);
velocity = state(2, :) ./ rho;
pressure = (gamma - 1) * (state(3, :) - 0.5 * rho .* velocity.^2);
if reconstruction == "first_order"
    interfaceRho = rho;
    interfacePressure = pressure;
    activationCount = 0;
    limitedCellCount = 0;
else
    [slopeRho, rhoActive] = minmodSlopes(rho);
    [~, velocityActive] = minmodSlopes(velocity);
    [slopePressure, pressureActive] = minmodSlopes(pressure);
    interfaceRho = [rho + 0.5 * slopeRho, rho - 0.5 * slopeRho];
    interfacePressure = [pressure + 0.5 * slopePressure, ...
        pressure - 0.5 * slopePressure];
    activationCount = nnz(rhoActive) + nnz(velocityActive) + nnz(pressureActive);
    limitedCellCount = nnz(rhoActive | velocityActive | pressureActive);
end

invalid = any(~isfinite(interfaceRho) | ~isfinite(interfacePressure) | ...
    interfaceRho <= 0 | interfacePressure <= 0);
diagnostics = struct( ...
    "minimum_reconstructed_density", min(interfaceRho), ...
    "minimum_reconstructed_pressure", min(interfacePressure), ...
    "invalid_reconstruction_count", double(invalid), ...
    "limiter_activation_count", activationCount, ...
    "limited_cell_count", limitedCellCount, ...
    "sampled_cell_count", numel(rho));
end

function [slopes, active] = minmodSlopes(values)
cellCount = numel(values);
slopes = zeros(size(values));
active = false(size(values));
if cellCount < 3
    return
end
for cellIndex = 1:cellCount
    leftIndex = mod(cellIndex - 2, cellCount) + 1;
    rightIndex = mod(cellIndex, cellCount) + 1;
    leftDelta = values(cellIndex) - values(leftIndex);
    rightDelta = values(rightIndex) - values(cellIndex);
    centered = 0.5 * (leftDelta + rightDelta);
    slopes(cellIndex) = minmod(leftDelta, rightDelta);
    active(cellIndex) = abs(slopes(cellIndex) - centered) > ...
        32 * eps(max(1, abs(centered)));
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
