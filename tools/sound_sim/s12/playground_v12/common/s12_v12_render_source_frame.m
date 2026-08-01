function [bankExcitation, context, diagnostics] = s12_v12_render_source_frame( ...
        state, sourceProfile, context, sampleRateHz, frameSamples, identityProfileId)
%S12_V12_RENDER_SOURCE_FRAME Render synthetic vehicle excitation before PTR.
% Causality is fixed: combustion/layers/transients/afterfire -> bankExcitation
% -> fixed pre-PTR bank mixer -> frozen PTR/Radiation -> renderer. This function
% never writes or plays audio.

if nargin < 6
    identityProfileId = [];
end
source = s12_v12_validate_source_profile(sourceProfile);
identity = s12_v12_resolve_engine_identity_profile(source, identityProfileId);
state = validateState(state);
validateFrameContract(sampleRateHz, frameSamples);
context = normalizeContext(context);
validateDiscreteTransitions(context, state);

[rpm, context.rpm_control] = smoothControl(context, "rpm_control", state.rpm, frameSamples);
[load, context.load_control] = smoothControl(context, "load_control", state.load, frameSamples);
[throttle, context.throttle_control] = smoothControl(context, "throttle_control", state.throttle, frameSamples);
[acceleration, context.acceleration_control] = smoothControl( ...
    context, "acceleration_control", state.acceleration, frameSamples);
previousAcceleration = context.acceleration_state;
[shiftProgress, context.shift_progress_control] = smoothControl( ...
    context, "shift_progress_control", state.shift_progress, frameSamples);
[afterfireProgress, context.afterfire_progress_control] = smoothControl( ...
    context, "afterfire_progress_control", state.afterfire_progress, frameSamples);
cycleIncrement = pi * rpm / (60 * sampleRateHz);
cyclePhase = context.cycle_phase_rad + [0; cumsum(cycleIncrement(1:end - 1))];
crankPhase = 2 * cyclePhase;
if source.engine_kind == "piston"
    combustion = renderPistonCombustion(source, cyclePhase, load);
    rotaryPhase = context.rotary_phase_rad;
else
    [combustion, rotaryPhase] = renderRotaryCombustion(source, context.rotary_phase_rad, ...
        rpm, load, sampleRateHz, frameSamples);
end
orders = dualBankLayer(renderOrderSurface(source, crankPhase, rpm, load));
intake = dualBankLayer(renderIntakeLayer(source, crankPhase, throttle));
induction = dualBankLayer(renderInductionLayer(source, crankPhase, rpm, load));
mechanical = dualBankLayer(renderMechanicalLayer(source, crankPhase, rpm));
flow = dualBankLayer(renderFlowLayer(source, crankPhase, rpm, load));
[transient, context.acceleration_envelope] = renderAccelerationTransient( ...
    source, crankPhase, acceleration, previousAcceleration, context.acceleration_envelope);
[gearbox, context.shift_envelope] = renderGearboxTransient( ...
    source, crankPhase, state.shift_event, shiftProgress, context.shift_envelope);
[afterfire, context.afterfire_envelope] = renderAfterfire( ...
    source, crankPhase, state.afterfire_kind, afterfireProgress, context.afterfire_envelope);
[identityBanks, context.identity, identityDiagnostics] = s12_v12_render_engine_identity_frame( ...
    identity, crankPhase, rpm, load, throttle, acceleration, context.identity, ...
    sampleRateHz, frameSamples);

rawExcitation = combustion + orders + intake + induction + mechanical + flow + ...
    dualBankLayer(transient) + dualBankLayer(gearbox) + dualBankLayer(afterfire) + identityBanks;
[bankExcitation, context.dc_input, context.dc_output] = applyDcBlocker( ...
    rawExcitation, context.dc_input, context.dc_output);
if ~isequal(size(bankExcitation), [frameSamples, 2]) || any(~isfinite(bankExcitation), "all")
    error("S12:EngineSoundV12:SourceFrame", ...
        "bankExcitation must be one finite [frameSamples, 2] pressure frame.");
end

context.cycle_phase_rad = mod(context.cycle_phase_rad + sum(cycleIncrement), 2 * pi);
context.rotary_phase_rad = rotaryPhase;
context.acceleration_state = state.acceleration;
context.shift_event_state = state.shift_event;
context.afterfire_kind_state = state.afterfire_kind;
context.frame_index = context.frame_index + 1;
diagnostics = struct( ...
    "architecture", "engine_identity_plus_source_layers_before_ptr_radiation", ...
    "causality_chain", ["vehicle_state", "engine_identity", "combustion_excitation", ...
        "exhaust_pulse", "order_surface", "intake", "induction", "mechanical", ...
        "flow", "transient", "gearbox", "afterfire", "before_ptr_radiation"], ...
    "identity", identityDiagnostics, ...
    "layer_energy", struct( ...
        "combustion", energy(combustion), "orders", energy(orders), "intake", energy(intake), ...
        "induction", energy(induction), "mechanical", energy(mechanical), "flow", energy(flow), ...
        "transient", energy(transient), "gearbox", energy(gearbox), "afterfire", energy(afterfire), ...
        "identity", energy(identityBanks)));
end

function state = validateState(state)
if ~isstruct(state) || ~isscalar(state) || ...
        ~all(isfield(state, ["rpm", "load", "throttle", "acceleration"]))
    error("S12:EngineSoundV12:SourceState", "State must provide rpm/load/throttle/acceleration.");
end
state.rpm = boundedScalar(state.rpm, "rpm", 0, 12000);
state.load = boundedScalar(state.load, "load", 0, 1);
state.throttle = boundedScalar(state.throttle, "throttle", 0, 1);
state.acceleration = boundedScalar(state.acceleration, "acceleration", -20, 20);
state.shift_event = optionalScalar(state, "shift_event", -1, 1, 0);
state.shift_progress = optionalScalar(state, "shift_progress", 0, 1, 0);
if isfield(state, "afterfire_kind")
    if ~((ischar(state.afterfire_kind) && isrow(state.afterfire_kind)) || ...
            (isstring(state.afterfire_kind) && isscalar(state.afterfire_kind)))
        error("S12:EngineSoundV12:SourceState", "afterfire_kind must be one text enum value.");
    end
    state.afterfire_kind = string(state.afterfire_kind);
else
    state.afterfire_kind = "none";
end
if ~ismember(state.afterfire_kind, ["none", "upshift_bark", "downshift_blip_pop", "overrun_crackle"])
    error("S12:EngineSoundV12:SourceState", "afterfire_kind is unsupported.");
end
state.afterfire_progress = optionalScalar(state, "afterfire_progress", 0, 1, 0);
end

function context = normalizeContext(context)
if isempty(context)
    context = struct();
end
if ~isstruct(context) || ~isscalar(context)
    error("S12:EngineSoundV12:SourceContext", "context must be a scalar struct.");
end
context.cycle_phase_rad = optionalScalar(context, "cycle_phase_rad", -inf, inf, 0);
context.rotary_phase_rad = optionalScalar(context, "rotary_phase_rad", -inf, inf, 0);
context.frame_index = optionalScalar(context, "frame_index", 0, inf, 0);
context.acceleration_envelope = optionalScalar(context, "acceleration_envelope", 0, 1, 0);
context.acceleration_state = optionalScalar(context, "acceleration_state", -20, 20, 0);
context.shift_envelope = optionalScalar(context, "shift_envelope", 0, 1, 0);
context.afterfire_envelope = optionalScalar(context, "afterfire_envelope", 0, 1, 0);
context.shift_event_state = optionalScalar(context, "shift_event_state", -1, 1, 0);
context.afterfire_kind_state = optionalAfterfireKind(context, "afterfire_kind_state", "none");
context.dc_input = optionalRowVector(context, "dc_input", 2, [0, 0]);
context.dc_output = optionalRowVector(context, "dc_output", 2, [0, 0]);
if ~isfield(context, "identity")
    context.identity = struct();
end
if ~isstruct(context.identity) || ~isscalar(context.identity)
    error("S12:EngineSoundV12:SourceContext", "identity must be a scalar context struct.");
end
end

function validateDiscreteTransitions(context, state)
settledEnvelope = 1e-4;
if context.shift_event_state ~= state.shift_event && context.shift_envelope > settledEnvelope
    error("S12:EngineSoundV12:SourceState", ...
        "shift_event may change only after the preceding transient has settled.");
end
if context.afterfire_kind_state ~= state.afterfire_kind && context.afterfire_envelope > settledEnvelope
    error("S12:EngineSoundV12:SourceState", ...
        "afterfire_kind may change only after the preceding transient has settled.");
end
end

function value = optionalScalar(container, field, lower, upper, fallback)
if ~isfield(container, field)
    value = fallback;
else
    value = boundedScalar(container.(field), field, lower, upper);
end
end

function value = optionalRowVector(container, field, width, fallback)
if ~isfield(container, field)
    value = fallback;
    return
end
value = container.(field);
if ~isnumeric(value) || ~isequal(size(value), [1, width]) || any(~isfinite(value), "all")
    error("S12:EngineSoundV12:SourceContext", "%s must be one finite row vector.", field);
end
value = double(value);
end

function value = optionalAfterfireKind(container, field, fallback)
if ~isfield(container, field)
    value = fallback;
    return
end
value = container.(field);
if ~(ischar(value) && isrow(value)) && ~(isstring(value) && isscalar(value))
    error("S12:EngineSoundV12:SourceContext", "%s must be one text enum value.", field);
end
value = string(value);
if ~ismember(value, ["none", "upshift_bark", "downshift_blip_pop", "overrun_crackle"])
    error("S12:EngineSoundV12:SourceContext", "%s is unsupported.", field);
end
end

function [values, nextValue] = smoothControl(context, field, target, frameSamples)
if isfield(context, field)
    current = boundedScalar(context.(field), field, -inf, inf);
else
    current = target;
end
values = linspace(current, target, frameSamples).';
nextValue = target;
end

function value = boundedScalar(value, label, lower, upper)
if ~isnumeric(value) || ~isscalar(value) || ~isfinite(value) || value < lower || value > upper
    error("S12:EngineSoundV12:SourceState", "%s is outside the source state contract.", label);
end
value = double(value);
end

function validateFrameContract(sampleRateHz, frameSamples)
if ~isnumeric(sampleRateHz) || ~isscalar(sampleRateHz) || sampleRateHz ~= 48000 || ...
        ~isnumeric(frameSamples) || ~isscalar(frameSamples) || frameSamples ~= 960
    error("S12:EngineSoundV12:SourceFrame", ...
        "v1.2 source core requires a 48 kHz, 960-sample frame contract.");
end
end

function frame = renderPistonCombustion(source, cyclePhase, load)
frame = zeros(numel(cyclePhase), 2);
for index = 1:source.cylinders
    eventId = source.firing_order(index);
    eventPhase = 2 * pi * source.firing_phases_deg(eventId) / 720;
    pulse = exp(source.pulse_sharpness * (cos(cyclePhase - eventPhase) - 1));
    bankSkew = 1 + 0.10 * source.bank_map(eventId) * sin(cyclePhase - eventPhase / 2);
    frame = addBankPulse(frame, 2 * bankSkew .* pulse, source.bank_map(eventId));
end
frame = source.combustion_gain * (0.25 + 0.75 * load) .* (frame / source.cylinders);
end

function [frame, nextPhase] = renderRotaryCombustion(source, startPhase, rpm, load, sampleRateHz, frameSamples)
% Rotary scheduling is independent of the piston cylinders/2 firing law.
% The rotor loop below already contributes one phase-offset event stream per
% rotor. Multiplying this per-rotor order by rotor_count here would therefore
% double-count its total shaft-rate event frequency.
eventOrder = source.chambers_per_rotor / source.shaft_turns_per_rotor_turn;
increment = 2 * pi * (rpm / 60) * eventOrder / sampleRateHz;
phase = startPhase + [0; cumsum(increment(1:end - 1))];
frame = zeros(frameSamples, 2);
for index = 1:source.rotor_count
    eventId = source.firing_order(index);
    eventPhase = 2 * pi * source.firing_phases_deg(eventId) / 720;
    chamberPulse = exp(source.pulse_sharpness * (cos(phase - eventPhase) - 1));
    pulse = 1 + 0.10 * source.bank_map(eventId) * sin(phase);
    frame = addBankPulse(frame, 2 * pulse .* chamberPulse, source.bank_map(eventId));
end
apexTexture = sin(3 * phase + pi / 7);
frame = source.combustion_gain * (0.25 + 0.75 * load) .* ...
    (frame / source.rotor_count + 0.25 * source.pulse_sharpness * dualBankLayer(apexTexture));
nextPhase = mod(startPhase + sum(increment), 2 * pi);
end

function frame = renderOrderSurface(source, crankPhase, rpm, load)
frame = zeros(size(crankPhase));
for index = 1:numel(source.order_surface)
    entry = source.order_surface(index);
    lowLoadGain = interp1(entry.rpm_nodes, entry.low_load_gains, rpm, "linear", "extrap");
    highLoadGain = interp1(entry.rpm_nodes, entry.high_load_gains, rpm, "linear", "extrap");
    rpmGain = lowLoadGain .* (1 - load) + highLoadGain .* load;
    loadGain = mean(entry.low_load_gains) .* (1 - load) + ...
        mean(entry.high_load_gains) .* load;
    gain = max(0, min(1, 0.85 * loadGain + 0.15 * rpmGain));
    phase = interp1(entry.rpm_nodes, entry.phase_rad, rpm, "linear", "extrap");
    frame = frame + gain .* sin(entry.order * crankPhase + phase);
end
frame = frame / numel(source.order_surface);
end

function frame = renderIntakeLayer(source, crankPhase, throttle)
frame = source.intake_gain * sqrt(throttle) .* sin(3 * crankPhase + 0.2 * sin(crankPhase));
end

function frame = renderInductionLayer(source, crankPhase, rpm, load)
rpmTexture = min(1, rpm / 9000);
frame = source.induction_gain * load .* (0.85 + 0.15 * rpmTexture) .* ...
    sin(8 * crankPhase + pi / 9);
end

function frame = renderMechanicalLayer(source, crankPhase, rpm)
rpmTexture = sqrt(min(1, rpm / 12000));
frame = source.mechanical_gain * (0.90 + 0.10 * rpmTexture) .* ...
    (0.7 * sin(5 * crankPhase) + 0.3 * sin(11 * crankPhase + pi / 6));
end

function frame = renderFlowLayer(source, crankPhase, rpm, load)
highRpm = max(0, min(1, (rpm - 3500) / 6500));
frame = 0.25 * source.flow_gain * highRpm .* load .* ...
    (0.6 * sin(13 * crankPhase + pi / 5) + 0.4 * sin(17 * crankPhase));
end

function [frame, nextEnvelope] = renderAccelerationTransient( ...
        source, crankPhase, acceleration, previousAcceleration, currentEnvelope)
% Acceleration defines a state change, not a sustained source-level gain.
% A held acceleration must therefore decay after its onset; engine level remains
% controlled by the combustion/order/intake/induction/flow layers.
change = acceleration(end) - previousAcceleration;
attack = source.transient.acceleration_attack_gain * min(1, max(0, change) / 5);
lift = source.transient.lift_decay_gain * min(1, max(0, -change) / 5);
startEnvelope = min(1, currentEnvelope + attack + lift);
release = exp(-3.5 * (0:numel(crankPhase) - 1)' / numel(crankPhase));
envelope = startEnvelope * release;
frame = envelope .* sin(9 * crankPhase + pi / 3);
nextEnvelope = envelope(end);
end

function [frame, nextEnvelope] = renderGearboxTransient(source, crankPhase, shiftEvent, shiftProgress, currentEnvelope)
if shiftEvent == 0
    target = zeros(size(crankPhase));
    envelope = smoothEnvelope(currentEnvelope, target(end), numel(crankPhase));
    frame = envelope .* sin(14 * crankPhase + pi / 4);
    nextEnvelope = target(end);
    return
end
target = sin(pi * shiftProgress);
envelope = smoothEnvelope(currentEnvelope, target(end), numel(crankPhase));
torqueCut = -source.gearbox.torque_cut_gain * envelope .* sin(2 * crankPhase);
bark = source.gearbox.shift_bark_gain * envelope .* sign(shiftEvent) .* sin(14 * crankPhase + pi / 4);
frame = torqueCut + bark;
nextEnvelope = target(end);
end

function [frame, nextEnvelope] = renderAfterfire(source, crankPhase, kind, progress, currentEnvelope)
if kind == "none"
    target = zeros(size(crankPhase));
    envelope = smoothEnvelope(currentEnvelope, target(end), numel(crankPhase));
    frame = envelope .* sin(12 * crankPhase);
    nextEnvelope = target(end);
    return
end
switch kind
    case "upshift_bark"
        gain = source.afterfire.upshift_bark_gain;
        target = gain * (1 - progress) .^ 2 .* exp(-4 * progress);
        envelope = smoothEnvelope(currentEnvelope, target(end), numel(crankPhase));
        frame = envelope .* (0.80 * sin(2 * crankPhase) + ...
            0.20 * sin(12 * crankPhase + pi / 6));
    case "downshift_blip_pop"
        gain = source.afterfire.downshift_blip_pop_gain;
        target = gain * (1 - progress) .^ 2 .* exp(-6 * progress);
        envelope = smoothEnvelope(currentEnvelope, target(end), numel(crankPhase));
        frame = envelope .* (0.55 * sin(2 * crankPhase) + ...
            0.30 * sin(9 * crankPhase + pi / 4) + 0.15 * sin(18 * crankPhase));
    case "overrun_crackle"
        gain = source.afterfire.overrun_crackle_gain;
        target = gain * (1 - progress) .^ 2 .* exp(-9 * progress);
        envelope = smoothEnvelope(currentEnvelope, target(end), numel(crankPhase));
        frame = envelope .* (0.25 * sin(2 * crankPhase) + ...
            0.35 * sin(16 * crankPhase + pi / 8) + 0.25 * sin(23 * crankPhase) + ...
            0.15 * sin(31 * crankPhase + pi / 5));
    otherwise
        error("S12:EngineSoundV12:Afterfire", "Unsupported afterfire kind.");
end
nextEnvelope = target(end);
end

function envelope = smoothEnvelope(current, target, frameSamples)
% The state compiler feeds continuous target progress. This ramp also keeps
% a packet boundary from producing an instantaneous gain discontinuity.
envelope = linspace(current, target, frameSamples).';
end

function [frame, priorInput, priorOutput] = applyDcBlocker(raw, priorInput, priorOutput)
if size(raw, 2) ~= 2 || ~isequal(size(priorInput), [1, 2]) || ~isequal(size(priorOutput), [1, 2])
    error("S12:EngineSoundV12:SourceFrame", "DC blocker requires exactly two bank channels.");
end
frame = zeros(size(raw));
coefficient = 0.995;
for index = 1:size(raw, 1)
    frame(index, :) = raw(index, :) - priorInput + coefficient * priorOutput;
    priorInput = raw(index, :);
    priorOutput = frame(index, :);
end
end

function value = energy(frame)
value = sum(frame .^ 2, "all");
end

function banks = dualBankLayer(frame)
if ~iscolumn(frame)
    error("S12:EngineSoundV12:SourceFrame", "Shared source layers must begin as one column.");
end
banks = [frame, frame];
end

function frame = addBankPulse(frame, pulse, bank)
if bank == -1
    frame(:, 1) = frame(:, 1) + pulse;
elseif bank == 1
    frame(:, 2) = frame(:, 2) + pulse;
else
    frame = frame + dualBankLayer(pulse);
end
end
