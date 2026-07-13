function locations = s12_benchmark_gradient_locations(x, density, count, minSeparation)
%S12_BENCHMARK_GRADIENT_LOCATIONS Return separated dominant density gradients.
arguments
    x (1,:) double
    density (1,:) double
    count (1,1) double {mustBeInteger, mustBePositive}
    minSeparation (1,1) double {mustBeNonnegative}
end
locations = NaN(1, count);
if numel(x) < 2 || any(~isfinite(density))
    return
end
gradient = abs(diff(density) ./ diff(x));
centers = 0.5 * (x(1:end - 1) + x(2:end));
[~, order] = sort(gradient, "descend");
selected = zeros(1, 0);
for index = 1:numel(order)
    candidate = centers(order(index));
    if isempty(selected) || all(abs(candidate - selected) >= minSeparation)
        selected(end + 1) = candidate; %#ok<AGROW>
        if numel(selected) == count
            break
        end
    end
end
locations(1:numel(selected)) = sort(selected);
end
