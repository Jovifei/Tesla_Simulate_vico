function result = s12_v11_validate_vehicle_package(packageRoot)
%S12_V11_VALIDATE_VEHICLE_PACKAGE Validate a synthetic-only v1.1 metadata package.

packageRoot = string(packageRoot);
if ~isscalar(packageRoot) || ~isfolder(packageRoot)
    error("S12:EngineSoundV11:Schema", "packageRoot must name an existing package folder.");
end
schema = jsondecode(fileread(fullfile(fileparts(mfilename("fullpath")), "schemas", "vehicle_package.schema.json")));
requiredFiles = ["README.md", "profile.json", "reference_manifest.json", "acoustic_targets.json", "afterfire_profile.json"];
actualFiles = string({dir(packageRoot).name});
actualFiles = actualFiles(~ismember(actualFiles, [".", ".."]));
generatedModels = "S12_" + reshape(string(schema.allowed_vehicle_ids), 1, []) + "_v11.slx";
if ~all(ismember(requiredFiles, actualFiles)) || ...
        any(~ismember(actualFiles, [requiredFiles, generatedModels]))
    error("S12:EngineSoundV11:Schema", ...
        "Vehicle packages must contain the five metadata files and only their optional canonical generated model.");
end

documentNames = ["profile", "reference_manifest", "acoustic_targets", "afterfire_profile"];
documents = struct();
for index = 1:numel(documentNames)
    name = documentNames(index);
    payload = jsondecode(fileread(fullfile(packageRoot, name + ".json")));
    requireExactFields(payload, string(schema.documents.(name)), name);
    validateCommonPayload(payload, name, schema);
    documents.(name) = payload;
end

profile = documents.profile;
for index = 2:numel(documentNames)
    name = documentNames(index);
    payload = documents.(name);
    if ~isequaln(payload.vehicle_identity, profile.vehicle_identity) || string(payload.vehicle_id) ~= string(profile.vehicle_id)
        error("S12:EngineSoundV11:Identity", "Every document must use one identical make/model/year/market/trim identity.");
    end
end
[~, packageName] = fileparts(packageRoot);
if string(profile.vehicle_id) ~= string(packageName)
    error("S12:EngineSoundV11:Identity", "vehicle_id must match its package folder name.");
end
validateProfile(profile, schema);
validateManifest(documents.reference_manifest, schema);
validateProfileManifestSourceLink(profile, documents.reference_manifest);
validateTargets(documents.acoustic_targets);
validateAfterfire(documents.afterfire_profile);
result = struct("valid", true, "vehicle_id", string(profile.vehicle_id), "schema_version", string(profile.schema_version));
end

function validateProfileManifestSourceLink(profile, manifest)
provenance = profile.provenance;
matched = false;
for index = 1:numel(manifest.references)
    reference = manifest.references(index);
    if string(reference.source_classification) == "official_manufacturer_configuration" && ...
            string(reference.source_url) == string(provenance.source_url)
        matched = true;
        break;
    end
end
if ~matched
    error("S12:EngineSoundV11:Provenance", ...
        "Profile A/manufacturer source_url must equal one official manufacturer manifest source_url.");
end
end

function validateCommonPayload(payload, name, schema)
if string(payload.schema_version) ~= string(schema.schema_version)
    error("S12:EngineSoundV11:Schema", "%s has an unsupported schema_version.", name);
end
if ~ismember(string(payload.vehicle_id), string(schema.allowed_vehicle_ids))
    error("S12:EngineSoundV11:Identity", "%s has an unsupported vehicle_id.", name);
end
requireExactFields(payload.vehicle_identity, string(schema.vehicle_identity_fields), name + ".vehicle_identity");
identityFields = string(fieldnames(payload.vehicle_identity));
for field = identityFields'
    if field == "model_year"
        validateModelYear(payload.vehicle_identity.(field), schema, name + ".vehicle_identity.model_year");
    else
        requireNonemptyText(payload.vehicle_identity.(field), name + ".vehicle_identity." + field);
    end
end
for field = ["market", "trim"]
    if strcmpi(string(payload.vehicle_identity.(field)), "unspecified")
        error("S12:EngineSoundV11:Identity", "%s must bind a concrete market and trim.", name);
    end
end
requireExactFields(payload.provenance, string(schema.provenance_fields), name + ".provenance");
documentedLevels = ["A", "B", "C", "pending", "synthetic_assumption"];
schemaLevels = reshape(string(schema.allowed_source_levels), 1, []);
if ~isequal(schemaLevels, documentedLevels)
    error("S12:EngineSoundV11:Schema", "Schema must retain the documented provenance-level contract.");
end
level = string(payload.provenance.source_level);
if ~isscalar(level) || ~ismember(level, documentedLevels)
    error("S12:EngineSoundV11:SourceLevel", "%s uses an unapproved source_level.", name);
end

requireNonemptyText(payload.provenance.source_type, name + ".provenance.source_type");
requireScalarText(payload.provenance.source_url, name + ".provenance.source_url");
if ismember(level, ["A", "B"]) && ~startsWith(string(payload.provenance.source_url), "https://")
    error("S12:EngineSoundV11:Provenance", "%s requires an HTTPS source_url for source level %s.", name, level);
elseif ~ismember(level, ["A", "B"]) && strlength(string(payload.provenance.source_url)) ~= 0
    error("S12:EngineSoundV11:Provenance", "%s must not use a placeholder source_url.", name);
end
requireNonemptyText(payload.provenance.claim, name + ".provenance.claim");
claim = lower(string(payload.provenance.claim));
if contains(claim, "real") || contains(claim, "oem") || ~contains(claim, "synthetic")
    error("S12:EngineSoundV11:Claim", "%s must make only synthetic, non-OEM claims.", name);
end
if isfield(payload, "scope")
    validateScope(payload.scope, schema, name);
end
end

function validateModelYear(value, schema, context)
contract = schema.model_year_contract;
isInteger = isnumeric(value) && isreal(value) && all(isfinite(value), "all") && all(value == floor(value), "all");
isSingleYear = isInteger && isscalar(value);
isRange = isInteger && isvector(value) && numel(value) == 2 && value(1) <= value(2);
if ~(isSingleYear || isRange) || any(value < contract.minimum | value > contract.maximum, "all")
    error("S12:EngineSoundV11:Identity", ...
        "%s must be one integer model year or an ascending two-integer inclusive range.", context);
end
end

function validateScope(scope, schema, name)
requireExactFields(scope, string(schema.scope_fields), name + ".scope");
if ~isequal(scope.synthetic, true) || ~isequal(scope.uncalibrated, true) || ~isequal(scope.offline, true) || ...
        string(scope.perspective) ~= "exterior-rear" || string(scope.orientation) ~= "stock-oriented" || ...
        string(scope.oem_status) ~= "non-OEM"
    error("S12:EngineSoundV11:Scope", "%s must remain synthetic, uncalibrated, offline, exterior-rear, stock-oriented, and non-OEM.", name);
end
end

function validateProfile(profile, schema)
validateCanonicalProfileProvenance(profile.provenance, schema);
validateRenderTuning(profile.render_tuning, schema);
validateEngineEventMap(profile.engine, schema, profile.render_tuning);
end

function validateCanonicalProfileProvenance(provenance, schema)
contract = schema.profile_provenance_contract;
if string(provenance.source_level) ~= string(contract.source_level) || ...
        string(provenance.source_type) ~= string(contract.source_type)
    error("S12:EngineSoundV11:Provenance", ...
        "Canonical profile provenance must be source level A and manufacturer.");
end
if ~startsWith(string(provenance.source_url), "https://")
    error("S12:EngineSoundV11:Provenance", ...
        "Canonical profile provenance must use one nonempty HTTPS manufacturer source_url.");
end
end

function validateEngineEventMap(engine, schema, tuning)
contract = schema.engine_contract;
fields = string(contract.fields);
requireExactFields(engine, fields, "profile.engine");
for field = fields'
    validateEngineRecord(engine.(field), field, contract);
end

configuration = string(engine.configuration.value);
layout = string(engine.layout.value);
firingOrder = reshape(double(engine.firing_order.value), 1, []);
firingPhases = reshape(double(engine.firing_phases_deg.value), 1, []);
bankMap = reshape(double(engine.bank_map.value), 1, []);
engineKind = string(tuning.architecture.engine_kind.value);
if configuration ~= engineKind
    error("S12:EngineSoundV11:EngineMap", ...
        "profile.engine.configuration must equal render_tuning.architecture.engine_kind.");
end
if engineKind == "piston"
    expectedEventCount = tuning.architecture.cylinders.value;
    if layout == "rotary"
        error("S12:EngineSoundV11:EngineMap", "Piston engine maps cannot use the rotary layout.");
    end
else
    expectedEventCount = tuning.architecture.rotor_count.value;
    if layout ~= "rotary"
        error("S12:EngineSoundV11:EngineMap", "Rotary engine maps must use the rotary layout.");
    end
end
if numel(firingOrder) ~= expectedEventCount || numel(firingPhases) ~= expectedEventCount || ...
        numel(bankMap) ~= expectedEventCount || ...
        any(firingOrder ~= floor(firingOrder)) || ...
        ~isequal(sort(firingOrder), 1:expectedEventCount) || ...
        numel(unique(firingOrder)) ~= expectedEventCount || ...
        any(firingPhases < 0 | firingPhases >= 720) || ...
        numel(unique(firingPhases)) ~= expectedEventCount || ...
        any(~ismember(bankMap, [-1, 0, 1]))
    error("S12:EngineSoundV11:EngineMap", ...
        "Synthetic firing_order, firing_phases_deg, and bank_map must form one unique in-range event map.");
end
if layout == "V" && (~any(bankMap == -1) || ~any(bankMap == 1))
    error("S12:EngineSoundV11:EngineMap", "Synthetic V layouts require both bank identifiers.");
elseif layout == "inline" && any(bankMap ~= 0)
    error("S12:EngineSoundV11:EngineMap", "Synthetic inline layouts require the neutral bank map.");
elseif layout == "rotary" && (~isequal(sort(bankMap), [-1, 1]) || expectedEventCount ~= 2)
    error("S12:EngineSoundV11:EngineMap", ...
        "The v1.1 rotary profile must use two synthetic rotor channels with bank identifiers [-1,1].");
end
if engine.redline_rpm.value ~= tuning.rpm_load.redline_rpm.value
    error("S12:EngineSoundV11:EngineMap", ...
        "profile.engine.redline_rpm must mirror the synthetic render tuning redline.");
end
end

function validateEngineRecord(record, parameterName, contract)
context = "profile.engine." + parameterName;
requireExactFields(record, string(contract.record_fields), context);
requireNonemptyText(record.unit, context + ".unit");
requireNonemptyText(record.source_scope, context + ".source_scope");
if ~contains(lower(string(record.source_scope)), "synthetic") || ...
        string(record.source_level) ~= string(contract.allowed_source_levels(1)) || ...
        string(record.source) ~= string(contract.allowed_sources(1)) || ...
        string(record.verification_state) ~= string(contract.allowed_verification_states(1)) || ...
        ~isScalarText(record.source_url) || strlength(string(record.source_url)) ~= 0
    error("S12:EngineSoundV11:EngineMap", ...
        "%s must be a C/synthetic synthetic_assumption record without source_url.", context);
end
if ismember(parameterName, string(contract.text_parameter_paths))
    validateEngineTextRecord(record, parameterName, contract);
elseif ismember(parameterName, string(contract.array_parameter_paths))
    validateEngineNumericRecord(record, parameterName, true, contract);
elseif ismember(parameterName, string(contract.numeric_parameter_paths))
    validateEngineNumericRecord(record, parameterName, false, contract);
else
    error("S12:EngineSoundV11:EngineMap", "Schema has no type for %s.", context);
end
end

function validateEngineTextRecord(record, parameterName, contract)
if ~isScalarText(record.value) || strlength(string(record.value)) == 0 || ...
        ~iscellstr(record.range) || ~ismember(string(record.value), string(record.range))
    error("S12:EngineSoundV11:EngineMap", ...
        "profile.engine.%s must be a text value in its declared range.", parameterName);
end
if parameterName == "configuration" && ...
        ~ismember(string(record.value), string(contract.allowed_engine_kinds))
    error("S12:EngineSoundV11:EngineMap", "profile.engine.configuration is unsupported.");
elseif parameterName == "layout" && ...
        ~ismember(string(record.value), string(contract.allowed_layouts))
    error("S12:EngineSoundV11:EngineMap", "profile.engine.layout is unsupported.");
end
end

function validateEngineNumericRecord(record, parameterName, requiresArray, contract)
value = record.value;
bounds = contract.numeric_bounds.(char(parameterName));
bounds = reshape(bounds, 1, []);
declaredRange = record.range;
if ~isnumeric(value) || any(~isfinite(value), "all") || ...
        (requiresArray && (~isvector(value) || isempty(value))) || ...
        (~requiresArray && ~isscalar(value)) || ...
        ~isnumeric(declaredRange) || ~isvector(declaredRange) || numel(declaredRange) ~= 2 || ...
        ~isnumeric(bounds) || ~isvector(bounds) || numel(bounds) ~= 2
    error("S12:EngineSoundV11:EngineMap", ...
        "profile.engine.%s must be finite and schema-bounded.", parameterName);
end
declaredRange = reshape(declaredRange, 1, []);
if any(~isfinite(declaredRange), "all") || declaredRange(1) > declaredRange(2) || ...
        declaredRange(1) < bounds(1) || declaredRange(2) > bounds(2) || ...
        any(value < declaredRange(1) | value > declaredRange(2), "all") || ...
        any(value < bounds(1) | value > bounds(2), "all")
    error("S12:EngineSoundV11:EngineMap", ...
        "profile.engine.%s must be finite and schema-bounded.", parameterName);
end
end

function validateRenderTuning(tuning, schema)
contract = schema.render_tuning;
sectionNames = string(fieldnames(contract.sections));
requireExactFields(tuning, sectionNames, "profile.render_tuning");
for sectionIndex = 1:numel(sectionNames)
    sectionName = sectionNames(sectionIndex);
    expectedParameters = string(contract.sections.(sectionName));
    section = tuning.(sectionName);
    requireExactFields(section, expectedParameters, "profile.render_tuning." + sectionName);
    for parameterIndex = 1:numel(expectedParameters)
        parameterName = expectedParameters(parameterIndex);
        parameterPath = sectionName + "." + parameterName;
        validateTuningRecord(section.(parameterName), parameterPath, contract);
    end
end
validateTuningRelationships(tuning);
end

function validateTuningRecord(record, parameterPath, contract)
requireExactFields(record, string(contract.record_fields), ...
    "profile.render_tuning." + parameterPath);
requireNonemptyText(record.unit, "profile.render_tuning." + parameterPath + ".unit");
requireNonemptyText(record.source_scope, "profile.render_tuning." + parameterPath + ".source_scope");
if ~contains(lower(string(record.source_scope)), "synthetic")
    error("S12:EngineSoundV11:RenderTuning", "%s must have a synthetic source_scope.", parameterPath);
end
if string(record.source_level) ~= string(contract.allowed_source_levels(1)) || ...
        string(record.source) ~= string(contract.allowed_sources(1)) || ...
        string(record.verification_state) ~= string(contract.allowed_verification_states(1)) || ...
        ~isScalarText(record.source_url) || strlength(string(record.source_url)) ~= 0
    error("S12:EngineSoundV11:RenderTuning", ...
        "%s must be a C/synthetic synthetic_assumption record without source_url.", parameterPath);
end
numericPaths = string(contract.numeric_parameter_paths);
arrayPaths = string(contract.array_parameter_paths);
textPaths = string(contract.text_parameter_paths);
logicalPaths = string(contract.logical_parameter_paths);
if ismember(parameterPath, numericPaths)
    validateNumericRecord(record, parameterPath, false, contract);
elseif ismember(parameterPath, arrayPaths)
    validateNumericRecord(record, parameterPath, true, contract);
elseif ismember(parameterPath, textPaths)
    validateTextRecord(record, parameterPath);
elseif ismember(parameterPath, logicalPaths)
    validateLogicalRecord(record, parameterPath);
else
    error("S12:EngineSoundV11:RenderTuning", "Schema has no type for %s.", parameterPath);
end
end

function validateNumericRecord(record, parameterPath, requiresArray, contract)
value = record.value;
schemaOwnedBounds = schemaOwnedNumericBounds(contract, parameterPath);
integerPaths = string(contract.integer_parameter_paths);
declaredRange = record.range;
if ~isnumeric(value) || any(~isfinite(value), "all") || ...
        (requiresArray && (~isvector(value) || numel(value) ~= 6)) || ...
        (~requiresArray && ~isscalar(value)) || ...
        ~isnumeric(declaredRange) || ~isvector(declaredRange) || numel(declaredRange) ~= 2
    error("S12:EngineSoundV11:RenderTuning", ...
        "%s must be finite, schema-bounded, and inside its declared numeric range.", parameterPath);
end
declaredRange = reshape(declaredRange, 1, []);
if any(~isfinite(declaredRange), "all") || declaredRange(1) > declaredRange(2) || ...
        declaredRange(1) < schemaOwnedBounds(1) || ...
        declaredRange(2) > schemaOwnedBounds(2) || ...
        any(value < declaredRange(1) | value > declaredRange(2), "all") || ...
        any(value < schemaOwnedBounds(1) | value > schemaOwnedBounds(2), "all") || ...
        (ismember(parameterPath, integerPaths) && any(value ~= floor(value), "all"))
    error("S12:EngineSoundV11:RenderTuning", ...
        "%s must be finite, schema-bounded, and inside its declared numeric range.", parameterPath);
end
end

function schemaOwnedBounds = schemaOwnedNumericBounds(contract, parameterPath)
parts = split(parameterPath, ".");
if numel(parts) ~= 2
    error("S12:EngineSoundV11:RenderTuning", ...
        "Schema has no numeric bounds for %s.", parameterPath);
end
sectionName = char(parts(1));
parameterName = char(parts(2));
if ~isfield(contract.numeric_bounds, sectionName) || ...
        ~isfield(contract.numeric_bounds.(sectionName), parameterName)
    error("S12:EngineSoundV11:RenderTuning", ...
        "Schema has no numeric bounds for %s.", parameterPath);
end
schemaOwnedBounds = contract.numeric_bounds.(sectionName).(parameterName);
if ~isnumeric(schemaOwnedBounds) || ~isvector(schemaOwnedBounds) || numel(schemaOwnedBounds) ~= 2
    error("S12:EngineSoundV11:RenderTuning", ...
        "Schema numeric bounds for %s are invalid.", parameterPath);
end
schemaOwnedBounds = reshape(schemaOwnedBounds, 1, []);
if any(~isfinite(schemaOwnedBounds), "all") || schemaOwnedBounds(1) > schemaOwnedBounds(2)
    error("S12:EngineSoundV11:RenderTuning", ...
        "Schema numeric bounds for %s are invalid.", parameterPath);
end
end

function validateTextRecord(record, parameterPath)
if ~isScalarText(record.value) || strlength(string(record.value)) == 0 || ...
        ~iscellstr(record.range) || numel(record.range) < 1 || ...
        ~ismember(string(record.value), string(record.range))
    error("S12:EngineSoundV11:RenderTuning", ...
        "%s must be a text value in its declared text range.", parameterPath);
end
end

function validateLogicalRecord(record, parameterPath)
if ~islogical(record.value) || ~isscalar(record.value) || ...
        ~islogical(record.range) || ~isequal(reshape(record.range, 1, []), [false, true])
    error("S12:EngineSoundV11:RenderTuning", ...
        "%s must be a logical value with range [false,true].", parameterPath);
end
end

function validateTuningRelationships(tuning)
architecture = tuning.architecture;
engineKind = string(architecture.engine_kind.value);
cylinders = architecture.cylinders.value;
rotorCount = architecture.rotor_count.value;
chambers = architecture.chambers_per_rotor.value;
shaftTurns = architecture.shaft_turns_per_rotor_turn.value;
if engineKind == "piston" && (cylinders < 1 || rotorCount ~= 0 || chambers ~= 0 || shaftTurns ~= 1)
    error("S12:EngineSoundV11:RenderTuning", "Piston architecture values are inconsistent.");
elseif engineKind == "rotary" && (cylinders ~= 0 || rotorCount < 1 || chambers < 1 || shaftTurns < 1)
    error("S12:EngineSoundV11:RenderTuning", "Rotary architecture values are inconsistent.");
end
idleRpm = tuning.rpm_load.idle_rpm.value;
redlineRpm = tuning.rpm_load.redline_rpm.value;
minimumLoad = tuning.rpm_load.minimum_load.value;
maximumLoad = tuning.rpm_load.maximum_load.value;
if idleRpm >= redlineRpm || minimumLoad < 0 || maximumLoad > 1 || minimumLoad >= maximumLoad
    error("S12:EngineSoundV11:RenderTuning", "RPM/load ranges are inconsistent.");
end
afterfire = tuning.afterfire;
if afterfire.idle_rpm_ceiling.value >= afterfire.minimum_event_rpm.value || ...
        afterfire.cruise_min_throttle.value > afterfire.cruise_max_throttle.value || ...
        afterfire.cluster_refractory_s.value < afterfire.cluster_interval_s.value || ...
        afterfire.refractory_jitter_fraction.value < 0 || ...
        afterfire.refractory_jitter_fraction.value > 0.45 || ...
        afterfire.interval_jitter_fraction.value <= 0 || ...
        afterfire.interval_jitter_fraction.value > 0.45 || ...
        afterfire.cluster_energy_decay.value <= 0 || afterfire.cluster_energy_decay.value >= 0.90 || ...
        afterfire.upshift_max_throttle_rate_per_s.value > 0 || ...
        afterfire.downshift_min_throttle_rate_per_s.value < 0 || ...
        afterfire.downshift_min_rpm_rate_per_s.value < 0 || ...
        afterfire.overrun_max_throttle_rate_per_s.value > 0 || ...
        afterfire.overrun_max_rpm_rate_per_s.value > 0 || ...
        afterfire.minimum_thermal_eligibility.value <= 0 || ...
        afterfire.minimum_thermal_eligibility.value > 1 || ...
        afterfire.lift_energy_decay_rate_per_s.value <= 0 || ...
        afterfire.lift_refractory_growth_per_s.value < 0
    error("S12:EngineSoundV11:RenderTuning", "Afterfire tuning relationships are inconsistent.");
end
renderer = tuning.renderer;
if renderer.sample_rate_hz.value ~= 48000 || renderer.frame_samples.value ~= 960 || ...
        renderer.channels.value ~= 2 || renderer.bits_per_sample.value ~= 24 || ...
        renderer.hard_limiter.value
    error("S12:EngineSoundV11:RenderTuning", "Renderer must remain 48 kHz, 960-sample, stereo, 24-bit, without a hard limiter.");
end
dashboard = tuning.dashboard_defaults;
if dashboard.rpm.value < idleRpm || dashboard.rpm.value > redlineRpm || ...
        dashboard.load.value < minimumLoad || dashboard.load.value > maximumLoad || ...
        dashboard.throttle.value < 0 || dashboard.throttle.value > 1 || ...
        dashboard.order_balance.value < 0 || dashboard.transient.value < 0 || ...
        dashboard.backfire_level.value ~= floor(dashboard.backfire_level.value) || ...
        dashboard.backfire_level.value < 0 || dashboard.backfire_level.value > 2 || ...
        dashboard.ptr_pipe_length_m.value ~= tuning.ptr.pipe_length_m.value || ...
        dashboard.ptr_area_m2.value ~= tuning.ptr.area_m2.value || ...
        dashboard.ptr_reflection.value ~= tuning.ptr.reflection.value || ...
        dashboard.ptr_damping.value ~= tuning.ptr.damping.value || ...
        dashboard.gain.value ~= tuning.character.output_gain.value
    error("S12:EngineSoundV11:RenderTuning", "Dashboard defaults must remain inside profile limits.");
end
vehicleState = tuning.vehicle_state;
if vehicleState.minimum_gear.value > vehicleState.maximum_gear.value || ...
        vehicleState.downshift_rpm_threshold.value >= vehicleState.upshift_rpm_threshold.value || ...
        vehicleState.upshift_rpm_threshold.value > redlineRpm || ...
        vehicleState.shift_hold_s.value <= 0 || ...
        vehicleState.derivative_min_dt_s.value <= 0 || ...
        vehicleState.thermal_initial_eligibility.value < 0 || ...
        vehicleState.thermal_initial_eligibility.value > 1 || ...
        vehicleState.thermal_heating_rate_per_s.value <= 0 || ...
        vehicleState.thermal_cooling_rate_per_s.value <= 0 || ...
        vehicleState.thermal_load_gain.value < 0 || vehicleState.thermal_load_gain.value > 1 || ...
        vehicleState.thermal_rpm_reference_rpm.value <= 0
    error("S12:EngineSoundV11:RenderTuning", ...
        "Vehicle-state tuning must define ordered gear, shift, and hold thresholds.");
end
end

function validateManifest(manifest, schema)
contract = schema.reference_manifest_contract;
if ~isequal(manifest.raw_reference_audio_in_git, false)
    error("S12:EngineSoundV11:RawAudio", "Reference manifests must exclude raw reference audio from Git.");
end
if ~ismember(string(manifest.research_status), string(contract.allowed_research_statuses))
    error("S12:EngineSoundV11:Provenance", "Reference manifest research_status is unsupported.");
end
requireExactFields(manifest.analysis_boundary, string(contract.analysis_boundary_fields), "reference_manifest.analysis_boundary");
boundary = manifest.analysis_boundary;
if string(boundary.raw_audio_state) ~= "not_acquired" || ...
        string(boundary.spectral_order_analysis_state) ~= "not_analyzed" || ...
        string(boundary.derived_metrics_state) ~= "not_analyzed"
    error("S12:EngineSoundV11:RawAudio", "Reference manifests must disclose not_acquired/not_analyzed research state.");
end
requireNonemptyText(boundary.repository_audio_policy, "reference_manifest.analysis_boundary.repository_audio_policy");

references = manifest.references;
if ~isstruct(references) || isempty(references)
    error("S12:EngineSoundV11:RawAudio", "Reference manifests must catalog at least one honest non-audio source.");
end
for index = 1:numel(references)
    reference = references(index);
    validateResearchReference(reference, manifest.vehicle_identity, contract, index);
end
end

function validateResearchReference(reference, identity, contract, index)
context = "reference_manifest.references(" + string(index) + ")";
requireExactFields(reference, string(contract.reference_fields), context);
requireNonemptyText(reference.reference_id, context + ".reference_id");
requireNonemptyText(reference.publisher, context + ".publisher");
requireScalarText(reference.source_url, context + ".source_url");
if ~startsWith(string(reference.source_url), "https://")
    error("S12:EngineSoundV11:Provenance", "%s requires an HTTPS source_url.", context);
end
requireUrlSha256(reference.source_url_sha256, context + ".source_url_sha256");
if ~ismember(string(reference.source_classification), string(contract.allowed_source_classifications)) || ...
        ~ismember(string(reference.vehicle_binding_state), string(contract.allowed_vehicle_binding_states)) || ...
        ~ismember(string(reference.stock_modified_status), string(contract.allowed_stock_modified_statuses)) || ...
        ~ismember(string(reference.listening_perspective), string(contract.allowed_listening_perspectives)) || ...
        ~ismember(string(reference.content_hash_state), string(contract.allowed_content_hash_states)) || ...
        ~ismember(string(reference.derived_analysis_state), string(contract.allowed_derived_analysis_states))
    error("S12:EngineSoundV11:Provenance", "%s uses an unsupported honest-research state.", context);
end
validateReferenceSemanticPair(reference, context);
requireExactFields(reference.vehicle_binding, string(fieldnames(identity)), context + ".vehicle_binding");
if ~isequaln(reference.vehicle_binding, identity)
    error("S12:EngineSoundV11:Identity", "%s must bind make/model/year/market/trim to the package identity.", context);
end
requireExactFields(reference.clip_time_metadata, string(contract.clip_time_metadata_fields), context + ".clip_time_metadata");
clip = reference.clip_time_metadata;
if ~ismember(string(clip.state), string(contract.allowed_clip_time_states)) || ...
        ~isScalarText(clip.start_s) || strlength(string(clip.start_s)) ~= 0 || ...
        ~isScalarText(clip.end_s) || strlength(string(clip.end_s)) ~= 0
    error("S12:EngineSoundV11:RawAudio", "%s must use explicit not_available clip times until media is acquired.", context);
end
requireNonemptyText(reference.licensing_use_boundary, context + ".licensing_use_boundary");
end

function validateReferenceSemanticPair(reference, context)
classification = string(reference.source_classification);
bindingState = string(reference.vehicle_binding_state);
stockStatus = string(reference.stock_modified_status);
if classification == "official_manufacturer_configuration"
    if ~((bindingState == "identity_verified" && stockStatus == "manufacturer_identity_only") || ...
            (bindingState == "identity_pending" && stockStatus == "manufacturer_identity_pending"))
        error("S12:EngineSoundV11:Provenance", ...
            "%s official manufacturer references require a verified or explicitly pending identity pair.", context);
    end
elseif classification == "public_candidate_sound_reference_discovery"
    if bindingState ~= "query_scoped_candidate_not_verified" || stockStatus ~= "unverified_candidate"
        error("S12:EngineSoundV11:Provenance", ...
            "%s candidate discovery references must remain query-scoped and unverified.", context);
    end
end
end

function requireUrlSha256(value, context)
if ~isScalarText(value) || isempty(regexp(char(string(value)), "^[0-9a-f]{64}$", "once"))
    error("S12:EngineSoundV11:Provenance", "%s must be the lowercase SHA-256 of source_url text.", context);
end
end

function validateTargets(targets)
requireExactFields(targets.targets, ["idle_character", "acceleration_character", "exterior_perspective"], "acoustic_targets.targets");
validateSyntheticTextFields(targets.targets, "acoustic_targets.targets");
end

function validateAfterfire(afterfire)
requireExactFields(afterfire.behavior, ["status", "description"], "afterfire_profile.behavior");
if ~ismember(string(afterfire.behavior.status), ["pending", "synthetic_assumption"])
    error("S12:EngineSoundV11:SourceLevel", "afterfire_profile.behavior has an unapproved status.");
end
requireNonemptyText(afterfire.behavior.description, "afterfire_profile.behavior.description");
end

function validateSyntheticTextFields(value, context)
fields = string(fieldnames(value));
for field = fields'
    requireNonemptyText(value.(field), context + "." + field);
end
end

function requireExactFields(value, expected, context)
if ~isstruct(value) || numel(value) ~= 1
    error("S12:EngineSoundV11:Schema", "%s must be a scalar struct.", context);
end
actual = reshape(string(fieldnames(value)), 1, []);
expected = reshape(string(expected), 1, []);
if ~isequal(sort(actual), sort(expected))
    if ~isempty(setdiff(actual, expected))
        error("S12:EngineSoundV11:UnknownField", "Unknown field in %s.", context);
    end
    error("S12:EngineSoundV11:Provenance", "Missing or invalid fields in %s.", context);
end
end

function requireNonemptyText(value, context)
if ~isScalarText(value) || strlength(string(value)) == 0
    error("S12:EngineSoundV11:Schema", "%s must be one nonempty text scalar.", context);
end
end

function requireScalarText(value, context)
if ~isScalarText(value)
    error("S12:EngineSoundV11:Schema", "%s must be one text scalar.", context);
end
end

function tf = isScalarText(value)
tf = (ischar(value) && (isrow(value) || isempty(value))) || ...
    (isstring(value) && isscalar(value));
end
