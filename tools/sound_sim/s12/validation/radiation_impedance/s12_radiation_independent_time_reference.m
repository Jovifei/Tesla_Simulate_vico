function result = s12_radiation_independent_time_reference( ...
        physical, boundaryLimit, time, outgoingPressure)
%S12_RADIATION_INDEPENDENT_TIME_REFERENCE Apply the frozen direct R(omega).
arguments
    physical (1,1) struct
    boundaryLimit (1,1) string
    time (1,:) double {mustBeFinite}
    outgoingPressure (1,:) double {mustBeFinite}
end
if numel(time) < 2 || numel(time) ~= numel(outgoingPressure) || ...
        any(diff(time) <= 0)
    error("S12:Radiation:InvalidReferenceInput", ...
        "Independent reference requires matching strictly increasing traces.");
end
uniformTime = linspace(time(1), time(end), numel(time));
uniformOutgoing = interp1(time, outgoingPressure, uniformTime, "pchip");
samplePeriod = uniformTime(2) - uniformTime(1);
fftSize = 2^nextpow2(2 * numel(uniformTime));
frequencyHz = (0:(fftSize - 1)) / (fftSize * samplePeriod);
signedFrequencyHz = frequencyHz;
signedFrequencyHz(frequencyHz > 1 / (2 * samplePeriod)) = ...
    signedFrequencyHz(frequencyHz > 1 / (2 * samplePeriod)) - 1 / samplePeriod;
ka = 2 * pi * signedFrequencyHz * physical.pipe_radius_m / physical.c0;
reflection = reflectionSpectrum(physical, boundaryLimit, ka);
outgoingSpectrum = fft(uniformOutgoing, fftSize);
incomingUniform = real(ifft(outgoingSpectrum .* reflection, fftSize));
incomingUniform = incomingUniform(1:numel(uniformTime));
incoming = interp1(uniformTime, incomingUniform, time, "pchip");
result = struct( ...
    "time_s", time, ...
    "incoming_pressure_pa", incoming, ...
    "reference_reflection", reflection, ...
    "frequency_hz", signedFrequencyHz, ...
    "ka", ka, ...
    "fft_size", fftSize, ...
    "sample_rate", 1 / samplePeriod, ...
    "interpolation_rule", "pchip_direct_quadrature_grid_129.v1", ...
    "reference_method_id", "levine_schwinger_direct_quadrature_fft.v1", ...
    "fit_method_id", physical.fit_method_id, ...
    "valid_ka_band", physical.accepted_ka_band);
end

function reflection = reflectionSpectrum(physical, boundaryLimit, ka)
switch boundaryLimit
    case "open"
        reflection = -ones(size(ka));
        return
    case "matched"
        reflection = zeros(size(ka));
        return
    case "rigid"
        reflection = ones(size(ka));
        return
    case "fitted"
    otherwise
        error("S12:Radiation:InvalidBoundary", "Unknown boundary limit.");
end
maximumKa = physical.accepted_ka_band(2);
persistent cacheKey referenceKa referenceReflection
nextKey = sprintf("%.17g|%.17g|%.17g|%.17g", maximumKa, ...
    physical.pipe_radius_m, physical.rho0, physical.c0);
if isempty(cacheKey) || cacheKey ~= nextKey
    referenceKa = linspace(0, maximumKa, 129);
    reference = s12_radiation_unflanged_reference(referenceKa, physical);
    referenceReflection = reference.reflection;
    cacheKey = nextKey;
end
absoluteKa = abs(ka);
limitedKa = min(absoluteKa, maximumKa);
magnitude = interp1(referenceKa, abs(referenceReflection), limitedKa, "pchip");
phase = interp1(referenceKa, unwrap(angle(referenceReflection)), limitedKa, "pchip");
reflection = magnitude .* exp(1i * sign(ka) .* phase);
reflection(ka == 0) = -1;
end
