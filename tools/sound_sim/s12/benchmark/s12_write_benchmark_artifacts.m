function result = s12_write_benchmark_artifacts(result, outputDirectory)
%S12_WRITE_BENCHMARK_ARTIFACTS Render all views from one canonical result.
arguments
    result (1,1) struct
    outputDirectory (1,1) string
end
if ~isfolder(outputDirectory)
    mkdir(outputDirectory);
end
validateCanonicalResult(result);

artifacts = [ ...
    artifact("report", "markdown", "benchmark-report.md"), ...
    artifact("manifest", "json", "benchmark-result.json"), ...
    artifact("summary", "csv", "benchmark-summary.csv"), ...
    artifact("smooth_convergence", "png", "smooth-convergence.png"), ...
    artifact("smooth_time_scan", "csv", "smooth-time-scan.csv"), ...
    artifact("conservation", "png", "conservation-residual.png"), ...
    artifact("sod_analytic", "png", "sod-analytic-comparison.png")];
if hasCase(result, "lax_shock_tube")
    artifacts(end + 1) = artifact("standard_grid_scan", "csv", ...
        "standard-grid-scan.csv");
    artifacts(end + 1) = artifact("lax_analytic", "png", ...
        "lax-analytic-comparison.png");
end
if hasCase(result, "shu_osher_shock_entropy")
    if ~hasArtifact(artifacts, "standard_grid_scan")
        artifacts(end + 1) = artifact("standard_grid_scan", "csv", ...
            "standard-grid-scan.csv");
    end
    artifacts(end + 1) = artifact("shu_osher_density", "png", ...
        "shu-osher-density.png");
end
if hasCase(result, "woodward_colella_blast_wave")
    if ~hasArtifact(artifacts, "standard_grid_scan")
        artifacts(end + 1) = artifact("standard_grid_scan", "csv", ...
            "standard-grid-scan.csv");
    end
    artifacts(end + 1) = artifact("woodward_colella_density", "png", ...
        "woodward-colella-density.png");
end
result.artifacts = artifacts;
writeSummaryCsv(result, fullfile(outputDirectory, artifacts(3).path));
writeSmoothScanCsv(result, fullfile(outputDirectory, artifacts(5).path));
writeMarkdown(result, fullfile(outputDirectory, artifacts(1).path));
writeSmoothPlot(result, fullfile(outputDirectory, artifacts(4).path));
writeConservationPlot(result, fullfile(outputDirectory, artifacts(6).path));
writeSodPlot(result, fullfile(outputDirectory, artifacts(7).path));
writeStandardArtifacts(result, outputDirectory);
writeText(fullfile(outputDirectory, artifacts(2).path), ...
    string(jsonencode(result, "PrettyPrint", true)) + newline);
end

function value = hasCase(result, id)
value = any(string({result.cases.id}) == id);
end

function value = hasArtifact(artifacts, id)
value = any(string({artifacts.id}) == id);
end

function writeSmoothScanCsv(result, path)
fileId = fopen(path, "wt", "n", "UTF-8");
assert(fileId >= 0, "S12:Benchmark:FileOpen", ...
    "Cannot open smooth-wave scan CSV.");
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, "%s\n", ...
    "schema_version,dt_requested,step_count,self_error,observed_order");
caseIds = string({result.cases.id});
index = find(caseIds == "smooth_periodic_entropy_wave", 1);
if isempty(index)
    return
end
metrics = result.cases(index).metrics;
for scanIndex = 1:numel(metrics.dt_requested)
    if isfield(metrics, "step_count")
        stepCount = indexedOrNaN(metrics.step_count, scanIndex);
    else
        stepCount = NaN;
    end
    selfError = indexedOrNaN(metrics.self_error, scanIndex);
    observedOrder = indexedOrNaN(metrics.observed_order, scanIndex);
    fprintf(fileId, "benchmark.schema.v1,%.12g,%.12g,%.12g,%.12g\n", ...
        metrics.dt_requested(scanIndex), stepCount, ...
        selfError, observedOrder);
end
end

function value = indexedOrNaN(values, index)
if index <= numel(values)
    value = values(index);
else
    value = NaN;
end
end

function value = artifact(id, type, path)
value = struct("id", id, "type", type, "path", path);
end

function validateCanonicalResult(result)
required = ["schema", "suite", "environment", "cases", ...
    "artifacts", "acceptance"];
if result.schema ~= "benchmark.schema.v1" || ...
        ~all(ismember(required, string(fieldnames(result))))
    error("S12:Benchmark:InvalidCanonicalResult", ...
        "The report input does not satisfy benchmark.schema.v1.");
end
end

function writeSummaryCsv(result, path)
fileId = fopen(path, "wt", "n", "UTF-8");
assert(fileId >= 0, "S12:Benchmark:FileOpen", ...
    "Cannot open benchmark summary CSV.");
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, "%s\n", ...
    "schema_version,case_id,category,status," + ...
    "finest_observed_order,max_conservation_error,runtime_seconds");
for caseIndex = 1:numel(result.cases)
    benchmarkCase = result.cases(caseIndex);
    order = metricOrNaN(benchmarkCase.metrics, "observed_order", true);
    conservation = metricOrNaN(benchmarkCase.metrics, ...
        "conservation_error", false);
    runtime = metricOrNaN(benchmarkCase.metrics, "runtime_seconds", false);
    fprintf(fileId, "benchmark.schema.v1,%s,%s,%s,%.12g,%.12g,%.12g\n", ...
        benchmarkCase.id, benchmarkCase.category, benchmarkCase.status, ...
        order, conservation, runtime);
end
end

function value = metricOrNaN(metrics, field, useLast)
if isfield(metrics, field)
    values = metrics.(field);
    if useLast
        value = values(end);
    else
        value = max(values, [], "all");
    end
else
    value = NaN;
end
end

function writeMarkdown(result, path)
lines = [ ...
    "# S12 Numerical Benchmark Report", ...
    "", ...
    "- Schema: `" + result.schema + "`", ...
    "- Profile: `" + result.suite.profile + "`", ...
    "- Selector: `" + result.suite.selector + "`", ...
    "- Git commit: `" + result.environment.git_commit + "`", ...
    "- MATLAB: `" + result.environment.matlab_release + "`", ...
    "- Overall acceptance: **" + upper(result.acceptance.status) + "**", ...
    "", ...
    "| Case | Category | Status | Finest order | Conservation | Runtime (s) |", ...
    "|---|---|---:|---:|---:|---:|"];
for caseIndex = 1:numel(result.cases)
    benchmarkCase = result.cases(caseIndex);
    lines(end + 1) = sprintf("| %s | %s | %s | %.12g | %.12g | %.12g |", ...
        benchmarkCase.id, benchmarkCase.category, benchmarkCase.status, ...
        metricOrNaN(benchmarkCase.metrics, "observed_order", true), ...
        metricOrNaN(benchmarkCase.metrics, "conservation_error", false), ...
        metricOrNaN(benchmarkCase.metrics, "runtime_seconds", false)); %#ok<AGROW>
end
lines(end + 1:end + 4) = ["", "## Artifacts", "", ...
    "Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it."];
writeText(path, strjoin(lines, newline) + newline);
end

function writeSmoothPlot(result, path)
caseIds = string({result.cases.id});
index = find(caseIds == "smooth_periodic_entropy_wave", 1);
if isempty(index)
    x = 1;
    y = NaN;
else
    x = result.cases(index).plot.x;
    y = result.cases(index).plot.error;
end
figureHandle = figure("Visible", "off", "Color", "white", ...
    "Position", [100, 100, 800, 500]);
cleanup = onCleanup(@() close(figureHandle));
axesHandle = axes(figureHandle);
loglog(axesHandle, x, y, "o-", "LineWidth", 1.5, "MarkerSize", 6);
grid(axesHandle, "on");
xlabel(axesHandle, "dt divisor");
ylabel(axesHandle, "error");
title(axesHandle, "Smooth Periodic Entropy Wave Convergence");
saveDeterministicFigure(figureHandle, path);
end

function writeConservationPlot(result, path)
values = zeros(1, numel(result.cases));
labels = strings(1, numel(result.cases));
for caseIndex = 1:numel(result.cases)
    labels(caseIndex) = result.cases(caseIndex).id;
    values(caseIndex) = metricOrNaN(result.cases(caseIndex).metrics, ...
        "conservation_error", false);
end
figureHandle = figure("Visible", "off", "Color", "white", ...
    "Position", [100, 100, 800, 500]);
cleanup = onCleanup(@() close(figureHandle));
axesHandle = axes(figureHandle);
bar(axesHandle, max(values, realmin));
set(axesHandle, "YScale", "log", "XTick", 1:numel(labels), ...
    "XTickLabel", labels);
ylabel(axesHandle, "scaled conservation error");
title(axesHandle, "Conservation Residuals");
grid(axesHandle, "on");
saveDeterministicFigure(figureHandle, path);
end

function writeSodPlot(result, path)
caseIds = string({result.cases.id});
index = find(caseIds == "long_time_sod", 1);
figureHandle = figure("Visible", "off", "Color", "white", ...
    "Position", [100, 100, 800, 500]);
cleanup = onCleanup(@() close(figureHandle));
axesHandle = axes(figureHandle);
if isempty(index)
    plot(axesHandle, 1, NaN);
else
    plotData = result.cases(index).plot;
    plot(axesHandle, plotData.x, plotData.numerical_density, ...
        "-", "LineWidth", 1.5);
    hold(axesHandle, "on");
    plot(axesHandle, plotData.x, plotData.exact_density, ...
        "--", "LineWidth", 1.5);
    legend(axesHandle, ["Numerical", "Exact"], "Location", "best");
end
xlabel(axesHandle, "x");
ylabel(axesHandle, "density");
title(axesHandle, "Sod Density: Numerical vs Exact");
grid(axesHandle, "on");
saveDeterministicFigure(figureHandle, path);
end

function writeStandardArtifacts(result, outputDirectory)
artifacts = result.artifacts;
if hasArtifact(artifacts, "standard_grid_scan")
    index = find(string({artifacts.id}) == "standard_grid_scan", 1);
    writeStandardGridScan(result, fullfile(outputDirectory, artifacts(index).path));
end
writeStandardDensityPlot(result, outputDirectory, "lax_shock_tube", ...
    "lax_analytic", "Lax Density: Numerical vs Exact");
writeStandardDensityPlot(result, outputDirectory, "shu_osher_shock_entropy", ...
    "shu_osher_density", "Shu-Osher Density");
writeStandardDensityPlot(result, outputDirectory, ...
    "woodward_colella_blast_wave", "woodward_colella_density", ...
    "Woodward-Colella Density");
end

function writeStandardGridScan(result, path)
fileId = fopen(path, "wt", "n", "UTF-8");
assert(fileId >= 0, "S12:Benchmark:FileOpen", ...
    "Cannot open standard grid-scan CSV.");
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, "%s\n", ...
    "schema_version,case_id,cell_count,density_l1_error,shock_position," + ...
    "min_density,min_pressure,conservation_error,max_courant");
for caseIndex = 1:numel(result.cases)
    benchmarkCase = result.cases(caseIndex);
    if ~startsWith(benchmarkCase.category, "standard_")
        continue
    end
    counts = benchmarkCase.metrics.grid_cell_counts;
    for gridIndex = 1:numel(counts)
        fprintf(fileId, ...
            "benchmark.schema.v1,%s,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g\n", ...
            benchmarkCase.id, counts(gridIndex), ...
            metricAt(benchmarkCase.metrics, "density_l1_by_grid", ...
                "density_l1_error", gridIndex), ...
            metricAt(benchmarkCase.metrics, "shock_position_by_grid", ...
                "shock_position", gridIndex), ...
            metricAt(benchmarkCase.metrics, "min_density", "min_density", gridIndex), ...
            metricAt(benchmarkCase.metrics, "min_pressure", "min_pressure", gridIndex), ...
            metricAt(benchmarkCase.metrics, "conservation_error", ...
                "conservation_error", gridIndex), ...
            metricAt(benchmarkCase.metrics, "max_courant", "max_courant", gridIndex));
    end
end
end

function value = metricAt(metrics, preferredField, fallbackField, index)
if isfield(metrics, preferredField)
    values = metrics.(preferredField);
elseif isfield(metrics, fallbackField)
    values = metrics.(fallbackField);
else
    value = NaN;
    return
end
if isscalar(values)
    value = values;
elseif index <= numel(values)
    value = values(index);
else
    value = NaN;
end
end

function writeStandardDensityPlot(result, outputDirectory, caseId, artifactId, titleText)
caseIndex = find(string({result.cases.id}) == caseId, 1);
artifactIndex = find(string({result.artifacts.id}) == artifactId, 1);
if isempty(caseIndex) || isempty(artifactIndex)
    return
end
plotData = result.cases(caseIndex).plot;
figureHandle = figure("Visible", "off", "Color", "white", ...
    "Position", [100, 100, 800, 500]);
cleanup = onCleanup(@() close(figureHandle));
axesHandle = axes(figureHandle);
plot(axesHandle, plotData.x, plotData.numerical_density, ...
    "-", "LineWidth", 1.5);
if isfield(plotData, "exact_density")
    hold(axesHandle, "on");
    plot(axesHandle, plotData.x, plotData.exact_density, ...
        "--", "LineWidth", 1.5);
    legend(axesHandle, ["Numerical", "Exact"], "Location", "best");
end
xlabel(axesHandle, "x");
ylabel(axesHandle, "density");
title(axesHandle, titleText);
grid(axesHandle, "on");
saveDeterministicFigure(figureHandle, ...
    fullfile(outputDirectory, result.artifacts(artifactIndex).path));
end

function saveDeterministicFigure(figureHandle, path)
temporaryPath = tempname(fileparts(path)) + ".png";
temporaryCleanup = onCleanup(@() deleteIfPresent(temporaryPath));
set(figureHandle, "PaperUnits", "inches", ...
    "PaperPosition", [0, 0, 8, 5], "PaperSize", [8, 5], ...
    "InvertHardcopy", "off", "Renderer", "painters");
print(figureHandle, temporaryPath, "-dpng", "-r100", "-vector");
pixels = imread(temporaryPath);
imwrite(pixels, path, "png");
stripPngTimeChunk(path);
end

function writeText(path, content)
fileId = fopen(path, "wt", "n", "UTF-8");
assert(fileId >= 0, "S12:Benchmark:FileOpen", ...
    "Cannot open benchmark text artifact.");
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, "%s", char(content));
end

function deleteIfPresent(path)
if isfile(path)
    delete(path);
end
end

function stripPngTimeChunk(path)
fileId = fopen(path, "rb");
assert(fileId >= 0, "S12:Benchmark:FileOpen", "Cannot read PNG artifact.");
readCleanup = onCleanup(@() fclose(fileId));
bytes = fread(fileId, Inf, "*uint8");
delete(readCleanup);
output = bytes(1:8);
offset = 9;
while offset <= numel(bytes)
    lengthBytes = double(bytes(offset:offset + 3));
    dataLength = lengthBytes.' * [256^3; 256^2; 256; 1];
    chunkEnd = offset + dataLength + 11;
    chunkType = string(char(bytes(offset + 4:offset + 7).'));
    if chunkType ~= "tIME"
        output = [output; bytes(offset:chunkEnd)]; %#ok<AGROW>
    end
    offset = chunkEnd + 1;
end
fileId = fopen(path, "wb");
assert(fileId >= 0, "S12:Benchmark:FileOpen", "Cannot normalize PNG artifact.");
writeCleanup = onCleanup(@() fclose(fileId));
fwrite(fileId, output, "uint8");
end
