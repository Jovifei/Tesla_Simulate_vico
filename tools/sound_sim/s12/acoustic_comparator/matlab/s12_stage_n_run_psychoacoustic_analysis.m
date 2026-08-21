function receipt = s12_stage_n_run_psychoacoustic_analysis(inputRoot, outputRoot)
%S12_STAGE_N_RUN_PSYCHOACOUSTIC_ANALYSIS Run Audio Toolbox fixture and candidates.
%   This is a manually invoked Desktop-session entry point. It preserves the
%   original PCM24 inputs, emits only Stage-N-owned artifacts, and makes no
%   calibration or external-reference claim.

arguments
    inputRoot (1,:) char
    outputRoot (1,:) char
end

if ~isfolder(inputRoot)
    error('s12:StageN:InputRootMissing', 'MATLAB project-input directory is missing.');
end
if isfolder(outputRoot)
    error('s12:StageN:OutputExists', 'Refusing to overwrite an existing MATLAB result directory.');
end
mkdir(outputRoot);

fixtureRoot = fullfile(outputRoot, 'fixture');
fixture = s12_psychoacoustic_analysis(struct('mode', 'fixture'), fixtureRoot);
fixture.output_artifact = fullfile(fixtureRoot, 'matlab_psychoacoustic_metrics.json');
files = dir(fullfile(inputRoot, '*.mat'));
if isempty(files)
    error('s12:StageN:ProjectInputsMissing', 'No Stage-N project MAT inputs were found.');
end

project = repmat(struct('input_file', '', 'vehicle_id', '', 'status', '', 'output_directory', ''), numel(files), 1);
for index = 1:numel(files)
    inputPath = fullfile(files(index).folder, files(index).name);
    values = load(inputPath);
    required = {'sample_rate_hz', 'rpm', 'state_trace', 'signal_pcm24'};
    if ~all(isfield(values, required)) || size(values.signal_pcm24, 2) ~= 2
        error('s12:StageN:InputContract', 'Project MAT input is missing exact stereo PCM24/RPM/state data.');
    end
    if isfield(values, 'vehicle_id')
        vehicleId = char(string(values.vehicle_id));
    else
        vehicleId = erase(files(index).name, '.mat');
    end
    if size(values.signal_pcm24, 1) ~= numel(values.rpm) || numel(values.rpm) ~= numel(values.state_trace)
        error('s12:StageN:InputContract', 'PCM/RPM/state sample counts do not match.');
    end
    vehicleRoot = fullfile(outputRoot, 'project', vehicleId);
    if isfolder(vehicleRoot)
        error('s12:StageN:VehicleOutputExists', 'A vehicle output directory already exists.');
    end
    inputSpec = struct( ...
        'signal', mean(double(values.signal_pcm24), 2) ./ (2^23), ...
        'sample_rate_hz', double(values.sample_rate_hz));
    result = s12_psychoacoustic_analysis(inputSpec, vehicleRoot);
    project(index) = struct( ...
        'input_file', inputPath, ...
        'vehicle_id', vehicleId, ...
        'status', result.status, ...
        'output_directory', vehicleRoot);
end

receipt = struct( ...
    'schema_version', 's12-stage-n-matlab-psychoacoustic-session-1', ...
    'fixture', fixture, ...
    'project', project, ...
    'input_calibration', 'digital-domain relative only; not absolute SPL', ...
    'reference_status', 'REFERENCE_RPM_UNAVAILABLE', ...
    'comparison_status', 'ORDER_COMPARISON_NOT_QUALIFIED');
s12_export_matlab_comparator_result(receipt, outputRoot, 'matlab_psychoacoustic_session_receipt');
writeValidationMarkdown(receipt, outputRoot);
end

function writeValidationMarkdown(receipt, outputRoot)
validation = receipt.fixture.validation;
lines = [ ...
    "# S12 MATLAB Psychoacoustic Fixture Validation", ...
    "", ...
    "- Status: `" + string(receipt.fixture.status) + "`.", ...
    "- Calibration: digital-domain relative only; not absolute SPL.", ...
    "- gain increases loudness: `" + string(validation.gain_increases_loudness) + "`.", ...
    "- high-frequency boost increases sharpness: `" + string(validation.high_frequency_increases_sharpness) + "`.", ...
    "- fast AM increases roughness: `" + string(validation.fast_am_increases_roughness) + "`.", ...
    "- slow AM increases fluctuation: `" + string(validation.slow_am_increases_fluctuation) + "`.", ...
    "- prominent tone increases tonality: `" + string(validation.prominent_tone_increases_tonality) + "`.", ...
    "- Project candidates: `" + string(numel(receipt.project)) + "`.", ...
    "- No external-reference residual is claimed." ...
    ];
fileId = fopen(fullfile(outputRoot, 'matlab_psychoacoustic_validation.md'), 'w', 'n', 'UTF-8');
if fileId < 0
    error('s12:StageN:PsychoValidationWrite', 'Cannot write psychoacoustic validation markdown.');
end
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, '%s\n', lines);
end
