% Edit this file, then press Run in MATLAB for a fresh listening preview.

profileName = "c63_w204";
overrides = struct();

% Common tuning examples:
% overrides.induction_gain = 0.16;
% overrides.resonance_gain = [0.34, 0.54, 0.46, 0.31, 0.16];
% overrides.backfire_overrun_s = 1.25;
% overrides.shift_reengage_gain = 1.12;
% overrides.texture_noise_gain = 0.008;

tune_classic_sound(profileName, overrides, true);
