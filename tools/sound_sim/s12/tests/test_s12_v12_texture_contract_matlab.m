classdef test_s12_v12_texture_contract_matlab < matlab.unittest.TestCase
    % Real MATLAB behavior contract for research-only external texture inputs.

    properties (Access = private)
        FixtureFolder
        LegacyPath
        LayerPaths
    end

    properties (Constant, Access = private)
        InputError = "S12:EngineSoundV12:TextureInput"
        LegacySha = "6684bb20b6a90ef26f8471ee74051a18b1601ca5a7eba19bc36b04a9f2b73106"
        LayerShas = [ ...
            "8ec3bce71cfc06be3b09fa7af2f4b92e7b3623a7c23ba781dc66385f362c374b", ...
            "c747239d6873afbdd07bc13b245390eb333c169ed9f800ff0ae9802ae4dba595", ...
            "87ef14babe4503ea56ea5146bfc3e13b679d52df3201edb1cb2297582bf70929"]
    end

    properties (TestParameter)
        invalidDuration = struct( ...
            "zero", 0, "negative", -0.02, "subFrame", 0.001, ...
            "fractionalFrame", 0.03, "nan", NaN, "infinite", Inf, ...
            "complex", 0.04 + 1i, "notScalar", [0.02, 0.04])
        invalidTextureWeight = struct( ...
            "negative", -0.01, "aboveOne", 1.01, "nan", NaN, ...
            "infinite", Inf, "complex", 0.2 + 1i, "notScalar", [0.1, 0.2])
        invalidLayerWeights = struct( ...
            "negative", [-0.01, 0.2, 0.3], ...
            "aboveOne", [0.1, 1.01, 0.3], ...
            "nan", [0.1, NaN, 0.3], "infinite", [0.1, Inf, 0.3], ...
            "complex", [0.1, 0.2, 0.3 + 1i], ...
            "column", [0.1; 0.2; 0.3], "short", [0.1, 0.2], ...
            "matrix", ones(2, 3), "text", "0.1 0.2 0.3")
        invalidPathIndices = struct( ...
            "column", [1; 2; 3], "short", [1, 2], "matrix", [1, 2; 2, 3])
        invalidSchedule = struct( ...
            "notStruct", 17, ...
            "missingAcceleration", struct("time_s", [0; 0.02; 0.04; 0.06], "load", zeros(4, 1)), ...
            "duplicateTime", struct("time_s", [0; 0.02; 0.02; 0.06], "load", zeros(4, 1), "acceleration", zeros(4, 1)), ...
            "shiftedTime", struct("time_s", [0.02; 0.04; 0.06; 0.08], "load", zeros(4, 1), "acceleration", zeros(4, 1)), ...
            "offGridTime", struct("time_s", [0; 0.021; 0.04; 0.06], "load", zeros(4, 1), "acceleration", zeros(4, 1)), ...
            "missingFrame", struct("time_s", [0; 0.02; 0.06], "load", zeros(3, 1), "acceleration", zeros(3, 1)), ...
            "nanTime", struct("time_s", [0; NaN; 0.04; 0.06], "load", zeros(4, 1), "acceleration", zeros(4, 1)), ...
            "matrixTime", struct("time_s", [0, 0.04; 0.02, 0.06], "load", zeros(4, 1), "acceleration", zeros(4, 1)), ...
            "nanLoad", struct("time_s", [0; 0.02; 0.04; 0.06], "load", [0; NaN; 0; 0], "acceleration", zeros(4, 1)), ...
            "complexLoad", struct("time_s", [0; 0.02; 0.04; 0.06], "load", [0; 1i; 0; 0], "acceleration", zeros(4, 1)), ...
            "textLoad", struct("time_s", [0; 0.02; 0.04; 0.06], "load", "bad", "acceleration", zeros(4, 1)), ...
            "negativeLoad", struct("time_s", [0; 0.02; 0.04; 0.06], "load", [0; -0.01; 0; 0], "acceleration", zeros(4, 1)), ...
            "aboveOneLoad", struct("time_s", [0; 0.02; 0.04; 0.06], "load", [0; 1.01; 0; 0], "acceleration", zeros(4, 1)), ...
            "matrixLoad", struct("time_s", [0; 0.02; 0.04; 0.06], "load", zeros(2, 2), "acceleration", zeros(4, 1)), ...
            "infiniteAcceleration", struct("time_s", [0; 0.02; 0.04; 0.06], "load", zeros(4, 1), "acceleration", [0; Inf; 0; 0]), ...
            "nanAcceleration", struct("time_s", [0; 0.02; 0.04; 0.06], "load", zeros(4, 1), "acceleration", [0; NaN; 0; 0]), ...
            "complexAcceleration", struct("time_s", [0; 0.02; 0.04; 0.06], "load", zeros(4, 1), "acceleration", [0; 1i; 0; 0]), ...
            "matrixAcceleration", struct("time_s", [0; 0.02; 0.04; 0.06], "load", zeros(4, 1), "acceleration", zeros(2, 2)))
        badSample = struct("nan", NaN, "infinite", Inf, "aboveOne", 1.01, "belowMinusOne", -1.01)
        shortSampleCount = struct("empty", 0, "exactFadeLimit", 11520)
        layerIndex = struct("body", 1, "mechanical", 2, "broadband", 3)
    end

    methods (TestClassSetup)
        function addPublicHelperPath(testCase)
            root = fileparts(fileparts(mfilename("fullpath")));
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture( ...
                fullfile(root, "playground_v12", "common")));
        end
    end

    methods (TestMethodSetup)
        function createDeterministicF32Sources(testCase)
            folder = testCase.applyFixture(matlab.unittest.fixtures.TemporaryFolderFixture());
            testCase.FixtureFolder = string(folder.Folder);
            testCase.LegacyPath = testCase.writeSamples("legacy.f32le", repmat(single(0.0625), 14400, 1));
            testCase.LayerPaths = [ ...
                testCase.writeSamples("body.f32le", repmat(single(0.125), 14400, 1)), ...
                testCase.writeSamples("mechanical.f32le", repmat(single(-0.25), 14400, 1)), ...
                testCase.writeSamples("broadband.f32le", repmat(single(0.375), 14400, 1))];
        end
    end

    methods (Test)
        function defaultTwoArgumentCallProducesMutedBodyOnlyInput(testCase)
            actual = s12_v12_prepare_texture_external_input(testCase.LegacyPath, 0.04);

            testCase.verifyEqual(actual.frame_count, 2);
            testCase.verifyEqual(actual.duration_seconds, 0.04, "AbsTol", eps);
            testCase.verifyEqual(actual.texture_residual, repmat(single(0.0625), 2, 960), "AbsTol", 0);
            testCase.verifyEqual(actual.texture_layers(:, :, 1), actual.texture_residual, "AbsTol", 0);
            testCase.verifyEqual(actual.texture_layers(:, :, 2:3), zeros(2, 960, 2, "single"), "AbsTol", 0);
            testCase.verifyEqual(actual.texture_weight, zeros(2, 1, "single"), "AbsTol", 0);
            testCase.verifyEqual(actual.texture_layer_weights, zeros(2, 3, "single"), "AbsTol", 0);
            testCase.verifyEqual(string(actual.source_sha256), testCase.LegacySha);
            testCase.verifyEqual(string(actual.layer_source_sha256), [testCase.LegacySha, "", ""]);
            testCase.verifyEqual(actual.state_qualification, "INSUFFICIENT_EVIDENCE");
            testCase.verifyEqual(actual.rpm_load_gear_phase, "UNKNOWN");
            testCase.verifyEqual(actual.purpose, "RESEARCH_ONLY_NOT_PRODUCT_AUDIO");
        end

        function legacyFiveArgumentCallPreservesBodyWeight(testCase)
            actual = s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0.4, struct(), strings(1, 0));

            testCase.verifyEqual(actual.texture_weight, repmat(single(0.4), 2, 1), "AbsTol", 0);
            testCase.verifyEqual(actual.texture_layer_weights, ...
                repmat(single([0.4, 0, 0]), 2, 1), "AbsTol", 0);
        end

        function suppliedLayerPathsAreAllConsumedWithoutChangingLegacySource(testCase)
            actual = s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0.4, struct(), testCase.LayerPaths);

            testCase.verifyEqual(actual.texture_layers(:, :, 1), repmat(single(0.125), 2, 960), "AbsTol", 0);
            testCase.verifyEqual(actual.texture_layers(:, :, 2), repmat(single(-0.25), 2, 960), "AbsTol", 0);
            testCase.verifyEqual(actual.texture_layers(:, :, 3), repmat(single(0.375), 2, 960), "AbsTol", 0);
            testCase.verifyEqual(string(actual.layer_source_sha256), testCase.LayerShas);
            testCase.verifyEqual(actual.texture_residual, repmat(single(0.0625), 2, 960), "AbsTol", 0);
            testCase.verifyEqual(string(actual.source_sha256), testCase.LegacySha);
            testCase.verifyEqual(actual.texture_layer_weights, ...
                repmat(single([0.4, 0, 0]), 2, 1), "AbsTol", 0);
        end

        function explicitLayerWeightsEnableIndependentLayers(testCase)
            actual = s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), testCase.LayerPaths, [0.2, 0.3, 0.4]);

            testCase.verifyEqual(actual.texture_layer_weights, ...
                repmat(single([0.2, 0.3, 0.4]), 2, 1), "AbsTol", 0);
            testCase.verifyEqual(actual.texture_weight, zeros(2, 1, "single"), "AbsTol", 0);
            testCase.verifyEqual(string(actual.layer_source_sha256), testCase.LayerShas);
        end

        function layerWeightsAcceptZeroAndOneBoundaries(testCase)
            actual = s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.02, 1, struct(), testCase.LayerPaths, [0, 1, 1]);

            testCase.verifyEqual(actual.texture_weight, single(1), "AbsTol", 0);
            testCase.verifyEqual(actual.texture_layer_weights, single([0, 1, 1]), "AbsTol", 0);
        end

        function emptyBodyPathFallsBackToLegacySource(testCase)
            actual = s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), ["", testCase.LayerPaths(2:3)], [0.2, 0.3, 0.4]);

            testCase.verifyEqual(actual.texture_layers(:, :, 1), actual.texture_residual, "AbsTol", 0);
            testCase.verifyEqual(string(actual.layer_source_sha256), [testCase.LegacySha, testCase.LayerShas(2:3)]);
        end

        function rejectsNonzeroWeightForMissingMechanicalLayer(testCase)
            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), strings(1, 0), [0.2, 0.3, 0]), testCase.InputError);
        end

        function rejectsNonzeroWeightForMissingBroadbandLayer(testCase)
            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), strings(1, 0), [0.2, 0, 0.3]), testCase.InputError);
        end

        function completeStateScheduleControlsEveryExplicitLayer(testCase)
            schedule = struct("time_s", [0; 0.02; 0.04; 0.06], ...
                "load", [0; 1; 1; 0], "acceleration", [0; 3; 0; -3]);
            expectedEnvelope = [0.25; 0.4375; 0.553125; 0.50234375];

            actual = s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.08, 0.4, schedule, testCase.LayerPaths, [0.2, 0.3, 0.4]);

            testCase.verifyEqual(actual.texture_weight, single(0.4 * expectedEnvelope), "AbsTol", single(1e-7));
            testCase.verifyEqual(actual.texture_layer_weights, ...
                single(expectedEnvelope * [0.2, 0.3, 0.4]), "AbsTol", single(1e-7));
        end

        function rowVectorStateScheduleIsAccepted(testCase)
            schedule = struct("time_s", [0, 0.02], "load", [0, 0], "acceleration", [0, 0]);
            actual = s12_v12_prepare_texture_external_input(testCase.LegacyPath, 0.04, 0.4, schedule);

            testCase.verifyEqual(actual.texture_weight, repmat(single(0.1), 2, 1), "AbsTol", single(1e-7));
        end

        function decimalDurationKeepsExactFrameCount(testCase)
            actual = s12_v12_prepare_texture_external_input(testCase.LegacyPath, 0.58);

            testCase.verifyEqual(actual.frame_count, 29);
            testCase.verifySize(actual.texture_residual, [29, 960]);
            testCase.verifyEqual(actual.duration_seconds, 0.58, "AbsTol", eps);
        end

        function rejectsInvalidDuration(testCase, invalidDuration)
            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, invalidDuration), testCase.InputError);
        end

        function rejectsInvalidLegacyWeight(testCase, invalidTextureWeight)
            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, invalidTextureWeight), testCase.InputError);
        end

        function rejectsInvalidLayerWeights(testCase, invalidLayerWeights)
            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), testCase.LayerPaths, invalidLayerWeights), testCase.InputError);
        end

        function rejectsMalformedLayerPathShape(testCase, invalidPathIndices)
            paths = reshape(testCase.LayerPaths(invalidPathIndices), size(invalidPathIndices));
            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0.2, struct(), paths), testCase.InputError);
        end

        function rejectsCellLayerPaths(testCase)
            paths = cellstr(testCase.LayerPaths);
            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0.2, struct(), paths), testCase.InputError);
        end

        function rejectsNonscalarLegacyPath(testCase)
            paths = [testCase.LegacyPath, testCase.LegacyPath];
            testCase.verifyError(@() s12_v12_prepare_texture_external_input(paths, 0.04), testCase.InputError);
        end

        function rejectsMalformedStateSchedule(testCase, invalidSchedule)
            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.08, 0.2, invalidSchedule), testCase.InputError);
        end

        function rejectsMissingLayerFileEvenWithZeroWeight(testCase, layerIndex)
            paths = testCase.LayerPaths;
            paths(layerIndex) = fullfile(testCase.FixtureFolder, "missing.f32le");
            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), paths), testCase.InputError);
        end

        function rejectsInvalidLegacySourceSamples(testCase, badSample)
            samples = repmat(single(0.125), 14400, 1);
            samples(17) = single(badSample);
            path = testCase.writeSamples("invalid-legacy.f32le", samples);

            testCase.verifyError(@() s12_v12_prepare_texture_external_input(path, 0.04), testCase.InputError);
        end

        function rejectsInvalidLayerSamplesEvenWithZeroWeight(testCase, badSample, layerIndex)
            samples = repmat(single(0.125), 14400, 1);
            samples(17) = single(badSample);
            paths = testCase.LayerPaths;
            paths(layerIndex) = testCase.writeSamples("invalid-layer.f32le", samples);

            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), paths), testCase.InputError);
        end

        function rejectsShortLegacySource(testCase, shortSampleCount)
            path = testCase.writeSamples("short-legacy.f32le", zeros(shortSampleCount, 1, "single"));

            testCase.verifyError(@() s12_v12_prepare_texture_external_input(path, 0.04), testCase.InputError);
        end

        function rejectsShortLayerSource(testCase, shortSampleCount, layerIndex)
            paths = testCase.LayerPaths;
            paths(layerIndex) = testCase.writeSamples("short-layer.f32le", zeros(shortSampleCount, 1, "single"));

            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), paths), testCase.InputError);
        end

        function rejectsPartialFloatBytesInLegacySource(testCase)
            path = testCase.writeBytes("partial-legacy.f32le", uint8([1, 2, 3]));

            testCase.verifyError(@() s12_v12_prepare_texture_external_input(path, 0.04), testCase.InputError);
        end

        function rejectsPartialFloatBytesInLayerSource(testCase, layerIndex)
            paths = testCase.LayerPaths;
            paths(layerIndex) = testCase.writeBytes("partial-layer.f32le", uint8([1, 2, 3]));

            testCase.verifyError(@() s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), paths), testCase.InputError);
        end

        function sourceJustLongerThanFadeMinimumIsAccepted(testCase)
            path = testCase.writeSamples("minimum-valid.f32le", repmat(single(0.125), 11521, 1));
            actual = s12_v12_prepare_texture_external_input(path, 0.04);

            testCase.verifyEqual(actual.texture_residual, repmat(single(0.125), 2, 960), "AbsTol", 0);
        end

        function preservesExistingWrapBoundarySamples(testCase)
            path = testCase.writeSamples("ramp.f32le", single((0:14399).' / 32768));
            actual = s12_v12_prepare_texture_external_input(path, 0.20);
            samples = reshape(actual.texture_residual.', [], 1);

            testCase.verifyEqual(samples([1, 2880, 2881, 8640, 8641]), ...
                single([5760; 8639; 8638.5; 5759; 5760] / 32768), "AbsTol", single(1e-7));
            testCase.verifyLessThanOrEqual(abs(samples(8641) - samples(8640)), single(1 / 32768));
        end

        function preparingInputsDoesNotModifySourceFiles(testCase)
            before = [testCase.readBytes(testCase.LegacyPath), ...
                testCase.readBytes(testCase.LayerPaths(1)), ...
                testCase.readBytes(testCase.LayerPaths(2)), ...
                testCase.readBytes(testCase.LayerPaths(3))];

            s12_v12_prepare_texture_external_input( ...
                testCase.LegacyPath, 0.04, 0, struct(), testCase.LayerPaths, [0.2, 0.3, 0.4]);
            after = [testCase.readBytes(testCase.LegacyPath), ...
                testCase.readBytes(testCase.LayerPaths(1)), ...
                testCase.readBytes(testCase.LayerPaths(2)), ...
                testCase.readBytes(testCase.LayerPaths(3))];

            testCase.verifyEqual(after, before);
        end
    end

    methods (Access = private)
        function path = writeSamples(testCase, name, samples)
            path = fullfile(testCase.FixtureFolder, name);
            fileId = fopen(path, "w", "ieee-le");
            testCase.assertGreaterThan(fileId, 0, "Cannot create test F32LE source.");
            cleanup = onCleanup(@() fclose(fileId));
            count = fwrite(fileId, samples, "single");
            testCase.assertEqual(count, numel(samples));
            clear cleanup
        end

        function path = writeBytes(testCase, name, bytes)
            path = fullfile(testCase.FixtureFolder, name);
            fileId = fopen(path, "w");
            testCase.assertGreaterThan(fileId, 0, "Cannot create test byte source.");
            cleanup = onCleanup(@() fclose(fileId));
            count = fwrite(fileId, bytes, "uint8");
            testCase.assertEqual(count, numel(bytes));
            clear cleanup
        end

        function bytes = readBytes(testCase, path)
            fileId = fopen(path, "r");
            testCase.assertGreaterThan(fileId, 0, "Cannot read test source.");
            cleanup = onCleanup(@() fclose(fileId));
            bytes = fread(fileId, inf, "*uint8");
            clear cleanup
        end
    end
end
