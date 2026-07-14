function result = s12_pp_reconstruct_primitive(primitive, slopes, rhoFloor, pFloor)
%S12_PP_RECONSTRUCT_PRIMITIVE Scale one primitive slope with a shared theta.
if ~(isfinite(rhoFloor) && rhoFloor > 0 && isfinite(pFloor) && pFloor > 0) || ...
        size(primitive, 1) ~= 3 || ~isequal(size(primitive), size(slopes)) || ...
        any(~isfinite(primitive), "all") || ...
        any(~isfinite(slopes), "all")
    error("S12:Positivity:InvalidReconstructionInput", ...
        "Primitive states and slopes must be finite and have equal size.");
end
if any(primitive(1, :) < rhoFloor) || any(primitive(3, :) < pFloor)
    error("S12:Positivity:InvalidCellAverage", ...
        "Slope scaling cannot repair an inadmissible cell average.");
end
thetaRho = floorTheta(primitive(1, :), slopes(1, :), rhoFloor);
thetaPressure = floorTheta(primitive(3, :), slopes(3, :), pFloor);
theta = min([ones(1, size(primitive, 2)); thetaRho; thetaPressure], [], 1);
scaledSlopes = slopes .* theta;
result = struct("left", primitive - 0.5 * scaledSlopes, ...
    "right", primitive + 0.5 * scaledSlopes, "theta", theta);
end

function theta = floorTheta(center, slope, floorValue)
theta = ones(size(center));
active = 0.5 * abs(slope) > center - floorValue;
theta(active) = 2 * (center(active) - floorValue) ./ abs(slope(active));
theta = min(max(theta, 0), 1);
end
