function [frame,report] = mb_receiver_step(packet,mode,k)
% Produce the separate mechanical input to the visible post-Frozen Sum.
persistent gate
report=[];
if ischar(packet) || isstring(packet)
    switch string(packet)
        case "reset",gate=[];frame=[];return
        case "report",frame=[];report=gate;if isempty(report),report=struct('frames',0,'duplicates',0);end;return
        otherwise,error('Cabin:Command','Unknown receiver command.');
    end
end
mode=string(mode);
if ~ismember(mode,["N","M","D","MD"]) || ~isa(packet,'double') || ~isreal(packet) || ...
        ~isequal(size(packet),[960 2]) || any(~isfinite(packet),'all') || ...
        ~isscalar(k) || ~isfinite(k) || k<=0
    error('Cabin:ReceiverInput','Expected finite modal/time frame, mode and frozen positive k.');
end
if mb_runtime_probe('active')
    mb_runtime_probe('branch','receiver_probe');frame=zeros(960,1);return
end
t=packet(1,2);
if any(abs(packet(:,2)-(t+(0:959)'/48000))>1e-10),error('Cabin:ReceiverInput','Sample clock differs.');end
[gate,duplicate]=mb_step_gate(gate,t,{packet,mode,k});
if duplicate,frame=gate.last_output;return;end
if mode=="M" || mode=="MD",frame=k*packet(:,1);else,frame=zeros(960,1);end
gate.last_time=t;gate.last_key={packet,mode,k};gate.last_output=frame;gate.frames=gate.frames+1;
end
