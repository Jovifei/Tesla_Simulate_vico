function [y,state]=rumble_pressure_color_frame(x,state,sampleRate,k)
% Bounded, persistent pre-Frozen research branch. Pressure is not PCM.
if ~isa(x,'double') || ~isreal(x) || ~isequal(size(x),[960,1]) || any(~isfinite(x)) || ...
        ~isequal(sampleRate,48000) || ~isscalar(k) || ~isreal(k) || ~isfinite(k) || ~ismember(k,[0,1])
    error('S12:Rumble:Filter','Expected finite double 960x1, 48kHz and k=0 or 1.');
end
if isempty(state),state=struct('x',0,'h',0,'z',0);end
if ~isstruct(state) || ~isscalar(state) || ~all(isfield(state,{'x','h','z'})) || ...
        ~all(cellfun(@(v) isa(v,'double') && isreal(v) && isscalar(v) && isfinite(v),{state.x,state.h,state.z}))
    error('S12:Rumble:Filter','Invalid persistent filter state.');
end
if k==0,y=x;return;end
a=.9973854300793629;b=.9716127758430366;c=(1+a)/2;
y=zeros(size(x));xp=state.x;h=state.h;z=state.z;
for j=1:960
    h=c*(x(j)-xp)+a*h;z=(1-b)*h+b*z;y(j)=x(j)+k*z;xp=x(j);
end
if any(~isfinite(y)) || any(~isfinite([xp,h,z]))
    error('S12:Rumble:Filter','Computed pressure or persistent state became nonfinite.');
end
state=struct('x',xp,'h',h,'z',z);
end
