function y=mb_split_modal(u)
if ~isequal(size(u),[960 15]) || any(~isfinite(u),'all'),error('Cabin:SplitPath','bad frame');end
y=u(:,2);
end
