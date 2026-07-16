function tests = test_s12_model_check_warning_waiver
%TEST_S12_MODEL_CHECK_WARNING_WAIVER Lock the approved Simscape inspector waiver.
tests = functiontests(localfunctions);
end

function testExactWaiverLocksCurrentModelsAndToolRelease(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
projectRoot = fileparts(fileparts(fileparts(s12Root)));
waiverPath = fullfile(projectRoot, ".satk", "model-check-waivers.json");
verifyTrue(testCase, isfile(waiverPath), "S12:ModelCheck:MissingWaiver");
if ~isfile(waiverPath), return; end

waiver = jsondecode(fileread(waiverPath));
verifyEqual(testCase, string(waiver.tool.matlab_release), "R" + string(version("-release")));
verifyEqual(testCase, numel(waiver.healthy_models), 1);
healthy = waiver.healthy_models;
verifyEqual(testCase, string(healthy.model_path), ...
    "models/fvm_ref/s12_euler_fvm_transient_wave_ref.slx");
verifyEqual(testCase, string(healthy.model_sha256), sha256(healthy.model_path, s12Root));
verifyEqual(testCase, string(healthy.expected_status), "healthy");
verifyEqual(testCase, healthy.expected_warning_count, 0);
verifyEqual(testCase, numel(waiver.waivers), 2);
for item = reshape(waiver.waivers, 1, [])
    verifyEqual(testCase, string(item.check_id), "unconnected_ports");
    verifyEqual(testCase, item.expected_count, 21);
    verifyEqual(testCase, string(item.review_status), ...
        "qualified_with_exact_tool_limitation_waiver");
    verifyEqual(testCase, string(item.model_sha256), sha256(item.model_path, s12Root));
    verifyEqual(testCase, string(item.warning_signature.sha256), ...
        signatureHash(string(item.warning_signature.items)));
    verifyEqual(testCase, string(item.warning_signature.items).', expectedItems(item.model_path));
end
end

function hash = sha256(relativePath, s12Root)
[status, output] = system(sprintf('certutil -hashfile "%s" SHA256', ...
    fullfile(s12Root, relativePath)));
verifyStatus(status);
hash = upper(string(regexp(output, '[0-9A-Fa-f]{64}', 'match', 'once')));
end

function hash = signatureHash(items)
path = string(tempname) + ".txt";
cleanup = onCleanup(@() delete(path));
fid = fopen(path, "w");
fprintf(fid, "%s\n", join(items, newline));
fclose(fid);
[status, output] = system(sprintf('certutil -hashfile "%s" SHA256', path));
verifyStatus(status);
hash = upper(string(regexp(output, '[0-9A-Fa-f]{64}', 'match', 'once')));
clear cleanup
end

function items = expectedItems(modelPath)
ports = ["A|LConn", "H|LConn", "B|RConn"];
items = strings(1, 21);
index = 1;
for cellIndex = 1:7
    for port = ports
        items(index) = "unconnected_port|" + modelPath + "/PrimaryCell" + ...
            compose("%02d", cellIndex) + "|" + port;
        index = index + 1;
    end
end
end

function verifyStatus(status)
if status ~= 0
    error("S12:ModelCheck:HashFailure", "Cannot hash model-check waiver input.");
end
end
