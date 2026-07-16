function result = s12_radiation_unflanged_reference(ka, definition)
%S12_RADIATION_UNFLANGED_REFERENCE Direct Levine-Schwinger quadrature reference.
arguments
    ka {mustBeNumeric, mustBeReal, mustBeFinite}
    definition (1,1) struct
end
ka = reshape(double(ka), 1, []);
absoluteKa = abs(ka);
if any(absoluteKa >= definition.plane_wave_cutoff_ka)
    error("S12:Radiation:PlaneWaveCutoff", ...
        "The plane-wave reference rejects abs(ka) >= %.12g.", ...
        definition.plane_wave_cutoff_ka);
end
tightReflection = zeros(size(ka));
tightCorrection = zeros(size(ka));
coarseReflection = zeros(size(ka));
coarseCorrection = zeros(size(ka));
for index = 1:numel(ka)
    if absoluteKa(index) == 0
        tightReflection(index) = -1;
        tightCorrection(index) = definition.static_end_correction_over_radius;
        coarseReflection(index) = tightReflection(index);
        coarseCorrection(index) = tightCorrection(index);
        continue
    end
    [tightReflection(index), tightCorrection(index)] = solvePositiveKa( ...
        absoluteKa(index), 1e-12, 1e-11);
    [coarseReflection(index), coarseCorrection(index)] = solvePositiveKa( ...
        absoluteKa(index), 1e-10, 1e-9);
    if ka(index) < 0
        tightReflection(index) = conj(tightReflection(index));
        coarseReflection(index) = conj(coarseReflection(index));
    end
end
reflection = tightReflection;
endCorrection = tightCorrection;
impedance = s12_radiation_impedance_from_reflection(reflection, ...
    definition.rho0, definition.c0, definition.pipe_radius_m);
maximumAccepted = definition.accepted_ka_band(2);
if any(absoluteKa > maximumAccepted)
    applicability = "diagnostic_near_plane_wave_cutoff";
else
    applicability = "accepted_plane_wave_band";
end
result = struct( ...
    "ka", ka, ...
    "frequency_hz", ka * definition.c0 / (2 * pi * definition.pipe_radius_m), ...
    "reflection", reflection, ...
    "normalized_impedance", impedance.normalized_impedance, ...
    "impedance_pa_s_per_m3", impedance.impedance_pa_s_per_m3, ...
    "end_correction_over_radius", endCorrection, ...
    "reference_method_id", definition.reference_method_id, ...
    "applicability", applicability, ...
    "quadrature", struct( ...
        "tight_abs_tolerance", 1e-12, ...
        "tight_rel_tolerance", 1e-11, ...
        "coarse_abs_tolerance", 1e-10, ...
        "coarse_rel_tolerance", 1e-9, ...
        "maximum_reflection_difference", max(abs(tightReflection - coarseReflection)), ...
        "maximum_end_correction_difference", max(abs(tightCorrection - coarseCorrection))), ...
    "similarity", similarityCheck(reflection, definition));
end

function [reflection, correction] = solvePositiveKa(ka, absTolerance, relTolerance)
magnitudeIntegral = integral(@(theta) magnitudeIntegrand(theta, ka), ...
    0, pi / 2, "AbsTol", absTolerance, "RelTol", relTolerance);
correctionFirst = integral(@(theta) correctionFirstIntegrand(theta, ka), ...
    0, pi / 2, "AbsTol", absTolerance, "RelTol", relTolerance);
correctionSecond = integral(@(theta) correctionSecondIntegrand(theta, ka), ...
    0, pi / 2, "AbsTol", absTolerance, "RelTol", relTolerance);
correction = (correctionFirst + correctionSecond) / pi;
magnitude = exp(-2 * magnitudeIntegral / pi);
reflection = -magnitude * exp(-2i * ka * correction);
end

function value = magnitudeIntegrand(theta, ka)
value = zeros(size(theta));
active = theta > 0 & theta < pi / 2;
if ~any(active, "all"); return; end
x = ka * sin(theta(active));
value(active) = atan(-besselj(1, x) ./ bessely(1, x)) ./ sin(theta(active));
end

function value = correctionFirstIntegrand(theta, ka)
value = zeros(size(theta));
active = theta > 0 & theta < pi / 2;
if ~any(active, "all"); return; end
x = ka * sin(theta(active));
term = pi * besselj(1, x) .* hypot(besselj(1, x), bessely(1, x));
value(active) = log(term) ./ (ka * sin(theta(active)));
end

function value = correctionSecondIntegrand(theta, ka)
value = zeros(size(theta));
active = theta > 0 & theta < pi / 2;
if ~any(active, "all"); return; end
y = ka * tan(theta(active));
product = besseli(1, y, 1) .* besselk(1, y, 1);
logTerm = -log(2 * product);
underflow = ~isfinite(logTerm);
logTerm(underflow) = log(y(underflow));
value(active) = logTerm ./ (ka * sin(theta(active)));
end

function value = similarityCheck(reflection, definition)
base = s12_radiation_impedance_from_reflection(reflection, ...
    definition.rho0, definition.c0, definition.pipe_radius_m);
normalised = zeros(numel(definition.similarity_mappings), numel(reflection));
for index = 1:numel(definition.similarity_mappings)
    mapping = definition.similarity_mappings(index);
    converted = s12_radiation_impedance_from_reflection(reflection, ...
        mapping.rho0, mapping.c0, mapping.pipe_radius_m);
    normalised(index, :) = converted.impedance_pa_s_per_m3 / ...
        converted.characteristic_impedance;
end
value = struct( ...
    "mapping_count", numel(definition.similarity_mappings), ...
    "maximum_normalized_impedance_difference", ...
    max(abs(normalised - base.normalized_impedance), [], "all"));
end
