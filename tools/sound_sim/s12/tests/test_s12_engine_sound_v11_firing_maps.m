function tests = test_s12_engine_sound_v11_firing_maps
%TEST_S12_ENGINE_SOUND_V11_FIRING_MAPS Runtime sensitivity tests for synthetic maps.
% Authored here; NOT RUN while the MATLAB/MCP control plane is unsafe.

tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
v11 = fullfile(s12Root, "playground_v11");
addpath(v11);
addpath(fullfile(v11, "common"));
testCase.TestData.v11 = v11;
end

function teardownOnce(testCase)
rmpath(fullfile(testCase.TestData.v11, "common"));
rmpath(testCase.TestData.v11);
end

function testAllSyntheticEngineMapsLoad(testCase)
for vehicleId = s12_v11_canonical_vehicle_ids()
    profile = s12_v11_load_profile(vehicleId);
    verifyEqual(testCase, sort(profile.engine.firing_order), 1:numel(profile.engine.firing_order));
    verifyEqual(testCase, numel(profile.engine.firing_order), numel(profile.engine.firing_phases_deg));
    verifyEqual(testCase, numel(profile.engine.firing_order), numel(profile.engine.bank_map));
    verifyEqual(testCase, numel(unique(profile.engine.firing_phases_deg)), numel(profile.engine.firing_phases_deg));
end
end

function testFiringOrderMutationChangesPistonSourceAndPcmHash(testCase)
profile = s12_v11_load_profile("hellcat_2022_stock");
baseline = s12_v11_render_profile(profile, "AfterfireLevel", "off", ...
    "FrameIndices", 1601, "ScenarioKey", "firing-map-order");
mutated = profile;
% Slots 3/4 map distinct synthetic banks: event IDs 4 (-1) and 3 (+1).
mutated.engine.firing_order([3, 4]) = mutated.engine.firing_order([4, 3]);
changed = s12_v11_render_profile(mutated, "AfterfireLevel", "off", ...
    "FrameIndices", 1601, "ScenarioKey", "firing-map-order");
verifyGreaterThan(testCase, norm(baseline.base_excitation), 0);
verifyGreaterThan(testCase, norm(baseline.base_excitation - changed.base_excitation), 0);
verifyNotEqual(testCase, baseline.base_excitation, changed.base_excitation);
verifyNotEqual(testCase, baseline.pcm_sha256, changed.pcm_sha256);
end

function testBankAndPhaseMutationsChangePistonSourceAndPcmHash(testCase)
profile = s12_v11_load_profile("hellcat_2022_stock");
baseline = s12_v11_render_profile(profile, "AfterfireLevel", "off", ...
    "FrameIndices", 1601, "ScenarioKey", "firing-map-bank-phase");
mutated = profile;
mutated.engine.bank_map = -mutated.engine.bank_map;
mutated.engine.firing_phases_deg([1, 2]) = mutated.engine.firing_phases_deg([2, 1]);
changed = s12_v11_render_profile(mutated, "AfterfireLevel", "off", ...
    "FrameIndices", 1601, "ScenarioKey", "firing-map-bank-phase");
verifyNotEqual(testCase, baseline.base_excitation, changed.base_excitation);
verifyNotEqual(testCase, baseline.pcm_sha256, changed.pcm_sha256);
end

function testRotaryMapMutationChangesSourceAndPcmHash(testCase)
profile = s12_v11_load_profile("rx7_fd_1991_stock");
baseline = s12_v11_render_profile(profile, "AfterfireLevel", "off", ...
    "FrameIndices", 1601, "ScenarioKey", "firing-map-rotary");
mutated = profile;
% Change only bank assignment; combining it with a phase swap could cancel.
mutated.engine.bank_map = fliplr(profile.engine.bank_map);
changed = s12_v11_render_profile(mutated, "AfterfireLevel", "off", ...
    "FrameIndices", 1601, "ScenarioKey", "firing-map-rotary");
verifyGreaterThan(testCase, norm(baseline.base_excitation), 0);
verifyGreaterThan(testCase, norm(baseline.base_excitation - changed.base_excitation), 0);
verifyNotEqual(testCase, baseline.base_excitation, changed.base_excitation);
verifyNotEqual(testCase, baseline.pcm_sha256, changed.pcm_sha256);
end

function testMissingOrInvalidMapsAreRejected(testCase)
container = tempname;
root = fullfile(container, "hellcat_2022_stock");
cleanup = onCleanup(@()rmdir(container, "s")); %#ok<NASGU>
copyfile(fullfile(testCase.TestData.v11, "vehicles", "hellcat_2022_stock"), root);
path = fullfile(root, "profile.json");
payload = jsondecode(fileread(path));
payload.engine = rmfield(payload.engine, "bank_map");
writeJson(path, payload);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Provenance");
end

function testDuplicateEventIdentifierIsRejected(testCase)
container = tempname;
root = fullfile(container, "hellcat_2022_stock");
cleanup = onCleanup(@()rmdir(container, "s")); %#ok<NASGU>
copyfile(fullfile(testCase.TestData.v11, "vehicles", "hellcat_2022_stock"), root);
path = fullfile(root, "profile.json");
payload = jsondecode(fileread(path));
payload.engine.firing_order.value(2) = payload.engine.firing_order.value(1);
writeJson(path, payload);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:EngineMap");
end

function writeJson(path, value)
file = fopen(path, "w", "n", "UTF-8");
cleanup = onCleanup(@()fclose(file)); %#ok<NASGU>
fprintf(file, "%s", jsonencode(value));
end
