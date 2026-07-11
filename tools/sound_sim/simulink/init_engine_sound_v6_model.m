%INIT_ENGINE_SOUND_V6_MODEL Build the editable V6 C63 Simulink state harness.

scriptDir = fileparts(mfilename("fullpath"));
matlabDir = fullfile(fileparts(scriptDir), "matlab");
addpath(fullfile(matlabDir, "v6"));
modelName = "engine_sound_v6";
modelPath = fullfile(scriptDir, modelName + ".slx");
profile = v6_vehicle_profile("c63_w204");

if bdIsLoaded(modelName)
    close_system(modelName, 0);
end
if isfile(modelPath)
    delete(modelPath);
end
new_system(modelName);
open_system(modelName);
set_param(modelName, "Solver", "FixedStepDiscrete", "FixedStep", "0.0001", ...
    "StopTime", "2", "SignalLogging", "on", "SignalLoggingName", "V6Logs");

workspace = get_param(modelName, "ModelWorkspace");
assignin(workspace, "V6Profile", profile);
assignin(workspace, "SpeedKmh", 80);
assignin(workspace, "ThrottleCmd", 0.65);
assignin(workspace, "GearCmd", 2);
assignin(workspace, "WheelRadiusM", profile.driveline.wheel_radius_m);
assignin(workspace, "OverallRatio", ...
    profile.driveline.gear_ratios(2) * profile.driveline.final_drive);
assignin(workspace, "EngineIdleRPM", profile.engine.idle_rpm);
assignin(workspace, "RedlineRPM", profile.engine.redline_rpm);
assignin(workspace, "V6SampleRateHz", profile.audio.sample_rate_hz);
assignin(workspace, "DFCOThrottle", profile.ecu.dfco_throttle);
assignin(workspace, "AfterfireEgtThresholdK", profile.afterfire.egt_threshold_k);
assignin(workspace, "CatalystReflection", profile.exhaust.catalyst_reflection);
assignin(workspace, "MufflerReflection", profile.exhaust.muffler_reflection);

add_constant(modelName, "VehicleSpeedKmh", "SpeedKmh", [30, 90, 110, 120]);
add_constant(modelName, "ThrottleCommand", "ThrottleCmd", [30, 160, 110, 190]);
add_constant(modelName, "GearCommand", "GearCmd", [30, 230, 110, 260]);
build_drive_cycle(modelName);
build_engine_ecu(modelName);
build_thermal(modelName);
build_waveguide(modelName);
build_afterfire(modelName);
build_mechanical(modelName);
build_propagation(modelName);
build_reference_metrics(modelName);

add_block("simulink/Sinks/Scope", modelName + "/V6MonitoringScope", ...
    "Position", [1330, 125, 1360, 155]);
add_block("simulink/Sinks/To Workspace", modelName + "/V6TuningData", ...
    "VariableName", "V6TuningData", "SaveFormat", "Structure With Time", ...
    "Position", [1330, 185, 1415, 215]);

add_line(modelName, "VehicleSpeedKmh/1", "DriveCycle/1", "autorouting", "on");
add_line(modelName, "ThrottleCommand/1", "DriveCycle/2", "autorouting", "on");
add_line(modelName, "GearCommand/1", "DriveCycle/3", "autorouting", "on");
add_line(modelName, "DriveCycle/1", "EngineECU/1", "autorouting", "on");
add_line(modelName, "DriveCycle/2", "EngineECU/2", "autorouting", "on");
add_line(modelName, "DriveCycle/3", "EngineECU/3", "autorouting", "on");
add_line(modelName, "EngineECU/3", "ThermalState/1", "autorouting", "on");
add_line(modelName, "EngineECU/2", "ThermalState/2", "autorouting", "on");
add_line(modelName, "EngineECU/1", "ExhaustWaveguide/1", "autorouting", "on");
add_line(modelName, "EngineECU/2", "ExhaustWaveguide/2", "autorouting", "on");
add_line(modelName, "ThermalState/1", "ExhaustWaveguide/3", "autorouting", "on");
add_line(modelName, "DriveCycle/2", "AfterfireShift/1", "autorouting", "on");
add_line(modelName, "EngineECU/1", "AfterfireShift/2", "autorouting", "on");
add_line(modelName, "ThermalState/1", "AfterfireShift/3", "autorouting", "on");
add_line(modelName, "EngineECU/1", "MechanicalTexture/1", "autorouting", "on");
add_line(modelName, "EngineECU/2", "MechanicalTexture/2", "autorouting", "on");
add_line(modelName, "ExhaustWaveguide/1", "PropagationMetrics/1", "autorouting", "on");
add_line(modelName, "AfterfireShift/1", "PropagationMetrics/2", "autorouting", "on");
add_line(modelName, "MechanicalTexture/1", "PropagationMetrics/3", "autorouting", "on");
add_line(modelName, "PropagationMetrics/1", "ReferenceMetrics/1", "autorouting", "on");
add_line(modelName, "ReferenceMetrics/1", "V6MonitoringScope/1", "autorouting", "on");
add_line(modelName, "ReferenceMetrics/1", "V6TuningData/1", "autorouting", "on");

set_param(modelName, "Description", [ ...
    "V6 C63 editable multi-rate state harness. The 96 kHz audio solver is ", ...
    "tools/sound_sim/matlab/v6/v6_synthesize_engine_sound.m. This model ", ...
    "validates its speed, load, thermal, waveguide, afterfire, and propagation states."]);
save_system(modelName, modelPath);
close_system(modelName);
fprintf("Created V6 model: %s\n", modelPath);

function add_constant(model, name, value, position)
add_block("simulink/Sources/Constant", model + "/" + name, ...
    "Value", value, "Position", position);
end

function build_drive_cycle(model)
path = model + "/DriveCycle";
create_subsystem(path, [180, 85, 330, 270]);
add_io(path, ["SpeedKmh", "Throttle", "Gear"], ["SpeedKmh", "Throttle", "Gear"]);
for index = 1:3
    add_line(path, "In" + index + "/1", "Out" + index + "/1");
end
end

function build_engine_ecu(model)
path = model + "/EngineECU";
create_subsystem(path, [410, 85, 570, 270]);
add_io(path, ["SpeedKmh", "Throttle", "Gear"], ["RPM", "Load", "EGT"]);
add_block("simulink/Math Operations/Gain", path + "/SpeedToWheelRPM", ...
    "Gain", "60/(3.6*2*pi*WheelRadiusM)", "Position", [105, 25, 180, 55]);
add_block("simulink/Math Operations/Gain", path + "/OverallRatio", ...
    "Gain", "OverallRatio", "Position", [205, 25, 275, 55]);
add_block("simulink/Discontinuities/Saturation", path + "/EngineRPM", ...
    "LowerLimit", "EngineIdleRPM", "UpperLimit", "RedlineRPM", ...
    "Position", [300, 25, 375, 55]);
add_block("simulink/Discontinuities/Saturation", path + "/LoadClamp", ...
    "LowerLimit", "0", "UpperLimit", "1", "Position", [210, 95, 280, 125]);
add_block("simulink/Math Operations/Gain", path + "/EgtScale", ...
    "Gain", "480", "Position", [205, 155, 275, 185]);
add_block("simulink/Sources/Constant", path + "/EgtBase", ...
    "Value", "520", "Position", [205, 205, 275, 235]);
add_block("simulink/Math Operations/Sum", path + "/EgtSum", ...
    "Inputs", "++", "Position", [300, 170, 335, 210]);
add_block("simulink/Sinks/Terminator", path + "/GearUsedByOfflineSolver", ...
    "Position", [205, 265, 225, 285]);
add_line(path, "In1/1", "SpeedToWheelRPM/1");
add_line(path, "SpeedToWheelRPM/1", "OverallRatio/1");
add_line(path, "OverallRatio/1", "EngineRPM/1");
add_line(path, "EngineRPM/1", "Out1/1");
add_line(path, "In2/1", "LoadClamp/1");
add_line(path, "LoadClamp/1", "Out2/1");
add_line(path, "LoadClamp/1", "EgtScale/1");
add_line(path, "EgtScale/1", "EgtSum/1");
add_line(path, "EgtBase/1", "EgtSum/2");
add_line(path, "EgtSum/1", "Out3/1");
add_line(path, "In3/1", "GearUsedByOfflineSolver/1");
end

function build_waveguide(model)
path = model + "/ExhaustWaveguide";
create_subsystem(path, [800, 85, 960, 250]);
add_io(path, ["RPM", "Load", "EGT"], "AcousticEnergy");
add_block("simulink/Math Operations/Gain", path + "/RpmToHz", ...
    "Gain", "1/60", "Position", [115, 25, 180, 55]);
add_block("simulink/Math Operations/Gain", path + "/EgtToSoundSpeedProxy", ...
    "Gain", "1/1000", "Position", [115, 125, 180, 155]);
add_block("simulink/Math Operations/Product", path + "/ThermalWaveProduct", ...
    "Inputs", "***", "Position", [225, 65, 270, 120]);
add_block("simulink/Math Operations/Gain", path + "/WaveguideGain", ...
    "Gain", "1+MufflerReflection-CatalystReflection", "Position", [305, 75, 385, 105]);
add_line(path, "In1/1", "RpmToHz/1");
add_line(path, "RpmToHz/1", "ThermalWaveProduct/1");
add_line(path, "In2/1", "ThermalWaveProduct/2");
add_line(path, "In3/1", "EgtToSoundSpeedProxy/1");
add_line(path, "EgtToSoundSpeedProxy/1", "ThermalWaveProduct/3");
add_line(path, "ThermalWaveProduct/1", "WaveguideGain/1");
add_line(path, "WaveguideGain/1", "Out1/1");
end

function build_thermal(model)
path = model + "/ThermalState";
create_subsystem(path, [610, 85, 740, 230]);
add_io(path, ["RawEGT", "Load"], "ThermalEGT");
add_block("simulink/Math Operations/Gain", path + "/LoadHeatBias", ...
    "Gain", "10", "Position", [115, 105, 180, 135]);
add_block("simulink/Math Operations/Sum", path + "/TargetEGT", ...
    "Inputs", "++", "Position", [225, 65, 260, 105]);
add_block("simulink/Discrete/Discrete Transfer Fcn", path + "/ThermalLag", ...
    "Numerator", "0.1", "Denominator", "[1 -0.9]", "SampleTime", "0.001", ...
    "Position", [305, 65, 385, 105]);
add_line(path, "In1/1", "TargetEGT/1");
add_line(path, "In2/1", "LoadHeatBias/1");
add_line(path, "LoadHeatBias/1", "TargetEGT/2");
add_line(path, "TargetEGT/1", "ThermalLag/1");
add_line(path, "ThermalLag/1", "Out1/1");
end

function build_afterfire(model)
path = model + "/AfterfireShift";
create_subsystem(path, [800, 315, 960, 470]);
add_io(path, ["Throttle", "RPM", "EGT"], "AfterfireGate");
add_block("simulink/Math Operations/Bias", path + "/ThrottleBias", ...
    "Bias", "-1", "Position", [115, 25, 180, 55]);
add_block("simulink/Math Operations/Gain", path + "/LiftProxy", ...
    "Gain", "-1", "Position", [205, 25, 270, 55]);
add_block("simulink/Math Operations/Gain", path + "/RpmNorm", ...
    "Gain", "1/RedlineRPM", "Position", [115, 95, 180, 125]);
add_block("simulink/Math Operations/Gain", path + "/EgtNorm", ...
    "Gain", "1/AfterfireEgtThresholdK", "Position", [115, 155, 180, 185]);
add_block("simulink/Math Operations/Product", path + "/AfterfireProduct", ...
    "Inputs", "***", "Position", [305, 80, 350, 135]);
add_line(path, "In1/1", "ThrottleBias/1");
add_line(path, "ThrottleBias/1", "LiftProxy/1");
add_line(path, "LiftProxy/1", "AfterfireProduct/1");
add_line(path, "In2/1", "RpmNorm/1");
add_line(path, "RpmNorm/1", "AfterfireProduct/2");
add_line(path, "In3/1", "EgtNorm/1");
add_line(path, "EgtNorm/1", "AfterfireProduct/3");
add_line(path, "AfterfireProduct/1", "Out1/1");
end

function build_propagation(model)
path = model + "/PropagationMetrics";
create_subsystem(path, [1040, 150, 1180, 330]);
add_io(path, ["AcousticEnergy", "AfterfireGate", "MechanicalTexture"], "SpeakerPreview");
add_block("simulink/Math Operations/Sum", path + "/Mix", ...
    "Inputs", "+++", "Position", [145, 60, 180, 100]);
add_block("simulink/Math Operations/Gain", path + "/SpeakerGain", ...
    "Gain", "0.5", "Position", [225, 65, 290, 95]);
add_line(path, "In1/1", "Mix/1");
add_line(path, "In2/1", "Mix/2");
add_line(path, "In3/1", "Mix/3");
add_line(path, "Mix/1", "SpeakerGain/1");
add_line(path, "SpeakerGain/1", "Out1/1");
end

function build_mechanical(model)
path = model + "/MechanicalTexture";
create_subsystem(path, [800, 535, 960, 665]);
add_io(path, ["RPM", "Load"], "TextureEnergy");
add_block("simulink/Math Operations/Gain", path + "/OrderProxy", ...
    "Gain", "88/60", "Position", [115, 25, 180, 55]);
add_block("simulink/Math Operations/Product", path + "/OrderLoadProduct", ...
    "Inputs", "**", "Position", [225, 50, 270, 90]);
add_block("simulink/Math Operations/Gain", path + "/MechanicalGain", ...
    "Gain", "0.02", "Position", [305, 55, 370, 85]);
add_line(path, "In1/1", "OrderProxy/1");
add_line(path, "OrderProxy/1", "OrderLoadProduct/1");
add_line(path, "In2/1", "OrderLoadProduct/2");
add_line(path, "OrderLoadProduct/1", "MechanicalGain/1");
add_line(path, "MechanicalGain/1", "Out1/1");
end

function build_reference_metrics(model)
path = model + "/ReferenceMetrics";
create_subsystem(path, [1210, 150, 1300, 280]);
add_io(path, "SpeakerPreview", "MonitoredOutput");
add_block("simulink/Math Operations/Gain", path + "/OutputMonitor", ...
    "Gain", "1", "Position", [150, 55, 215, 85]);
add_line(path, "In1/1", "OutputMonitor/1");
add_line(path, "OutputMonitor/1", "Out1/1");
end

function create_subsystem(path, position)
add_block("built-in/Subsystem", path, "Position", position);
Simulink.SubSystem.deleteContents(path);
end

function add_io(path, inputs, outputs)
inputs = string(inputs);
outputs = string(outputs);
for index = 1:numel(inputs)
    add_block("simulink/Ports & Subsystems/In1", path + "/In" + index, ...
        "Port", string(index), ...
        "Position", [25, 25 + 70 * (index - 1), 55, 45 + 70 * (index - 1)]);
end
for index = 1:numel(outputs)
    add_block("simulink/Ports & Subsystems/Out1", path + "/Out" + index, ...
        "Port", string(index), ...
        "Position", [435, 25 + 70 * (index - 1), 465, 45 + 70 * (index - 1)]);
end
end
