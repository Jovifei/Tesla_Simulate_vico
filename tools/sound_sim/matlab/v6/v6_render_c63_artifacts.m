function outputDir = v6_render_c63_artifacts(profile, iterationName, fitReport)
%V6_RENDER_C63_ARTIFACTS Render a C63 V6 iteration and its inspection stems.

arguments
    profile (1,1) struct
    iterationName (1,1) string
    fitReport (1,1) struct = struct()
end

scenario = v6_build_cycle(profile, "full_demo", 1000);
[audio, result] = v6_synthesize_engine_sound(profile, scenario);
scriptDir = fileparts(mfilename("fullpath"));
projectRoot = fileparts(fileparts(fileparts(fileparts(scriptDir))));
outputDir = fullfile(projectRoot, "build", "sound-sim", "matlab-classics-v6", ...
    "c63_w204", iterationName);
if ~isfolder(outputDir)
    mkdir(outputDir);
end

write_wav(fullfile(outputDir, "c63_w204_v6_external_96k.wav"), audio, ...
    profile.audio.sample_rate_hz, 24);
write_wav(fullfile(outputDir, "c63_w204_v6_external_48k.wav"), ...
    resample(audio, profile.audio.export_sample_rate_hz, profile.audio.sample_rate_hz), ...
    profile.audio.export_sample_rate_hz, 16);
write_stem(fullfile(outputDir, "c63_w204_v6_exhaust.wav"), result.layers.exhaust, profile.audio.sample_rate_hz);
write_stem(fullfile(outputDir, "c63_w204_v6_afterfire.wav"), result.layers.afterfire, profile.audio.sample_rate_hz);
write_stem(fullfile(outputDir, "c63_w204_v6_mechanical.wav"), result.layers.mechanical, profile.audio.sample_rate_hz);
write_stem(fullfile(outputDir, "c63_w204_v6_cabin.wav"), result.layers.cabin, profile.audio.sample_rate_hz);
write_stem(fullfile(outputDir, "c63_w204_v6_speaker.wav"), result.layers.speaker, profile.audio.sample_rate_hz);

traceStep = round(profile.audio.sample_rate_hz / 100);
traceIndex = 1:traceStep:numel(result.time_s);
trace = table(result.time_s(traceIndex).', result.state.rpm(traceIndex).', ...
    result.state.load(traceIndex).', result.state.torque_nm(traceIndex).', ...
    result.state.spark_deg(traceIndex).', result.state.lambda(traceIndex).', ...
    result.state.egt_k(traceIndex).', result.state.dfco(traceIndex).', ...
    result.state.sound_speed_mps(traceIndex).', result.layers.exhaust(traceIndex).', ...
    result.layers.afterfire(traceIndex).', result.layers.mechanical(traceIndex).', ...
    VariableNames=["time_s", "rpm", "load", "torque_nm", "spark_deg", ...
    "lambda", "egt_k", "dfco", "sound_speed_mps", "exhaust", "afterfire", "mechanical"]);
writetable(trace, fullfile(outputDir, "c63_w204_v6_trace.csv"));
writetable(result.events, fullfile(outputDir, "c63_w204_v6_events.csv"));

payload = struct("schema", profile.schema, "profile", profile, "scenario", ...
    scenario.name, "metrics", result.metrics, "normalization_gain", ...
    result.normalization_gain, "events", result.events, "fit", fitReport);
write_text(fullfile(outputDir, "c63_w204_v6_params.json"), jsonencode(payload, PrettyPrint=true));
write_plot(fullfile(outputDir, "c63_w204_v6_analysis.png"), result, audio, profile);
fprintf("V6 artifacts: %s\n", outputDir);
end

function write_wav(path, audio, sampleRate, bits)
audiowrite(path, audio.', sampleRate, BitsPerSample=bits);
end

function write_stem(path, layer, sampleRate)
peak = max(abs(layer));
layer = layer * min(1, 0.98 / max(peak, eps));
audiowrite(path, layer.', sampleRate, BitsPerSample=24);
end

function write_text(path, content)
fileId = fopen(path, "w", "n", "UTF-8");
if fileId < 0
    error("jovi:soundv6:FileOpen", "Cannot write %s", path);
end
cleanup = onCleanup(@() fclose(fileId));
fwrite(fileId, content, "char");
end

function write_plot(path, result, audio, profile)
figureHandle = figure(Visible="off", Color="white", Position=[100, 100, 1280, 900]);
cleanup = onCleanup(@() close(figureHandle));
layout = tiledlayout(4, 1, TileSpacing="compact", Padding="compact");
title(layout, profile.display_name + " - V6 physical-acoustics iteration");
nexttile;
plot(result.time_s, audio, Color=[0.10, 0.24, 0.44]);
xlabel("Time (s)"); ylabel("Audio"); grid on;
nexttile;
plot(result.time_s, result.state.rpm, LineWidth=1.0);
hold on;
plot(result.time_s, result.state.egt_k, LineWidth=1.0);
legend("RPM", "EGT (K)", Location="best"); xlabel("Time (s)"); grid on;
nexttile;
plot(result.time_s, result.layers.exhaust, LineWidth=0.7);
hold on;
plot(result.time_s, result.layers.afterfire, LineWidth=0.7);
plot(result.time_s, result.layers.mechanical, LineWidth=0.7);
legend("Exhaust", "Afterfire", "Mechanical", Location="best"); xlabel("Time (s)"); grid on;
nexttile;
sampleCount = min(numel(audio), 262144);
window = hann(sampleCount, "periodic").';
spectrum = abs(fft(audio(1:sampleCount) .* window));
frequency = (0:sampleCount - 1) * profile.audio.sample_rate_hz / sampleCount;
mask = frequency <= 20000;
plot(frequency(mask), 20 * log10(spectrum(mask) / max(spectrum) + 1e-8));
xlabel("Frequency (Hz)"); ylabel("Magnitude (dB)"); ylim([-90, 0]); grid on;
exportgraphics(figureHandle, path, Resolution=140);
end
