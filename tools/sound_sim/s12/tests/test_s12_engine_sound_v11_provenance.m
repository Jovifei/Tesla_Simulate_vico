function tests = test_s12_engine_sound_v11_provenance
%TEST_S12_ENGINE_SOUND_V11_PROVENANCE Contract tests for v1.1 vehicle metadata.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
testCase.TestData.source = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground_v11");
addpath(fullfile(testCase.TestData.source, "common"));
end

function teardownOnce(testCase)
source = fullfile(testCase.TestData.source, "common");
if isfolder(source)
    rmpath(source);
end
end

function testAllVehiclePackagesValidate(testCase)
ids = ["hellcat_2022_stock", "gtr_r35_2007_stock", "c63_w204_facelift_stock", "supra_jza80_rz_stock", ...
    "rx7_fd_1991_stock", "lexus_lfa_stock", "ferrari_458_stock", "aventador_lp700_stock"];
for id = ids
    result = s12_v11_validate_vehicle_package(fullfile(testCase.TestData.source, "vehicles", id));
    verifyTrue(testCase, result.valid);
    verifyEqual(testCase, result.vehicle_id, id);
end
end

function testRejectsMissingProvenanceField(testCase)
root = clonePackage(testCase);
profile = jsondecode(fileread(fullfile(root, "profile.json")));
profile.provenance = rmfield(profile.provenance, "source_level");
writeJson(fullfile(root, "profile.json"), profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Provenance");
end

function testRejectsUnknownField(testCase)
root = clonePackage(testCase);
profile = jsondecode(fileread(fullfile(root, "profile.json")));
profile.unreviewed_parameter = true;
writeJson(fullfile(root, "profile.json"), profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:UnknownField");
end

function testRejectsMixedVehicleIdentity(testCase)
root = clonePackage(testCase);
manifest = jsondecode(fileread(fullfile(root, "reference_manifest.json")));
manifest.vehicle_identity.model_year = "2099";
writeJson(fullfile(root, "reference_manifest.json"), manifest);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Identity");
end

function testRejectsInvalidSourceLevel(testCase)
root = clonePackage(testCase);
targets = jsondecode(fileread(fullfile(root, "acoustic_targets.json")));
targets.provenance.source_level = "Z";
writeJson(fullfile(root, "acoustic_targets.json"), targets);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:SourceLevel");
end

function testRejectsRealOrOemClaim(testCase)
root = clonePackage(testCase);
afterfire = jsondecode(fileread(fullfile(root, "afterfire_profile.json")));
afterfire.provenance.claim = "Real OEM calibration";
writeJson(fullfile(root, "afterfire_profile.json"), afterfire);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Claim");
end

function testRejectsNumericIdentityText(testCase)
root = clonePackage(testCase);
profile = jsondecode(fileread(fullfile(root, "profile.json")));
profile.vehicle_identity.trim = 2022;
writeJson(fullfile(root, "profile.json"), profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Schema");
end

function testRejectsNumericSourceUrlText(testCase)
root = clonePackage(testCase);
profile = jsondecode(fileread(fullfile(root, "profile.json")));
profile.provenance.source_url = 42;
writeJson(fullfile(root, "profile.json"), profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Schema");
end

function testRejectsLogicalClaimText(testCase)
root = clonePackage(testCase);
afterfire = jsondecode(fileread(fullfile(root, "afterfire_profile.json")));
afterfire.provenance.claim = true;
writeJson(fullfile(root, "afterfire_profile.json"), afterfire);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Schema");
end

function testAcceptsEmptyOptionalSourceUrl(testCase)
root = clonePackage(testCase);
afterfire = jsondecode(fileread(fullfile(root, "afterfire_profile.json")));
afterfire.provenance.source_url = '';
writeJson(fullfile(root, "afterfire_profile.json"), afterfire);
result = s12_v11_validate_vehicle_package(root);
verifyTrue(testCase, result.valid);
end

function testRejectsUnstructuredC63ModelYear(testCase)
root = clonePackage(testCase, "c63_w204_facelift_stock");
profile = jsondecode(fileread(fullfile(root, "profile.json")));
profile.vehicle_identity.model_year = "facelift";
writeJson(fullfile(root, "profile.json"), profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Identity");
end

function testRejectsDescendingC63YearRange(testCase)
root = clonePackage(testCase, "c63_w204_facelift_stock");
profile = jsondecode(fileread(fullfile(root, "profile.json")));
profile.vehicle_identity.model_year = [2014, 2011];
writeJson(fullfile(root, "profile.json"), profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Identity");
end

function testRejectsInvalidOfficialReferenceSemanticPair(testCase)
root = clonePackage(testCase, "hellcat_2022_stock");
manifest = jsondecode(fileread(fullfile(root, "reference_manifest.json")));
manifest.references(1).vehicle_binding_state = "identity_verified";
writeJson(fullfile(root, "reference_manifest.json"), manifest);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Provenance");
end

function testRejectsInvalidCandidateReferenceSemanticPair(testCase)
root = clonePackage(testCase, "c63_w204_facelift_stock");
manifest = jsondecode(fileread(fullfile(root, "reference_manifest.json")));
manifest.references(2).stock_modified_status = "manufacturer_identity_only";
writeJson(fullfile(root, "reference_manifest.json"), manifest);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Provenance");
end

function testRejectsProfileOfficialManifestSourceDrift(testCase)
root = clonePackage(testCase, "c63_w204_facelift_stock");
profile = jsondecode(fileread(fullfile(root, "profile.json")));
profile.provenance.source_url = "https://mercedes-benz-publicarchive.com/marsClassic/en/instance/ko/C-63-AMG-2007---2011.xhtml?oid=189266924";
writeJson(fullfile(root, "profile.json"), profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Provenance");
end

function testRejectsCanonicalProfileProvenanceDowngrade(testCase)
root = clonePackage(testCase, "c63_w204_facelift_stock");
profile = jsondecode(fileread(fullfile(root, "profile.json")));
profile.provenance.source_level = "C";
profile.provenance.source_type = "synthetic";
profile.provenance.source_url = '';
writeJson(fullfile(root, "profile.json"), profile);
verifyError(testCase, @()s12_v11_validate_vehicle_package(root), "S12:EngineSoundV11:Provenance");
end

function root = clonePackage(testCase, vehicleId)
if nargin < 2
    vehicleId = "hellcat_2022_stock";
end
source = fullfile(testCase.TestData.source, "vehicles", vehicleId);
root = fullfile(tempname, vehicleId);
[copied, message] = copyfile(source, root);
assert(copied, "Cannot clone the vehicle package fixture: %s", message);
end

function writeJson(path, value)
fid = fopen(path, "w");
cleanup = onCleanup(@()fclose(fid));
fwrite(fid, jsonencode(value), "char");
end
