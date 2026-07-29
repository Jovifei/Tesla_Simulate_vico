function stats = s12_v11_compute_afterfire_statistics(events)
%S12_V11_COMPUTE_AFTERFIRE_STATISTICS Summarize synthetic event timing/clusters.

if ~(isstruct(events) || isempty(events))
    error("S12:EngineSoundV11:Analysis", "events must be a struct array.");
end
if isempty(events)
    stats = emptyStatistics();
    return;
end
required = ["time_s", "kind", "energy", "cluster_id"];
if ~all(isfield(events, cellstr(required)))
    error("S12:EngineSoundV11:Analysis", "events do not satisfy the afterfire statistics contract.");
end
times = double([events.time_s]);
energies = double([events.energy]);
if any(~isfinite(times)) || any(~isfinite(energies)) || any(energies < 0)
    error("S12:EngineSoundV11:Analysis", "event times and energies must be finite and nonnegative.");
end
[times, order] = sort(times);
energies = energies(order);
events = events(order);
intervals = diff(times);
intervalCv = coefficientOfVariation(intervals);
amplitudeCv = coefficientOfVariation(energies);
clusterIds = string({events.cluster_id});
uniqueClusters = unique(clusterIds, "stable");
clusterSizes = zeros(1, numel(uniqueClusters));
decaying = 0;
transitions = 0;
for index = 1:numel(uniqueClusters)
    mask = clusterIds == uniqueClusters(index);
    clusterSizes(index) = sum(mask);
    clusterEvents = events(mask);
    [~, clusterOrder] = sort([clusterEvents.time_s]);
    clusterEnergy = [clusterEvents(clusterOrder).energy];
    changes = diff(clusterEnergy);
    decaying = decaying + sum(changes < 0);
    transitions = transitions + numel(changes);
end
if transitions == 0
    decayFraction = 0;
else
    decayFraction = decaying / transitions;
end
kinds = string({events.kind});
stats = struct( ...
    "event_count", numel(events), ...
    "total_energy", sum(energies), ...
    "cluster_count", numel(uniqueClusters), ...
    "cluster_ids", uniqueClusters, ...
    "cluster_sizes", clusterSizes, ...
    "mean_interval_s", safeMean(intervals), ...
    "interval_std_s", safeStd(intervals), ...
    "interval_cv", intervalCv, ...
    "pulse_amplitude_cv", amplitudeCv, ...
    "decaying_transition_fraction", decayFraction, ...
    "kind_counts", struct( ...
        "upshift_bark", sum(kinds == "upshift_bark"), ...
        "downshift_blip_pop", sum(kinds == "downshift_blip_pop"), ...
        "overrun_crackle", sum(kinds == "overrun_crackle")));
end

function stats = emptyStatistics()
stats = struct( ...
    "event_count", 0, ...
    "total_energy", 0, ...
    "cluster_count", 0, ...
    "cluster_ids", strings(1, 0), ...
    "cluster_sizes", zeros(1, 0), ...
    "mean_interval_s", 0, ...
    "interval_std_s", 0, ...
    "interval_cv", 0, ...
    "pulse_amplitude_cv", 0, ...
    "decaying_transition_fraction", 0, ...
    "kind_counts", struct("upshift_bark", 0, ...
        "downshift_blip_pop", 0, "overrun_crackle", 0));
end

function value = coefficientOfVariation(values)
if numel(values) < 2 || mean(values) <= eps
    value = 0;
else
    value = std(values) / mean(values);
end
end

function value = safeMean(values)
if isempty(values)
    value = 0;
else
    value = mean(values);
end
end

function value = safeStd(values)
if numel(values) < 2
    value = 0;
else
    value = std(values);
end
end
