function tests = test_s12_engine_sound_v10_simulink_sources
%TEST_S12_ENGINE_SOUND_V10_SIMULINK_SOURCES Contract tests for model workspace data.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
source = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground_v10");
testCase.TestData.source = source;
addpath(source);
end

function teardownOnce(testCase)
if isfolder(testCase.TestData.source)
    rmpath(testCase.TestData.source);
end
end

function testSourcesCarryFixedStateResetAndBackfireContracts(testCase)
profile = s12_engine_sound_load_profile("v6_sport");
sources = s12_engine_sound_simulink_sources(profile, "subtle");
verifySize(testCase, sources.vehicle_state.Data, [4500, 6]);
verifySize(testCase, sources.reset.Data, [4500, 1]);
verifySize(testCase, sources.backfire_energy.Data, [4500, 1]);
verifyEqual(testCase, sources.vehicle_state.Time(1), 0, "AbsTol", 1e-12);
verifyEqual(testCase, sources.vehicle_state.Time(end), 89.98, "AbsTol", 1e-12);
verifyEqual(testCase, sources.reset.Data(1), true);
verifyFalse(testCase, any(sources.reset.Data(2:end)));
verifyEqual(testCase, nnz(sources.backfire_energy.Data), numel(sources.cycle.backfire_events));
end

function testOffSourcesContainNoBackfireEnergy(testCase)
profile = s12_engine_sound_load_profile("inline6_smooth");
sources = s12_engine_sound_simulink_sources(profile, "off");
verifyEqual(testCase, nnz(sources.backfire_energy.Data), 0);
verifyEmpty(testCase, sources.cycle.backfire_events);
end
