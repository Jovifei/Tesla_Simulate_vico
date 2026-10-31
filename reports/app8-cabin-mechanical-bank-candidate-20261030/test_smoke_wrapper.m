classdef test_smoke_wrapper < matlab.unittest.TestCase
    methods (TestClassSetup)
        function setupPaths(test)
            lab=fileparts(mfilename('fullpath'));project=fileparts(fileparts(lab));
            common=fullfile(project,'tools','sound_sim','s12','playground_v12','common');
            test.applyFixture(matlab.unittest.fixtures.PathFixture(lab));
            test.applyFixture(matlab.unittest.fixtures.PathFixture(common));
            test.applyFixture(matlab.unittest.fixtures.PathFixture(fullfile(common,'shared_model')));
        end
    end
    methods (Test)
        function frameHasFiniteOutputAndCachesRepeatedPacket(test)
            lab=fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'mb_smoke_step.m')),'Smoke wrapper must exist.');
            mb_smoke_step([],'reset'); p=packet(0); first=mb_smoke_step(p);second=mb_smoke_step(p);
            [~,report]=mb_smoke_step([],'report');
            test.verifySize(first,[960 1]);test.verifyTrue(all(isfinite(first)));test.verifyTrue(any(first~=0));
            test.verifyEqual(second,first);test.verifyEqual(report.frame_count,1);test.verifyEqual(report.duplicate_count,1);
        end
        function changedDuplicateIsRejected(test)
            lab=fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'mb_smoke_step.m')),'Smoke wrapper must exist.');
            mb_smoke_step([],'reset');p=packet(0);mb_smoke_step(p);p(2)=.36;
            test.verifyError(@() mb_smoke_step(p),'Cabin:SmokeDuplicate');
        end
        function droppedFrameIsRejected(test)
            lab=fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'mb_smoke_step.m')),'Smoke wrapper must exist.');
            mb_smoke_step([],'reset');mb_smoke_step(packet(0));
            test.verifyError(@() mb_smoke_step(packet(.04)),'Cabin:SmokeOrder');
        end
        function resetIsDeterministic(test)
            lab=fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'mb_smoke_step.m')),'Smoke wrapper must exist.');
            mb_smoke_step([],'reset');a=mb_smoke_step(packet(0));mb_smoke_step(packet(.02));
            mb_smoke_step([],'reset');b=mb_smoke_step(packet(0));
            test.verifyEqual(a,b);
        end
    end
end
function p=packet(t)
p=[2200;.35;.32;0;0;0;0;0;t];
end
