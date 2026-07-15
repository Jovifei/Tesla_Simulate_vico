function profile = s12_benchmark_profile(profileId)
%S12_BENCHMARK_PROFILE Load one deterministic benchmark profile.
arguments
    profileId (1,1) string
end
root = fileparts(mfilename("fullpath"));
profileFile = fullfile(root, "config", "profiles", profileId + ".json");
if exist(profileFile, "file") ~= 2
    error("S12:Benchmark:UnknownProfile", ...
        "Unknown benchmark profile '%s'.", profileId);
end
profile = jsondecode(fileread(profileFile));
profile.id = string(profile.id);
profile.smooth.dt_divisors = reshape(profile.smooth.dt_divisors, 1, []);
for field = ["lax", "shu_osher", "woodward_colella"]
    profile.(field).cell_counts = reshape(profile.(field).cell_counts, 1, []);
end
profile.fanno_fvm.lengths_m = reshape(profile.fanno_fvm.lengths_m, 1, []);
profile.fanno_fvm.grid_cell_counts = ...
    reshape(profile.fanno_fvm.grid_cell_counts, 1, []);
end
