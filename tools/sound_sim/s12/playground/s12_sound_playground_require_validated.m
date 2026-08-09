function result = s12_sound_playground_require_validated(cases)
%S12_SOUND_PLAYGROUND_REQUIRE_VALIDATED Return a durable PCM-validation artifact.

for index = 1:numel(cases)
    if ~strcmp(s12_sound_playground_require_text_scalar(cases(index).status, "simulation case status"), ...
            "SIMULATION_COMPLETED_AND_VALIDATED")
        error("S12:Playground:QualificationGate", "Case %s did not pass PCM validation.", cases(index).scenario);
    end
end
result = struct("status", "PCM_VALIDATION_PASSED", "case_count", numel(cases), ...
    "scenarios", string({cases.scenario}));
end
