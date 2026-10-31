function y=mb_path_bus_step(u,mode)
% Explicit two-column bus for Simulink: pre-Frozen and modal input.
u=reshape(u,960,9);
if any(~isfinite(u),'all'),error('Cabin:PathBus','Expected finite source package.');end
p=mb_path_step(u,mode); y=p(:,[1 2]);
end
