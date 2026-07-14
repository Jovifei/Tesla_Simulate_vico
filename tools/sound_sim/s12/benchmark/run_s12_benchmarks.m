function result = run_s12_benchmarks(selector, options)
%RUN_S12_BENCHMARKS Run one case, one category, the suite, or report-only.
arguments
    selector (1,1) string = "all"
    options.Profile (1,1) string = "quick"
    options.OutputDirectory (1,1) string = ""
    options.SourceManifest (1,1) string = ""
    options.Reconstruction (1,1) string {mustBeMember( ...
        options.Reconstruction, ["first_order", "muscl_minmod"])} = "first_order"
end
benchmarkRoot = fileparts(mfilename("fullpath"));
if options.OutputDirectory == ""
    safeSelector = replace(selector, [":", "\\", "/"], "_");
    options.OutputDirectory = fullfile(benchmarkRoot, "out", ...
        options.Profile, safeSelector);
end
if selector == "report-only"
    if options.SourceManifest == "" || ~isfile(options.SourceManifest)
        error("S12:Benchmark:MissingManifest", ...
            "report-only requires an existing SourceManifest.");
    end
    result = normalizeStrings(jsondecode(fileread(options.SourceManifest)));
    result = s12_write_benchmark_artifacts(result, options.OutputDirectory);
    return
end

profile = s12_benchmark_profile(options.Profile);
profile.reconstruction = options.Reconstruction;
registry = s12_benchmark_registry();
selected = s12_benchmark_select(registry, selector);
result = s12_benchmark_new_result(options.Profile, selector, environmentInfo());
cases = repmat(emptyCase(), 1, numel(selected));
for caseIndex = 1:numel(selected)
    definition = selected(caseIndex).factory();
    config = definition.configure(profile);
    raw = definition.run(config);
    analysis = definition.analyze(raw);
    acceptance = definition.accept(analysis.metrics);
    cases(caseIndex) = struct( ...
        "id", selected(caseIndex).id, ...
        "category", selected(caseIndex).category, ...
        "status", acceptance.status, ...
        "config", config, ...
        "metrics", analysis.metrics, ...
        "acceptance", acceptance, ...
        "plot", analysis.plot);
end
result.cases = cases;
result.acceptance = suiteAcceptance(cases);
result = s12_write_benchmark_artifacts(result, options.OutputDirectory);
end

function value = emptyCase
value = struct("id", "", "category", "", "status", "", ...
    "config", struct(), "metrics", struct(), ...
    "acceptance", struct(), "plot", struct());
end

function environment = environmentInfo
benchmarkRoot = fileparts(mfilename("fullpath"));
repoRoot = fileparts(fileparts(fileparts(fileparts(benchmarkRoot))));
[status, commit] = system(sprintf('git -C "%s" rev-parse HEAD', repoRoot));
if status ~= 0
    commit = "unknown";
end
environment = struct( ...
    "git_commit", string(strtrim(commit)), ...
    "matlab_release", "R" + string(version("-release")), ...
    "matlab_version", string(version), ...
    "platform", string(computer("arch")));
end

function acceptance = suiteAcceptance(cases)
checks = repmat(struct("id", "", "passed", false), 1, numel(cases));
for caseIndex = 1:numel(cases)
    checks(caseIndex) = struct("id", cases(caseIndex).id, ...
        "passed", cases(caseIndex).status == "passed");
end
if all([checks.passed])
    status = "passed";
else
    status = "failed";
end
acceptance = struct("status", status, "checks", checks);
end

function result = normalizeStrings(result)
result.schema = string(result.schema);
result.suite.profile = string(result.suite.profile);
result.suite.selector = string(result.suite.selector);
environmentFields = fieldnames(result.environment);
for fieldIndex = 1:numel(environmentFields)
    field = environmentFields{fieldIndex};
    result.environment.(field) = string(result.environment.(field));
end
result.acceptance.status = string(result.acceptance.status);
for caseIndex = 1:numel(result.cases)
    result.cases(caseIndex).id = string(result.cases(caseIndex).id);
    result.cases(caseIndex).category = string(result.cases(caseIndex).category);
    result.cases(caseIndex).status = string(result.cases(caseIndex).status);
    result.cases(caseIndex).acceptance.status = ...
        string(result.cases(caseIndex).acceptance.status);
end
for artifactIndex = 1:numel(result.artifacts)
    result.artifacts(artifactIndex).id = string(result.artifacts(artifactIndex).id);
    result.artifacts(artifactIndex).type = string(result.artifacts(artifactIndex).type);
    result.artifacts(artifactIndex).path = string(result.artifacts(artifactIndex).path);
end
end
