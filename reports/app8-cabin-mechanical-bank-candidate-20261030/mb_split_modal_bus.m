function y=mb_split_modal_bus(u)
u=reshape(u,960,2); if any(~isfinite(u),'all'),error('Cabin:SplitPath','Expected finite bus.');end
y=u(:,2);
end
