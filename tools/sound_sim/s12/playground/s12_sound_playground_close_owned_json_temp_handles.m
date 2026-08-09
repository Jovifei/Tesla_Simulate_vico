function result = s12_sound_playground_close_owned_json_temp_handles(transactionRoot)
%S12_SOUND_PLAYGROUND_CLOSE_OWNED_JSON_TEMP_HANDLES Close only exact Runtime Proof JSON temp handles.

transactionRoot = string(transactionRoot);
if ~isfolder(transactionRoot)
    error("S12:Playground:OwnedJsonTempRoot", "Runtime Proof transaction root is absent: %s", transactionRoot);
end
root = canonicalPath(transactionRoot);
result = struct("transaction_root", root, "matched_handle_ids", zeros(1, 0), ...
    "closed_handle_ids", zeros(1, 0), "close_failures", struct("file_id", {}, "status", {}), ...
    "temporary_files_before", matchingTemporaryPaths(root), "deleted_temporary_paths", strings(1, 0), ...
    "delete_failures", struct("path", {}, "message", {}), "remaining_matching_handles", zeros(1, 0), ...
    "temporary_files_after", strings(1, 0));

ids = openedFiles;
for index = 1:numel(ids)
    fileId = ids(index);
    filename = fopen(fileId);
    if isOwnedTemporaryPath(filename, root)
        result.matched_handle_ids(end + 1) = fileId;
    end
end
for index = 1:numel(result.matched_handle_ids)
    fileId = result.matched_handle_ids(index);
    status = fclose(fileId);
    if status == 0
        result.closed_handle_ids(end + 1) = fileId;
    else
        result.close_failures(end + 1) = struct("file_id", fileId, "status", status);
    end
end
result.remaining_matching_handles = matchingOpenHandleIds(root);
if ~isempty(result.close_failures) || ~isempty(result.remaining_matching_handles)
    error("S12:Playground:OwnedJsonTempClose", ...
        "Owned Runtime Proof JSON temporary handles remain open under %s.", root);
end
for index = 1:numel(result.temporary_files_before)
    path = result.temporary_files_before(index);
    if ~isfile(path)
        continue;
    end
    try
        delete(char(path));
        result.deleted_temporary_paths(end + 1) = path;
    catch cause
        result.delete_failures(end + 1) = struct("path", path, "message", string(cause.message));
    end
end
result.temporary_files_after = matchingTemporaryPaths(root);
if ~isempty(result.delete_failures) || ~isempty(result.temporary_files_after)
    error("S12:Playground:OwnedJsonTempDelete", ...
        "Owned Runtime Proof JSON temporary files remain under %s.", root);
end
end

function ids = matchingOpenHandleIds(root)
opened = openedFiles;
ids = zeros(1, numel(opened));
count = 0;
for index = 1:numel(opened)
    fileId = opened(index);
    filename = fopen(fileId);
    if isOwnedTemporaryPath(filename, root)
        count = count + 1;
        ids(count) = fileId;
    end
end
ids = ids(1:count);
end

function paths = matchingTemporaryPaths(root)
entries = dir(fullfile(char(root), "**", ".s12_playground_json_*.tmp"));
paths = strings(1, numel(entries));
count = 0;
for index = 1:numel(entries)
    candidate = string(fullfile(entries(index).folder, entries(index).name));
    if isOwnedTemporaryPath(candidate, root)
        count = count + 1;
        paths(count) = canonicalPath(candidate);
    end
end
paths = paths(1:count);
end

function matches = isOwnedTemporaryPath(path, root)
matches = false;
if ~(ischar(path) || isstring(path)) || strlength(string(path)) == 0 || ~isfile(path)
    return;
end
candidate = canonicalPath(path);
if ~(strcmpi(candidate, root) || startsWith(candidate, root + filesep, "IgnoreCase", true))
    return;
end
[~, name, extension] = fileparts(candidate);
matches = startsWith(string(name), ".s12_playground_json_") && strcmp( ...
    s12_sound_playground_require_text_scalar(extension, "temporary file extension"), ".tmp");
end

function path = canonicalPath(path)
path = string(java.io.File(char(path)).getCanonicalPath());
end
