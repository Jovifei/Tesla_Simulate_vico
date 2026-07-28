function sources = s12_engine_sound_simulink_sources(profile, backfireLevel)
%S12_ENGINE_SOUND_SIMULINK_SOURCES Build deterministic Model Workspace sources.

cycle = s12_engine_sound_compile_drive_cycle(profile, backfireLevel);
resetValues = false(cycle.frame_count, 1);
resetValues(1) = true;
backfireEnergy = zeros(cycle.frame_count, 1);
for index = 1:numel(cycle.backfire_events)
    frameIndex = floor(cycle.backfire_events(index).time_s / 0.02) + 1;
    backfireEnergy(frameIndex) = cycle.backfire_events(index).energy;
end
sources = struct("cycle", cycle, ...
    "vehicle_state", timeseries(cycle.state, cycle.timestamp_s), ...
    "reset", timeseries(resetValues, cycle.timestamp_s), ...
    "backfire_energy", timeseries(backfireEnergy, cycle.timestamp_s));
end
