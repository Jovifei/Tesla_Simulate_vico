classdef test_s12_v12_texture_candidate_matlab < matlab.unittest.TestCase
    % Validate the public runner before allocating or running a model.
    methods (TestClassSetup)
        function useProjectFunctions(testCase)
            root = fileparts(fileparts(mfilename('fullpath')));
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture( ...
                fullfile(root,'playground_v12','common')));
        end
    end
    methods (Test)
        function rejectsWrongFrameWidth(testCase)
            input = makeInput();
            input.texture_layers = zeros(2,959,3,'single');
            testCase.verifyError(@() s12_v12_run_texture_candidate( ...
                sourceModel(),input,tempname,false),'S12:EngineSoundV12:CandidateRun');
        end
        function rejectsNonfiniteSamples(testCase)
            input = makeInput();
            input.texture_layers(1,1,2) = NaN;
            testCase.verifyError(@() s12_v12_run_texture_candidate( ...
                sourceModel(),input,tempname,false),'S12:EngineSoundV12:CandidateRun');
        end
        function rejectsOutOfRangeLayerWeight(testCase)
            input = makeInput();
            input.texture_layer_weights(1,3) = 1.1;
            testCase.verifyError(@() s12_v12_run_texture_candidate( ...
                sourceModel(),input,tempname,false),'S12:EngineSoundV12:CandidateRun');
        end
        function rejectsFractionalFrameDuration(testCase)
            input = makeInput();
            input.duration_seconds = 0.05;
            testCase.verifyError(@() s12_v12_run_texture_candidate( ...
                sourceModel(),input,tempname,false),'S12:EngineSoundV12:CandidateRun');
        end
        function rejectsInconsistentFrameCount(testCase)
            input = makeInput();
            input.frame_count = 3;
            testCase.verifyError(@() s12_v12_run_texture_candidate( ...
                sourceModel(),input,tempname,false),'S12:EngineSoundV12:CandidateRun');
        end
        function rejectsHalfPresentLayerContract(testCase)
            input = rmfield(makeInput(),'texture_layer_weights');
            testCase.verifyError(@() s12_v12_run_texture_candidate( ...
                sourceModel(),input,tempname,false),'S12:EngineSoundV12:CandidateRun');
        end
        function validDryRunDoesNotCreateOutput(testCase)
            folder = string(tempname);
            result = s12_v12_run_texture_candidate(sourceModel(),makeInput(),folder,false);
            testCase.verifyEqual(result.status,"NOT_EXECUTED");
            testCase.verifyEqual(result.frame_count,2);
            testCase.verifyFalse(isfolder(folder));
        end
        function allZeroBypassPreservesNativeBytes(testCase)
            clear s12_v12_model_texture_layers_step
            base = -zeros(960,1,'single');
            mixed = s12_v12_model_texture_layers_step(base,base,base,base,[0,0,0]);
            testCase.verifyEqual(typecast(mixed(:),'uint32'),typecast(base(:),'uint32'));
        end
        function allZeroBypassAcceptsFinitePressureAbovePCMRange(testCase)
            base = 1.1 * ones(960,1);
            mixed = s12_v12_model_texture_layers_step(base,zeros(960,1),zeros(960,1),zeros(960,1),[0,0,0]);
            testCase.verifyEqual(mixed,base);
        end
        function nonzeroMixAcceptsFinitePressureAbovePCMRange(testCase)
            base = 1.1 * ones(960,1);
            clear s12_v12_model_texture_layers_step
            mixed = s12_v12_model_texture_layers_step(base,ones(960,1),ones(960,1),ones(960,1),[0.1,0.1,0.1]);
            testCase.verifyTrue(all(isfinite(mixed)));
            testCase.verifyGreaterThan(max(mixed),1);
        end
        function legacyZeroBypassAcceptsFinitePressureAbovePCMRange(testCase)
            base = 1.1 * ones(960,1);
            mixed = s12_v12_mix_texture_residual(base,zeros(960,1),0,[]);
            testCase.verifyEqual(mixed,base);
        end
        function legacyWeightedMixAcceptsFinitePressureAbovePCMRange(testCase)
            base = 1.1 * ones(960,1);
            mixed = s12_v12_mix_texture_residual(base,zeros(960,1),0.1,[]);
            testCase.verifyTrue(all(isfinite(mixed)));
            testCase.verifyGreaterThan(max(mixed),1);
        end
        function nonzeroThenZeroReturnsToPressureBypass(testCase)
            base = 1.1 * ones(960,1);
            clear s12_v12_model_texture_layers_step
            s12_v12_model_texture_layers_step(base,ones(960,1),ones(960,1),ones(960,1),[0.1,0.1,0.1]);
            mixed = s12_v12_model_texture_layers_step(base,ones(960,1),ones(960,1),ones(960,1),[0,0,0]);
            testCase.verifyEqual(mixed,base);
        end
        function pressureStillRejectsNonfiniteValues(testCase)
            base = NaN(960,1);
            testCase.verifyError(@() s12_v12_model_texture_layers_step( ...
                base,zeros(960,1),zeros(960,1),zeros(960,1),[0,0,0]), ...
                'S12:EngineSoundV12:ModelTextureLayers');
        end
    end
end

function value = makeInput()
value = struct('sample_rate_hz',48000,'frame_samples',960, ...
    'frame_rate_hz',50,'frame_count',2,'duration_seconds',0.04, ...
    'texture_residual',zeros(2,960,'single'),'texture_weight',zeros(2,1,'single'), ...
    'texture_layers',zeros(2,960,3,'single'),'texture_layer_weights',zeros(2,3,'single'));
end

function path = sourceModel()
root = fileparts(fileparts(mfilename('fullpath')));
path = fullfile(root,'playground_v12','vehicles','hellcat_2022_stock', ...
    'S12_hellcat_2022_stock_v12.slx');
end
