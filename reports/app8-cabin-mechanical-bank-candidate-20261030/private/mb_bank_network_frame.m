function [pressure, context, trace] = mb_bank_network_frame(input, context, options)
% Three-port scattering with independent two-way delay lines, no units implied.
if nargin<3 || isempty(options),options=struct();end
if ~isfield(options,'delays'),options.delays=[48 72];end
if ~isfield(options,'losses'),options.losses=[.99 .99];end
if ~isfield(options,'reflections'),options.reflections=[.3 .3];end
d=reshape(options.delays,1,[]);g=reshape(options.losses,1,[]);r=reshape(options.reflections,1,[]);
if ~isnumeric(input) || ~isreal(input) || size(input,2)~=2 || any(~isfinite(input),'all') || ...
        numel(d)~=2 || any(d<1 | d~=fix(d)) || numel(g)~=2 || any(g<0 | g>1) || ...
        numel(r)~=2 || any(abs(r)>1) || any(~isfinite([d g r]))
    error('Cabin:BankInput','Invalid bank input or passive network parameters.');
end
if isempty(context)
    context=struct('delays',d,'losses',g,'reflections',r,'forward',{{zeros(d(1),1),zeros(d(2),1)}}, ...
        'reverse',{{zeros(d(1),1),zeros(d(2),1)}},'position',[1 1]);
elseif ~isequal(context.delays,d) || ~isequal(context.losses,g) || ~isequal(context.reflections,r)
    error('Cabin:BankContext','Network parameters changed while state was active.');
end
n=size(input,1);pressure=zeros(n,1);incident=zeros(n,3);outgoing=zeros(n,3);
for k=1:n
    i=context.position(1);j=context.position(2);
    a=[g(1)*context.forward{1}(i),g(2)*context.forward{2}(j),0];
    p=(a(1)+a(2))/2;b=[p-a(1),p-a(2),p];
    context.forward{1}(i)=input(k,1)+r(1)*g(1)*context.reverse{1}(i);
    context.forward{2}(j)=input(k,2)+r(2)*g(2)*context.reverse{2}(j);
    context.reverse{1}(i)=b(1);context.reverse{2}(j)=b(2);
    context.position=[mod(i,d(1))+1,mod(j,d(2))+1];
    pressure(k)=p;incident(k,:)=a;outgoing(k,:)=b;
end
trace=struct('incoming',incident,'outgoing',outgoing);
end
