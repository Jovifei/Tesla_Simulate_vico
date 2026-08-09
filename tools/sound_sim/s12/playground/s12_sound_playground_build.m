function result = s12_sound_playground_build(runId, execute)
%S12_SOUND_PLAYGROUND_BUILD Transactional candidate builder entry point.
% Audit evidence is immutable and the current workspace binary is never a build target.

if nargin < 1
    runId = "controlled_rebuild_required";
end
if nargin < 2
    execute = false;
end
plan = s12_sound_playground_build_plan(runId);
result = struct("plan", plan, "status", "PLAN_ONLY_NOT_EXECUTED");
if ~execute
    return;
end
error("S12:Playground:DirectBuildForbidden", ...
    "Use the single controlled rebuild orchestrator after explicit authorization; direct build execution is forbidden.");
end
