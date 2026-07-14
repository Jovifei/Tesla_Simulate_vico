function slopes = s12_pp_minmod_primitive_slopes(primitive, options)
%S12_PP_MINMOD_PRIMITIVE_SLOPES Compute explicit periodic/transmissive slopes.
arguments
    primitive (3,:) double
    options.Boundary (1,1) string {mustBeMember(options.Boundary, ...
        ["periodic", "transmissive"])}
end
cellCount = size(primitive, 2);
slopes = zeros(size(primitive));
if cellCount < 3
    return
end
for cellIndex = 1:cellCount
    if options.Boundary == "transmissive" && ...
            (cellIndex == 1 || cellIndex == cellCount)
        continue
    end
    leftIndex = mod(cellIndex - 2, cellCount) + 1;
    rightIndex = mod(cellIndex, cellCount) + 1;
    leftDelta = primitive(:, cellIndex) - primitive(:, leftIndex);
    rightDelta = primitive(:, rightIndex) - primitive(:, cellIndex);
    sameSign = leftDelta .* rightDelta > 0;
    slopes(sameSign, cellIndex) = sign(leftDelta(sameSign)) .* ...
        min(abs(leftDelta(sameSign)), abs(rightDelta(sameSign)));
end
end
