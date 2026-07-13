function approval = promote_s12_benchmark_baseline( ...
        sourceManifest, destination, options)
%PROMOTE_S12_BENCHMARK_BASELINE Explicitly promote a passing result.
arguments
    sourceManifest (1,1) string
    destination (1,1) string
    options.ApprovalToken (1,1) string = ""
end
if options.ApprovalToken ~= "PROMOTE_ACCEPTED_BASELINE"
    error("S12:Benchmark:PromotionNotAuthorized", ...
        "Baseline promotion requires the explicit approval token.");
end
if ~isfile(sourceManifest)
    error("S12:Benchmark:MissingManifest", "Source manifest does not exist.");
end
manifest = jsondecode(fileread(sourceManifest));
if string(manifest.schema) ~= "benchmark.schema.v1" || ...
        string(manifest.acceptance.status) ~= "passed"
    error("S12:Benchmark:UnacceptedResult", ...
        "Only a passing benchmark.schema.v1 result can be promoted.");
end
if isfolder(destination) && ~isempty(dir(fullfile(destination, "*")))
    error("S12:Benchmark:BaselineExists", ...
        "The baseline destination must be absent or empty.");
end
if ~isfolder(destination)
    mkdir(destination);
end
sourceDirectory = fileparts(sourceManifest);
for artifactIndex = 1:numel(manifest.artifacts)
    relativePath = string(manifest.artifacts(artifactIndex).path);
    sourcePath = fullfile(sourceDirectory, relativePath);
    if ~isfile(sourcePath)
        error("S12:Benchmark:MissingArtifact", ...
            "Manifest artifact '%s' is missing.", relativePath);
    end
    copyfile(sourcePath, fullfile(destination, relativePath));
end
manifestName = "benchmark-result.json";
if ~isfile(fullfile(destination, manifestName))
    copyfile(sourceManifest, fullfile(destination, manifestName));
end
approval = struct( ...
    "schema", "benchmark.baseline.approval.v1", ...
    "source_schema", string(manifest.schema), ...
    "source_git_commit", string(manifest.environment.git_commit), ...
    "source_manifest", manifestName, ...
    "status", "accepted", ...
    "promotion_mode", "explicit_local_promotion");
writeJson(fullfile(destination, "baseline-approval.json"), approval);
end

function writeJson(path, value)
fileId = fopen(path, "wt", "n", "UTF-8");
assert(fileId >= 0, "S12:Benchmark:FileOpen", ...
    "Cannot write baseline approval record.");
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, "%s", char(string(jsonencode(value, "PrettyPrint", true)) + newline));
end
