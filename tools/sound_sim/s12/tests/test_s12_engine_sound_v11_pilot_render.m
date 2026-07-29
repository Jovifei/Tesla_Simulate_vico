function tests = test_s12_engine_sound_v11_pilot_render
%TEST_S12_ENGINE_SOUND_V11_PILOT_RENDER Runtime contracts for pilot rendering.
% This suite is authored for the approved existing shared Desktop only.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
v11 = fullfile(s12Root, "playground_v11");
common = fullfile(v11, "common");
addpath(v11);
adapter = s12_v11_resolve_frozen_ptr_adapter();
testCase.TestData.paths = [string(v11), string(common), adapter.source_folder];
testCase.TestData.adapter = adapter;
addpath(common);
addpath(adapter.source_folder, "-begin");
if string(which(adapter.function_name)) ~= adapter.source_path
    error("S12:EngineSoundV11:TestSetup", ...
        "Behavior tests must call the verified canonical PTR adapter.");
end
end

function teardownOnce(testCase)
clear s12_sound_playground_ptr_tuning_step
for path = testCase.TestData.paths
    if isfolder(path)
        rmpath(path);
    end
end
end

function testPilotListAndLoadContract(testCase)
listed = s12_v11_list_profiles();
pilots = ["hellcat_2022_stock", "c63_w204_facelift_stock", "ferrari_458_stock"];
verifyTrue(testCase, all(ismember(pilots, string({listed.profile_id}))));
listedPilots = string({listed([listed.pilot]).profile_id});
verifyEqual(testCase, sort(listedPilots), sort(pilots));
for pilot = pilots
    profile = s12_v11_load_profile(pilot);
    verifyEqual(testCase, profile.vehicle_id, pilot);
    verifyTrue(testCase, profile.synthetic);
    verifyTrue(testCase, profile.uncalibrated);
    verifyTrue(testCase, profile.offline);
end

function testRuntimePtrAdapterResolutionIsCanonical(testCase)
adapter = s12_v11_resolve_frozen_ptr_adapter();
baseExcitation = 0.01 * ones(960, 1);
[pressure, diagnostics] = s12_v11_apply_afterfire_before_ptr( ...
    baseExcitation, zeros(960, 1), 1.10, 0.0175, -0.26, 0.09, true);
verifySize(testCase, pressure, [960, 1]);
verifyTrue(testCase, all(isfinite(pressure)));
verifyEqual(testCase, diagnostics.ptr_source_path, adapter.source_path);
verifyEqual(testCase, diagnostics.ptr_source_sha256, adapter.sha256);
verifyEqual(testCase, string(which(adapter.function_name)), adapter.source_path);
end
end

function testCycleHasExactFixedDimensions(testCase)
cycle = s12_v11_compile_vehicle_cycle(s12_v11_load_profile("hellcat_2022_stock"));
verifyEqual(testCase, cycle.duration_s, 90);
verifyEqual(testCase, cycle.sample_rate_hz, 48000);
verifyEqual(testCase, cycle.frame_samples, 960);
verifyEqual(testCase, cycle.frame_count, 4500);
verifyEqual(testCase, cycle.sample_count, 4320000);
verifySize(testCase, cycle.state, [4500, 13]);
end

function testSelectedFrameRenderIsFinitePhaseContinuousAndPrePtr(testCase)
frameIndices = 3194:3200;
rendered = s12_v11_render_profile("hellcat_2022_stock", ...
    "AfterfireLevel", "subtle", "FrameIndices", frameIndices, ...
    "ScenarioKey", "phase-causality");
verifySize(testCase, rendered.pcm, [numel(frameIndices) * 960, 2]);
verifyTrue(testCase, all(isfinite(rendered.pcm), "all"));
verifyLessThan(testCase, max(abs(rendered.pcm), [], "all"), 1);
for index = 2:numel(rendered.frame_diagnostics)
    verifyEqual(testCase, rendered.frame_diagnostics(index).phase_start_rad, ...
        rendered.frame_diagnostics(index - 1).phase_next_rad, "AbsTol", 1e-12);
end
verifyTrue(testCase, all(string({rendered.frame_diagnostics.insertion_stage}) == ...
    "before_ptr_radiation"));
verifyFalse(testCase, any([rendered.frame_diagnostics.post_pcm_append]));
verifyTrue(testCase, all([rendered.frame_diagnostics.frame_samples] == 960));
verifyTrue(testCase, all([rendered.frame_diagnostics.channels] == 2));
verifyGreaterThan(testCase, sum([rendered.frame_diagnostics.event_count]), 0);
verifyTrue(testCase, any([rendered.frame_diagnostics.pre_ptr_changed]));
off = s12_v11_render_profile("hellcat_2022_stock", ...
    "AfterfireLevel", "off", "FrameIndices", frameIndices, ...
    "ScenarioKey", "phase-causality");
verifyEqual(testCase, rendered.base_excitation, off.base_excitation);
verifyNotEqual(testCase, rendered.pre_ptr_excitation, off.pre_ptr_excitation);
verifyNotEqual(testCase, rendered.pcm, off.pcm);
end

function testSameScenarioRenderHasRepeatablePcmSha(testCase)
first = s12_v11_render_profile("c63_w204_facelift_stock", ...
    "FrameIndices", 1700:1715, "ScenarioKey", "same-run-repeatability");
second = s12_v11_render_profile("c63_w204_facelift_stock", ...
    "FrameIndices", 1700:1715, "ScenarioKey", "same-run-repeatability");
verifyEqual(testCase, first.pcm, second.pcm);
verifyEqual(testCase, first.pcm_sha256, second.pcm_sha256);
end

function testPilotSignaturesAreDistinguishable(testCase)
pilots = ["hellcat_2022_stock", "c63_w204_facelift_stock", "ferrari_458_stock"];
indices = [200:210, 1800:1810, 3300:3310];
first = s12_v11_render_profile(pilots(1), ...
    "FrameIndices", indices, "ScenarioKey", "pilot-signature");
results = repmat(first, 1, numel(pilots));
for index = 2:numel(pilots)
    results(index) = s12_v11_render_profile(pilots(index), ...
        "FrameIndices", indices, "ScenarioKey", "pilot-signature");
end
comparison = s12_v11_compare_audio_analysis(results);
verifyTrue(testCase, comparison.distinguishable);
verifyTrue(testCase, all(comparison.pairwise_distance > ...
    comparison.distinguishable_threshold));
verifyEqual(testCase, numel(comparison.feature_names), size(comparison.features, 2));
end

function testPilotWrapperAndPublishedArtifactContract(testCase)
pilots = s12_v11_render_pilot_profiles("Publish", false, ...
    "FrameIndices", 1:2, "ScenarioKey", "pilot-wrapper");
verifyEqual(testCase, string({pilots.profile_id}), ...
    ["hellcat_2022_stock", "c63_w204_facelift_stock", "ferrari_458_stock"]);
runId = "task3_contract_" + string(datetime("now", Format="yyyyMMdd_HHmmss_SSS"));
published = s12_v11_audition_profile("hellcat_2022_stock", ...
    "RunId", runId, "AfterfireLevel", "subtle", ...
    "ScenarioKey", "publication-contract");
expectedRoot = "E:\Tesla_speed\tasks\reports\runtime\s12-engine-sound-v11";
verifyTrue(testCase, startsWith(string(published.output_directory), expectedRoot + filesep));
expected = sort(["full_drive_cycle.wav", "idle.wav", "acceleration.wav", ...
    "upshift.wav", "downshift.wav", "deceleration.wav", "afterfire.wav", ...
    "vehicle_trace.csv", "profile_snapshot.json", "sound_analysis.json", ...
    "manifest.json", "SHA256.txt"]);
actual = string({dir(published.output_directory).name});
actual = sort(actual(~ismember(actual, [".", ".."])));
verifyEqual(testCase, actual, expected);
wavNames = expected(endsWith(expected, ".wav"));
for name = wavNames
    info = audioinfo(fullfile(published.output_directory, name));
    verifyEqual(testCase, info.SampleRate, 48000);
    verifyEqual(testCase, info.NumChannels, 2);
    verifyEqual(testCase, info.BitsPerSample, 24);
end
fullInfo = audioinfo(fullfile(published.output_directory, "full_drive_cycle.wav"));
verifyEqual(testCase, fullInfo.TotalSamples, 4320000);
shaLines = splitlines(strtrim(fileread(fullfile( ...
    published.output_directory, "SHA256.txt"))));
verifyEqual(testCase, numel(shaLines), 11);
verifyTrue(testCase, all(~cellfun("isempty", regexp(cellstr(shaLines), ...
    "^[0-9a-f]{64}  .+$", "once"))));
secondRunId = runId + "_repeat";
secondPublished = s12_v11_audition_profile("hellcat_2022_stock", ...
    "RunId", secondRunId, "AfterfireLevel", "subtle", ...
    "ScenarioKey", "publication-contract");
secondShaLines = splitlines(strtrim(fileread(fullfile( ...
    secondPublished.output_directory, "SHA256.txt"))));
verifyEqual(testCase, secondShaLines, shaLines);
end

function testPublicationRejectsPathTraversalBeforeRender(testCase)
malicious = struct("vehicle_id", "..", "character", struct());
verifyError(testCase, @()s12_v11_audition_profile(malicious), ...
    "S12:EngineSoundV11:ProfileId");
end
