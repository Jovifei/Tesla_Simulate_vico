function [banks, context, diagnostics] = s12_v12_render_engine_identity_frame( ...
        identity, crankPhase, rpm, load, throttle, acceleration, context, sampleRateHz, frameSamples)
%S12_V12_RENDER_ENGINE_IDENTITY_FRAME Render a synthetic pre-PTR engine identity.
% This renderer owns engine-specific pulse timing, induction mechanics, and
% transient texture. It does not access the PTR, radiation boundary, audio
% renderer, PCM path, or any measured/OEM data.

validateFrameContract(sampleRateHz, frameSamples);
validateIdentity(identity);
crankPhase = columnSignal(crankPhase, "crankPhase", frameSamples, -inf, inf);
rpm = columnSignal(rpm, "rpm", frameSamples, 0, 12000);
load = columnSignal(load, "load", frameSamples, 0, 1);
throttle = columnSignal(throttle, "throttle", frameSamples, 0, 1);
acceleration = columnSignal(acceleration, "acceleration", frameSamples, -20, 20);
context = normalizeContext(context);

rpmRatio = min(1, max(0, rpm / identity.rpm_limit));
loadGain = 0.25 + 0.75 * load;
bankSkew = identity.firing_character.bank_asymmetry * ...
    sin(identity.order_profile.primary_order * crankPhase + pi / 9);

switch identity.engine_type
    case "supercharged_cross_plane_v8"
        [banks, layers, context] = renderHellcat( ...
            identity, crankPhase, rpmRatio, load, throttle, loadGain, bankSkew, context);
    case "naturally_aspirated_flat_plane_v8"
        [banks, layers, context] = renderFerrari( ...
            identity, crankPhase, rpmRatio, loadGain, bankSkew, acceleration, context);
    case "twin_rotor_turbo"
        [banks, layers, context] = renderRx7( ...
            identity, crankPhase, rpmRatio, load, throttle, loadGain, bankSkew, ...
            acceleration, context, sampleRateHz);
    case {"twin_turbo_v6", "twin_turbo_inline6"}
        [banks, layers, context] = renderInlineTurbo( ...
            identity, crankPhase, rpmRatio, load, throttle, loadGain, ...
            bankSkew, context);
    case "naturally_aspirated_v10"
        [banks, layers, context] = renderV10( ...
            identity, crankPhase, rpmRatio, loadGain, bankSkew, throttle, context);
    otherwise
        error("S12:EngineIdentity:Render", "Engine identity type is unsupported.");
end

% RPM changes pulse spacing and spectral balance, not steady source loudness.
% Keep a load/throttle-dependent identity RMS while retaining each layer's
% relative spectral and temporal structure.
[banks, layers] = normalizeIdentityLevel(banks, layers, load, throttle);

if ~isequal(size(banks), [frameSamples, 2]) || any(~isfinite(banks), "all")
    error("S12:EngineIdentity:Render", ...
        "Engine identity must render one finite [frameSamples,2] frame.");
end
context.previous_acceleration = acceleration(end);
context.frame_index = context.frame_index + 1;
diagnostics = struct( ...
    "architecture", "engine_identity_pre_ptr_v014", ...
    "profile_id", identity.profile_id, ...
    "engine_type", identity.engine_type, ...
    "provenance", identity.provenance, ...
    "high_frequency_energy", energy(layers.high_frequency), ...
    "supercharger_whine_energy", energy(layers.supercharger_whine), ...
    "v8_exhaust_energy", energy(layers.v8_exhaust), ...
    "piston_exhaust_energy", energy(layers.piston_exhaust), ...
    "rotary_event_count", layers.rotary_event_count, ...
    "rotary_gate_variance", layers.rotary_gate_variance, ...
    "turbo_spool", context.turbo_spool, ...
    "turbine_energy", energy(layers.turbine));
end

function [banks, layers, context] = renderHellcat( ...
        identity, phase, rpmRatio, load, throttle, loadGain, bankSkew, context)
pulseExponent = 1 + 5 * (1 - identity.firing_character.pulse_width);
crossPlanePulse = max(0, sin(identity.order_profile.primary_order * phase)) .^ pulseExponent;
crossPlanePulse = crossPlanePulse + 0.55 * max(0, ...
    sin(identity.order_profile.primary_order * phase + pi / 2)) .^ (pulseExponent + 1);
v8Exhaust = loadGain .* (identity.acoustic_color_profile.low_band_gain * ...
    (0.72 * crossPlanePulse + 0.28 * sin(identity.order_profile.secondary_order * phase)) + ...
    identity.harmonic_profile.base_gain * sin(identity.order_profile.high_order * phase + pi / 7));
whineEnvelope = identity.turbo_or_supercharger_profile.whine_gain * ...
    sqrt(max(0, load .* throttle));
whineOrder = identity.turbo_or_supercharger_profile.drive_ratio * ...
    identity.harmonic_profile.high_frequency_order;
superchargerWhine = whineEnvelope .* (sin(whineOrder * phase) + ...
    0.32 * sin(2 * whineOrder * phase + pi / 5));
mechanical = identity.mechanical_noise_profile.base_gain * (0.55 + 0.45 * rpmRatio) .* ...
    (sin(identity.mechanical_noise_profile.mechanical_order * phase) + ...
    identity.mechanical_noise_profile.roughness * sin(7 * phase + pi / 8));
banks = toBanks(v8Exhaust + superchargerWhine + mechanical, bankSkew);
layers = emptyLayers();
layers.high_frequency = superchargerWhine;
layers.supercharger_whine = superchargerWhine;
layers.v8_exhaust = v8Exhaust;
end

function [banks, layers, context] = renderFerrari( ...
        identity, phase, rpmRatio, loadGain, bankSkew, acceleration, context)
pulseExponent = 2 + 10 * (1 - identity.firing_character.pulse_width);
flatPlanePulse = max(0, sin(identity.order_profile.primary_order * phase)) .^ pulseExponent;
flatPlanePulse = flatPlanePulse - 0.36 * max(0, ...
    sin(identity.order_profile.primary_order * phase + pi / 2)) .^ pulseExponent;
harmonicEnvelope = 4.0 * identity.acoustic_color_profile.high_band_gain * loadGain .* ...
    (identity.harmonic_profile.base_gain + identity.harmonic_profile.high_rpm_gain * ...
    rpmRatio .^ identity.harmonic_profile.rpm_exponent);
highFrequency = harmonicEnvelope .* (sin(identity.harmonic_profile.high_frequency_order * phase) + ...
    0.42 * sin(2 * identity.harmonic_profile.high_frequency_order * phase + pi / 6));
exhaust = identity.acoustic_color_profile.mid_band_gain * loadGain .* ...
    (0.70 * flatPlanePulse + 0.30 * sin(identity.order_profile.secondary_order * phase));
mechanical = identity.mechanical_noise_profile.base_gain * (0.4 + 0.6 * rpmRatio) .* ...
    sin(identity.mechanical_noise_profile.mechanical_order * phase + pi / 5);
[transient, context.ferrari_attack] = onsetTransient( ...
    identity.transient_profile, phase, acceleration, context.previous_acceleration, context.ferrari_attack);
banks = toBanks(exhaust + highFrequency + mechanical + transient, bankSkew);
layers = emptyLayers();
layers.high_frequency = highFrequency;
layers.v8_exhaust = exhaust;
end

function [banks, layers, context] = renderRx7( ...
        identity, phase, rpmRatio, load, throttle, loadGain, bankSkew, acceleration, context, sampleRateHz)
% Rotary chamber scheduling uses a continuous chamber phase, not a piston order.
chamberPhase = identity.order_profile.secondary_order * phase + pi / 6;
gateExponent = 1 + 4 * (1 - identity.firing_character.pulse_width);
rotaryGate = max(0, cos(chamberPhase)) .^ gateExponent;
rotaryGate = 0.68 * rotaryGate + 0.32 * max(0, cos(chamberPhase + 2 * pi / 3)) .^ gateExponent;
rotaryExcitation = 1.8 * identity.acoustic_color_profile.mid_band_gain * loadGain .* ...
    (0.82 * rotaryGate + 0.18 * sin(identity.order_profile.primary_order * phase));
roughness = identity.mechanical_noise_profile.base_gain * (0.3 + 0.7 * rpmRatio) .* ...
    (sin(identity.mechanical_noise_profile.mechanical_order * phase + pi / 4) + ...
    identity.mechanical_noise_profile.roughness * sin(identity.order_profile.high_order * phase));
targetSpool = min(1, max(0, 0.10 + load .* throttle .* (0.35 + 0.65 * rpmRatio)));
spool = linspace(context.turbo_spool, targetSpool(end), numel(phase)).';
turboHz = 120 + 1800 * spool + 240 * rpmRatio;
turboPhase = context.turbo_phase_rad + [0; cumsum(2 * pi * turboHz(1:end - 1) / sampleRateHz)];
turbine = identity.turbo_or_supercharger_profile.turbine_gain * spool .* ...
    (sin(turboPhase) + 0.35 * sin(2 * turboPhase + pi / 7));
[transient, context.rx7_attack] = onsetTransient( ...
    identity.transient_profile, phase, acceleration, context.previous_acceleration, context.rx7_attack);
banks = toBanks(rotaryExcitation + roughness + turbine + transient, bankSkew);
context.turbo_spool = spool(end);
context.turbo_phase_rad = mod(turboPhase(end) + 2 * pi * turboHz(end) / sampleRateHz, 2 * pi);
layers = emptyLayers();
layers.high_frequency = turbine;
layers.turbine = turbine;
layers.rotary_event_count = sum(diff(rotaryGate > 0.35) > 0);
layers.rotary_gate_variance = var(rotaryGate);
end

function [banks, layers, context] = renderInlineTurbo( ...
        identity, phase, rpmRatio, load, throttle, loadGain, bankSkew, context)
primary = identity.order_profile.primary_order;
secondary = identity.order_profile.secondary_order;
pulseExponent = 2 + 8 * (1 - identity.firing_character.pulse_width);
eventPulse = max(0, sin(primary * phase)) .^ pulseExponent;
exhaust = identity.acoustic_color_profile.low_band_gain * loadGain .* ...
    (0.72 * eventPulse + 0.28 * sin(secondary * phase));
if identity.engine_type == "twin_turbo_v6"
    lowBody = 0.95 * identity.acoustic_color_profile.low_band_gain * loadGain .* ...
        sin(0.75 * primary * phase + pi / 12);
    edgeScale = 0.50;
    racyScale = 0.80;
else
    lowBody = 12.0 * identity.acoustic_color_profile.low_band_gain * loadGain .* ...
        sin(0.68 * primary * phase + pi / 14);
    edgeScale = 0.03;
    racyScale = 0.03;
end
midEdge = edgeScale * identity.acoustic_color_profile.mid_band_gain * loadGain .* ...
    (0.55 * sin(primary * phase) + 0.30 * sin(secondary * phase + pi / 8));
targetSpool = min(1, max(0, 0.08 + load .* throttle .* (0.25 + 0.75 * rpmRatio)));
spool = linspace(context.turbo_spool, targetSpool(end), numel(phase)).';
turboOrder = identity.turbo_or_supercharger_profile.drive_ratio * ...
    identity.harmonic_profile.high_frequency_order;
turboPhase = context.turbo_phase_rad + turboOrder * phase;
whistle = identity.turbo_or_supercharger_profile.whine_gain * spool .* ...
    (sin(turboPhase) + 0.28 * sin(2 * turboPhase + pi / 7));
turbine = identity.turbo_or_supercharger_profile.turbine_gain * spool .* ...
    (sin(0.65 * turboPhase + pi / 5) + 0.20 * sin(1.3 * turboPhase));
mechanical = identity.mechanical_noise_profile.base_gain * (0.45 + 0.55 * rpmRatio) .* ...
    (sin(identity.mechanical_noise_profile.mechanical_order * phase) + ...
    identity.mechanical_noise_profile.roughness * sin(7 * phase + pi / 9));
if identity.engine_type == "twin_turbo_v6"
    racy = racyScale * 0.55 * sin(4 * phase + pi / 11);
else
    racy = racyScale * 0.28 * sin(5 * phase + pi / 13);
end
mono = lowBody + exhaust + midEdge + racy + whistle + turbine + mechanical;
banks = toBanks(mono, bankSkew);
context.turbo_spool = spool(end);
context.turbo_phase_rad = mod(turboPhase(end), 2 * pi);
layers = emptyLayers();
layers.high_frequency = whistle + turbine;
layers.turbine = turbine;
layers.piston_exhaust = lowBody + exhaust + midEdge + racy;
end

function [banks, layers, context] = renderV10( ...
        identity, phase, rpmRatio, loadGain, bankSkew, throttle, context)
primary = identity.order_profile.primary_order;
secondary = identity.order_profile.secondary_order;
highOrder = identity.order_profile.high_order;
body = identity.acoustic_color_profile.mid_band_gain * loadGain .* ...
    (0.80 * sin(primary * phase) + 0.06 * sin(secondary * phase) + ...
    0.01 * sin(highOrder * phase + pi / 10));
scream = identity.acoustic_color_profile.high_band_gain * ...
    (0.35 + 0.65 * rpmRatio) .* ...
    (sin(identity.harmonic_profile.high_frequency_order * phase) + ...
    0.30 * sin(0.5 * identity.harmonic_profile.high_frequency_order * phase + pi / 8));
intake = 0.35 * identity.acoustic_color_profile.mid_band_gain * sqrt(max(throttle, 0)) .* ...
    sin(3 * primary * phase + pi / 6);
mechanical = identity.mechanical_noise_profile.base_gain * (0.40 + 0.60 * rpmRatio) .* ...
    (sin(identity.mechanical_noise_profile.mechanical_order * phase) + ...
    identity.mechanical_noise_profile.roughness * sin(17 * phase + pi / 5));
mono = body + scream + intake + mechanical;
banks = toBanks(mono, bankSkew);
layers = emptyLayers();
layers.high_frequency = scream;
layers.piston_exhaust = body + intake;
end

function [frame, nextEnvelope] = onsetTransient(profile, phase, acceleration, previous, current)
change = acceleration(end) - previous;
attack = profile.attack_gain * min(1, max(0, change) / 5) * profile.load_coupling;
startEnvelope = min(1, current + attack);
envelope = startEnvelope * exp(-profile.release_per_frame * (0:numel(phase) - 1)' / numel(phase));
frame = envelope .* sin(12 * phase + pi / 3);
nextEnvelope = envelope(end);
end

function banks = toBanks(mono, bankSkew)
banks = [mono .* (1 + bankSkew), mono .* (1 - bankSkew)];
end

function layers = emptyLayers()
layers = struct( ...
    "high_frequency", 0, "supercharger_whine", 0, "v8_exhaust", 0, ...
    "piston_exhaust", 0, "turbine", 0, "rotary_event_count", 0, ...
    "rotary_gate_variance", 0);
end

function [banks, layers] = normalizeIdentityLevel(banks, layers, load, throttle)
currentRms = sqrt(mean(banks(:) .^ 2));
if currentRms <= eps
    error("S12:EngineIdentity:Render", "Identity frame has no normalizable energy.");
end
targetRms = 0.14 + 0.25 * sqrt(mean(load .* throttle));
scale = targetRms / currentRms;
banks = scale * banks;
layers.high_frequency = scale * layers.high_frequency;
layers.supercharger_whine = scale * layers.supercharger_whine;
layers.v8_exhaust = scale * layers.v8_exhaust;
layers.piston_exhaust = scale * layers.piston_exhaust;
layers.turbine = scale * layers.turbine;
end

function context = normalizeContext(context)
if isempty(context)
    context = struct();
end
if ~isstruct(context) || ~isscalar(context)
    error("S12:EngineIdentity:Render", "Identity context must be a scalar struct.");
end
context.turbo_spool = optionalScalar(context, "turbo_spool", 0, 1, 0);
context.turbo_phase_rad = optionalScalar(context, "turbo_phase_rad", -inf, inf, 0);
context.previous_acceleration = optionalScalar(context, "previous_acceleration", -20, 20, 0);
context.ferrari_attack = optionalScalar(context, "ferrari_attack", 0, 1, 0);
context.rx7_attack = optionalScalar(context, "rx7_attack", 0, 1, 0);
context.frame_index = optionalScalar(context, "frame_index", 0, inf, 0);
end

function value = optionalScalar(container, field, lower, upper, fallback)
if ~isfield(container, field)
    value = fallback;
    return
end
value = container.(field);
if ~isnumeric(value) || ~isscalar(value) || ~isfinite(value) || value < lower || value > upper
    error("S12:EngineIdentity:Render", "%s is outside the identity context contract.", field);
end
value = double(value);
end

function values = columnSignal(values, label, count, lower, upper)
if ~isnumeric(values) || ~isequal(size(values), [count, 1]) || ...
        any(~isfinite(values), "all") || any(values < lower) || any(values > upper)
    error("S12:EngineIdentity:Render", "%s is outside the identity frame contract.", label);
end
values = double(values);
end

function validateFrameContract(sampleRateHz, frameSamples)
if ~isnumeric(sampleRateHz) || ~isscalar(sampleRateHz) || sampleRateHz ~= 48000 || ...
        ~isnumeric(frameSamples) || ~isscalar(frameSamples) || frameSamples ~= 960
    error("S12:EngineIdentity:Render", ...
        "v0.14 identity requires a 48 kHz, 960-sample frame contract.");
end
end

function validateIdentity(identity)
required = ["profile_id", "engine_type", "rpm_limit", "firing_character", ...
    "order_profile", "harmonic_profile", "transient_profile", ...
    "mechanical_noise_profile", "turbo_or_supercharger_profile", ...
    "acoustic_color_profile", "provenance"];
if ~isstruct(identity) || ~isscalar(identity) || ~all(isfield(identity, required)) || ...
        string(identity.provenance) ~= "C/synthetic/uncalibrated"
    error("S12:EngineIdentity:Render", "Identity must be a validated synthetic v0.4 profile.");
end
end

function value = energy(frame)
value = mean(frame(:) .^ 2);
end
