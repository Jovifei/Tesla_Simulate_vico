function y=mb_mechanical_bus_step(u,mode,k)
u=reshape(u,960,2); if any(~isfinite(u),'all'),error('Cabin:MechanicalBus','Expected finite path bus.');end
if mode=="M" || mode=="MD",y=mb_receiver_step([u(:,2),zeros(960,1)],mode,k); else,y=zeros(960,1); end
y=reshape(y,960,1);
end
