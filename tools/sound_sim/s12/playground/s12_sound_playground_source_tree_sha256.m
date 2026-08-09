function result = s12_sound_playground_source_tree_sha256()
%S12_SOUND_PLAYGROUND_SOURCE_TREE_SHA256 Deterministic source/test identity.

playground = string(fileparts(mfilename("fullpath")));
s12Root = fileparts(playground);
files = immutableSourceFiles(playground, s12Root);
files = sort(string(files));
digest = java.security.MessageDigest.getInstance("SHA-256");
for index = 1:numel(files)
    path = files(index);
    relative = replace(path, s12Root + filesep, "");
    digest.update(uint8(char(relative + "\n")));
    digest.update(uint8(char(s12_sound_playground_sha256(path) + "\n")));
end
result = struct("sha256", upper(hexDigest(digest.digest)), "file_count", numel(files), ...
    "scope", "immutable_playground_source_contracts_and_named_tests");
end

function files = immutableSourceFiles(playground, s12Root)
entries = [dir(fullfile(playground, "*.m")); dir(fullfile(playground, "*.json")); ...
    dir(fullfile(playground, "*.py")); dir(fullfile(playground, "audit_manifests", "*.json"))];
files = strings(numel(entries), 1);
for index = 1:numel(entries)
    files(index) = string(fullfile(entries(index).folder, entries(index).name));
end
files = [files; collectPlaygroundTests(fullfile(s12Root, "tests"))];
end

function files = collectPlaygroundTests(root)
names = ["test_s12_sound_playground.m", "test_s12_sound_playground_offline_repair.m", ...
    "test_s12_sound_playground_v3_static.py", "test_s12_sound_playground_v4_static.py", ...
    "test_s12_sound_playground_v5_static.py", "test_s12_sound_playground_v6_static.py", ...
    "test_s12_sound_playground_v6_contract.m", "test_s12_sound_playground_v7_static.py", ...
    "test_s12_sound_playground_v7_contract.m", "test_s12_sound_playground_runtime_proof_static.py", ...
    "test_s12_sound_playground_runtime_proof_contract.m", "test_s12_sound_playground_atomic_write_json_runtime.m", ...
    "test_s12_sound_playground_sha256_contracts.m", "test_s12_sound_playground_condition_contracts.m", ...
    "test_s12_sound_playground_runtime_preflight.m", "test_s12_sound_playground_function_scripts.m", ...
    "test_s12_sound_playground_stateflow_root_access.m", "test_s12_sound_playground_fixed_size_parser.m", ...
    "test_package_self_contained.py"];
files = strings(numel(names), 1);
for index = 1:numel(names)
    files(index) = fullfile(root, names(index));
    if ~isfile(files(index))
        error("S12:Playground:SourceTree", "Required playground test is absent: %s", names(index));
    end
end
end

function value = hexDigest(bytes)
value = string(reshape(dec2hex(typecast(bytes, "uint8"), 2).', 1, []));
end
