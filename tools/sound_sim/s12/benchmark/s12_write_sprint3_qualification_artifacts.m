function result = s12_write_sprint3_qualification_artifacts(result, outputDirectory)
%S12_WRITE_SPRINT3_QUALIFICATION_ARTIFACTS Render Sprint 3 evidence.
arguments
    result (1,1) struct
    outputDirectory (1,1) string
end
if ~isfolder(outputDirectory)
    mkdir(outputDirectory);
end
validateResult(result);
result.artifacts = [ ...
    artifact("report", "markdown", "benchmark-report.md"), ...
    artifact("manifest", "json", "benchmark-result.json"), ...
    artifact("case_comparison", "csv", "sprint3-case-comparison.csv"), ...
    artifact("positivity_diagnostics", "csv", ...
        "sprint3-positivity-diagnostics.csv"), ...
    artifact("smooth_spatial", "png", ...
        "sprint3-smooth-spatial-convergence.png"), ...
    artifact("double_rarefaction", "png", ...
        "sprint3-double-rarefaction.png")];
writeComparisonCsv(result, fullfile(outputDirectory, result.artifacts(3).path));
writePositivityCsv(result, fullfile(outputDirectory, result.artifacts(4).path));
writeMarkdown(result, fullfile(outputDirectory, result.artifacts(1).path));
writeSmoothPlot(result, fullfile(outputDirectory, result.artifacts(5).path));
writeStressPlot(result, fullfile(outputDirectory, result.artifacts(6).path));
writeText(fullfile(outputDirectory, result.artifacts(2).path), ...
    string(jsonencode(result, "PrettyPrint", true)) + newline);
end

function validateResult(result)
required = ["schema", "schema_minor", "suite", "environment", "cases", ...
    "artifacts", "acceptance"];
if string(result.schema) ~= "benchmark.schema.v1" || result.schema_minor < 2 || ...
        ~all(ismember(required, string(fieldnames(result))))
    error("S12:Benchmark:InvalidQualificationResult", ...
        "Sprint 3 report input must satisfy benchmark.schema.v1 minor 2.");
end
end

function value = artifact(id, type, path)
value = struct("id", id, "type", type, "path", path);
end

function writeComparisonCsv(result, path)
fileId = openText(path);
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, "%s\n", ...
    "schema_version,case_id,scheme,rho_l1_error,min_density,min_pressure," + ...
    "conservation_error,max_courant,step_count,reconstruction_pp_activation_count," + ...
    "flux_pp_activation_count,retry_count,rho_error_ratio");
for index = 1:numel(result.cases)
    comparison = result.cases(index);
    if ~isempty(fieldnames(comparison.muscl_minmod))
        writeComparisonRow(fileId, comparison, "muscl_minmod", ...
            comparison.muscl_minmod);
    end
    writeComparisonRow(fileId, comparison, "muscl_minmod_pp", ...
        comparison.muscl_minmod_pp);
end
end

function writeComparisonRow(fileId, comparison, scheme, metrics)
fprintf(fileId, ...
    "benchmark.schema.v1,%s,%s,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g," + ...
    "%.12g,%.12g,%.12g,%.12g\n", comparison.id, scheme, ...
    metric(metrics, ["rho_l1_error", "density_l1_error"]), ...
    metric(metrics, "min_density"), metric(metrics, "min_pressure"), ...
    metric(metrics, "conservation_error"), metric(metrics, "max_courant"), ...
    metric(metrics, "step_count"), ...
    metric(metrics, "reconstruction_pp_activation_count"), ...
    metric(metrics, "flux_pp_activation_count"), metric(metrics, "retry_count"), ...
    comparison.rho_error_ratio);
end

function writePositivityCsv(result, path)
fileId = openText(path);
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, "%s\n", ...
    "schema_version,case_id,rho_floor,p_floor,reconstruction_pp_activation_count," + ...
    "flux_pp_activation_count,reconstruction_pp_min_theta,flux_pp_min_theta," + ...
    "min_cell_rho_stage1,min_cell_rho_stage2,min_cell_rho_stage3," + ...
    "min_cell_p_stage1,min_cell_p_stage2,min_cell_p_stage3," + ...
    "min_interface_rho_stage1,min_interface_rho_stage2,min_interface_rho_stage3," + ...
    "min_interface_p_stage1,min_interface_p_stage2,min_interface_p_stage3," + ...
    "min_anchor_rho_stage1,min_anchor_rho_stage2,min_anchor_rho_stage3," + ...
    "min_anchor_p_stage1,min_anchor_p_stage2,min_anchor_p_stage3," + ...
    "min_final_rho_stage1,min_final_rho_stage2,min_final_rho_stage3," + ...
    "min_final_p_stage1,min_final_p_stage2,min_final_p_stage3," + ...
    "rejected_step_count,retry_count,maximum_flux_correction_norm");
for index = 1:numel(result.cases)
    metrics = result.cases(index).muscl_minmod_pp;
    values = [metrics.rho_floor, metrics.p_floor, ...
        metrics.reconstruction_pp_activation_count, metrics.flux_pp_activation_count, ...
        metrics.reconstruction_pp_min_theta, metrics.flux_pp_min_theta, ...
        row(metrics.minimum_cell_density_by_stage), ...
        row(metrics.minimum_cell_pressure_by_stage), ...
        row(metrics.minimum_interface_density_by_stage), ...
        row(metrics.minimum_interface_pressure_by_stage), ...
        row(metrics.minimum_anchor_partial_density_by_stage), ...
        row(metrics.minimum_anchor_partial_pressure_by_stage), ...
        row(metrics.minimum_final_partial_density_by_stage), ...
        row(metrics.minimum_final_partial_pressure_by_stage), ...
        metrics.rejected_step_count, metrics.retry_count, ...
        metrics.maximum_flux_correction_norm];
    fprintf(fileId, "benchmark.schema.v1,%s", result.cases(index).id);
    fprintf(fileId, ",%.12g", values);
    fprintf(fileId, "\n");
end
end

function writeMarkdown(result, path)
lines = [ ...
    "# S12 Sprint 3 Positivity Final Qualification", "", ...
    "- Schema: `" + string(result.schema) + "` minor `" + ...
        string(result.schema_minor) + "`", ...
    "- Profile: `" + string(result.suite.profile) + "`", ...
    "- Git commit: `" + string(result.environment.git_commit) + "`", ...
    "- MATLAB: `" + string(result.environment.matlab_release) + "`", ...
    "- Acceptance: **" + upper(string(result.acceptance.status)) + "**", "", ...
    "| Case | MUSCL rho L1 | PP rho L1 | PP/MUSCL | Recon PP | Flux PP | Retries |", ...
    "|---|---:|---:|---:|---:|---:|---:|"];
for index = 1:numel(result.cases)
    comparison = result.cases(index);
    pp = comparison.muscl_minmod_pp;
    lines(end + 1) = sprintf("| %s | %.12g | %.12g | %.12g | %.12g | %.12g | %.12g |", ...
        comparison.id, metric(comparison.muscl_minmod, ...
        ["rho_l1_error", "density_l1_error"]), ...
        metric(pp, ["rho_l1_error", "density_l1_error"]), ...
        comparison.rho_error_ratio, pp.reconstruction_pp_activation_count, ...
        pp.flux_pp_activation_count, pp.retry_count); %#ok<AGROW>
end
lines(end + 1:end + 4) = ["", "## Acceptance", "", ...
    "Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it."];
for index = 1:numel(result.acceptance.checks)
    check = result.acceptance.checks(index);
    lines(end + 1) = "- `" + string(check.id) + "`: " + ...
        string(check.passed); %#ok<AGROW>
end
writeText(path, strjoin(lines, newline) + newline);
end

function writeSmoothPlot(result, path)
comparison = selectCase(result, "smooth_periodic_entropy_wave_spatial");
figureHandle = newFigure;
cleanup = onCleanup(@() close(figureHandle));
axesHandle = axes(figureHandle);
loglog(axesHandle, comparison.muscl_minmod.cell_counts, ...
    comparison.muscl_minmod.rho_l1_error, "o-", "LineWidth", 1.5);
hold(axesHandle, "on");
loglog(axesHandle, comparison.muscl_minmod_pp.cell_counts, ...
    comparison.muscl_minmod_pp.rho_l1_error, "s-", "LineWidth", 1.5);
grid(axesHandle, "on");
xlabel(axesHandle, "cell count"); ylabel(axesHandle, "rho L1 error");
title(axesHandle, "Smooth Spatial Convergence: MUSCL vs PP");
legend(axesHandle, ["muscl_minmod", "muscl_minmod_pp"], ...
    "Location", "southwest");
saveDeterministicFigure(figureHandle, path);
end

function writeStressPlot(result, path)
comparison = selectCase(result, "double_rarefaction");
plotData = comparison.plot;
figureHandle = newFigure;
cleanup = onCleanup(@() close(figureHandle));
axesHandle = axes(figureHandle);
plot(axesHandle, plotData.x, plotData.numerical_density, ...
    "-", "LineWidth", 1.5);
hold(axesHandle, "on");
plot(axesHandle, plotData.x, plotData.numerical_pressure, ...
    "--", "LineWidth", 1.5);
grid(axesHandle, "on"); xlabel(axesHandle, "x"); ylabel(axesHandle, "value");
title(axesHandle, "Double Rarefaction Exact-Vacuum Stress");
legend(axesHandle, ["Density", "Pressure"], "Location", "best");
saveDeterministicFigure(figureHandle, path);
end

function comparison = selectCase(result, id)
comparison = result.cases(string({result.cases.id}) == id);
if numel(comparison) ~= 1
    error("S12:Benchmark:QualificationCaseMissing", ...
        "Qualification report requires case '%s'.", id);
end
end

function value = metric(metrics, fields)
value = NaN;
for field = fields
    if isfield(metrics, field)
        candidate = metrics.(field);
        if ~isempty(candidate)
            value = candidate(end);
        end
        return
    end
end
end

function value = row(value)
value = reshape(value, 1, []);
end

function fileId = openText(path)
fileId = fopen(path, "wt", "n", "UTF-8");
assert(fileId >= 0, "S12:Benchmark:FileOpen", ...
    "Cannot open Sprint 3 qualification artifact.");
end

function figureHandle = newFigure
figureHandle = figure("Visible", "off", "Color", "white", ...
    "Position", [100, 100, 800, 500]);
end

function saveDeterministicFigure(figureHandle, path)
temporaryPath = tempname(fileparts(path)) + ".png";
cleanup = onCleanup(@() deleteIfPresent(temporaryPath));
set(figureHandle, "PaperUnits", "inches", ...
    "PaperPosition", [0, 0, 8, 5], "PaperSize", [8, 5], ...
    "InvertHardcopy", "off", "Renderer", "painters");
print(figureHandle, temporaryPath, "-dpng", "-r100", "-vector");
pixels = imread(temporaryPath);
imwrite(pixels, path, "png");
stripPngTimeChunk(path);
end

function writeText(path, content)
fileId = openText(path);
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
assert(fileId >= 0, "S12:Benchmark:FileOpen", "Cannot rewrite PNG artifact.");
writeCleanup = onCleanup(@() fclose(fileId));
fwrite(fileId, output, "uint8");
end
