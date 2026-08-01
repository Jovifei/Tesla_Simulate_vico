function prePtrExcitation = s12_v12_mix_bank_excitation(bankExcitation)
%S12_V12_MIX_BANK_EXCITATION Fixed source-routing adapter before frozen PTR.
% The adapter is intentionally outside the frozen PTR/Radiation mathematics.
% It converts independent left/right pre-PTR source banks to the existing
% one-port physical-network input without renderer/WAV post-processing.

frameSamples = 960;
if ~isnumeric(bankExcitation) || ~isequal(size(bankExcitation), [frameSamples, 2]) || ...
        any(~isfinite(bankExcitation), "all")
    error("S12:EngineSoundV12:BankMixer", ...
        "bankExcitation must be finite [frameSamples, 2].");
end
prePtrExcitation = 0.5 * (bankExcitation(:, 1) + bankExcitation(:, 2));
if ~isequal(size(prePtrExcitation), [frameSamples, 1]) || ...
        any(~isfinite(prePtrExcitation), "all")
    error("S12:EngineSoundV12:BankMixer", ...
        "prePtrExcitation must be finite [frameSamples, 1].");
end
end
