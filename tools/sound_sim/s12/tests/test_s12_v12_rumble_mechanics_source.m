function tests = test_s12_v12_rumble_mechanics_source
% Source-only contracts for the bounded Hellcat mechanical research controls.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12 = fileparts(fileparts(mfilename("fullpath")));
common = fullfile(s12, "playground_v12", "common");
testCase.TestData.vehicles = fullfile(s12, "playground_v12", "vehicles");
root = fileparts(fileparts(fileparts(s12)));
saved = load(fullfile(root, "reports", "app8-rumble-mechanics-candidate-20261029", ...
    "source-before-mechanics-golden.mat"));
testCase.TestData.golden = saved.golden;
testCase.TestData.ids = saved.ids;
addpath(common);
testCase.addTeardown(@() rmpath(common));
end

function testMissingAndNeutralOptionsPreservePreEditGoldenExactly(testCase)
for mode = 1:5
    source = loadSource(testCase, testCase.TestData.ids(mode));
    context = [];
    neutralContext = [];
    for index = 1:4
        expected = testCase.TestData.golden{mode, index};
        if mode <= 3
            [frame, context, diagnostics] = s12_v12_render_source_frame( ...
                expected.state, source, context, 48000, 960);
            options = struct("enabled", false, "mechanical_gain", 1, "mechanical_mod_depth", 0);
        else
            options = oldOptions();
            if mode == 5
                options.whine_scale = 10^(-6/20);
                options.induction_scale = 10^(-3/20);
            end
            [frame, context, diagnostics] = s12_v12_render_source_frame( ...
                expected.state, source, context, 48000, 960, [], options);
            options.mechanical_gain = 1;
            options.mechanical_mod_depth = 0;
        end
        verifyEqual(testCase, frame, expected.frame);
        verifyEqual(testCase, context, expected.context);
        verifyEqual(testCase, diagnostics, expected.diagnostics);
        [frame, neutralContext, diagnostics] = s12_v12_render_source_frame( ...
            expected.state, source, neutralContext, 48000, 960, [], options);
        verifyEqual(testCase, frame, expected.frame);
        verifyEqual(testCase, neutralContext, expected.context);
        verifyEqual(testCase, diagnostics, expected.diagnostics);
    end
end
end

function testBothMechanicalLayersUseExactBankEnvelopeAfterIdentityNormalization(testCase)
source = loadSource(testCase, "hellcat_2022_stock");
state = stateAt(3600);
context = struct("cycle_phase_rad", 2*pi - 0.12);
for setting = [1.25, 0.15; 1.5, 0.45; 1.25, 0; 1, 0.15]'
    options = mechanicsOptions(setting(1), setting(2));
    [active, activeContext, diagnostics] = s12_v12_render_source_frame( ...
        state, source, context, 48000, 960, [], options);
    assertTrue(testCase, isfield(diagnostics.research, "mechanics"), ...
        "Nonneutral mechanical controls must expose their actual source waveforms.");
    m = diagnostics.research.mechanics;
    phase = context.cycle_phase_rad + [0; cumsum(repmat(pi*state.rpm/(60*48000), 959, 1))];
    verifyEqual(testCase, m.cycle_phase_rad, phase);
    envelope = expectedEnvelope(source, phase);
    verifyEqual(testCase, m.envelope, envelope, "AbsTol", 2e-14);
    verifyEqual(testCase, m.multiplier, setting(1)*(1 + setting(2)*envelope), "AbsTol", 2e-14);
    verifyEqual(testCase, [m.gain, m.depth], setting');
    for field = ["envelope", "multiplier", "source_before", "source_after", "identity_before", "identity_after"]
        verifySize(testCase, m.(field), [960, 2]);
        verifyTrue(testCase, all(isfinite(m.(field)), "all"));
    end
    crank = 2*phase;
    mechanical = source.source.mechanical_gain.value * (0.9 + 0.1*sqrt(state.rpm/12000)) .* ...
        (0.7*sin(5*crank) + 0.3*sin(11*crank + pi/6));
    verifyEqual(testCase, m.source_before, [mechanical, mechanical], "AbsTol", 2e-15);
    identity = s12_v12_load_engine_identity_profile("hellcat_2022_stock");
    [~, ~, ~, components] = s12_v12_render_engine_identity_frame(identity, crank, ...
        state.rpm*ones(960,1), state.load*ones(960,1), state.throttle*ones(960,1), ...
        zeros(960,1), [], 48000, 960);
    verifyEqual(testCase, m.identity_before, components.mechanical);
    verifyEqual(testCase, m.source_after, m.source_before.*m.multiplier);
    verifyEqual(testCase, m.identity_after, m.identity_before.*m.multiplier);
    [baseline, baselineContext, baselineDiagnostics] = s12_v12_render_source_frame( ...
        state, source, context, 48000, 960, [], oldOptions());
    rawDelta = cumsum([active(1,:)-baseline(1,:); ...
        diff(active-baseline,1,1) + 0.005*(active(1:end-1,:)-baseline(1:end-1,:))], 1);
    verifyEqual(testCase, rawDelta, m.source_after-m.source_before + ...
        m.identity_after-m.identity_before, "AbsTol", 3e-13);
    verifyEqual(testCase, activeContext.cycle_phase_rad, baselineContext.cycle_phase_rad);
    verifyEqual(testCase, activeContext.identity, baselineContext.identity);
    verifyEqual(testCase, rmfield(diagnostics.research,"mechanics"), baselineDiagnostics.research);
    verifyEqual(testCase, diagnostics.layer_energy.mechanical, sum(m.source_after.^2,"all"));
end
end

function testProfileBanksEventsWrapAndFixedFortyDegreeWidth(testCase)
source = loadSource(testCase, "hellcat_2022_stock");
state = stateAt(0);
options = mechanicsOptions(1.5, 0.45);
for degrees = [-720.01, -20, -10, 0, 10, 20, 20.01, 90, 180, 359.99, 630, 719.99, 720, 1440]
    phase = degrees*2*pi/720;
    [~, ~, diagnostics] = s12_v12_render_source_frame( ...
        state, source, struct("cycle_phase_rad", phase), 48000, 960, [], options);
    assertTrue(testCase, isfield(diagnostics.research,"mechanics"));
    m = diagnostics.research.mechanics;
    verifyEqual(testCase, m.envelope, expectedEnvelope(source, repmat(phase,960,1)), "AbsTol", 2e-14);
    verifyGreaterThanOrEqual(testCase, min(m.envelope,[],"all"), -0.125-1e-14);
    verifyLessThanOrEqual(testCase, max(m.envelope,[],"all"), 1+1e-14);
end
phase = 10*2*pi/720;
[~, ~, diagnostics] = s12_v12_render_source_frame( ...
    state, source, struct("cycle_phase_rad", phase), 48000, 960, [], options);
verifyEqual(testCase, diagnostics.research.mechanics.envelope(1,:), [0.4375,-0.125], "AbsTol", 2e-14);
swapped = source;
swapped.source.bank_map.value = -swapped.source.bank_map.value;
[~, ~, reversed] = s12_v12_render_source_frame( ...
    state, swapped, struct("cycle_phase_rad", phase), 48000, 960, [], options);
verifyEqual(testCase, reversed.research.mechanics.envelope, ...
    fliplr(diagnostics.research.mechanics.envelope), "AbsTol", 2e-14);
end

function testCycleMeanAndPhaseContinueAcrossShiftAndFrameBoundaries(testCase)
source = loadSource(testCase, "hellcat_2022_stock");
state = stateAt(1200);
options = mechanicsOptions(1.25, 0.15);
context = [];
envelopes = zeros(4800,2);
for index = 1:5
    if index == 3
        state.shift_event = 1;
        state.shift_progress = 0.5;
    end
    [~, context, diagnostics] = s12_v12_render_source_frame( ...
        state, source, context, 48000, 960, [], options);
    assertTrue(testCase, isfield(diagnostics.research,"mechanics"));
    m = diagnostics.research.mechanics;
    expectedPhase = (index-1)*960*pi*1200/(60*48000) + ...
        (0:959)'*pi*1200/(60*48000);
    verifyEqual(testCase, m.cycle_phase_rad, expectedPhase, "AbsTol", 2e-13);
    verifyEqual(testCase, m.envelope, expectedEnvelope(source, expectedPhase), "AbsTol", 2e-12);
    envelopes((index-1)*960+(1:960),:) = m.envelope;
    verifyEqual(testCase, diagnostics.research.cut_energy_before.mechanical, ...
        diagnostics.research.cut_energy_after.mechanical);
    verifyEqual(testCase, diagnostics.research.cut_energy_before.identity_mechanical, ...
        diagnostics.research.cut_energy_after.identity_mechanical);
end
verifyEqual(testCase, mean(envelopes,1), [0,0], "AbsTol", 2e-8);
verifyEqual(testCase, exp(1i*context.cycle_phase_rad), 1, "AbsTol", 2e-13);
% Smoothed RPM determines the phase; an active event must not reset it.
state.rpm = 5000;
start = context.cycle_phase_rad;
[~, next, diagnostics] = s12_v12_render_source_frame(state, source, context, 48000, 960, [], options);
rpm = linspace(1200,5000,960)';
increment = pi*rpm/(60*48000);
verifyEqual(testCase, diagnostics.research.mechanics.cycle_phase_rad, start+[0;cumsum(increment(1:end-1))]);
verifyEqual(testCase, next.cycle_phase_rad, mod(start+sum(increment),2*pi));
end

function testRejectsInvalidNewControlsAndActiveOnlyEventGuard(testCase)
source = loadSource(testCase,"hellcat_2022_stock");
state = stateAt(3500);
for field = ["mechanical_gain", "mechanical_mod_depth"]
    badValues = {-0.01, 1.51, NaN, Inf, [1,1], 1i, true, "1"};
    if field == "mechanical_gain"
        badValues{end+1} = 0.99;
    else
        badValues{end+1} = 0.451;
    end
    for index = 1:numel(badValues)
        options = oldOptions();
        options.(field) = badValues{index};
        verifyError(testCase,@() s12_v12_render_source_frame(state,source,[],48000,960,[],options), ...
            "S12:EngineSoundV12:ResearchOptions");
    end
end
uneven = source;
uneven.source.firing_phases_deg.value(1) = 1;
unbalanced = source;
unbalanced.source.bank_map.value(1) = 1;
for malformed = {uneven,unbalanced}
    % Legacy-compatible profiles are rejected only for new nonneutral controls.
    s12_v12_render_source_frame(state,malformed{1},[],48000,960,[],oldOptions());
    s12_v12_render_source_frame(state,malformed{1},[],48000,960,[],mechanicsOptions(1,0));
    verifyError(testCase,@() s12_v12_render_source_frame( ...
        state,malformed{1},[],48000,960,[],mechanicsOptions(1.25,0.15)), ...
        "S12:EngineSoundV12:ResearchOptions");
end
for id = ["ferrari_458_stock","rx7_fd_1991_stock"]
    other = loadSource(testCase,id);
    verifyError(testCase,@() s12_v12_render_source_frame( ...
        state,other,[],48000,960,id,mechanicsOptions(1.25,0.15)), ...
        "S12:EngineSoundV12:ResearchOptions");
end
% Each field independently defaults to the neutral value.
for field = ["mechanical_gain", "mechanical_mod_depth"]
    options = mechanicsOptions(1,0);
    options = rmfield(options,field);
    [frame, context, diagnostics] = s12_v12_render_source_frame(state,source,[],48000,960,[],options);
    [expected, next, original] = s12_v12_render_source_frame(state,source,[],48000,960,[],oldOptions());
    verifyEqual(testCase,frame,expected);
    verifyEqual(testCase,context,next);
    verifyEqual(testCase,diagnostics,original);
end
end

function envelope = expectedEnvelope(profile, phase)
envelope = zeros(numel(phase),2);
for bank = 1:2
    phases = profile.source.firing_phases_deg.value(profile.source.bank_map.value == 2*bank-3);
    pulses = zeros(numel(phase),1);
    for event = phases(:)'
        delta = mod(phase*720/(2*pi)-event+360,720)-360;
        inside = abs(delta)<=20;
        pulses(inside) = pulses(inside) + 0.5*(1+cos(pi*delta(inside)/20));
    end
    envelope(:,bank) = (pulses-1/9)/(8/9);
end
end

function options = oldOptions()
options = struct("enabled",true,"cut_minimum",0.35,"whine_scale",1, ...
    "induction_scale",1,"voicing_rpm_band",[2000,3500]);
end

function options = mechanicsOptions(gain,depth)
options = oldOptions();
options.mechanical_gain = gain;
options.mechanical_mod_depth = depth;
end

function profile = loadSource(testCase,id)
profile = jsondecode(fileread(fullfile(testCase.TestData.vehicles,id,"source_profile.json")));
end

function state = stateAt(rpm)
state = struct("rpm",rpm,"load",0.7,"throttle",0.8,"acceleration",0, ...
    "shift_event",0,"shift_progress",0,"afterfire_kind","none","afterfire_progress",0);
end
