function identity = s12_sound_playground_verify_audit_zip_source_identity(auditZipPath, declaredZipSourceSha, authorizationSourceSha)
%S12_SOUND_PLAYGROUND_VERIFY_AUDIT_ZIP_SOURCE_IDENTITY Bind ZIP metadata to authorization source identity.

auditZipPath = string(auditZipPath);
root = string(tempname);
mkdir(root);
cleanup = onCleanup(@() rmdir(root, "s"));
unzip(char(auditZipPath), char(root));
identityPath = fullfile(root, "metadata", "source_identity_manifest.json");
if ~isfile(identityPath)
    error("S12:Playground:AuthorizationAuditZipIdentity", "Audit ZIP lacks source identity metadata.");
end
identity = jsondecode(fileread(identityPath));
if ~isfield(identity, "immutable_source_sha256")
    error("S12:Playground:AuthorizationAuditZipIdentity", "Audit ZIP source identity is incomplete.");
end
assertSha("audit ZIP declared source SHA", declaredZipSourceSha);
assertSha("authorization source SHA", authorizationSourceSha);
assertEqual("audit ZIP declared source SHA", declaredZipSourceSha, identity.immutable_source_sha256);
assertEqual("audit ZIP versus authorization source SHA", identity.immutable_source_sha256, authorizationSourceSha);
end

function assertSha(role, value)
if isempty(regexp(char(string(value)), "^[A-Fa-f0-9]{64}$", "once"))
    error("S12:Playground:AuthorizationSha", "Invalid %s SHA-256.", role);
end
end

function assertEqual(role, actual, expected)
s12_sound_playground_require_sha256_equal(actual, expected, string(role) + " mismatch");
end
