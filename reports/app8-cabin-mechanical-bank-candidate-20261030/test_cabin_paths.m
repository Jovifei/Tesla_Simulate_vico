classdef test_cabin_paths < matlab.unittest.TestCase
    methods (Test)
        function pulseAreaAndZoh(test)
            lab = fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'private','mb_event_modal_frame.m')), ...
                'Event and modal implementation must exist.');
            fs = 48000; n = 80; rpm = 2200*ones(n,1); load = .35*ones(n,1);
            phase = (0:n-1)'*(pi*2200/(60*fs));
            [event,y,~,trace] = mb_event_modal_frame(phase,rpm,load,fs,[],0:90:630);
            test.verifyEqual(sum(event)/fs,.25+.75*.35,'AbsTol',1e-12);
            [expected,raw] = independentModal(event,fs);
            test.verifyEqual(trace.modal_before_dc,raw,'AbsTol',1e-13);
            test.verifyEqual(y,expected,'AbsTol',1e-13);
        end
        function fractionalPulseSurvivesFrameSplit(test)
            lab = fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'private','mb_event_modal_frame.m')), ...
                'Event and modal implementation must exist.');
            fs=48000;n=80;increment=pi*2200/(60*fs);rpm=2200*ones(n,1);load=.35*ones(n,1);
            phase=pi/4-.37*increment+(0:n-1)'*increment;
            [whole,yWhole]=mb_event_modal_frame(phase,rpm,load,fs,[],0:90:630);
            [a,ya,c]=mb_event_modal_frame(phase(1:10),rpm(1:10),load(1:10),fs,[],0:90:630);
            [b,yb]=mb_event_modal_frame(phase(11:end),rpm(11:end),load(11:end),fs,c,0:90:630);
            expectedFirst=(.25+.75*.35)*pulseIntegral(0,.63/fs,.0006)*fs;
            test.verifyEqual(whole(1),expectedFirst,'AbsTol',1e-9);
            test.verifyEqual([a;b],whole,'AbsTol',1e-11);
            test.verifyEqual([ya;yb],yWhole,'AbsTol',1e-13);
            test.verifyEqual(sum(whole)/fs,.25+.75*.35,'AbsTol',1e-12);
        end
        function wrapAndStoppedEngine(test)
            lab = fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'private','mb_event_modal_frame.m')), ...
                'Event and modal implementation must exist.');
            fs=48000;n=80;increment=pi*2200/(60*fs);rpm=2200*ones(n,1);load=.35*ones(n,1);
            phase=mod(2*pi-.2*increment+(0:n-1)'*increment,2*pi);
            [event,~,~,trace]=mb_event_modal_frame(phase,rpm,load,fs,[],0:90:630);
            [stopped,y]=mb_event_modal_frame(zeros(n,1),zeros(n,1),load,fs,[],0:90:630);
            test.verifyEqual(sum(event)/fs,.25+.75*.35,'AbsTol',1e-12);
            test.verifyEqual(trace.event_count,1);
            test.verifyEqual(stopped,zeros(n,1));
            test.verifyEqual(y,zeros(n,1));
        end
        function networkScatteringAndArrival(test)
            lab = fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'private','mb_bank_network_frame.m')), ...
                'Bank network implementation must exist.');
            x=zeros(300,2);x(1,1)=1;
            [y,~,trace]=mb_bank_network_frame(x,[],struct());
            inEnergy=sum(trace.incoming.^2.*[1 1 2],2);
            outEnergy=sum(trace.outgoing.^2.*[1 1 2],2);
            test.verifyEqual(inEnergy,outEnergy,'AbsTol',1e-13);
            test.verifyEqual(y(1:48),zeros(48,1));
            test.verifyEqual(y(49),.99/2,'AbsTol',1e-14);
            test.verifyEqual(y(145),-.3*.99^3/4,'AbsTol',1e-14);
            test.verifyTrue(all(isfinite(y)));
        end
        function networkSymmetryAndChunking(test)
            lab = fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'private','mb_bank_network_frame.m')), ...
                'Bank network implementation must exist.');
            n=200;t=(0:n-1)';x=[sin(t/13),cos(t/17)];
            options=struct('delays',[8 8],'losses',[1 1],'reflections',[0 0]);
            [y,~]=mb_bank_network_frame(x,[],options);
            [a,c]=mb_bank_network_frame(x(1:57,:),[],options);
            [b,~]=mb_bank_network_frame(x(58:end,:),c,options);
            test.verifyEqual(y,[zeros(8,1);mean(x(1:end-8,:),2)],'AbsTol',1e-14);
            test.verifyEqual([a;b],y,'AbsTol',1e-14);
        end
    end
end
function [y,raw]=independentModal(u,fs)
f=[160 370 820 1630];z=[.18 .14 .12 .10];x=zeros(2,4);raw=zeros(size(u));y=raw;prevX=0;prevY=0;
alpha=exp(-2*pi*15/fs);
for j=1:numel(u)
    for i=1:4
        w=2*pi*f(i);A=[0 1;-w^2 -2*z(i)*w];B=[0;.25];Ad=expm(A/fs);Bd=A\((Ad-eye(2))*B);
        x(:,i)=Ad*x(:,i)+Bd*u(j);
    end
    raw(j)=.25*sum(x(1,:));y(j)=alpha*(prevY+raw(j)-prevX);prevX=raw(j);prevY=y(j);
end
end
function v=pulseIntegral(a,b,T)
a=max(0,min(T,a));b=max(0,min(T,b));v=((b-a)-T/(2*pi)*(sin(2*pi*b/T)-sin(2*pi*a/T)))/T;
end
