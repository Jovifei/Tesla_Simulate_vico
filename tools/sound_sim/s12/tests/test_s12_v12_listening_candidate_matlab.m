classdef test_s12_v12_listening_candidate_matlab < matlab.unittest.TestCase
    properties (Access=private)
        ContractPath
    end
    methods (TestClassSetup)
        function paths(testCase)
            s12=fileparts(fileparts(mfilename('fullpath')));
            project=fileparts(fileparts(fileparts(s12)));
            lab=fullfile(project,'reports','app8-listening-candidate-20261029');
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture(lab));
            testCase.ContractPath=fullfile(lab,'LISTENING_CONTRACT.json');
        end
    end
    methods (Test)
        function expectedDriveEventsAndFrameGrid(testCase)
            drive=compile_listening_drive(testCase.ContractPath);
            testCase.verifySize(drive.state,[4500,9]);
            testCase.verifyEqual(drive.time,(0:4499)'*.02,'AbsTol',1e-12);
            testCase.verifyEqual(numel(drive.events),4);
            testCase.verifyEqual([drive.events.kind],[1,1,1,-1]);
            testCase.verifyEqual([drive.events.duration_s],[.24,.24,.24,.30],'AbsTol',1e-12);
        end
        function lockedRpmAgreesWithSpeedAndGear(testCase)
            drive=compile_listening_drive(testCase.ContractPath);
            cfg=jsondecode(fileread(testCase.ContractPath));
            ratio=reshape(cfg.gear_ratios(drive.gear),[],1);
            expected=drive.speed_mps*60/(2*pi*cfg.wheel_radius_m).*ratio*cfg.final_drive;
            testCase.verifyEqual(drive.state(~drive.slip,1),expected(~drive.slip),'AbsTol',1e-9);
            testCase.verifyGreaterThanOrEqual(drive.state(:,1),cfg.idle_rpm);
            testCase.verifyTrue(all(isfinite(drive.state),'all'));
        end
        function accelerationIsVelocityDerivative(testCase)
            drive=compile_listening_drive(testCase.ContractPath);
            cfg=jsondecode(fileread(testCase.ContractPath));
            nearKnot=any(abs(drive.time-cfg.speed_knots_s(:)')<.041,2);
            difference=gradient(drive.speed_mps,.02);
            valid=~nearKnot;
            testCase.verifyEqual(drive.acceleration_mps2(valid),difference(valid),'AbsTol',1e-3);
            testCase.verifyLessThan(max(abs(diff(drive.speed_mps))),.2);
        end
        function shiftFlagsCompleteAndClear(testCase)
            drive=compile_listening_drive(testCase.ContractPath);
            active=drive.state(:,5)~=0;
            testCase.verifyEqual(nnz(active),51);
            testCase.verifyEqual(nnz(diff([0;double(active)])==1),4);
            testCase.verifyEqual(nnz(diff([double(active);0])==-1),4);
            testCase.verifyEqual(drive.state(end,5),0);
            testCase.verifyEqual(drive.state(end,6),0);
        end
        function overlappingEventsFailClosed(testCase)
            cfg=jsondecode(fileread(testCase.ContractPath));
            cfg.events(2).start_s=cfg.events(1).start_s;
            folder=testCase.applyFixture(matlab.unittest.fixtures.TemporaryFolderFixture());
            file=fullfile(folder.Folder,'bad.json');
            fid=fopen(file,'w');fprintf(fid,'%s',jsonencode(cfg));fclose(fid);
            testCase.verifyError(@() compile_listening_drive(file),'S12:Listening:Drive');
        end
    end
end
