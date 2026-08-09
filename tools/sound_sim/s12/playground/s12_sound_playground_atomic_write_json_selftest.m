function result = s12_sound_playground_atomic_write_json_selftest(runtimeBase, runId)
%S12_SOUND_PLAYGROUND_ATOMIC_WRITE_JSON_SELFTEST Validate JSON publication without Simulink or audio.

runtimeBase = string(runtimeBase);
runId = string(runId);
root = fullfile(runtimeBase, "atomic writer selftest " + runId + " path with spaces");
if isfolder(root)
    error("S12:Playground:AtomicWriterSelftestRoot", "Atomic writer self-test root already exists: %s", root);
end
[created, message] = mkdir(char(root));
if ~created
    error("S12:Playground:AtomicWriterSelftestRoot", "Cannot create atomic writer self-test root: %s", message);
end
rootCleanup = onCleanup(@() cleanupRoot(root));
maxTemporaryLeaf = ".s12_playground_json_" + string(repmat('9', 1, 10)) + "_" + ...
    string(repmat('9', 1, 10)) + ".tmp";
if strlength(fullfile(root, maxTemporaryLeaf)) >= 260
    error("S12:Playground:AtomicWriterSelftestPath", "Atomic writer self-test path is too long for Windows: %s", root);
end

target = fullfile(root, "nested UTF-8.json");
initial = struct("label", "发动机声音", "nested", struct());
initial.nested.orders = [1, 2, 3];
initial.nested.items = [struct("name", "idle", "gain", 0.2), ...
    struct("name", "load", "gain", 0.8)];
s12_sound_playground_atomic_write_json(target, initial, true);
verifyJsonField(target, "label", "发动机声音");

replacement = struct("label", "replacement", "nested", struct("orders", [4, 5, 6]));
s12_sound_playground_atomic_write_json(target, replacement, true);
originalTargetSha = s12_sound_playground_sha256(target);
verifyJsonField(target, "label", "replacement");

encoding_failure = false;
try
    s12_sound_playground_atomic_write_json(target, @sin, true);
catch
    encoding_failure = true;
end
if ~encoding_failure
    error("S12:Playground:AtomicWriterSelftestEncoding", "Expected the encoding operation to fail.");
end
actualTargetShaAfterFailure = s12_sound_playground_sha256(target);
s12_sound_playground_require_sha256_equal(actualTargetShaAfterFailure, originalTargetSha, ...
    "Encoding failure modified the existing target");

move_failure = false;
try
    s12_sound_playground_atomic_write_json(target, struct("move_failure", true), false);
catch
    move_failure = true;
end
if ~move_failure
    error("S12:Playground:AtomicWriterSelftestMove", "Expected no-replace publication to fail for an existing target.");
end
actualTargetShaAfterNoReplace = s12_sound_playground_sha256(target);
s12_sound_playground_require_sha256_equal(actualTargetShaAfterNoReplace, originalTargetSha, ...
    "No-replace publication modified the existing target");

for index = 1:100
    s12_sound_playground_atomic_write_json(target, struct("consecutive", index), true);
end
deterministic = struct("name", "deterministic", "values", [1, 2, 3], "synthetic", true);
first = fullfile(root, "deterministic first.json");
second = fullfile(root, "deterministic second.json");
s12_sound_playground_atomic_write_json(first, deterministic, true);
s12_sound_playground_atomic_write_json(second, deterministic, true);
s12_sound_playground_require_sha256_equal(s12_sound_playground_sha256(first), s12_sound_playground_sha256(second), ...
    "Identical JSON input produced different SHA-256 values");

temporary_files = dir(fullfile(char(root), "**", ".s12_playground_json_*.tmp"));
if ~isempty(temporary_files)
    error("S12:Playground:AtomicWriterSelftestTemporary", "Successful atomic JSON writes left temporary files.");
end
owned_open_handles = s12_sound_playground_close_owned_json_temp_handles(root);
if ~isempty(owned_open_handles.matched_handle_ids) || ...
        ~isempty(owned_open_handles.remaining_matching_handles) || ...
        ~isempty(owned_open_handles.deleted_temporary_paths)
    error("S12:Playground:AtomicWriterSelftestHandles", "Successful atomic JSON writes left owned temporary handles.");
end

result = struct("status", "ATOMIC_WRITER_SELFTEST_PASSED", "root", string(root), ...
    "target_path", string(target), "path_with_spaces", true, "utf_8", true, "nested", true, ...
    "overwrite", true, "encoding_failure", true, "move_failure", true, "consecutive_writes", 100, ...
    "temporary_files", 0, "owned_open_handles", 0, "deterministic_sha256", s12_sound_playground_sha256(first));
[removed, removeMessage] = rmdir(char(root), "s");
if ~removed
    error("S12:Playground:AtomicWriterSelftestCleanup", "Cannot remove self-test root after owned handles closed: %s", removeMessage);
end
clear rootCleanup
end

function verifyJsonField(path, field, expected)
decoded = jsondecode(fileread(path));
field = s12_sound_playground_require_text_scalar(field, "JSON field name");
expected = s12_sound_playground_require_text_scalar(expected, "expected JSON field value");
if ~isstruct(decoded) || ~isscalar(decoded) || ~isfield(decoded, char(field))
    error("S12:Playground:AtomicWriterSelftestContent", "Atomic JSON field is absent: %s.", field);
end
actual = s12_sound_playground_require_text_scalar(decoded.(char(field)), "decoded JSON field " + field);
if ~strcmp(actual, expected)
    error("S12:Playground:AtomicWriterSelftestContent", "Atomic JSON content mismatch for %s.", path);
end
end

function cleanupRoot(root)
if ~isfolder(root)
    return;
end
[removed, message] = rmdir(char(root), "s");
if ~removed
    warning("S12:Playground:AtomicWriterSelftestCleanup", ...
        "Cannot remove atomic writer self-test root %s: %s", root, message);
end
end
