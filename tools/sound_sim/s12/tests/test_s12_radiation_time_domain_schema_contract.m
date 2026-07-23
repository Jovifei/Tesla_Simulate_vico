function tests = test_s12_radiation_time_domain_schema_contract
%TEST_S12_RADIATION_TIME_DOMAIN_SCHEMA_CONTRACT Reserve 4D-B provenance fields.
tests = functiontests(localfunctions);
end

function testSchemaReservesTimeDomainRadiationFields(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
schema = jsondecode(fileread(fullfile(s12Root, "benchmark", "schema", ...
    "benchmark.schema.v1.json")));
verifyGreaterThanOrEqual(testCase, schema.schema_minor, 8);
required = ["radiation_boundary_type", "radiation_package_sha256", ...
    "radiation_state_order", "radiation_state_initialization", ...
    "radiation_reference_integrator_id", "maximum_radiation_stage_pole_amplification", ...
    "radiation_energy_balance_residual"];
verifyTrue(testCase, all(ismember(required, string(schema.case_metric_fields))));
end
