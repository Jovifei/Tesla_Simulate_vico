function arrivalTime = s12_transient_wave_arrival_time(time, signal, leadingFraction)
%S12_TRANSIENT_WAVE_ARRIVAL_TIME Measure a fixed leading-level crossing.
arguments
    time (1,:) double {mustBeFinite}
    signal (1,:) double {mustBeFinite}
    leadingFraction (1,1) double {mustBeGreaterThan(leadingFraction, 0), ...
        mustBeLessThan(leadingFraction, 1)}
end
if numel(time) ~= numel(signal) || numel(time) < 2 || any(diff(time) <= 0)
    error("S12:TransientWave:InvalidTrace", ...
        "Arrival-time traces must be strictly increasing and aligned.");
end
envelope = abs(signal);
threshold = leadingFraction * max(envelope);
if threshold <= 0
    error("S12:TransientWave:NoArrival", ...
        "A zero-amplitude trace has no deterministic arrival time.");
end
index = find(envelope >= threshold, 1);
if isempty(index)
    error("S12:TransientWave:NoArrival", ...
        "The leading level was not reached in the supplied trace.");
end
if index == 1
    arrivalTime = time(1);
    return
end
previous = envelope(index - 1);
current = envelope(index);
fraction = (threshold - previous) / (current - previous);
arrivalTime = time(index - 1) + fraction * (time(index) - time(index - 1));
end
