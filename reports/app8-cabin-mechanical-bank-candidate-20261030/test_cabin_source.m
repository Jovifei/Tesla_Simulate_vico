classdef test_cabin_source < matlab.unittest.TestCase
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
        function neutralPrivateSourceMatchesOriginal(test)
            lab=fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'private','mb_source_frame.m')),'Private source implementation must exist.');
            profile=sourceProfile(lab);state=statePacket();opt=options();
            [old,oldCtx,oldDiag]=s12_v12_render_source_frame(state,profile,[],48000,960,'hellcat_2022_stock',opt);
            [new,newCtx,newDiag]=mb_source_frame(state,profile,[],48000,960,'hellcat_2022_stock',opt,false);
            test.verifyEqual(new,old);
            test.verifyEqual(newCtx,oldCtx);
            test.verifyEqual(newDiag,oldDiag);
        end
        function identityMechanicalRemovedBeforeNormalization(test)
            lab=fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'private','mb_identity_frame.m')),'Private identity implementation must exist.');
            profile=s12_v12_validate_source_profile(sourceProfile(lab));
            identity=s12_v12_resolve_engine_identity_profile(profile,'hellcat_2022_stock');
            zeroMechanical=identity;zeroMechanical.mechanical_noise_profile.base_gain=0;
            phase=(0:959)'*.007;rpm=2200*ones(960,1);load=.35*ones(960,1);throttle=.32*ones(960,1);acc=zeros(960,1);
            [expected,~,~,expectedParts]=s12_v12_render_engine_identity_frame(zeroMechanical,phase,rpm,load,throttle,acc,[],48000,960);
            [actual,~,~,parts]=mb_identity_frame(identity,phase,rpm,load,throttle,acc,[],48000,960,true);
            test.verifyEqual(actual,expected);
            test.verifyEqual(parts,expectedParts);
            test.verifyEqual(parts.mechanical,zeros(960,2));
        end
        function isolatedSourceReconstructsAndCutIsApplied(test)
            lab=fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'private','mb_source_frame.m')),'Private source implementation must exist.');
            profile=sourceProfile(lab);state=statePacket();state.shift_event=1;state.shift_progress=.5;opt=options();
            [banks,~,~,parts]=mb_source_frame(state,profile,[],48000,960,'hellcat_2022_stock',opt,true);
            independentlyBlocked=filter([1 -1],[1 -.995],parts.combustion_raw+parts.other_raw);
            test.verifyEqual(banks,independentlyBlocked,'AbsTol',3e-13);
            test.verifyEqual(parts.combustion_raw,parts.combustion_uncut.*parts.cut,'AbsTol',1e-15);
            test.verifyEqual(parts.cut,.35*ones(960,1),'AbsTol',1e-15);
            test.verifyEqual(parts.source_mechanical,zeros(960,2));
            test.verifyEqual(parts.identity_mechanical,zeros(960,2));
        end
        function baselineMechanicalTapUsesActualOriginalComponents(test)
            lab=fileparts(mfilename('fullpath'));
            test.assertTrue(isfile(fullfile(lab,'private','mb_source_frame.m')),'Private source implementation must exist.');
            [~,~,~,parts]=mb_source_frame(statePacket(),sourceProfile(lab),[],48000,960,'hellcat_2022_stock',options(),false);
            test.verifyEqual(parts.old_mechanical_raw,parts.source_mechanical+parts.identity_mechanical);
            test.verifyGreaterThan(norm(parts.old_mechanical_raw,'fro'),0);
        end
    end
end
function p=sourceProfile(lab)
project=fileparts(fileparts(lab));p=jsondecode(fileread(fullfile(project,'tools','sound_sim','s12','playground_v12','vehicles','hellcat_2022_stock','source_profile.json')));
end
function s=statePacket()
s=struct('rpm',2200,'load',.35,'throttle',.32,'acceleration',0,'shift_event',0,'shift_progress',0,'afterfire_kind','none','afterfire_progress',0);
end
function o=options()
o=struct('enabled',true,'cut_minimum',.35,'whine_scale',1,'induction_scale',1,'voicing_rpm_band',[2000 3500],'mechanical_gain',1,'mechanical_mod_depth',0);
end
