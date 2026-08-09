function pressurePa = s12_radiation_input_signal(signal, timeS)
%S12_RADIATION_INPUT_SIGNAL Deterministic small-signal drive waveforms.
arguments
    signal (1,1) struct
    timeS {mustBeFinite}
end
if ~all(isfield(signal, ["id", "amplitude_pa"]))
    error("S12:Radiation:InvalidInput", "Input signal requires id and amplitude_pa.");
end
amplitude = reshape(double(signal.amplitude_pa), 1, []);
timeRow = reshape(double(timeS), 1, []);
switch string(signal.id)
    case "single_tone.v1"
        requireFields(signal, "frequency_hz");
        phase = fieldOr(signal, "phase_rad", 0);
        pressurePa = scalarAmplitude(amplitude) * sin(2 * pi * signal.frequency_hz * timeRow + phase);
    case "multisine.v1"
        requireFields(signal, "frequency_hz");
        frequencies = reshape(double(signal.frequency_hz), 1, []);
        phase = reshape(double(fieldOr(signal, "phase_rad", zeros(size(frequencies)))), 1, []);
        if ~isequal(size(amplitude), size(frequencies)) || ~isequal(size(phase), size(frequencies))
            error("S12:Radiation:InvalidInput", "Multisine amplitudes, frequencies, and phases must align.");
        end
        pressurePa = sum(amplitude(:) .* sin(2 * pi * frequencies(:) * timeRow + phase(:)), 1);
    case "chirp_linear.v1"
        requireFields(signal, ["start_frequency_hz", "end_frequency_hz", "duration_s"]);
        if signal.duration_s <= 0
            error("S12:Radiation:InvalidInput", "Chirp duration must be positive.");
        end
        phase = fieldOr(signal, "phase_rad", 0);
        slope = (signal.end_frequency_hz - signal.start_frequency_hz) / signal.duration_s;
        phaseValue = 2 * pi * (signal.start_frequency_hz * timeRow + 0.5 * slope * timeRow.^2) + phase;
        pressurePa = scalarAmplitude(amplitude) * sin(phaseValue);
    case "gaussian_pulse.v1"
        requireFields(signal, ["center_time_s", "sigma_time_s"]);
        if signal.sigma_time_s <= 0
            error("S12:Radiation:InvalidInput", "Pulse sigma must be positive.");
        end
        pressurePa = scalarAmplitude(amplitude) * exp(-0.5 * ((timeRow - signal.center_time_s) / signal.sigma_time_s).^2);
    otherwise
        error("S12:Radiation:UnsupportedInput", "Unsupported radiation input signal '%s'.", string(signal.id));
end
pressurePa = reshape(pressurePa, size(timeS));
end

function requireFields(value, fields)
if ~all(isfield(value, fields))
    error("S12:Radiation:InvalidInput", "Input signal is missing required fields.");
end
end

function value = fieldOr(input, name, defaultValue)
if isfield(input, name), value = input.(name); else, value = defaultValue; end
end

function value = scalarAmplitude(amplitude)
if numel(amplitude) ~= 1
    error("S12:Radiation:InvalidInput", "This waveform requires a scalar amplitude.");
end
value = amplitude;
end
