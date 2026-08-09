function tests = test_s12_engine_sound_v11_analysis
%TEST_S12_ENGINE_SOUND_V11_ANALYSIS Derived synthetic PCM/trace analysis.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
source = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground_v11", "common");
testCase.TestData.source = source;
addpath(source);
end

function teardownOnce(testCase)
if isfolder(testCase.TestData.source)
    rmpath(testCase.TestData.source);
end
end

function testHalfOrderMapHasFixedGrid(testCase)
[pcm, trace, ~] = syntheticInputs();
result = s12_v11_compute_order_map(pcm, [trace.rpm], 48000);
verifyEqual(testCase, result.orders, 0.5:0.5:12);
verifyEqual(testCase, size(result.energy, 2), 24);
verifyEqual(testCase, size(result.energy, 1), numel(result.time_s));
verifyTrue(testCase, all(isfinite(result.energy), "all"));
end

function testAudioMetricsExposeFourBandsAndFiniteFeatures(testCase)
[pcm, ~, ~] = syntheticInputs();
metrics = s12_v11_compute_audio_metrics(pcm, 48000);
verifySize(testCase, metrics.fixed_bands_hz, [4, 2]);
verifySize(testCase, metrics.band_energy_ratios, [1, 4]);
verifyEqual(testCase, sum(metrics.band_energy_ratios), 1, "AbsTol", 1e-10);
values = [metrics.centroid_hz, metrics.rolloff_hz, metrics.flatness, ...
    metrics.modulation_depth, metrics.pulse_amplitude_cv];
verifyTrue(testCase, all(isfinite(values)));
end

function testAfterfireStatisticsCaptureTimingAndClusters(testCase)
[~, ~, events] = syntheticInputs();
stats = s12_v11_compute_afterfire_statistics(events);
verifyEqual(testCase, stats.event_count, 4);
verifyEqual(testCase, stats.cluster_count, 2);
verifyGreaterThan(testCase, stats.interval_cv, 0);
verifyGreaterThan(testCase, stats.pulse_amplitude_cv, 0);
verifyGreaterThan(testCase, stats.decaying_transition_fraction, 0);
end

function testAggregateAnalysisConsumesOnlySyntheticInputs(testCase)
[pcm, trace, events] = syntheticInputs();
analysis = s12_v11_analyze_sound(pcm, trace, events, 48000);
verifyTrue(testCase, isfield(analysis, "order_map"));
verifyTrue(testCase, isfield(analysis, "audio_metrics"));
verifyTrue(testCase, isfield(analysis, "afterfire_statistics"));
verifyEqual(testCase, analysis.input_scope, "synthetic_pcm_and_trace_only");
verifyFalse(testCase, analysis.raw_reference_audio_used);
end

function [pcm, trace, events] = syntheticInputs()
sampleRate = 48000;
sampleCount = 9600;
time = (0:sampleCount - 1).' / sampleRate;
pcm = 0.15 * sin(2 * pi * 100 * time) + 0.04 * sin(2 * pi * 900 * time);
pulseLocations = [900, 2450, 4150, 7200];
for index = 1:numel(pulseLocations)
    span = pulseLocations(index) + (0:30);
    pcm(span) = pcm(span) + (0.22 / index) * exp(-(0:30).' / 8);
end
trace = struct("timestamp_s", num2cell((0:9) * 0.02), "rpm", num2cell(3000 * ones(1, 10)));
events = repmat(struct("time_s", 0, "kind", "", "location", "pre_ptr_exhaust_source", ...
    "energy", 0, "cluster_id", "", "variation", 0, ...
    "eligibility_explanation", "synthetic test event"), 1, 4);
eventTimes = [0.010, 0.014, 0.021, 0.080];
energies = [0.20, 0.14, 0.09, 0.16];
clusters = ["cluster-a", "cluster-a", "cluster-a", "cluster-b"];
kinds = ["upshift_bark", "upshift_bark", "upshift_bark", "overrun_crackle"];
for index = 1:4
    events(index).time_s = eventTimes(index);
    events(index).energy = energies(index);
    events(index).cluster_id = clusters(index);
    events(index).kind = kinds(index);
    events(index).variation = 0.1 * index;
end
end
