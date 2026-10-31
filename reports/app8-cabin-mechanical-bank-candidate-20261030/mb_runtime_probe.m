function value = mb_runtime_probe(command,varargin)
% Bind the real first packet; never infer an invalidation from time alone.
persistent mode firstPacket model active events
if isempty(mode),mode="disarmed";firstPacket=[];model="";active=false;events=struct('kind',{},'status',{});end
command=string(command);value=[];
switch command
    case "arm"
        firstPacket=varargin{1};model=string(varargin{2});
        if ~isa(firstPacket,'double') || ~isequal(size(firstPacket),[9 1]) || any(~isfinite(firstPacket)) || firstPacket(9)~=0
            error('Cabin:FirstInput','Expected the exact finite native first packet at t=0.');
        end
        mode="armed";active=false;events=struct('kind',{},'status',{});
    case "build"
        model=string(varargin{1});mode="build";firstPacket=[];active=false;events=struct('kind',{},'status',{});
    case "disarm"
        mode="disarmed";active=false;
    case "source"
        packet=varargin{1};alreadyAdvanced=varargin{2};status="unavailable";
        if strlength(string(model))>0 && bdIsLoaded(model),status=string(get_param(model,'SimulationStatus'));end
        if mode=="build"
            value=true;
        elseif mode=="armed"
            value=mb_is_initial_probe(packet,firstPacket,status,alreadyAdvanced);
            if ~value && ~alreadyAdvanced && ~isequal(packet,firstPacket)
                error('Cabin:FirstInput','Initial signal differs from bound input; status %s.',status);
            end
        else,value=false;end
        active=value;
        if value,events(end+1)=struct('kind','source_probe','status',char(status));end
    case "active"
        value=active;
    case "branch"
        if active,events(end+1)=struct('kind',char(varargin{1}),'status','probe_passthrough');end
    case "report"
        value=struct('mode',mode,'model',model,'first_packet',firstPacket,'events',events);
    otherwise,error('Cabin:ProbeCommand','Unknown probe command.');
end
end
