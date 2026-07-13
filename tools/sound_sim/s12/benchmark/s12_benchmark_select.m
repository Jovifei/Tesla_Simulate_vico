function selected = s12_benchmark_select(registry, selector)
%S12_BENCHMARK_SELECT Select one case, one category, or the full suite.
arguments
    registry (1,:) struct
    selector (1,1) string
end
if selector == "all"
    selected = registry;
elseif startsWith(selector, "case:")
    id = extractAfter(selector, "case:");
    selected = registry(string({registry.id}) == id);
elseif startsWith(selector, "category:")
    category = extractAfter(selector, "category:");
    selected = registry(string({registry.category}) == category);
else
    selected = registry([]);
end
if isempty(selected)
    error("S12:Benchmark:UnknownSelector", ...
        "Unknown or empty benchmark selector '%s'.", selector);
end
end
