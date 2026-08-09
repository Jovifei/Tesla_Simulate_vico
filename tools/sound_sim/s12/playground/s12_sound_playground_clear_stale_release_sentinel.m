function s12_sound_playground_clear_stale_release_sentinel(sentinelPath, evidence)
%S12_SOUND_PLAYGROUND_CLEAR_STALE_RELEASE_SENTINEL Remove a blocking release sentinel only with external absence proof.

sentinelPath = string(sentinelPath);
if ~isfile(sentinelPath)
    error("S12:Playground:ReleaseSentinel", "Release sentinel is absent: %s", sentinelPath);
end
if ~isstruct(evidence) || ~isfield(evidence, "external_process_absent") || ...
        ~isfield(evidence, "sha256") || ~logical(evidence.external_process_absent) || ...
        isempty(regexp(char(string(evidence.sha256)), "^[A-Fa-f0-9]{64}$", "once"))
    error("S12:Playground:ReleaseSentinelEvidence", ...
        "Clearing a stale release sentinel requires external_process_absent and SHA-256 evidence.");
end
delete(char(sentinelPath));
end
