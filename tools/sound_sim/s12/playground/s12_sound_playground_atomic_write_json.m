function s12_sound_playground_atomic_write_json(path, value, replaceExisting)
%S12_SOUND_PLAYGROUND_ATOMIC_WRITE_JSON Verify a sibling UTF-8 JSON before atomic publish.

if nargin < 3
    replaceExisting = true;
end
path = string(path);
folder = string(fileparts(path));
if strlength(folder) == 0
    error("S12:Playground:AtomicJsonDirectory", "JSON destination has no parent directory: %s", path);
end
ensureDirectory(folder);
payload = string(jsonencode(value, PrettyPrint = true)) + newline;
payloadBytes = unicode2native(char(payload), "UTF-8");
expectedSha256 = sha256Bytes(payloadBytes);
temporary = "";
file = -1;
try
    temporary = reserveTemporaryPath(folder);
    [file, message] = fopen(char(temporary), "w", "n", "UTF-8");
    if file < 0
        error("S12:Playground:AtomicJsonWrite", "Cannot open temporary JSON path %s: %s", temporary, message);
    end
    written = fprintf(file, "%s", char(payload));
    if written < 0
        error("S12:Playground:AtomicJsonWrite", "Cannot write temporary JSON path %s.", temporary);
    end
    [fileErrorMessage, fileErrorNumber] = ferror(file);
    if fileErrorNumber ~= 0
        error("S12:Playground:AtomicJsonWrite", ...
            "Temporary JSON write failed for %s: %s", temporary, fileErrorMessage);
    end
    closeOwnedFile();
    checkWriteCount(temporary, numel(payloadBytes));
    verifyJsonAndSha(temporary, expectedSha256, "temporary");
    publishTemporary(temporary, path, replaceExisting);
    temporary = "";
    verifyJsonAndSha(path, expectedSha256, "published");
catch cause
    cleanupOwnedTemporary();
    rethrow(cause);
end

    function closeOwnedFile()
        if file < 0
            return;
        end
        status = fclose(file);
        if status ~= 0
            error("S12:Playground:AtomicJsonClose", "Cannot close temporary JSON path %s.", temporary);
        end
        file = -1;
    end

    function cleanupOwnedTemporary()
        if file >= 0
            try
                status = fclose(file);
                if status ~= 0
                    warning("S12:Playground:AtomicJsonCleanupClose", ...
                        "Cannot close owned temporary JSON file ID %d.", file);
                end
            catch cause
                warning("S12:Playground:AtomicJsonCleanupClose", ...
                    "Cannot close owned temporary JSON file ID %d: %s", file, cause.message);
            end
            file = -1;
        end
        if strlength(temporary) > 0 && isfile(temporary)
            try
                delete(char(temporary));
            catch cause
                warning("S12:Playground:AtomicJsonCleanupDelete", ...
                    "Cannot delete owned temporary JSON path %s: %s", temporary, cause.message);
            end
        end
    end
end

function ensureDirectory(folder)
if isfolder(folder)
    return;
end
[created, message] = mkdir(char(folder));
if ~created && ~isfolder(folder)
    error("S12:Playground:AtomicJsonDirectory", "Cannot create JSON destination directory %s: %s", folder, message);
end
end

function temporary = reserveTemporaryPath(folder)
temporary = "";
attributes = javaArray("java.nio.file.attribute.FileAttribute", 0);
for attempt = 1:16
    candidate = fullfile(folder, ".s12_playground_json_" + string(matlabProcessID) + "_" + ...
        string(randi(2^31 - 1)) + ".tmp");
    try
        java.nio.file.Files.createFile(toJavaPath(candidate), attributes);
        temporary = candidate;
        return;
    catch cause
        if ~isfile(candidate)
            error("S12:Playground:AtomicJsonTemporary", ...
                "Cannot reserve temporary JSON path %s: %s", candidate, cause.message);
        end
        if attempt == 16
            error("S12:Playground:AtomicJsonTemporary", ...
                "Cannot reserve a unique temporary JSON path in %s after 16 collisions: %s", folder, cause.message);
        end
    end
end
end

function checkWriteCount(temporary, expected)
info = dir(char(temporary));
if isempty(info) || info.bytes ~= expected
    error("S12:Playground:AtomicJsonWrite", ...
        "Temporary JSON byte count mismatch for %s: expected %d bytes.", temporary, expected);
end
end

function verifyJsonAndSha(path, expectedSha256, role)
try
    jsondecode(fileread(path));
catch cause
    error("S12:Playground:AtomicJsonParse", "Cannot parse %s JSON %s: %s", role, path, cause.message);
end
verifySha256(path, expectedSha256, role);
end

function verifySha256(path, expectedSha256, role)
actualSha256 = s12_sound_playground_sha256(path);
s12_sound_playground_require_sha256_equal(actualSha256, expectedSha256, ...
    "SHA-256 mismatch for " + role + " JSON " + string(path));
end

function publishTemporary(temporary, path, replaceExisting)
if ~replaceExisting
    if isfile(path)
        error("S12:Playground:AtomicJsonTargetExists", "JSON destination already exists: %s", path);
    end
    options = javaArray("java.nio.file.CopyOption", 0);
else
    options = javaArray("java.nio.file.CopyOption", 2);
    options(1) = java.nio.file.StandardCopyOption.ATOMIC_MOVE;
    options(2) = java.nio.file.StandardCopyOption.REPLACE_EXISTING;
end
java.nio.file.Files.move(toJavaPath(temporary), ...
    toJavaPath(path), options);
end

function pathObject = toJavaPath(path)
pathObject = java.io.File(char(path)).toPath;
end

function digest = sha256Bytes(bytes)
messageDigest = java.security.MessageDigest.getInstance("SHA-256");
messageDigest.update(typecast(uint8(bytes), "int8"));
digest = lower(string(reshape(dec2hex(typecast(messageDigest.digest, "uint8"), 2).', 1, [])));
end
