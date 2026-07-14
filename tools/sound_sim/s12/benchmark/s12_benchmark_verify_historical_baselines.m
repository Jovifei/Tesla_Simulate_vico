function result = s12_benchmark_verify_historical_baselines
%S12_BENCHMARK_VERIFY_HISTORICAL_BASELINES Prove frozen baselines are unchanged.
benchmarkRoot = fileparts(mfilename("fullpath"));
repoRoot = fileparts(fileparts(fileparts(fileparts(benchmarkRoot))));
acceptedCommit = "eaf629532d937584b8992f0de5ca86410c3ba9e6";
quotedPaths = "tools/sound_sim/s12/benchmark/baselines/sprint-0.5 " + ...
    "tools/sound_sim/s12/benchmark/baselines/sprint-1 " + ...
    "tools/sound_sim/s12/benchmark/baselines/sprint-2";
command = sprintf('git -C "%s" diff --name-only %s -- %s', ...
    repoRoot, acceptedCommit, quotedPaths);
[statusCode, output] = system(command);
if statusCode ~= 0
    error("S12:Benchmark:HistoricalBaselineAudit", ...
        "Cannot audit historical accepted baselines: %s", strtrim(output));
end
changed = splitlines(strtrim(string(output)));
changed(changed == "") = [];
if isempty(changed)
    status = "passed";
else
    status = "failed";
end
result = struct("status", status, ...
    "accepted_commit", acceptedCommit, ...
    "changed_file_count", numel(changed), ...
    "changed_files", reshape(changed, 1, []));
end
