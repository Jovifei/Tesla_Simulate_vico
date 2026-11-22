function pressure = app8_synthetic_cylinder_frame(control)
% Fixed dimensionless four-stroke test excitation, not an OEM calibration.
persistent angles banks
if ~isa(control,'double') || ~isreal(control) || ~isequal(size(control),[960 4]) || ...
        any(~isfinite(control),'all') || any(control(:,2)<0 | control(:,2)>12000) || ...
        any(control(:,3)<0 | control(:,3)>1)
    error('App8Diagnostic:Input','Expected finite phase, RPM, load and clock frames.');
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
        error('App8Diagnostic:Profile','Invalid synthetic firing map.');
    end
    angles = 2*pi*phases(order)/720;
    banks = mapping(order);
end
time = control(1,4);
expectedTime = time+(0:959)'/48000;
increment = pi*control(:,2)/(60*48000);
phaseError = diff(control(:,1))-increment(1:end-1);
if any(abs(control(:,4)-expectedTime)>1e-10) || ...
        any(abs(atan2(sin(phaseError),cos(phaseError)))>1e-9)
    error('App8Diagnostic:Clock','Phase or clock is inconsistent with the 48 kHz packet.');
end
pulses = max(0,cos(control(:,1)-angles)).^16;
% This is the exact DC component of a half-wave cosine raised to the 16th power.
pulseMean = nchoosek(16,8)/2^17;
left = sum(pulses(:,banks==-1)-pulseMean,2);
right = sum(pulses(:,banks==1)-pulseMean,2);
pressure = (.25+.75*control(:,3)).*(.55*left+.45*right);
end
