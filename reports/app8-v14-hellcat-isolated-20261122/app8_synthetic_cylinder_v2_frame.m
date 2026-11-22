function pressure = app8_synthetic_cylinder_v2_frame(control)
% Dimensionless causal fixed cylinder pulses, not an OEM calibration.
persistent angles banks
if ~isa(control,'double') || ~isreal(control) || ~isequal(size(control),[960 4]) || ...
        any(~isfinite(control),'all') || any(control(:,2)<0 | control(:,2)>12000) || ...
        any(control(:,3)<0 | control(:,3)>1)
    error('App8DiagnosticV2:Input','Expected finite phase, RPM, load and clock frames.');
end
if isempty(angles)
    root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
    profilePath = fullfile(root,'tools','sound_sim','s12','playground_v12', ...
        'vehicles','hellcat_2022_stock','source_profile.json');
    profile = jsondecode(fileread(profilePath));
    order = double(profile.source.firing_order.value(:).');
    phases = double(profile.source.firing_phases_deg.value(:).');
    mapping = double(profile.source.bank_map.value(:).');
    if ~isequal(sort(order),1:8) || numel(phases)~=8 || ...
            any(~isfinite(phases) | phases<0 | phases>=720) || numel(unique(phases))~=8 || ...
            numel(mapping)~=8 || any(~ismember(mapping,[-1 1]))
        error('App8DiagnosticV2:Profile','Invalid synthetic firing map.');
    end
    angles = 2*pi*phases(order)/720;
    banks = mapping(order);
end
time = control(1,4);
increment = pi*control(:,2)/(60*48000);
phaseError = diff(control(:,1))-increment(1:end-1);
if any(abs(control(:,4)-(time+(0:959)'/48000))>1e-10) || ...
        any(abs(atan2(sin(phaseError),cos(phaseError)))>1e-9)
    error('App8DiagnosticV2:Clock','Phase or clock differs from the 48 kHz packet.');
end
elapsed = mod(control(:,1)-angles,2*pi)/(pi/4);
pulses = zeros(size(elapsed));
rising = elapsed<.125;
falling = elapsed>=.125 & elapsed<.5;
pulses(rising) = .5*(1-cos(pi*elapsed(rising)/.125));
pulses(falling) = .5*(1+cos(pi*(elapsed(falling)-.125)/.375));
left = sum(pulses(:,banks==-1)-.03125,2);
right = sum(pulses(:,banks==1)-.03125,2);
pressure = .25*(.25+.75*control(:,3)).*(.55*left+.45*right);
end
