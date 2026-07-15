function averages = s12_fanno_cell_average(profile, cellEdges, quadratureNodes)
%S12_FANNO_CELL_AVERAGE Deterministically integrate conservative cell averages.
if ~isa(profile, "function_handle") || ~isnumeric(cellEdges) || ...
        ~isvector(cellEdges) || numel(cellEdges) < 2 || ...
        any(~isfinite(cellEdges)) || any(diff(cellEdges) <= 0) || ...
        ~isscalar(quadratureNodes) || quadratureNodes < 1 || ...
        quadratureNodes ~= floor(quadratureNodes)
    error("S12:Fanno:InvalidInput", "Invalid Fanno cell-average quadrature input.");
end
[nodes, weights] = gaussLegendre(quadratureNodes);
cellCount = numel(cellEdges) - 1;
averages = zeros(3, cellCount);
for cellIndex = 1:cellCount
    left = cellEdges(cellIndex);
    right = cellEdges(cellIndex + 1);
    x = 0.5 * ((right - left) * nodes + right + left);
    values = profile(x);
    if ~isequal(size(values), [3, quadratureNodes]) || any(~isfinite(values), "all")
        error("S12:Fanno:InvalidProfile", ...
            "Fanno profile must return finite 3-by-nodeCount conservative values.");
    end
    averages(:, cellIndex) = 0.5 * (values * weights);
end
end

function [nodes, weights] = gaussLegendre(count)
index = (1:count - 1).';
beta = index ./ sqrt(4 * index.^2 - 1);
matrix = diag(beta, 1) + diag(beta, -1);
[vectors, eigenvalues] = eig(matrix, "vector");
[sortedNodes, order] = sort(eigenvalues);
nodes = sortedNodes.';
weights = 2 * vectors(1, order).'.^2;
end
