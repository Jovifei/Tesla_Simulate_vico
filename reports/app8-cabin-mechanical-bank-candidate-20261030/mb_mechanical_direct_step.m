function y=mb_mechanical_direct_step(u,mode,k)
u=reshape(u,960,2);
if mode=="M" || mode=="MD", y=k*u(:,2); else, y=zeros(960,1); end
end
