function result = s12_radiation_impedance_from_reflection(reflection, rho0, c0, radius)
%S12_RADIATION_IMPEDANCE_FROM_REFLECTION Convert pressure R to p/Q impedance.
arguments
    reflection {mustBeNumeric}
    rho0 (1,1) double {mustBeFinite, mustBePositive}
    c0 (1,1) double {mustBeFinite, mustBePositive}
    radius (1,1) double {mustBeFinite, mustBePositive}
end
if any(~isfinite(reflection) & ~isinf(reflection), "all")
    error("S12:Radiation:ReflectionFinite", "Reflection must be finite or infinite.");
end
area = pi * radius^2;
z0 = rho0 * c0 / area;
normalized = (1 + reflection) ./ (1 - reflection);
result = struct( ...
    "reflection", reflection, ...
    "cross_section_area_m2", area, ...
    "characteristic_impedance", z0, ...
    "normalized_impedance", normalized, ...
    "impedance_pa_s_per_m3", normalized * z0);
end
