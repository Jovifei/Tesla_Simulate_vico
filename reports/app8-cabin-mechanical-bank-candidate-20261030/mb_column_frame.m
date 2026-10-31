function y = mb_column_frame(u)
% Normalize a 960-sample Frozen output at the isolated model boundary.
if ~isa(u,'double') || ~isreal(u) || numel(u) ~= 960 || any(~isfinite(u(:)))
    error('Cabin:ColumnFrame','Expected 960 finite real double samples.');
end
y = reshape(u,960,1);
end
