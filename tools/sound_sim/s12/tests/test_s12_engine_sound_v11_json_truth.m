function tests = test_s12_engine_sound_v11_json_truth
%TEST_S12_ENGINE_SOUND_V11_JSON_TRUTH Exercise JSON-only render tuning contracts.

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

function testAllEightPackagesValidateAndLoadFromJson(testCase)
for vehicleId = s12_v11_canonical_vehicle_ids()
    packageRoot = fullfile(testCase.TestData.v11, "vehicles", vehicleId);
    validation = s12_v11_validate_vehicle_package(packageRoot);
    profile = s12_v11_load_profile(vehicleId);
    verifyTrue(testCase, validation.valid);
    verifyEqual(testCase, profile.vehicle_id, vehicleId);
    verifyEqual(testCase, profile.character.idle_rpm, ...
        profile.render_tuning.rpm_load.idle_rpm.value);
    verifyEqual(testCase, profile.afterfire.cluster_refractory_s, ...
        profile.render_tuning.afterfire.cluster_refractory_s.value);
end
end

function testRejectsInvalidRenderTuningValue(testCase)
root = copyHellcatPackage(testCase);
cleanup = onCleanup(@()rmdir(fileparts(root), "s")); %#ok<NASGU>
profilePath = fullfile(root, "profile.json");
profile = jsondecode(fileread(profilePath));
profile.render_tuning.afterfire.base_energy.value = -1;
writeJson(profilePath, profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), ...
    "S12:EngineSoundV11:RenderTuning");
end

function testRejectsMissingRenderTuningParameter(testCase)
root = copyHellcatPackage(testCase);
cleanup = onCleanup(@()rmdir(fileparts(root), "s")); %#ok<NASGU>
profilePath = fullfile(root, "profile.json");
profile = jsondecode(fileread(profilePath));
profile.render_tuning.ptr = rmfield(profile.render_tuning.ptr, "damping");
writeJson(profilePath, profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), ...
    "S12:EngineSoundV11:Provenance");
end

function testRejectsFractionalArchitectureCount(testCase)
root = copyHellcatPackage(testCase);
cleanup = onCleanup(@()rmdir(fileparts(root), "s")); %#ok<NASGU>
profilePath = fullfile(root, "profile.json");
profile = jsondecode(fileread(profilePath));
profile.render_tuning.architecture.cylinders.value = 8.5;
writeJson(profilePath, profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), ...
    "S12:EngineSoundV11:RenderTuning");
end

function testRejectsValueOutsideSchemaOwnedDomain(testCase)
root = copyHellcatPackage(testCase);
cleanup = onCleanup(@()rmdir(fileparts(root), "s")); %#ok<NASGU>
profilePath = fullfile(root, "profile.json");
profile = jsondecode(fileread(profilePath));
profile.render_tuning.architecture.cylinders.value = 18;
profile.render_tuning.architecture.cylinders.range = [0, 18];
writeJson(profilePath, profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), ...
    "S12:EngineSoundV11:RenderTuning");
end

function testMutatingConsumedFiringGainChangesOfflinePcm(testCase)
profile = s12_v11_load_profile("hellcat_2022_stock");
baseline = s12_v11_render_profile(profile, "AfterfireLevel", "off", ...
    "FrameIndices", 1601, "ScenarioKey", "json-truth-firing");
mutated = profile;
mutated.character.firing_gain = 0.5 * profile.character.firing_gain;
changed = s12_v11_render_profile(mutated, "AfterfireLevel", "off", ...
    "FrameIndices", 1601, "ScenarioKey", "json-truth-firing");
verifyNotEqual(testCase, baseline.pcm_sha256, changed.pcm_sha256);
end

function testMutatingConsumedLoadBoundChangesOfflinePcm(testCase)
profile = s12_v11_load_profile("hellcat_2022_stock");
baseline = s12_v11_render_profile(profile, "AfterfireLevel", "off", ...
    "FrameIndices", 1, "ScenarioKey", "json-truth-load");
mutated = profile;
mutated.character.minimum_load = 0.50;
changed = s12_v11_render_profile(mutated, "AfterfireLevel", "off", ...
    "FrameIndices", 1, "ScenarioKey", "json-truth-load");
verifyNotEqual(testCase, baseline.pcm_sha256, changed.pcm_sha256);
end

function testMutatingRx7RotaryCharacterGainsChangesOfflinePcm(testCase)
profile = s12_v11_load_profile("rx7_fd_1991_stock");
baseline = s12_v11_render_profile(profile, "AfterfireLevel", "off", ...
    "FrameIndices", 1601, "ScenarioKey", "json-truth-rx7-rotary");
for name = ["firing_gain", "firing_harmonic_gain", "rotary_apex_gain"]
    mutated = profile;
    mutated.character.(name) = 0.5 * profile.character.(name);
    changed = s12_v11_render_profile(mutated, "AfterfireLevel", "off", ...
        "FrameIndices", 1601, "ScenarioKey", "json-truth-rx7-rotary");
    verifyNotEqual(testCase, baseline.pcm_sha256, changed.pcm_sha256, ...
        "Mutating RX-7 " + name + " must alter the rendered PCM.");
    verifyNotEqual(testCase, baseline.pcm, changed.pcm, ...
        "Mutating RX-7 " + name + " must alter the rendered PCM samples.");
end
end

function root = copyHellcatPackage(testCase)
source = fullfile(testCase.TestData.v11, "vehicles", "hellcat_2022_stock");
root = fullfile(tempname, "hellcat_2022_stock");
copyfile(source, root);
end

function writeJson(path, value)
file = fopen(path, "w", "n", "UTF-8");
if file < 0
    error("S12:EngineSoundV11:Test", "Could not open test JSON path.");
end
cleanup = onCleanup(@()fclose(file)); %#ok<NASGU>
fprintf(file, "%s", jsonencode(value));
end
