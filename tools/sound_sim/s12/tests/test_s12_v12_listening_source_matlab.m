function tests = test_s12_v12_listening_source_matlab
%TEST_S12_V12_LISTENING_SOURCE_MATLAB Source-only listening research contracts.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Folder = fileparts(fileparts(mfilename("fullpath")));
commonFolder = fullfile(s12Folder, "playground_v12", "common");
vehicleFolder = fullfile(s12Folder, "playground_v12", "vehicles");
testCase.TestData.root = fileparts(fileparts(fileparts(s12Folder)));
testCase.TestData.vehicleFolder = vehicleFolder;
testCase.TestData.ids = ["hellcat_2022_stock", "ferrari_458_stock", "rx7_fd_1991_stock"];
addpath(commonFolder);
testCase.addTeardown(@() rmpath(commonFolder));
end

function testDefaultAndDisabledMatchOriginalMultiFrameGolden(testCase)
goldenPath = fullfile(testCase.TestData.root, "reports", ...
    "app8-listening-candidate-20261029", "source-interface-default-golden.mat");
saved = load(goldenPath, "golden");
for i = 1:numel(testCase.TestData.ids)
    source = loadSource(testCase, testCase.TestData.ids(i));
    omittedContext = [];
    disabledContext = [];
    for j = 1:3
        state = goldenState(j);
        [frame, omittedContext, diagnostics] = s12_v12_render_source_frame( ...
            state, source, omittedContext, 48000, 960, []);
        expected = saved.golden{i, j};
        verifyEqual(testCase, frame, expected.frame);
        verifyEqual(testCase, omittedContext, expected.context);
        verifyEqual(testCase, diagnostics, expected.diagnostics);
        assertEqual(testCase, nargin("s12_v12_render_source_frame"), 7, ...
            "The disabled research option is not yet available.");
        [frame, disabledContext, diagnostics] = s12_v12_render_source_frame( ...
            state, source, disabledContext, 48000, 960, [], struct("enabled", false));
        verifyEqual(testCase, frame, expected.frame);
        verifyEqual(testCase, disabledContext, expected.context);
        verifyEqual(testCase, diagnostics, expected.diagnostics);
    end
end
end

function testIdentityComponentsReconstructWithoutChangingLegacyOutputs(testCase)
assertEqual(testCase, nargout("s12_v12_render_engine_identity_frame"), 4, ...
    "Normalized identity components are not yet available.");
samples = 960;
rpm = 3600 * ones(samples, 1);
phase = 2 * pi * (3600 / 60) * (0:samples - 1)' / 48000;
for id = testCase.TestData.ids
    identity = s12_v12_load_engine_identity_profile(id);
    args = {identity, phase, rpm, 0.7 * ones(samples, 1), ...
        0.8 * ones(samples, 1), zeros(samples, 1), [], 48000, samples};
    [original, originalContext, originalDiagnostics] = s12_v12_render_engine_identity_frame(args{:});
    [banks, context, diagnostics, components] = s12_v12_render_engine_identity_frame(args{:});
    verifyEqual(testCase, banks, original);
    verifyEqual(testCase, context, originalContext);
    verifyEqual(testCase, diagnostics, originalDiagnostics);
    for field = ["exhaust", "whine", "mechanical"]
        verifySize(testCase, components.(field), [samples, 2]);
        verifyTrue(testCase, all(isfinite(components.(field)), "all"));
    end
    verifyEqual(testCase, components.exhaust + components.whine + components.mechanical, ...
        banks, "AbsTol", 2e-15);
    if id == "hellcat_2022_stock"
        verifyGreaterThan(testCase, sum(components.whine .^ 2, "all"), 0);
        verifyGreaterThan(testCase, sum(components.mechanical .^ 2, "all"), 0);
    end
end
end

function testShiftCutUsesSmoothedProgressAndPreservesBypassLayers(testCase)
requireResearchInterface(testCase);
source = loadSource(testCase, "hellcat_2022_stock");
options = researchOptions(1, 1);
state = stateAt(4200, 1, 0.5);
context = struct("shift_progress_control", 0.5);
for event = [-1, 1]
    state.shift_event = event;
    [~, next, d] = s12_v12_render_source_frame(state, source, context, 48000, 960, [], options);
    r = d.research;
    verifySize(testCase, r.cut_multiplier, [960, 1]);
    verifyEqual(testCase, r.cut_multiplier, 0.35 * ones(960, 1), "AbsTol", 1e-15);
    verifyEqual(testCase, [r.cut_min, r.cut_max], [0.35, 0.35], "AbsTol", 1e-15);
    for field = ["combustion", "orders", "identity_exhaust"]
        before = r.cut_energy_before.(field);
        verifyGreaterThan(testCase, before, 0);
        verifyEqual(testCase, r.cut_energy_after.(field), 0.35^2 * before, "RelTol", 1e-12);
    end
    for field = ["identity_whine", "identity_mechanical", "mechanical"]
        verifyEqual(testCase, r.cut_energy_after.(field), r.cut_energy_before.(field));
    end
    verifyEqual(testCase, d.layer_energy.gearbox, 0);
    verifyEqual(testCase, next.shift_envelope, 0);
end
state.shift_event = 0;
[~, ~, noShift] = s12_v12_render_source_frame(state, source, context, 48000, 960, [], options);
verifyEqual(testCase, noShift.research.cut_multiplier, ones(960, 1));
state.shift_event = 1;
state.shift_progress = 1;
context.shift_progress_control = 0;
[~, ~, swept] = s12_v12_render_source_frame(state, source, context, 48000, 960, [], options);
progress = linspace(0, 1, 960)';
expected = 1 - 0.65 * sin(pi * progress) .^ 2;
verifyEqual(testCase, swept.research.cut_multiplier, expected, "AbsTol", 1e-15);
verifyEqual(testCase, swept.research.cut_multiplier([1, end]), [1; 1], "AbsTol", 1e-15);
verifyLessThan(testCase, min(swept.research.cut_multiplier), 0.351);
legacyState = state;
legacyState.shift_progress = 0.5;
[~, ~, legacy] = s12_v12_render_source_frame(legacyState, source, context, 48000, 960, []);
verifyGreaterThan(testCase, legacy.layer_energy.gearbox, 0);
end

function testVoicingUsesSmoothedRpmAndKeepsAttenuationAfterNormalization(testCase)
requireResearchInterface(testCase);
source = loadSource(testCase, "hellcat_2022_stock");
whine = 10^(-6 / 20);
induction = 10^(-3 / 20);
options = researchOptions(whine, induction);
state = stateAt(4000, 0, 0);
context = struct("rpm_control", 1500);
[~, ~, d] = s12_v12_render_source_frame(state, source, context, 48000, 960, [], options);
rpm = linspace(1500, 4000, 960)';
x = max(0, min(1, (rpm - 2000) / 1500));
activation = x .^ 2 .* (3 - 2 * x);
verifyEqual(testCase, d.research.voicing_activation, activation, "AbsTol", 1e-15);
verifyEqual(testCase, d.research.whine_scale, 1 - (1 - whine) * activation, "AbsTol", 1e-15);
verifyEqual(testCase, d.research.induction_scale, 1 - (1 - induction) * activation, "AbsTol", 1e-15);
verifyEqual(testCase, d.research.whine_scale(1), 1);
verifyEqual(testCase, d.research.whine_scale(end), whine, "AbsTol", 1e-15);
[~, ~, c] = s12_v12_render_source_frame(state, source, [], 48000, 960, [], options);
[~, ~, b] = s12_v12_render_source_frame(state, source, [], 48000, 960, [], researchOptions(1, 1));
for field = ["identity_whine", "induction"]
    verifyGreaterThan(testCase, b.research.voicing_energy_before.(field), 0);
end
verifyEqual(testCase, c.research.voicing_energy_after.identity_whine, ...
    b.research.voicing_energy_after.identity_whine * whine^2, "RelTol", 1e-12);
verifyEqual(testCase, c.research.voicing_energy_after.induction, ...
    b.research.voicing_energy_after.induction * induction^2, "RelTol", 1e-12);
verifyEqual(testCase, c.research.cut_energy_after.identity_exhaust, ...
    b.research.cut_energy_after.identity_exhaust);
verifyEqual(testCase, c.research.cut_energy_after.identity_mechanical, ...
    b.research.cut_energy_after.identity_mechanical);
end

function testPhaseAndDcStateRemainContinuousAcrossResearchFrames(testCase)
requireResearchInterface(testCase);
source = loadSource(testCase, "hellcat_2022_stock");
state = stateAt(3500, 1, 0.5);
options = researchOptions(1, 1);
context = struct("cycle_phase_rad", 1.1, "shift_progress_control", 0.5, ...
    "dc_input", [0.123, -0.04], "dc_output", [0.32, 0.17]);
zeroDc = context;
zeroDc.dc_input = [0, 0];
zeroDc.dc_output = [0, 0];
[first, next] = s12_v12_render_source_frame(state, source, context, 48000, 960, [], options);
[reference, nextReference] = s12_v12_render_source_frame(state, source, zeroDc, 48000, 960, [], options);
offset = -context.dc_input + 0.995 * context.dc_output;
expected = 0.995 .^ (0:959)' .* offset;
verifyEqual(testCase, first - reference, expected, "AbsTol", 2e-14);
[second, final] = s12_v12_render_source_frame(state, source, next, 48000, 960, [], options);
[secondReference, finalReference] = s12_v12_render_source_frame( ...
    state, source, nextReference, 48000, 960, [], options);
verifyEqual(testCase, second - secondReference, 0.995 .^ (960:1919)' .* offset, "AbsTol", 2e-14);
verifyEqual(testCase, final.cycle_phase_rad, finalReference.cycle_phase_rad);
verifyEqual(testCase, final.identity, finalReference.identity);
verifyEqual(testCase, final.frame_index, 2);
verifyEqual(testCase, final.cycle_phase_rad, mod(1.1 + 2 * pi * 3500 / 60 * 960 / 48000, 2 * pi), ...
    "AbsTol", 1e-12);
end

function testActualOutputReflectsSelectiveVoicingAndCut(testCase)
requireResearchInterface(testCase);
source = loadSource(testCase, "hellcat_2022_stock");
state = stateAt(4000, 0, 0.5);
context = struct("shift_progress_control", 0.5);
unscaled = researchOptions(1, 1);
[baseline, ~] = s12_v12_render_source_frame(state, source, context, 48000, 960, [], unscaled);
[quieterWhine, ~] = s12_v12_render_source_frame( ...
    state, source, context, 48000, 960, [], researchOptions(0.5, 1));
delta = baseline - quieterWhine;
rawDelta = cumsum([delta(1, :); delta(2:end, :) - 0.995 * delta(1:end - 1, :)], 1);
increment = pi * state.rpm / (60 * 48000);
phase = 2 * [0; cumsum(repmat(increment, 959, 1))];
identity = s12_v12_load_engine_identity_profile("hellcat_2022_stock");
[~, ~, ~, components] = s12_v12_render_engine_identity_frame(identity, phase, ...
    state.rpm * ones(960, 1), state.load * ones(960, 1), ...
    state.throttle * ones(960, 1), zeros(960, 1), [], 48000, 960);
verifyEqual(testCase, rawDelta, 0.5 * components.whine, "AbsTol", 2e-13);

% Change only a copied fixture in memory to isolate the induction contribution.
noInductionSource = source;
noInductionSource.source.induction_gain.value = 0;
[noInduction, ~] = s12_v12_render_source_frame( ...
    state, noInductionSource, context, 48000, 960, [], unscaled);
[halfInduction, ~] = s12_v12_render_source_frame( ...
    state, source, context, 48000, 960, [], researchOptions(1, 0.5));
verifyGreaterThan(testCase, norm(baseline - noInduction, "fro"), 0);
verifyEqual(testCase, 2 * (baseline - halfInduction), baseline - noInduction, "AbsTol", 2e-13);

% With copied combustion and order gains set to zero, the shift difference
% can only be the separately returned normalized identity exhaust.
isolated = source;
isolated.source.combustion_gain.value = 0;
for k = 1:numel(isolated.source.order_surface)
    isolated.source.order_surface(k).low_load_gains.value(:) = 0;
    isolated.source.order_surface(k).high_load_gains.value(:) = 0;
end
fullCut = unscaled;
fullCut.cut_minimum = 0;
[isolatedNoShift, ~] = s12_v12_render_source_frame( ...
    state, isolated, context, 48000, 960, [], fullCut);
shift = state;
shift.shift_event = 1;
[isolatedCut, ~] = s12_v12_render_source_frame( ...
    shift, isolated, context, 48000, 960, [], fullCut);
delta = isolatedNoShift - isolatedCut;
rawDelta = cumsum([delta(1, :); delta(2:end, :) - 0.995 * delta(1:end - 1, :)], 1);
verifyEqual(testCase, rawDelta, components.exhaust, "AbsTol", 2e-13);
[fullSourceCut, ~] = s12_v12_render_source_frame( ...
    shift, source, context, 48000, 960, [], fullCut);
verifyEqual(testCase, baseline - fullSourceCut, ...
    (baseline - isolatedNoShift) + (isolatedNoShift - isolatedCut), "AbsTol", 2e-13);
[noCutShift, ~] = s12_v12_render_source_frame( ...
    shift, source, context, 48000, 960, [], setField(unscaled, "cut_minimum", 1));
verifyEqual(testCase, noCutShift, baseline);
end

function testResearchRejectsInvalidOptionsAndOtherVehicles(testCase)
requireResearchInterface(testCase);
source = loadSource(testCase, "hellcat_2022_stock");
state = stateAt(4000, 0, 0);
valid = researchOptions(1, 1);
bad = {struct("enabled", 1), struct("enabled", true), ...
    setField(valid, "cut_minimum", -0.01), setField(valid, "cut_minimum", NaN), ...
    setField(valid, "whine_scale", 1.01), setField(valid, "induction_scale", -0.1), ...
    setField(valid, "voicing_rpm_band", [2000, 2000]), ...
    setField(valid, "voicing_rpm_band", [3500, 2000]), ...
    setField(valid, "voicing_rpm_band", [2000, Inf]), ...
    setField(valid, "voicing_rpm_band", [2000; 3500])};
for i = 1:numel(bad)
    verifyError(testCase, @() s12_v12_render_source_frame( ...
        state, source, [], 48000, 960, [], bad{i}), "S12:EngineSoundV12:ResearchOptions");
end
for id = ["ferrari_458_stock", "rx7_fd_1991_stock"]
    other = loadSource(testCase, id);
    verifyError(testCase, @() s12_v12_render_source_frame( ...
        state, other, [], 48000, 960, id, valid), "S12:EngineSoundV12:ResearchOptions");
end
end

function testResearchRejectsFerrariSourceWithExplicitHellcatIdentity(testCase)
requireResearchInterface(testCase);
source = loadSource(testCase, "ferrari_458_stock");
state = stateAt(4000, 0, 0);
verifyError(testCase, @() s12_v12_render_source_frame( ...
    state, source, [], 48000, 960, "hellcat_2022_stock", researchOptions(1, 1)), ...
    "S12:EngineSoundV12:ResearchOptions");
end

function requireResearchInterface(testCase)
assertEqual(testCase, nargin("s12_v12_render_source_frame"), 7, ...
    "The source research option is not yet available.");
end

function options = researchOptions(whine, induction)
options = struct("enabled", true, "cut_minimum", 0.35, "whine_scale", whine, ...
    "induction_scale", induction, "voicing_rpm_band", [2000, 3500]);
end

function changed = setField(value, field, replacement)
changed = value;
changed.(field) = replacement;
end

function source = loadSource(testCase, id)
source = jsondecode(fileread(fullfile(testCase.TestData.vehicleFolder, id, "source_profile.json")));
end

function state = stateAt(rpm, event, progress)
state = struct("rpm", rpm, "load", 0.7, "throttle", 0.8, "acceleration", 0, ...
    "shift_event", event, "shift_progress", progress, ...
    "afterfire_kind", "none", "afterfire_progress", 0);
end

function state = goldenState(index)
rpms = [800, 3200, 4200];
loads = [0.22, 0.7, 0.9];
throttles = [0.15, 0.65, 0.8];
accelerations = [0, 2, 1];
events = [0, 1, 1];
progress = [0, 0.3, 0.7];
state = struct("rpm", rpms(index), "load", loads(index), "throttle", throttles(index), ...
    "acceleration", accelerations(index), "shift_event", events(index), ...
    "shift_progress", progress(index), "afterfire_kind", "none", "afterfire_progress", 0);
end
