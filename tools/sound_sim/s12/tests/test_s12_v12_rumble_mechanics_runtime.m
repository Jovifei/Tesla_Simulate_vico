classdef test_s12_v12_rumble_mechanics_runtime < matlab.unittest.TestCase
    properties
        Contract
    end
    methods(TestClassSetup)
        function paths(t)
            root=fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
            lab=fullfile(root,'reports','app8-rumble-mechanics-candidate-20261029');
            t.applyFixture(matlab.unittest.fixtures.PathFixture(lab));
            t.applyFixture(matlab.unittest.fixtures.PathFixture(fullfile(root,'tools','sound_sim','s12','playground_v12','common')));
            t.Contract=fullfile(lab,'EXPERIMENT_CONTRACT.json');
        end
    end
    methods(Test)
        function bypassIsExactAndRetainsState(t)
            x=sin((1:960)'*.123);state=struct('x',.7,'h',-.3,'z',.2);
            [y,out]=rumble_pressure_color_frame(x,state,48000,0);
            t.verifyEqual(y,x);t.verifyEqual(out,state);
        end
        function impulseMatchesAnalyticFilterAndFrameContinuity(t)
            x=zeros(960*5,1);x(1)=1;a=.9973854300793629;b=.9716127758430366;
            expected=x+filter((1-b)*(1+a)/2*[1,-1],conv([1,-a],[1,-b]),x);
            y=zeros(size(x));state=[];
            for k=1:5
                ix=(k-1)*960+(1:960);[y(ix),state]=rumble_pressure_color_frame(x(ix),state,48000,1);
            end
            t.verifyEqual(y,expected,'AbsTol',3e-14);t.verifyLessThan(max(abs(roots(conv([1,-a],[1,-b])))),1);
        end
        function dcSilenceAndSteadySines(t)
            for kind=0:3
                state=[];n=(0:960*160-1)';
                if kind==0,x=zeros(size(n));elseif kind==1,x=ones(size(n));else,x=sin(2*pi*(kind-1)*50*n/48000);end
                y=zeros(size(x));
                for k=1:160,ix=(k-1)*960+(1:960);[y(ix),state]=rumble_pressure_color_frame(x(ix),state,48000,1);end
                if kind<2,t.verifyEqual(y(end-959:end),x(end-959:end),'AbsTol',1e-12);continue;end
                f=(kind-1)*50;w=2*pi*f/48000;q=exp(-1i*w);a=.9973854300793629;b=.9716127758430366;
                H=1+(1-b)*(1+a)/2*(1-q)/((1-a*q)*(1-b*q));
                ix=n>=2*48000;v=exp(-1i*w*n(ix));measured=sum(y(ix).*v)/sum(x(ix).*v);
                t.verifyLessThan(abs(20*log10(abs(measured/H))),.01);
                t.verifyLessThan(abs(angle(measured/H)*180/pi),.1);
            end
        end
        function rejectsMalformedInputs(t)
            t.verifyError(@() rumble_pressure_color_frame(zeros(959,1),[],48000,1),'S12:Rumble:Filter');
            t.verifyError(@() rumble_pressure_color_frame(zeros(960,1),[],44100,1),'S12:Rumble:Filter');
            t.verifyError(@() rumble_pressure_color_frame(zeros(960,1),struct('x',NaN,'h',0,'z',0),48000,0),'S12:Rumble:Filter');
            t.verifyError(@() rumble_pressure_color_frame(repmat([realmax;-realmax],480,1),[],48000,1),'S12:Rumble:Filter');
        end
        function reportAfterResetHasNoEvaluations(t)
            s12_v12_model_rumble_mechanics_step([],t.Contract,'reset');
            [x,r]=s12_v12_model_rumble_mechanics_step([],t.Contract,'report');
            t.verifyEmpty(x);t.verifyEqual(r.frame_count,0);t.verifyEqual(r.evaluation_count,0);
        end
        function wrapperCachesDuplicateAndRewindsOnlyAtRunStart(t)
            s12_v12_model_rumble_mechanics_step([],t.Contract,'reset');
            packet=[2200;.35;.32;0;0;0;0;0;0];
            a=s12_v12_model_rumble_mechanics_step(packet,t.Contract,'SR');
            b=s12_v12_model_rumble_mechanics_step(packet,t.Contract,'SR');t.verifyEqual(a,b);
            packet(9)=.02;c=s12_v12_model_rumble_mechanics_step(packet,t.Contract,'SR');
            [~,r]=s12_v12_model_rumble_mechanics_step([],t.Contract,'report');
            t.verifyEqual(r.frame_count,2);t.verifyEqual(r.evaluation_count,3);t.verifyEqual(r.duplicate_count,1);
            t.verifyEqual(r.values(2,3),r.values(1,4),'AbsTol',1e-12);
            packet(5)=1;packet(6)=.5;packet(9)=.04;s12_v12_model_rumble_mechanics_step(packet,t.Contract,'SR');
            [~,r]=s12_v12_model_rumble_mechanics_step([],t.Contract,'report');t.verifyEqual(r.frame_count,3);
            packet(5:6)=0;packet(9)=0;d=s12_v12_model_rumble_mechanics_step(packet,t.Contract,'SR');t.verifyEqual(d,a);
            t.verifyNotEqual(c,a);
        end
    end
end
