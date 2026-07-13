function location = s12_benchmark_leading_level_location( ...
        x, signal, baseline, amplitude, fraction)
%S12_BENCHMARK_LEADING_LEVEL_LOCATION Locate a resolved leading level set.
if ~isvector(x) || ~isvector(signal) || numel(x) ~= numel(signal)
    error("S12:Benchmark:LeadingLevelShape", ...
        "x and signal must be vectors with equal lengths.");
end
if ~isscalar(baseline) || ~isscalar(amplitude) || ~isscalar(fraction) || ...
        ~isfinite(amplitude) || amplitude <= 0 || ...
        ~isfinite(fraction) || fraction <= 0 || fraction >= 1
    error("S12:Benchmark:LeadingLevelParameters", ...
        "amplitude must be positive and fraction must lie in (0, 1).");
end
index = find(abs(signal - baseline) >= fraction * amplitude, 1);
if isempty(index)
    location = NaN;
else
    location = x(index);
end
end
