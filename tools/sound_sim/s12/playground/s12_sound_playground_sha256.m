function digest = s12_sound_playground_sha256(filePath)
%S12_SOUND_PLAYGROUND_SHA256 Return a lowercase SHA-256 digest for a file.

fileId = fopen(filePath, "r");
if fileId < 0
    error("S12:Playground:Hash", "Cannot read %s", filePath);
end
cleanup = onCleanup(@() fclose(fileId));
bytes = fread(fileId, inf, "*uint8");
messageDigest = java.security.MessageDigest.getInstance("SHA-256");
messageDigest.update(typecast(bytes, "int8"));
digest = lower(string(reshape(dec2hex(typecast(messageDigest.digest, "uint8"), 2).', 1, [])));
end
