function result = s12_engine_sound_audition(profileInput, varargin)
%S12_ENGINE_SOUND_AUDITION Render, publish, and optionally play one full 90-second audition.

parser = inputParser;
parser.addParameter("BackfireLevel", "");
parser.addParameter("Play", false, @(value)islogical(value) && isscalar(value));
parser.addParameter("RunId", "");
parser.parse(varargin{:});
profile = resolveProfile(profileInput);
level = string(parser.Results.BackfireLevel);
if strlength(level) == 0
    level = profile.backfire.default_level.value;
end
render = s12_engine_sound_render_cycle(profile, "BackfireLevel", level);
cycle = s12_engine_sound_compile_drive_cycle(profile, level);
s12_engine_sound_require_shared_adapter();
outputDirectory = createRunDirectory(profile.profile_id.value, parser.Results.RunId);
publishRun(outputDirectory, profile, cycle, render);
if parser.Results.Play
    sound(render.pcm, render.sample_rate_hz);
end
result = struct("profile_id", profile.profile_id.value, "backfire_level", level, ...
    "output_directory", outputDirectory, "sample_rate_hz", render.sample_rate_hz, ...
    "frame_count", cycle.frame_count, "pcm_sha256", s12_sound_playground_sha256( ...
        fullfile(outputDirectory, "full_drive_cycle_pcm_f32le.bin")));
end

function profile = resolveProfile(profileInput)
if isstruct(profileInput)
    profile = profileInput;
    s12_engine_sound_validate_profile(profile);
else
    profile = s12_engine_sound_load_profile(profileInput);
end
end

function outputDirectory = createRunDirectory(profileId, requestedRunId)
runRoot = s12_engine_sound_runtime_root();
if ~isfolder(runRoot)
    mkdir(runRoot);
end
runId = string(requestedRunId);
if strlength(runId) == 0
    runId = "run_" + string(datetime("now", Format="yyyyMMdd_HHmmss_SSS"));
end
if ~isscalar(runId) || isempty(regexp(char(runId), "^[A-Za-z0-9_-]+$", "once"))
    error("S12:EngineSoundV10:RunId", "RunId must contain only letters, digits, underscores, or hyphens.");
end
candidate = fullfile(runRoot, runId, profileId);
suffix = 1;
while isfolder(candidate)
    candidate = fullfile(runRoot, runId + "_" + string(suffix), profileId);
    suffix = suffix + 1;
end
[created, message] = mkdir(candidate);
if ~created
    error("S12:EngineSoundV10:OutputDirectory", "Cannot create runtime output directory: %s", message);
end
outputDirectory = string(candidate);
end

function publishRun(outputDirectory, profile, cycle, render)
sampleRate = render.sample_rate_hz;
writePcm(fullfile(outputDirectory, "full_drive_cycle_pcm_f32le.bin"), render.pcm);
audiowrite(fullfile(outputDirectory, "full_drive_cycle.wav"), render.pcm, sampleRate, BitsPerSample=24);
writeSegment(fullfile(outputDirectory, "idle.wav"), render.pcm, sampleRate, 2, 12);
writeSegment(fullfile(outputDirectory, "acceleration.wav"), render.pcm, sampleRate, 32, 48);
writeSegment(fullfile(outputDirectory, "deceleration.wav"), render.pcm, sampleRate, 54, 66);
writeSegment(fullfile(outputDirectory, "overrun_backfire.wav"), render.pcm, sampleRate, 82, 88);
trace = array2table([cycle.timestamp_s, cycle.state], VariableNames=["timestamp_s", cycle.state_columns]);
writetable(trace, fullfile(outputDirectory, "vehicle_trace.csv"));
s12_sound_playground_atomic_write_json(fullfile(outputDirectory, "profile_snapshot.json"), profile, false);
analysis = buildAnalysis(profile, cycle, render);
s12_sound_playground_atomic_write_json(fullfile(outputDirectory, "sound_analysis.json"), analysis, false);
manifest = struct("schema_version", "s12_engine_sound_v10_manifest", ...
    "architecture", "engine_excitation_to_shared_ptr_adapter_to_renderer", ...
    "profile_id", profile.profile_id.value, "synthetic", true, "calibrated", false, ...
    "offline", true, "realtime_qualified", false, "sample_rate_hz", sampleRate, ...
    "frame_samples", cycle.frame_samples, "frame_count", cycle.frame_count, ...
    "duration_s", 90, "backfire_level", cycle.backfire_level, ...
    "profile_snapshot_sha256", s12_sound_playground_sha256(fullfile(outputDirectory, "profile_snapshot.json")), ...
    "vehicle_trace_sha256", s12_sound_playground_sha256(fullfile(outputDirectory, "vehicle_trace.csv")));
s12_sound_playground_atomic_write_json(fullfile(outputDirectory, "manifest.json"), manifest, false);
writeSha256(outputDirectory);
end

function analysis = buildAnalysis(profile, cycle, render)
pcm = render.pcm;
boundaries = cycle.frame_samples:cycle.frame_samples:(size(pcm, 1) - cycle.frame_samples);
if isempty(boundaries)
    boundaryJump = 0;
else
    boundaryJump = max(abs(pcm(boundaries + 1, :) - pcm(boundaries, :)), [], "all");
end
analysis = struct("profile_id", profile.profile_id.value, "synthetic", true, ...
    "rpm_range", [min(cycle.state(:, 1)), max(cycle.state(:, 1))], ...
    "load_range", [min(cycle.state(:, 2)), max(cycle.state(:, 2))], ...
    "sample_rate_hz", render.sample_rate_hz, "channels", 2, ...
    "peak", max(abs(pcm), [], "all"), "rms", rms(pcm, "all"), ...
    "dc", mean(pcm, "all"), "clipping_count", sum(abs(pcm) >= 1, "all"), ...
    "boundary_jump_peak", boundaryJump, "firing_frequency_hz", ...
    profile.engine.cylinder_count.value / 2 * cycle.state(:, 1) / 60, ...
    "harmonics", render.analysis.order_energy, ...
    "backfire_event_count", numel(cycle.backfire_events));
end

function writeSegment(path, pcm, sampleRate, startSeconds, endSeconds)
startSample = floor(startSeconds * sampleRate) + 1;
endSample = min(floor(endSeconds * sampleRate), size(pcm, 1));
segment = pcm(startSample:endSample, :);
fadeSamples = min(round(0.01 * sampleRate), floor(size(segment, 1) / 2));
if fadeSamples > 0
    envelope = ones(size(segment, 1), 1);
    ramp = (0:fadeSamples - 1).' / fadeSamples;
    envelope(1:fadeSamples) = ramp;
    envelope(end - fadeSamples + 1:end) = flipud(ramp);
    segment = segment .* envelope;
end
audiowrite(path, segment, sampleRate, BitsPerSample=24);
end

function writePcm(path, pcm)
file = fopen(path, "w", "ieee-le");
if file < 0
    error("S12:EngineSoundV10:PcmWrite", "Cannot write PCM: %s", path);
end
cleanup = onCleanup(@() fclose(file));
written = fwrite(file, single(pcm.'), "single");
if written ~= numel(pcm)
    error("S12:EngineSoundV10:PcmWrite", "PCM write was incomplete: %s", path);
end
end

function writeSha256(outputDirectory)
names = ["full_drive_cycle.wav", "idle.wav", "acceleration.wav", "deceleration.wav", ...
    "overrun_backfire.wav", "vehicle_trace.csv", "profile_snapshot.json", "sound_analysis.json", ...
    "manifest.json", "full_drive_cycle_pcm_f32le.bin"];
lines = strings(numel(names), 1);
for index = 1:numel(names)
    lines(index) = s12_sound_playground_sha256(fullfile(outputDirectory, names(index))) + "  " + names(index);
end
file = fopen(fullfile(outputDirectory, "SHA256.txt"), "w", "n", "UTF-8");
if file < 0
    error("S12:EngineSoundV10:HashWrite", "Cannot write SHA256.txt.");
end
cleanup = onCleanup(@() fclose(file));
fprintf(file, "%s\n", lines);
end
