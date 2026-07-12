function outputDir = v6_render_c63_artifacts(profile, iterationName, fitReport)
%V6_RENDER_C63_ARTIFACTS Compatibility wrapper for existing C63 scripts.

arguments
    profile (1,1) struct
    iterationName (1,1) string
    fitReport (1,1) struct = struct()
end

outputDir = v6_render_vehicle_artifacts(profile, iterationName, fitReport);
end
