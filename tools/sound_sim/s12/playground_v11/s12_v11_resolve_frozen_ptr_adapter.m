function adapter = s12_v11_resolve_frozen_ptr_adapter(expectedSha256)
%S12_V11_RESOLVE_FROZEN_PTR_ADAPTER Resolve only the canonical PTR adapter.
% This function never copies the frozen source into v1.1.  It rejects a
% missing adapter or any byte-level drift from the declared invocation hash.

canonicalFolder = "E:\Tesla_speed\prj\tools\sound_sim\s12\playground";
canonicalPath = fullfile(canonicalFolder, "s12_sound_playground_ptr_tuning_step.m");
defaultExpectedSha256 = "3ce53f44883686ed2fa10a6c5b20cfe15d11b813ff75fb164489c62a241020e1";
if nargin < 1 || strlength(string(expectedSha256)) == 0
    expectedSha256 = defaultExpectedSha256;
end
expectedSha256 = normalizeSha256(expectedSha256);
if ~isfile(canonicalPath)
    error("S12:EngineSoundV11:FrozenPtrAdapter", ...
        "Canonical frozen PTR adapter is missing: %s", canonicalPath);
end
actualSha256 = sha256File(canonicalPath);
if actualSha256 ~= expectedSha256
    error("S12:EngineSoundV11:FrozenPtrAdapter", ...
        "Canonical frozen PTR adapter SHA-256 differs from the declared expected value.");
end
adapter = struct( ...
    "source_path", string(canonicalPath), ...
    "source_folder", string(canonicalFolder), ...
    "sha256", actualSha256, ...
    "expected_sha256", expectedSha256, ...
    "function_name", "s12_sound_playground_ptr_tuning_step", ...
    "frozen", true);
end

function value = normalizeSha256(value)
if ~((ischar(value) && isrow(value)) || (isstring(value) && isscalar(value)))
    error("S12:EngineSoundV11:FrozenPtrAdapter", ...
        "Expected frozen PTR adapter SHA-256 must be one text scalar.");
end
value = lower(string(value));
if isempty(regexp(char(value), "^[0-9a-f]{64}$", "once"))
    error("S12:EngineSoundV11:FrozenPtrAdapter", ...
        "Expected frozen PTR adapter SHA-256 must be 64 lowercase hexadecimal characters.");
end
end

function hash = sha256File(path)
file = fopen(path, "r", "ieee-le");
if file < 0
    error("S12:EngineSoundV11:FrozenPtrAdapter", "Cannot read canonical PTR adapter.");
end
cleanup = onCleanup(@()fclose(file));
digest = java.security.MessageDigest.getInstance("SHA-256");
while true
    bytes = fread(file, 1024 * 1024, "*uint8");
    if isempty(bytes)
        break;
    end
    digest.update(bytes);
end
hash = lower(join(compose("%02x", typecast(digest.digest(), "uint8")), ""));
end
