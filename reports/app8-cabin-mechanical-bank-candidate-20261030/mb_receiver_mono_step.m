function y=mb_receiver_mono_step(u,mode,k)
% Return the one-column mechanical bus used by the post-Frozen Sum.
if ~isa(u,'double') || ~isequal(size(u),[960 15]), error('Cabin:ReceiverMono','Expected 960x15 path frame.'); end
full=mb_receiver_step([u(:,2),u(:,15)],mode,k);
y=reshape(full,960,1);
end
