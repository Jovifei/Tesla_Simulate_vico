function y=mb_split_control(u)
if ~isequal(size(u),[960 9]) || any(~isfinite(u),'all'),error('Cabin:SplitSource','bad frame');end
y=u(:,5:9);
end
