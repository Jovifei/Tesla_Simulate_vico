function [frame, report] = mb_path_step(packet, mode)
% The network receives combustion only. DC is common after the two paths join.
persistent gate network modal dcInput dcOutput history
report=[];
if ischar(packet) || isstring(packet)
    switch string(packet)
        case "reset"
            gate=[];network=[];modal=[];dcInput=0;dcOutput=0;history=zeros(0,9);frame=[];return
        case "report"
            frame=[];report=gate;if isempty(report),report=struct('frames',0,'duplicates',0);end
            report.network_context=network;report.modal_context=modal;
            report.dc_input=dcInput;report.dc_output=dcOutput;report.frame_states=history;return
        otherwise,error('Cabin:Command','Unknown path command.');
    end
end
mode=string(mode);
if ~ismember(mode,["N","M","D","MD"]) || ~isa(packet,'double') || ~isreal(packet) || ...
        ~isequal(size(packet),[960 9]) || any(~isfinite(packet),'all')
    error('Cabin:PathInput','Expected the 960x9 source frame and N/M/D/MD.');
end
if mb_runtime_probe('active')
    mb_runtime_probe('branch','path_probe');frame=[zeros(960,14),packet(:,9)];return
end
t=packet(1,9);
if any(abs(packet(:,9)-(t+(0:959)'/48000))>1e-10)
    error('Cabin:PathInput','Sample clock is inconsistent.');
end
if isempty(gate),network=[];modal=[];dcInput=0;dcOutput=0;history=zeros(0,9);end
[gate,duplicate,newRun]=mb_step_gate(gate,t,{packet,mode});
if newRun
    network=[];modal=[];dcInput=0;dcOutput=0;history=zeros(0,9);
end
if duplicate,frame=gate.last_output;return;end
combustion=packet(:,1:2);
if mode=="N" || mode=="M",average=mean(combustion,2);combustion=[average average];end
[pressure,network,networkTrace]=mb_bank_network_frame(combustion,network,struct());
other=.5*(packet(:,3)+packet(:,4));raw=pressure+other;
[blocked,~]=filter([1 -1],[1 -.995],raw,.995*dcOutput-dcInput);
dcInput=raw(end);dcOutput=blocked(end);
[event,mechanical,modal,modalTrace]=mb_event_modal_frame(packet(:,5),packet(:,6),packet(:,7),48000,modal,0:90:630);
frame=[blocked,mechanical,event,pressure,other,combustion,networkTrace.incoming,networkTrace.outgoing,raw,packet(:,9)];
if ~isequal(size(frame),[960 15]) || any(~isfinite(frame),'all')
    error('Cabin:PathFrame','Invalid branch frame.');
end
history(end+1,:)=[t gate.frames+1 network.position dcInput dcOutput modal.total_events modalTrace.event_count norm(modal.state,'fro')];
gate.last_time=t;gate.last_key={packet,mode};gate.last_output=frame;gate.frames=gate.frames+1;
end
