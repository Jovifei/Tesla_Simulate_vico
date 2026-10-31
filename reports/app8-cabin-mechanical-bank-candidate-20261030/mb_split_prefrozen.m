function y=mb_split_prefrozen(u)
if ~isequal(size(u),[960 15]) || any(~isfinite(u),'all'),error('Cabin:SplitPath','bad frame');end
y=u(:,1);
end
