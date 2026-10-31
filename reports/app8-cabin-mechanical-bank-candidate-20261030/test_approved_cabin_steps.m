classdef test_approved_cabin_steps < matlab.unittest.TestCase
    methods (TestClassSetup)
        function paths(test)
            lab=fileparts(mfilename('fullpath')); root=fileparts(fileparts(lab));
            common=fullfile(root,'tools','sound_sim','s12','playground_v12','common');
            test.applyFixture(matlab.unittest.fixtures.PathFixture(lab));
            test.applyFixture(matlab.unittest.fixtures.PathFixture(common));
            test.applyFixture(matlab.unittest.fixtures.PathFixture(fullfile(common,'shared_model')));
        end
    end
    methods (TestMethodSetup)
        function reset(~)
            mb_runtime_probe('disarm');mb_source_step('reset');mb_path_step('reset');mb_receiver_step('reset');
        end
    end
    methods (Test)
        function initializationProbeIsBoundAndDoesNotHideRealZero(test)
            zero=zeros(9,1);first=[750;.12;.06;0;0;0;0;0;0];
            test.verifyTrue(mb_is_initial_probe(zero,first,'initializing',false));
            test.verifyFalse(mb_is_initial_probe(zero,zero,'initializing',false));
            test.verifyTrue(mb_is_initial_probe(zero,first,'running',false));
            test.verifyFalse(mb_is_initial_probe(zero,first,'initializing',true));
            mb_source_step(zero);[~,state]=mb_source_step('report');test.verifyEqual(state.frames,1);
        end
        function sourceCacheAndFrameClock(test)
            u=[2200;.35;.32;0;0;0;0;0;0];
            a=mb_source_step(u);b=mb_source_step(u);test.verifyEqual(a,b);
            [~,r]=mb_source_step('report');test.verifyEqual(r.frames,1);test.verifyEqual(r.duplicates,1);
            test.verifySize(a,[960 9]);test.verifyEqual(a(:,9),(0:959)'/48000,'AbsTol',1e-14);
            u(9)=.02;mb_source_step(u); changed=u;changed(2)=.36;
            test.verifyError(@()mb_source_step(changed),'Cabin:DuplicateInput');
            u(9)=.06;test.verifyError(@()mb_source_step(u),'Cabin:FrameOrder');
        end
        function sourceRestartsAtZero(test)
            u=[2200;.35;.32;0;0;0;0;0;0];
            mb_source_step(u);
            u(9)=.02;mb_source_step(u);
            restart=[2201;.35;.32;0;0;0;0;0;0];
            frame=mb_source_step(restart);
            test.verifySize(frame,[960 9]);
            [~,report]=mb_source_step('report');
            test.verifyEqual(report.frames,1);
        end
        function onlyCombustionGoesToNetwork(test)
            u=[2200;.35;.32;0;0;0;0;0;0];p=mb_source_step(u);
            n=mb_path_step(p,'N');mb_path_step('reset');
            m=mb_path_step(p,'M');test.verifyEqual(n,m);
            test.verifyEqual(n(:,6),mean(p(:,1:2),2),'AbsTol',0);
            test.verifyEqual(n(:,7),n(:,6),'AbsTol',0);
            mb_path_step('reset');d=mb_path_step(p,'D');
            test.verifyEqual(d(:,6:7),p(:,1:2));
            changed=p;changed(:,3:4)=changed(:,3:4)+2;
            mb_path_step('reset');other=mb_path_step(changed,'D');
            test.verifyEqual(other(:,4),d(:,4));
            test.verifyNotEqual(other(:,1),d(:,1));
        end
        function pathAndReceiverCacheRejectChangedNonzeroTime(test)
            u=[2200;.35;.32;0;0;0;0;0;0];p=mb_source_step(u);
            a0=mb_path_step(p,'MD');mb_receiver_step([a0(:,2),a0(:,15)],'MD',2);
            u(9)=.02;p=mb_source_step(u);
            a=mb_path_step(p,'MD');test.verifyEqual(mb_path_step(p,'MD'),a);
            changed=p;changed(1,1)=changed(1,1)+1;
            test.verifyError(@()mb_path_step(changed,'MD'),'Cabin:DuplicateInput');
            r=[a(:,2),a(:,15)];mb_receiver_step(r,'MD',2);
            test.verifyEqual(mb_receiver_step(r,'MD',2),2*a(:,2));
            test.verifyError(@()mb_receiver_step(r,'MD',3),'Cabin:DuplicateInput');
        end
        function mechanicalMonoPassesRepeatedFrames(test)
            mb_mechanical_mono_step('reset');
            u=reshape(1:960,960,1)/1000;
            test.verifyEqual(mb_mechanical_mono_step(u,'M',2),2*u);
            test.verifyEqual(mb_mechanical_mono_step(u,'M',2),2*u);
            test.verifyEqual(mb_mechanical_mono_step(u,'N',2),zeros(960,1));
            test.verifyEqual(mb_mechanical_mono_step(u,'MD',2),2*u);
        end
    end
end
