function [y,report]=mb_mechanical_mono_step(u,mode,k)
persistent evaluations
report=[];
if ischar(u) || isstring(u)
    switch string(u)
        case "reset",evaluations=0;y=[];return
        case "report",y=[];report=struct('evaluations',evaluations);return
    end
end
u=reshape(u,960,1);
if isempty(evaluations),evaluations=0;end
if mb_runtime_probe('active')
    mb_runtime_probe('branch','receiver_probe'); y=zeros(960,1); return
end
if mode=="M" || mode=="MD", y=k*u; else, y=zeros(960,1); end
evaluations=evaluations+1;
end
