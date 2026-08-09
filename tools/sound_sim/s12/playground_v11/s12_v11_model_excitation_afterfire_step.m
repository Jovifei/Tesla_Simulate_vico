function prePtrExcitation = s12_v11_model_excitation_afterfire_step(packedInput, vehicleId)
%S12_V11_MODEL_EXCITATION_AFTERFIRE_STEP Render JSON-driven source before PTR.
% Dashboard order/transient/backfire controls affect only the excitation side.

profile = s12_v11_load_profile(vehicleId);
sampleRateHz = profile.renderer.sample_rate_hz;
frameSamples = profile.renderer.frame_samples;
if ~isnumeric(packedInput) || ~isequal(size(packedInput), [22, 1]) || ...
        any(~isfinite(packedInput), "all")
    error("S12:EngineSoundV11:ModelExcitation", ...
        "Excitation input must pack [21,1] Vehicle State plus one Clock time.");
end
stateVector = double(packedInput(1:21));
frameTimeS = double(packedInput(22));
persistent context lastVehicleId schedulerState lastFrameTimeS activeEvents
if ~isnumeric(frameTimeS) || ~isscalar(frameTimeS) || ~isfinite(frameTimeS) || frameTimeS < 0
    error("S12:EngineSoundV11:ModelExcitation", "Clock time must be one finite nonnegative scalar.");
end
if isempty(lastVehicleId) || string(lastVehicleId) ~= string(profile.vehicle_id) || ...
        isempty(lastFrameTimeS) || frameTimeS < lastFrameTimeS || frameTimeS <= 0
    context = emptyContext();
    lastVehicleId = string(profile.vehicle_id);
    schedulerState = [];
    activeEvents = emptyEventArray();
end
state = unpackState(stateVector, frameTimeS);
[baseExcitation, context] = renderBaseExcitation(profile, state, context, sampleRateHz, frameSamples);
afterfireLevel = afterfireLevelFromControl(state.backfire_level);
[events, ~, schedulerState] = s12_v11_schedule_afterfire(state, profile, afterfireLevel, ...
    "simulink-model|" + string(profile.vehicle_id), schedulerState);
if ~isempty(events)
    activeEvents(end + (1:numel(events)), 1) = events; %#ok<AGROW>
end
eventsForPressure = selectEventsForPressureFrame(activeEvents, state.timestamp_s, sampleRateHz, frameSamples);
[afterfirePressure, ~] = s12_v11_render_afterfire_pressure_frame(eventsForPressure, ...
    state.timestamp_s, sampleRateHz, frameSamples, ...
    "simulink-model|" + string(profile.vehicle_id) + "|t-" + string(frameTimeS));
prePtrExcitation = baseExcitation + afterfirePressure;
if ~isequal(size(prePtrExcitation), [frameSamples, 1]) || any(~isfinite(prePtrExcitation), "all")
    error("S12:EngineSoundV11:ModelExcitation", ...
        "Vehicle excitation plus afterfire must be one finite [960,1] frame.");
end
lastFrameTimeS = frameTimeS;
activeEvents = keepFutureTails(activeEvents, frameTimeS + frameSamples / sampleRateHz);
end

function context = emptyContext()
context = struct("order_phase_rad", zeros(1, 6), "firing_phase_rad", 0, ...
    "intake_phase_rad", 0, "supercharger_phase_rad", 0, "last_throttle", 0);
end

function state = unpackState(stateVector, frameTimeS)
if ~isnumeric(stateVector) || ~isequal(size(stateVector), [21, 1]) || any(~isfinite(stateVector), "all")
    error("S12:EngineSoundV11:ModelState", "Vehicle State must provide twenty-one finite values.");
end
values = double(stateVector(:));
shiftNames = ["none", "upshift", "downshift"];
shiftIndex = max(1, min(numel(shiftNames), round(values(7)) + 1));
state = struct( ...
    "rpm", values(1), "load", values(2), "throttle", values(3), ...
    "acceleration", values(4), "speed_kph", values(5), "gear", values(6), ...
    "shift_type", shiftNames(shiftIndex), "dfco", logical(values(8)), ...
    "thermal_state", ternary(values(9) > 0, "warm", "cold"), ...
    "oxygen_state", ternary(values(10) > 0, "normal", "limited"), ...
    "order_balance", values(11), "transient_scale", values(12), ...
    "backfire_level", values(13), "dthrottle_dt", values(19), ...
    "drpm_dt", values(20), "thermal_eligibility", values(21), ...
    "timestamp_s", frameTimeS);
end

function level = afterfireLevelFromControl(value)
index = max(0, min(2, round(value)));
levels = ["off", "subtle", "aggressive"];
level = levels(index + 1);
end

function [excitation, context] = renderBaseExcitation(profile, state, context, sampleRateHz, frameSamples)
character = profile.character;
rpm = max(character.idle_rpm, min(character.redline_rpm, state.rpm));
loadValue = max(character.minimum_load, min(character.maximum_load, state.load));
throttle = max(0, min(1, state.throttle));
timeIndex = (0:frameSamples - 1).';
baseFrequency = rpm / 60;
excitation = zeros(frameSamples, 1);
for order = 1:numel(character.order_gains)
    omega = 2 * pi * baseFrequency * order / sampleRateHz;
    phase = context.order_phase_rad(order) + omega * timeIndex;
    tilt = 1 + character.order_load_tilt_gain * loadValue * (order - 1) / ...
        max(numel(character.order_gains) - 1, 1);
    excitation = excitation + state.order_balance * character.order_gains(order) * tilt .* sin(phase);
    context.order_phase_rad(order) = mod(context.order_phase_rad(order) + omega * frameSamples, 2 * pi);
end
if character.engine_kind == "rotary"
    [rotaryExcitation, context.firing_phase_rad, firingPhase] = s12_v11_render_rotary_excitation_frame( ...
        state, character, profile.engine, context.firing_phase_rad, sampleRateHz, frameSamples);
    excitation = excitation + rotaryExcitation;
else
    % Shared helper consumes character.firing_gain and character.firing_harmonic_gain
    % with the JSON-owned profile.engine firing-event geometry.
    [pistonExcitation, context.firing_phase_rad, firingPhase] = ...
        s12_v11_render_piston_excitation_frame(state, character, profile.engine, ...
        context.firing_phase_rad, sampleRateHz, frameSamples);
    excitation = excitation + pistonExcitation;
end
intakeOmega = 2 * pi * 0.5 * baseFrequency / sampleRateHz;
excitation = excitation + character.intake_tone * ...
    (character.intake_base_mix + character.intake_throttle_mix * throttle) .* ...
    sin(context.intake_phase_rad + intakeOmega * timeIndex);
context.intake_phase_rad = mod(context.intake_phase_rad + intakeOmega * frameSamples, 2 * pi);
if character.supercharger_tone > 0
    superchargerOmega = 2 * pi * 10 * baseFrequency / sampleRateHz;
    excitation = excitation + character.supercharger_tone * ...
        (character.supercharger_base_mix + character.supercharger_throttle_mix * throttle) .* ...
        sin(context.supercharger_phase_rad + superchargerOmega * timeIndex);
    context.supercharger_phase_rad = mod(context.supercharger_phase_rad + ...
        superchargerOmega * frameSamples, 2 * pi);
end
transient = max(state.acceleration, 0) * profile.transient.acceleration_gain + ...
    profile.transient.throttle_delta_gain * abs(throttle - context.last_throttle);
context.last_throttle = throttle;
excitation = character.source_gain * ...
    (character.source_base_mix + character.source_load_mix * loadValue) .* excitation + ...
    state.transient_scale * profile.transient.output_gain * transient .* sin(2 * firingPhase);
end

function events = emptyEventArray()
template = struct("time_s", 0, "kind", "", "location", "pre_ptr_exhaust_source", ...
    "energy", 0, "cluster_id", "", "variation", 0, "eligibility_explanation", "", ...
    "dynamic_energy_scale", 1, "lift_duration_s", 0);
events = repmat(template, 0, 1);
end

function events = selectEventsForPressureFrame(allEvents, frameStartS, sampleRateHz, frameSamples)
if isempty(allEvents), events = allEvents; return; end
frameEndS = frameStartS + frameSamples / sampleRateHz;
times = [allEvents.time_s];
events = allEvents(times >= frameStartS - 0.012 & times < frameEndS);
end

function events = keepFutureTails(allEvents, nextFrameStartS)
if isempty(allEvents), events = allEvents; return; end
events = allEvents([allEvents.time_s] >= nextFrameStartS - 0.012);
end

function value = ternary(condition, trueValue, falseValue)
if condition, value = trueValue; else, value = falseValue; end
end
