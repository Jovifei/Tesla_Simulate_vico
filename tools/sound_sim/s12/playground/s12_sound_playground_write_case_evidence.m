function evidence = s12_sound_playground_write_case_evidence(pcm, result, scenario, parameters, outputDirectory)
%S12_SOUND_PLAYGROUND_WRITE_CASE_EVIDENCE Persist all qualification evidence before returning success.

if ~isfolder(outputDirectory)
    mkdir(outputDirectory);
end
pcmPath = fullfile(outputDirectory, "simulink_qualification.pcm");
pcmFile = fopen(pcmPath, "w");
if pcmFile < 0
    error("S12:Playground:EvidenceWrite", "Cannot write PCM evidence.");
end
pcmCleanup = onCleanup(@() fclose(pcmFile));
fwrite(pcmFile, pcm.', "double");
clear pcmCleanup
wavPath = fullfile(outputDirectory, "simulink_qualification.wav");
audiowrite(wavPath, pcm, 48000, "BitsPerSample", 24);
snapshotPath = fullfile(outputDirectory, "parameter_snapshot.json");
scenarioPath = fullfile(outputDirectory, "scenario.json");
metricsPath = fullfile(outputDirectory, "simulink_metrics.json");
s12_sound_playground_atomic_write_json(snapshotPath, parameters);
s12_sound_playground_atomic_write_json(scenarioPath, scenario);
s12_sound_playground_atomic_write_json(metricsPath, result.metrics);
evidence = struct( ...
    "pcm_path", string(pcmPath), "pcm_sha256", s12_sound_playground_sha256(pcmPath), ...
    "wav_path", string(wavPath), "wav_sha256", s12_sound_playground_sha256(wavPath), ...
    "parameter_snapshot_path", string(snapshotPath), "parameter_snapshot_sha256", s12_sound_playground_sha256(snapshotPath), ...
    "scenario_path", string(scenarioPath), "scenario_sha256", s12_sound_playground_sha256(scenarioPath), ...
    "model_sha256_before", result.model_sha256_before, "model_sha256_after", result.model_sha256_after, ...
    "metrics_json_path", string(metricsPath), "metrics_json_sha256", s12_sound_playground_sha256(metricsPath));
s12_sound_playground_atomic_write_json(fullfile(outputDirectory, "case_evidence.json"), evidence);
end
