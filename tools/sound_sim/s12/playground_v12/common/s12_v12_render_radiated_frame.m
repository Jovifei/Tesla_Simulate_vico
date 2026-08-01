function [pressure, context, diagnostics] = s12_v12_render_radiated_frame( ...
        vehicleState, profile, context, sampleRate, frameSamples)
%S12_V12_RENDER_RADIATED_FRAME Render one causal source-to-radiation frame.

arguments
    vehicleState (1, 1) struct
    profile (1, 1) struct
    context = []
    sampleRate (1, 1) double {mustBeFinite, mustBePositive} = 48000
    frameSamples (1, 1) double {mustBeInteger, mustBePositive} = 960
end

if isempty(context)
    sourceContext = [];
    radiationContext = [];
else
    if ~isstruct(context) || ~isscalar(context) || ...
            ~all(isfield(context, ["source", "radiation"]))
        error("S12:EngineSoundV12:RadiatedFrame", ...
            "Radiated-frame context is invalid.");
    end
    sourceContext = context.source;
    radiationContext = context.radiation;
end

[prePtr, sourceContext, sourceDiagnostics] = ...
    s12_v12_render_pre_ptr_frame(vehicleState, profile, sourceContext, ...
        sampleRate, frameSamples);
[pressure, radiationContext, radiationDiagnostics] = ...
    s12_v12_apply_frozen_radiation_frame(prePtr, radiationContext, sampleRate);

context = struct( ...
    "source", sourceContext, ...
    "radiation", radiationContext);
diagnostics = struct( ...
    "topology", "source_to_bank_mixer_to_frozen_radiation_adapter", ...
    "full_fvm_ptr_network", false, ...
    "source", sourceDiagnostics, ...
    "radiation", radiationDiagnostics);
end
