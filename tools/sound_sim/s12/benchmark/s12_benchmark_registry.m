function registry = s12_benchmark_registry
%S12_BENCHMARK_REGISTRY Load the ordered benchmark case registry.
root = fileparts(mfilename("fullpath"));
raw = jsondecode(fileread(fullfile(root, "config", "registry.json")));
registry = repmat(struct("id", "", "category", "", ...
    "factory", @() []), size(raw));
for caseIndex = 1:numel(raw)
    registry(caseIndex).id = string(raw(caseIndex).id);
    registry(caseIndex).category = string(raw(caseIndex).category);
    registry(caseIndex).factory = str2func(raw(caseIndex).factory);
end
end
