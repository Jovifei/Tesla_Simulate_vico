function [preFrozen,mechanical] = mb_split_path(pathFrame)
if ~isa(pathFrame,'double') || ~isequal(size(pathFrame),[960 15]) || any(~isfinite(pathFrame),'all')
    error('Cabin:SplitPath','Expected finite 960x15 path frame.');
end
preFrozen=pathFrame(:,1); mechanical=pathFrame(:,2);
end
