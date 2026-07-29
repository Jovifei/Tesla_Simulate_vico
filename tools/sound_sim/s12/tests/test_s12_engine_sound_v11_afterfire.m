function tests = test_s12_engine_sound_v11_afterfire
%TEST_S12_ENGINE_SOUND_V11_AFTERFIRE Shared synthetic afterfire contracts.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
v11 = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground_v11");
source = fullfile(v11, "common");
addpath(v11);
adapter = s12_v11_resolve_frozen_ptr_adapter();
testCase.TestData.v11 = v11;
testCase.TestData.source = source;
testCase.TestData.adapter = adapter;
addpath(source);
addpath(adapter.source_folder, "-begin");
if string(which(adapter.function_name)) ~= adapter.source_path
    error("S12:EngineSoundV11:TestSetup", ...
        "Behavior tests must call the verified canonical PTR adapter.");
end
end

function teardownOnce(testCase)
clear s12_sound_playground_ptr_tuning_step
if isfolder(testCase.TestData.adapter.source_folder)
    rmpath(testCase.TestData.adapter.source_folder);
end
if isfolder(testCase.TestData.source)
    rmpath(testCase.TestData.source);
end
if isfolder(testCase.TestData.v11)
    rmpath(testCase.TestData.v11);
end
end

function testClosedEligibilityProducesNoEvents(testCase)
profile = makeProfile();
states = [
    makeState("none", false, 850, 0.10, 0.05, 0.00, 0, "warm", "normal")
    makeState("none", false, 2600, 0.35, 0.35, 0.00, 4, "warm", "normal")
    makeState("upshift", false, 4200, 0.60, 0.05, 0.20, 3, "cold", "normal")
    makeState("none", false, 4200, 0.20, 0.05, -1.50, 3, "warm", "depleted")
];
for index = 1:numel(states)
    events = s12_v11_schedule_afterfire(states(index), profile, "subtle", "closed-" + index);
    verifyEmpty(testCase, events);
end
events = s12_v11_schedule_afterfire(makeState("upshift", false), profile, "off", "off");
verifyEmpty(testCase, events);
end

function testThreeStateRoutesAreIsolated(testCase)
profile = makeProfile();
upshift = s12_v11_schedule_afterfire(makeState("upshift", false), profile, "subtle", "upshift");
downshift = s12_v11_schedule_afterfire( ...
    makeState("downshift", false, 3600, 0.35, 0.45, -0.8, 3), profile, "subtle", "downshift");
overrun = s12_v11_schedule_afterfire( ...
    makeState("none", true, 3400, 0.25, 0.03, -1.4, 3), profile, "subtle", "overrun");
verifyEqual(testCase, unique(string({upshift.kind})), "upshift_bark");
verifyEqual(testCase, unique(string({downshift.kind})), "downshift_blip_pop");
verifyEqual(testCase, unique(string({overrun.kind})), "overrun_crackle");
end

function testLevelsAreMonotonicAndRepeatable(testCase)
profile = makeProfile();
state = makeState("none", true, 3900, 0.30, 0.02, -1.8, 4);
subtle = s12_v11_schedule_afterfire(state, profile, "subtle", "repeatable");
aggressive = s12_v11_schedule_afterfire(state, profile, "aggressive", "repeatable");
repeat = s12_v11_schedule_afterfire(state, profile, "aggressive", "repeatable");
verifyGreaterThan(testCase, numel(aggressive), numel(subtle));
verifyGreaterThan(testCase, sum([aggressive.energy]), sum([subtle.energy]));
verifyEqual(testCase, repeat, aggressive);
end

function testClusterIntervalsVaryAndEnergyDecays(testCase)
events = s12_v11_schedule_afterfire( ...
    makeState("none", true, 4100, 0.20, 0.02, -1.6, 4), makeProfile(), ...
    "aggressive", "cluster-shape");
intervals = diff([events.time_s]);
verifyGreaterThanOrEqual(testCase, numel(events), 4);
verifyGreaterThan(testCase, max(intervals) - min(intervals), 1e-6);
verifyTrue(testCase, all(diff([events.energy]) < 0));
verifyTrue(testCase, all([events.variation] >= -1 & [events.variation] <= 1));
verifyTrue(testCase, all(string({events.location}) == "pre_ptr_exhaust_source"));
end

function testNearUpperAcceptedDecayAlwaysStrictlyDecreases(testCase)
profile = makeProfile();
profile.afterfire.cluster_energy_decay = 0.899;
state = makeState("none", true, 4100, 0.20, 0.02, -1.6, 4);
for scenario = 1:32
    events = s12_v11_schedule_afterfire( ...
        state, profile, "aggressive", "near-upper-decay-" + scenario);
    verifyTrue(testCase, all(diff([events.energy]) < 0));
end
end

function testRejectsUnsafeClusterDecay(testCase)
profile = makeProfile();
profile.afterfire.cluster_energy_decay = 0.90;
verifyError(testCase, @()s12_v11_schedule_afterfire( ...
    makeState("upshift", false), profile, "aggressive", "unsafe-decay"), ...
    "S12:EngineSoundV11:Profile");
end

function testPressureFrameIsFiniteFixedSizeAndBeforePtr(testCase)
state = makeState("upshift", false);
[events, scheduling] = s12_v11_schedule_afterfire(state, makeProfile(), "aggressive", "pressure");
[pressure, rendering] = s12_v11_render_afterfire_pressure_frame( ...
    events, state.timestamp_s, 48000, 960, "pressure");
verifySize(testCase, pressure, [960, 1]);
verifyTrue(testCase, all(isfinite(pressure)));
verifyGreaterThan(testCase, norm(pressure), 0);
verifyEqual(testCase, rendering.insertion_stage, "before_ptr_radiation");
verifyFalse(testCase, rendering.post_pcm_append);
verifyEqual(testCase, scheduling.causality_chain, ...
    ["state", "eligibility", "events", "pre_ptr_pressure_excitation", "ptr_radiation"]);
verifyEqual(testCase, rendering.causality_chain, ...
    ["state", "eligibility", "events", "pre_ptr_pressure_excitation", "ptr_radiation"]);
end

function testRejectsNonpositiveBaseEnergy(testCase)
state = makeState("upshift", false);
for invalid = [0, -0.01]
    profile = makeProfile();
    profile.afterfire.base_energy = invalid;
    verifyError(testCase, @()s12_v11_schedule_afterfire( ...
        state, profile, "subtle", "invalid-energy"), "S12:EngineSoundV11:Profile");
end
end

function testRejectsNonpositiveIntervalJitter(testCase)
state = makeState("upshift", false);
for invalid = [0, -0.01]
    profile = makeProfile();
    profile.afterfire.interval_jitter_fraction = invalid;
    verifyError(testCase, @()s12_v11_schedule_afterfire( ...
        state, profile, "subtle", "invalid-jitter"), "S12:EngineSoundV11:Profile");
end
end

function testAdapterInjectsRenderedEventBeforeExistingPtrContract(testCase)
state = makeState("upshift", false);
events = s12_v11_schedule_afterfire(state, makeProfile(), "aggressive", "adapter-event");
[afterfirePressure, ~] = s12_v11_render_afterfire_pressure_frame( ...
    events, state.timestamp_s, 48000, 960, "adapter-event");
baseExcitation = 0.01 * ones(960, 1);
[pressure, diagnostics] = s12_v11_apply_afterfire_before_ptr( ...
    baseExcitation, afterfirePressure, 1.25, 0.020, -0.35, 0.12, true);
verifySize(testCase, pressure, [960, 1]);
verifyTrue(testCase, all(isfinite(pressure)));
verifyTrue(testCase, diagnostics.pre_ptr_changed);
verifyEqual(testCase, diagnostics.pre_ptr_excitation, baseExcitation + afterfirePressure);
verifyEqual(testCase, diagnostics.ptr_function, "s12_sound_playground_ptr_tuning_step");
verifyEqual(testCase, diagnostics.ptr_source_path, testCase.TestData.adapter.source_path);
verifyEqual(testCase, diagnostics.ptr_source_sha256, testCase.TestData.adapter.sha256);
verifyEqual(testCase, string(which(diagnostics.ptr_function)), diagnostics.ptr_source_path);
verifyFalse(testCase, diagnostics.post_pcm_append);
end

function testLongDfcoScheduleIsRefractoryAndDeterministic(testCase)
profile = s12_v11_load_profile("hellcat_2022_stock");
cycle = s12_v11_compile_vehicle_cycle(profile);
[events, diagnostics] = s12_v11_compile_afterfire_schedule( ...
    cycle, profile, "aggressive", "long-dfco-contract");
[repeatEvents, repeatDiagnostics] = s12_v11_compile_afterfire_schedule( ...
    cycle, profile, "aggressive", "long-dfco-contract");
verifyEqual(testCase, repeatEvents, events);
verifyEqual(testCase, repeatDiagnostics.cluster_start_times_s, ...
    diagnostics.cluster_start_times_s);

starts = diagnostics.cluster_start_times_s;
longDfcoStarts = starts(starts >= 63 & starts < 66);
verifyNotEmpty(testCase, longDfcoStarts);
verifyGreaterThan(testCase, numel(longDfcoStarts), 1);
intervals = diff(longDfcoStarts);
verifyGreaterThanOrEqual(testCase, min(intervals), ...
    profile.afterfire.cluster_refractory_s);
verifyTrue(testCase, all(abs(intervals - 0.02) > 1e-6));
verifyGreaterThan(testCase, max(intervals) - min(intervals), 1e-6);
longDfcoEvents = events([events.time_s] >= 63 & [events.time_s] < 66);
verifyEqual(testCase, numel(unique(string({longDfcoEvents.cluster_id}))), ...
    numel(longDfcoStarts));
end

function testShiftClustersRequireEdges(testCase)
profile = makeProfile();
upshift = makeState("upshift", false, 4200, 0.55, 0.08, 0.4, 3);
upshift.timestamp_s = 12.5;
[first, ~, schedulerState] = s12_v11_schedule_afterfire( ...
    upshift, profile, "aggressive", "shift-edge", []);
verifyNotEmpty(testCase, first);
upshift.timestamp_s = upshift.timestamp_s + 1.0;
[repeated, ~, schedulerState] = s12_v11_schedule_afterfire( ...
    upshift, profile, "aggressive", "shift-edge", schedulerState);
verifyEmpty(testCase, repeated);

neutral = upshift;
neutral.shift_type = "none";
neutral.timestamp_s = neutral.timestamp_s + 0.02;
[~, ~, schedulerState] = s12_v11_schedule_afterfire( ...
    neutral, profile, "aggressive", "shift-edge", schedulerState);
upshift.timestamp_s = neutral.timestamp_s + 0.02;
[nextEdge, ~] = s12_v11_schedule_afterfire( ...
    upshift, profile, "aggressive", "shift-edge", schedulerState);
verifyNotEmpty(testCase, nextEdge);
end

function testDerivativeEligibilityChangesEventScheduling(testCase)
profile = makeProfile();
state = makeState("none", true, 3900, 0.30, 0.02, -1.6, 4);
events = s12_v11_schedule_afterfire(state, profile, "aggressive", "derivative-open");
verifyNotEmpty(testCase, events);

invalidThrottleRate = state;
invalidThrottleRate.dthrottle_dt = 0.02;
verifyEmpty(testCase, s12_v11_schedule_afterfire( ...
    invalidThrottleRate, profile, "aggressive", "derivative-throttle-closed"));

invalidRpmRate = state;
invalidRpmRate.drpm_dt = 0;
verifyEmpty(testCase, s12_v11_schedule_afterfire( ...
    invalidRpmRate, profile, "aggressive", "derivative-rpm-closed"));
end

function testThermalAndLiftDurationReduceRepeatedOverrunEnergyAndRate(testCase)
profile = makeProfile();
state = makeState("none", true, 3900, 0.30, 0.02, -1.6, 4);
state.timestamp_s = 60;
[first, firstDiagnostics, schedulerState] = s12_v11_schedule_afterfire( ...
    state, profile, "aggressive", "thermal-lift", []);
verifyNotEmpty(testCase, first);
state.timestamp_s = 60.6;
[middle, middleDiagnostics, schedulerState] = s12_v11_schedule_afterfire( ...
    state, profile, "aggressive", "thermal-lift", schedulerState);
verifyNotEmpty(testCase, middle);
state.timestamp_s = 63;
state.thermal_eligibility = 0.55;
[late, lateDiagnostics] = s12_v11_schedule_afterfire( ...
    state, profile, "aggressive", "thermal-lift", schedulerState);
verifyNotEmpty(testCase, late);
verifyGreaterThan(testCase, firstDiagnostics.total_energy, 0);
verifyLessThan(testCase, lateDiagnostics.total_energy, middleDiagnostics.total_energy);
verifyGreaterThan(testCase, lateDiagnostics.lift_duration_s, middleDiagnostics.lift_duration_s);
verifyLessThan(testCase, lateDiagnostics.lift_energy_scale, middleDiagnostics.lift_energy_scale);
verifyGreaterThan(testCase, lateDiagnostics.next_cluster_not_before_s - state.timestamp_s, ...
    middleDiagnostics.next_cluster_not_before_s - 60.6);
end

function testWholeCycleAfterfireEventsStayInApprovedWindows(testCase)
for vehicleId = s12_v11_canonical_vehicle_ids()
    profile = s12_v11_load_profile(vehicleId);
    cycle = s12_v11_compile_vehicle_cycle(profile);
    events = s12_v11_compile_afterfire_schedule( ...
        cycle, profile, "subtle", "cycle-window-" + vehicleId);
    verifyEventTimesInWindow(testCase, events, "upshift_bark", 48, 54);
    verifyEventTimesInWindow(testCase, events, "downshift_blip_pop", 66, 72);
    verifyEventTimesInEitherWindow(testCase, events, "overrun_crackle", ...
        [54, 66], [82, 88]);
end
end

function testUpshiftHoldRetainsRedlineAndHighLoadWhileEmittingEvent(testCase)
for vehicleId = s12_v11_canonical_vehicle_ids()
    profile = s12_v11_load_profile(vehicleId);
    cycle = s12_v11_compile_vehicle_cycle(profile);
    hold = cycle.timestamp_s >= 48 & cycle.timestamp_s < 54;
    verifyEqual(testCase, cycle.state.rpm(hold), ...
        profile.character.redline_rpm * ones(nnz(hold), 1), "AbsTol", 1e-12);
    verifyEqual(testCase, cycle.state.load(hold), ...
        0.98 * ones(nnz(hold), 1), "AbsTol", 1e-12);
    verifyGreaterThanOrEqual(testCase, min(cycle.state.load(hold)), ...
        profile.afterfire.minimum_shift_load);
    events = s12_v11_compile_afterfire_schedule( ...
        cycle, profile, "subtle", "upshift-hold-" + vehicleId);
    verifyEventTimesInWindow(testCase, events, "upshift_bark", 48, 54);
end
end

function testUpshiftAllowsEitherValidatedNegativeDerivativeEdge(testCase)
profile = makeProfile();
throttleEdge = makeState("upshift", false, 4200, 0.55, 0.08, 0.4, 3);
throttleEdge.drpm_dt = 0;
verifyNotEmpty(testCase, s12_v11_schedule_afterfire( ...
    throttleEdge, profile, "subtle", "upshift-throttle-edge"));

rpmEdge = throttleEdge;
rpmEdge.dthrottle_dt = 0;
rpmEdge.drpm_dt = -120;
verifyNotEmpty(testCase, s12_v11_schedule_afterfire( ...
    rpmEdge, profile, "subtle", "upshift-rpm-edge"));

closed = rpmEdge;
closed.drpm_dt = 0;
verifyEmpty(testCase, s12_v11_schedule_afterfire( ...
    closed, profile, "subtle", "upshift-derivative-closed"));
end

function testThermalEligibilitySeparatelyChangesOverrunEnergyAndRefractory(testCase)
profile = makeProfile();
warm = makeState("none", true, 3900, 0.30, 0.02, -1.6, 4);
warm.timestamp_s = 60;
warm.thermal_eligibility = 0.85;
cool = warm;
cool.thermal_eligibility = 0.55;
[warmEvents, warmDiagnostics] = s12_v11_schedule_afterfire( ...
    warm, profile, "aggressive", "thermal-isolation", []);
[coolEvents, coolDiagnostics] = s12_v11_schedule_afterfire( ...
    cool, profile, "aggressive", "thermal-isolation", []);
verifyNotEmpty(testCase, warmEvents);
verifyNotEmpty(testCase, coolEvents);
verifyEqual(testCase, warmDiagnostics.lift_duration_s, 0);
verifyEqual(testCase, coolDiagnostics.lift_duration_s, 0);
verifyGreaterThan(testCase, warmDiagnostics.total_energy, coolDiagnostics.total_energy);
warmRefractoryS = warmDiagnostics.next_cluster_not_before_s - warm.timestamp_s;
coolRefractoryS = coolDiagnostics.next_cluster_not_before_s - cool.timestamp_s;
verifyLessThan(testCase, warmRefractoryS, coolRefractoryS);
end

function testIdleAndCruiseRemainEventFreeWithDynamicState(testCase)
profile = makeProfile();
idle = makeState("none", false, 900, 0.05, 0.02, 0, 0);
cruise = makeState("none", false, 3000, 0.35, 0.35, 0, 4);
for state = [idle, cruise]
    verifyEmpty(testCase, s12_v11_schedule_afterfire( ...
        state, profile, "aggressive", "dynamic-idle-cruise"));
end
end

function verifyEventTimesInWindow(testCase, events, kind, startS, endS)
matches = events(string({events.kind}) == string(kind));
verifyNotEmpty(testCase, matches);
timesS = [matches.time_s];
verifyGreaterThanOrEqual(testCase, min(timesS), startS);
verifyLessThan(testCase, max(timesS), endS);
end

function verifyEventTimesInEitherWindow(testCase, events, kind, firstWindowS, secondWindowS)
matches = events(string({events.kind}) == string(kind));
verifyNotEmpty(testCase, matches);
timesS = [matches.time_s];
insideFirst = timesS >= firstWindowS(1) & timesS < firstWindowS(2);
insideSecond = timesS >= secondWindowS(1) & timesS < secondWindowS(2);
verifyTrue(testCase, all(insideFirst | insideSecond));
end

function testModelStateProvidesDerivativeAndThermalSlots(testCase)
profile = s12_v11_load_profile("hellcat_2022_stock");
controls = s12_v11_model_dashboard_controls(profile);
controlVector = reshape([controls.default], [], 1);
initial = s12_v11_model_vehicle_state_step([controlVector; 0], 1);
throttleIndex = find(string({controls.field}) == "throttle", 1, "first");
rpmIndex = find(string({controls.field}) == "rpm", 1, "first");
altered = controlVector;
altered(throttleIndex) = controls(throttleIndex).range(2);
altered(rpmIndex) = controls(rpmIndex).range(2);
changed = s12_v11_model_vehicle_state_step([altered; 0.02], 1);
verifySize(testCase, initial, [21, 1]);
verifySize(testCase, changed, [21, 1]);
verifyEqual(testCase, initial(19), 0);
verifyGreaterThan(testCase, changed(19), 0);
verifyGreaterThan(testCase, changed(20), 0);
verifyGreaterThanOrEqual(testCase, changed(21), 0);
verifyLessThanOrEqual(testCase, changed(21), 1);
end

function testEveryAfterfireProfileFieldIsRequiredAndFinite(testCase)
state = makeState("upshift", false);
for field = afterfireFieldNames()
    profile = makeProfile();
    profile.afterfire = rmfield(profile.afterfire, field);
    verifyError(testCase, @()s12_v11_schedule_afterfire( ...
        state, profile, "subtle", "missing-stateful-field"), ...
        "S12:EngineSoundV11:Profile");
    profile = makeProfile();
    profile.afterfire.(field) = NaN;
    verifyError(testCase, @()s12_v11_schedule_afterfire( ...
        state, profile, "subtle", "invalid-stateful-field"), ...
        "S12:EngineSoundV11:Profile");

    profile = makeProfile();
    profile.afterfire.(field) = invalidFiniteValue(field);
    verifyError(testCase, @()s12_v11_schedule_afterfire( ...
        state, profile, "subtle", "out-of-range-stateful-field"), ...
        "S12:EngineSoundV11:Profile");
end
end

function state = makeState(shiftType, dfco, rpm, loadValue, throttle, acceleration, gear, thermal, oxygen)
arguments
    shiftType = "upshift"
    dfco = false
    rpm = 4200
    loadValue = 0.55
    throttle = 0.08
    acceleration = 0.6
    gear = 3
    thermal = "warm"
    oxygen = "normal"
end
state = struct("rpm", rpm, "load", loadValue, "throttle", throttle, ...
    "acceleration", acceleration, "gear", gear, "shift_type", shiftType, ...
    "dfco", dfco, "thermal_state", thermal, "oxygen_state", oxygen, ...
    "dthrottle_dt", defaultThrottleRate(shiftType), ...
    "drpm_dt", defaultRpmRate(shiftType), "thermal_eligibility", 0.85, ...
    "timestamp_s", 12.5);
end

function rate = defaultThrottleRate(shiftType)
if string(shiftType) == "downshift"
    rate = 0.5;
else
    rate = -0.5;
end
end

function rate = defaultRpmRate(shiftType)
if string(shiftType) == "downshift"
    rate = 120;
else
    rate = -120;
end
end

function profile = makeProfile()
profile = struct();
profile.vehicle_id = "synthetic_contract_vehicle";
profile.afterfire = struct( ...
    "idle_rpm_ceiling", 1200, ...
    "minimum_event_rpm", 1800, ...
    "upshift_max_throttle", 0.18, ...
    "downshift_min_throttle", 0.20, ...
    "overrun_max_throttle", 0.10, ...
    "overrun_max_acceleration", -0.25, ...
    "minimum_shift_load", 0.25, ...
    "steady_acceleration_limit", 0.15, ...
    "cruise_min_throttle", 0.15, ...
    "cruise_max_throttle", 0.65, ...
    "base_energy", 0.16, ...
    "onset_delay_s", 0.0015, ...
    "cluster_interval_s", 0.0028, ...
    "interval_jitter_fraction", 0.22, ...
    "cluster_energy_decay", 0.72, ...
    "cluster_refractory_s", 0.25, ...
    "refractory_jitter_fraction", 0.30, ...
    "upshift_max_throttle_rate_per_s", -0.1, ...
    "downshift_min_throttle_rate_per_s", 0.1, ...
    "downshift_min_rpm_rate_per_s", 10, ...
    "overrun_max_throttle_rate_per_s", 0, ...
    "overrun_max_rpm_rate_per_s", -10, ...
    "minimum_thermal_eligibility", 0.25, ...
    "lift_energy_decay_rate_per_s", 0.18, ...
    "lift_refractory_growth_per_s", 0.12);
end

function fields = afterfireFieldNames()
fields = ["idle_rpm_ceiling", "minimum_event_rpm", "upshift_max_throttle", ...
    "downshift_min_throttle", "overrun_max_throttle", ...
    "overrun_max_acceleration", "minimum_shift_load", ...
    "steady_acceleration_limit", "cruise_min_throttle", ...
    "cruise_max_throttle", "base_energy", "onset_delay_s", ...
    "cluster_interval_s", "cluster_refractory_s", ...
    "refractory_jitter_fraction", "interval_jitter_fraction", ...
    "cluster_energy_decay", "upshift_max_throttle_rate_per_s", ...
    "downshift_min_throttle_rate_per_s", "downshift_min_rpm_rate_per_s", ...
    "overrun_max_throttle_rate_per_s", "overrun_max_rpm_rate_per_s", ...
    "minimum_thermal_eligibility", "lift_energy_decay_rate_per_s", ...
    "lift_refractory_growth_per_s"];
end

function value = invalidFiniteValue(field)
switch field
    case "idle_rpm_ceiling"
        value = -1;
    case "minimum_event_rpm"
        value = 0;
    case {"upshift_max_throttle", "downshift_min_throttle", ...
            "overrun_max_throttle", "minimum_shift_load", "cruise_max_throttle"}
        value = 1.1;
    case "overrun_max_acceleration"
        value = 0;
    case "steady_acceleration_limit"
        value = -0.1;
    case "cruise_min_throttle"
        value = -0.1;
    case "base_energy"
        value = 0;
    case "onset_delay_s"
        value = -0.001;
    case {"cluster_interval_s", "refractory_jitter_fraction", ...
            "interval_jitter_fraction"}
        value = 0;
    case "cluster_refractory_s"
        value = 0;
    case "cluster_energy_decay"
        value = 0.90;
    case {"upshift_max_throttle_rate_per_s", "overrun_max_throttle_rate_per_s", ...
            "overrun_max_rpm_rate_per_s"}
        value = 0.01;
    case {"downshift_min_throttle_rate_per_s", "downshift_min_rpm_rate_per_s"}
        value = -0.01;
    case {"minimum_thermal_eligibility", "lift_energy_decay_rate_per_s"}
        value = 0;
    case "lift_refractory_growth_per_s"
        value = -0.01;
    otherwise
        error("S12:EngineSoundV11:Test", "No invalid finite value for %s.", field);
end
end
