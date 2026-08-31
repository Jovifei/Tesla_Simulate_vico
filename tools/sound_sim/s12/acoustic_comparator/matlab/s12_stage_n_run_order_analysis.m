function receipt = s12_stage_n_run_order_analysis(inputRoot, outputRoot)
%S12_STAGE_N_RUN_ORDER_ANALYSIS Run fixture plus hash-bound project inputs.
%   This is a manually invoked Desktop-session entry point. It neither starts
%   MATLAB nor derives RPM from audio or an external reference recording.

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
fixture = s12_order_analysis(struct('mode', 'fixture'), fixtureRoot);
files = dir(fullfile(inputRoot, '*.mat'));
if isempty(files)
    error('s12:StageN:ProjectInputsMissing', 'No Stage-N project MAT inputs were found.');
end

project = repmat(struct('input_file', '', 'vehicle_id', '', 'status', '', 'output_directory', ''), numel(files), 1);
for index = 1:numel(files)
    inputPath = fullfile(files(index).folder, files(index).name);
    values = load(inputPath);
    required = {'sample_rate_hz', 'rpm', 'state_trace'};
    if ~all(isfield(values, required)) || (~isfield(values, 'signal') && ~isfield(values, 'signal_pcm24'))
        error('s12:StageN:InputContract', 'Project MAT input is missing the order-analysis contract.');
    end
    if isfield(values, 'vehicle_id')
        vehicleId = char(string(values.vehicle_id));
    else
        vehicleId = erase(files(index).name, '.mat');
    end
    vehicleRoot = fullfile(outputRoot, 'project', vehicleId);
    if isfolder(vehicleRoot)
        error('s12:StageN:VehicleOutputExists', 'A vehicle output directory already exists.');
    end
    result = s12_order_analysis(values, vehicleRoot);
    project(index) = struct( ...
        'input_file', inputPath, ...
        'vehicle_id', vehicleId, ...
        'status', result.status, ...
        'output_directory', vehicleRoot);
end

receipt = struct( ...
    'schema_version', 's12-stage-n-matlab-order-session-1', ...
    'fixture', fixture, ...
    'project', project, ...
    'reference_status', 'REFERENCE_RPM_UNAVAILABLE', ...
    'comparison_status', 'ORDER_COMPARISON_NOT_QUALIFIED');
s12_export_matlab_comparator_result(receipt, outputRoot, 'matlab_order_session_receipt');
end
