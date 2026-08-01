function [pressure, context, diagnostics] = ...
        s12_v12_apply_frozen_radiation_frame(prePtr, context, sampleRate)
%S12_V12_APPLY_FROZEN_RADIATION_FRAME Apply the frozen 4D-B audio adapter.
% This is a stateful audio adapter for the accepted radiation package. It is
% not the complete FVM/PTR network.

arguments
    prePtr (:, 1) double
    context = []
    sampleRate (1, 1) double {mustBeFinite, mustBePositive} = 48000
end

expectedSha = "0f4b2ca494cd44f79d05968513759578d04e6ab38b1ee37f7621158abb0d2d6f";
expectedCommit = "4afe65a67ed21822422f1eb6dbf43fdd627072d3";
upstreamDelay = 8;
downstreamDelay = 12;
upstreamLoss = 0.98;
downstreamLoss = 0.97;

if any(~isfinite(prePtr), "all")
    fail("pre-PTR input must be finite");
end

packagePath = frozenPackagePath();
actualSha = sha256File(packagePath);
if actualSha ~= expectedSha
    fail("accepted radiation package content hash drifted");
end
package = jsondecode(fileread(packagePath));
validatePackage(package, expectedCommit);

if isempty(context)
    context = struct( ...
        "upstream_delay", zeros(upstreamDelay, 1), ...
        "downstream_delay", zeros(downstreamDelay, 1), ...
        "radiation_state", reshape(double(package.initial_state), [2, 1]), ...
        "frame_index", 0);
else
    validateContext(context, upstreamDelay, downstreamDelay);
end

a = double(package.state_space_A);
b = reshape(double(package.state_space_B), [2, 1]);
c = reshape(double(package.state_space_C), [1, 2]);
d = double(package.state_space_D);
dt = 1 / sampleRate;
left = eye(2) - 0.5 * dt * a;
right = eye(2) + 0.5 * dt * a;
determinant = det(left);
if ~isfinite(determinant) || abs(determinant) < 1e-15
    fail("frozen radiation Tustin update is singular");
end

pressure = zeros(size(prePtr));
state = context.radiation_state;
for index = 1:numel(prePtr)
    outgoing = upstreamLoss * context.upstream_delay(1);
    context.upstream_delay = [context.upstream_delay(2:end); prePtr(index)];
    downstreamInput = outgoing;
    outgoing = downstreamLoss * context.downstream_delay(1);
    context.downstream_delay = ...
        [context.downstream_delay(2:end); downstreamInput];

    state = left \ (right * state + dt * b * outgoing);
    pressure(index) = outgoing + c * state + d * outgoing;
end

if any(~isfinite(pressure), "all")
    fail("frozen radiation adapter output became nonfinite");
end
context.radiation_state = state;
context.frame_index = context.frame_index + 1;
diagnostics = struct( ...
    "configuration", "frozen_4d_b_radiation_audio_adapter", ...
    "full_fvm_ptr_network", false, ...
    "radiation_package_sha256", actualSha, ...
    "radiation_source_commit", expectedCommit, ...
    "reference_plane", string(package.reference_plane), ...
    "sample_rate_hz", sampleRate);
end

function path = frozenPackagePath()
commonFolder = fileparts(mfilename("fullpath"));
s12Folder = fileparts(fileparts(commonFolder));
path = fullfile(s12Folder, "benchmark", "baselines", "sprint-4d-b", ...
    "radiation-boundary-package.json");
if ~isfile(path)
    fail("accepted radiation package is missing");
end
end

function validatePackage(package, expectedCommit)
required = ["schema", "state_space_A", "state_space_B", "state_space_C", ...
    "state_space_D", "initial_state", "reference_plane", "source_commit"];
if ~isstruct(package) || any(~isfield(package, required)) || ...
        string(package.schema) ~= "radiation_boundary_package.v1" || ...
        string(package.source_commit) ~= expectedCommit || ...
        ~isequal(size(package.state_space_A), [2, 2]) || ...
        numel(package.state_space_B) ~= 2 || ...
        numel(package.state_space_C) ~= 2 || ...
        numel(package.initial_state) ~= 2 || ...
        ~isscalar(package.state_space_D) || ...
        any(~isfinite(double(package.state_space_A)), "all") || ...
        any(~isfinite(double(package.state_space_B)), "all") || ...
        any(~isfinite(double(package.state_space_C)), "all") || ...
        any(~isfinite(double(package.initial_state)), "all") || ...
        ~isfinite(double(package.state_space_D))
    fail("accepted radiation package contract is invalid");
end
end

function validateContext(context, upstreamDelay, downstreamDelay)
required = ["upstream_delay", "downstream_delay", "radiation_state", ...
    "frame_index"];
if ~isstruct(context) || ~isscalar(context) || any(~isfield(context, required)) || ...
        ~isequal(size(context.upstream_delay), [upstreamDelay, 1]) || ...
        ~isequal(size(context.downstream_delay), [downstreamDelay, 1]) || ...
        ~isequal(size(context.radiation_state), [2, 1]) || ...
        ~isscalar(context.frame_index) || ...
        context.frame_index < 0 || fix(context.frame_index) ~= context.frame_index || ...
        any(~isfinite(context.upstream_delay), "all") || ...
        any(~isfinite(context.downstream_delay), "all") || ...
        any(~isfinite(context.radiation_state), "all")
    fail("radiation adapter context is invalid");
end
end

function value = sha256File(path)
bytes = uint8(filereadBytes(path));
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(bytes);
value = lower(string(reshape(dec2hex(typecast(digest.digest(), "uint8"), 2).', 1, [])));
end

function bytes = filereadBytes(path)
file = fopen(path, "rb");
if file < 0
    fail("accepted radiation package cannot be opened");
end
cleanup = onCleanup(@() fclose(file));
bytes = fread(file, Inf, "*uint8");
end

function fail(message)
error("S12:EngineSoundV12:RadiationAdapter", "%s", message);
end
