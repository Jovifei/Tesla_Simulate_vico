function receipt = s12_stage_n_run_shared_psychoacoustic_fixture(fixtureRoot, outputRoot)
%S12_STAGE_N_RUN_SHARED_PSYCHOACOUSTIC_FIXTURE Execute the shared MAT fixture.
%   The MAT payload is generated once outside MATLAB and is consumed unchanged
%   by this Desktop-only call and by the isolated MoSQITo process.

arguments
    fixtureRoot (1,:) char
    outputRoot (1,:) char
end

manifestPath = fullfile(fixtureRoot, 'fixture_manifest.json');
if ~isfile(manifestPath)
    error('s12:StageN:SharedFixtureMissing', 'Shared psychoacoustic fixture manifest is missing.');
end
if isfolder(outputRoot)
    error('s12:StageN:OutputExists', 'Refusing to overwrite an existing shared fixture result directory.');
end
manifest = jsondecode(fileread(manifestPath));
matPath = fullfile(fixtureRoot, manifest.fixture_mat);
if ~isfile(matPath)
    error('s12:StageN:SharedFixtureMissing', 'Shared psychoacoustic MAT payload is missing.');
end
values = load(matPath);
names = {'base', 'gain', 'high_frequency_boost', 'fast_am', 'slow_am', 'prominent_tone'};
if ~all(isfield(values, names)) || ~isfield(values, 'sample_rate_hz')
    error('s12:StageN:SharedFixtureContract', 'Shared psychoacoustic MAT payload is incomplete.');
end
signals = rmfield(values, 'sample_rate_hz');
provenance = struct( ...
    'fixture_id', manifest.fixture_id, ...
    'fixture_manifest_sha256', '', ...
    'fixture_mat_sha256', manifest.fixture_mat_sha256);
inputSpec = struct( ...
    'mode', 'shared_fixture', ...
    'fixture_signals', signals, ...
    'sample_rate_hz', double(values.sample_rate_hz), ...
    'fixture_provenance', provenance);
mkdir(outputRoot);
result = s12_psychoacoustic_analysis(inputSpec, outputRoot);
result.output_artifact = fullfile(outputRoot, 'matlab_psychoacoustic_metrics.json');
receipt = struct( ...
    'schema_version', 's12-stage-n-matlab-shared-psychoacoustic-fixture-1', ...
    'status', result.status, ...
    'fixture', result, ...
    'fixture_manifest_path', manifestPath, ...
    'fixture_mat_path', matPath);
s12_export_matlab_comparator_result(receipt, outputRoot, 'matlab_shared_psychoacoustic_fixture_receipt');
end
