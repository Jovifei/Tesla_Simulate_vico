function [combustion,other,control] = mb_split_source(packet)
% Explicitly split the packaged source frame for Simulink shape inference.
if ~isa(packet,'double') || ~isequal(size(packet),[960 9]) || any(~isfinite(packet),'all')
    error('Cabin:SplitInput','Expected finite 960x9 source frame.');
end
combustion=packet(:,1:2); other=packet(:,3:4); control=packet(:,5:9);
end
