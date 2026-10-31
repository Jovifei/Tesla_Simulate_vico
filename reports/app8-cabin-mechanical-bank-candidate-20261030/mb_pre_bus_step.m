function y=mb_pre_bus_step(u)
if ~isequal(size(u),[960 2]),error('Cabin:PreBus','Expected 960x2 path bus.');end
y=u(:,1);
end
