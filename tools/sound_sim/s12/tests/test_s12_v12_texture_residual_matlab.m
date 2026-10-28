function tests = test_s12_v12_texture_residual_matlab
%TEST_S12_V12_TEXTURE_RESIDUAL_MATLAB Research-only residual contract.
tests = functiontests(localfunctions);
end

function testZeroWeightIsBitExact(testCase)
base = linspace(-0.2, 0.2, 960).';
texture = flipud(base);
[mixed, context, diagnostics] = s12_v12_mix_texture_residual(base, texture, 0, []);
verifyEqual(testCase, mixed, base);
verifyEqual(testCase, context.frame_index, 1);
verifyFalse(testCase, diagnostics.product_candidate);
verifyEqual(testCase, diagnostics.qualification, "INSUFFICIENT_EVIDENCE");
end

function testWeightedTextureIsBoundedAndStateful(testCase)
base = 0.05 * sin((1:960).');
texture = 0.9 * cos((1:960).');
[first, context, diagnostics] = s12_v12_mix_texture_residual(base, texture, 0.35, []);
[second, context2] = s12_v12_mix_texture_residual(base, texture, 0.35, context);
verifyTrue(testCase, all(isfinite(first)) && all(abs(first) <= 1));
verifyTrue(testCase, all(isfinite(second)) && all(abs(second) <= 1));
verifyEqual(testCase, context2.frame_index, 2);
verifyGreaterThan(testCase, context2.weight_state, 0);
verifyLessThan(testCase, context2.weight_state, 0.35);
verifyEqual(testCase, diagnostics.source_class, "PUBLIC_TEXTURE_RESEARCH_ONLY");
end

function testInvalidTextureAndWeightFailClosed(testCase)
base = zeros(960, 1);
verifyError(testCase, @() s12_v12_mix_texture_residual(base, zeros(959, 1), 0, []), ...
    "S12:EngineSoundV12:TextureResidual");
verifyError(testCase, @() s12_v12_mix_texture_residual(base, base, 1.1, []), ...
    "S12:EngineSoundV12:TextureResidual");
end

function testPrePtrRouteAcceptsOptionalResearchTextureAtZeroWeight(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
common = fullfile(root, "playground_v12", "common");
vehicleFolder = fullfile(root, "playground_v12", "vehicles", "hellcat_2022_stock");
addpath(common);
cleanup = onCleanup(@() rmpath(common));
profile = jsondecode(fileread(fullfile(vehicleFolder, "source_profile.json")));
state = struct("rpm", 1200, "load", .35, "throttle", .30, "acceleration", 0, ...
    "shift_event", 0, "shift_progress", 0, "afterfire_kind", "none", ...
    "afterfire_progress", 0);
[baseline, ~] = s12_v12_render_pre_ptr_frame(state, profile, [], 48000, 960);
[withZeroTexture, ~, diagnostics] = s12_v12_render_pre_ptr_frame( ...
    state, profile, [], 48000, 960, [], ones(960, 1), 0);
verifyEqual(testCase, withZeroTexture, baseline);
verifyEqual(testCase, diagnostics.texture_residual.qualification, "INSUFFICIENT_EVIDENCE");
verifyFalse(testCase, diagnostics.texture_residual.product_candidate);
end
