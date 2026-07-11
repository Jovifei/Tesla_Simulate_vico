%INIT_V6_EXHAUST_THERMAL_PLANT Build the V6 low-frequency Simscape Gas plant.

scriptDir = fileparts(mfilename("fullpath"));
modelName = "v6_exhaust_thermal_plant";
modelPath = fullfile(scriptDir, modelName + ".slx");
load_system("fl_lib");
load_system("nesl_utility");
if bdIsLoaded(modelName)
    close_system(modelName, 0);
end
if isfile(modelPath)
    delete(modelPath);
end
new_system(modelName);
open_system(modelName);
set_param(modelName, "Solver", "ode23t", "StopTime", "0.10");

gasProperties = modelName + "/GasProperties";
inlet = modelName + "/HotBlowdownReservoir";
pipe = modelName + "/MidPipe";
outlet = modelName + "/AmbientReservoir";
solver = modelName + "/SolverConfiguration";
thermalReference = modelName + "/ThermalReference";

add_block("fl_lib/Gas/Utilities/Gas Properties (G)", gasProperties, ...
    "Position", [70, 95, 130, 145]);
add_block("fl_lib/Gas/Elements/Reservoir (G)", inlet, ...
    "Position", [190, 70, 260, 145]);
add_block("fl_lib/Gas/Elements/Pipe (G)", pipe, ...
    "Position", [355, 75, 455, 145]);
add_block("fl_lib/Gas/Elements/Reservoir (G)", outlet, ...
    "Position", [600, 75, 670, 145]);
add_block("nesl_utility/Solver Configuration", solver, ...
    "Position", [205, 210, 265, 260]);
add_block("fl_lib/Thermal/Thermal Elements/Thermal Reference", thermalReference, ...
    "Position", [390, 205, 450, 255]);

set_param(inlet, "reservoir_pressure", "250000", "reservoir_pressure_unit", "Pa", ...
    "reservoir_temperature", "900", "reservoir_temperature_unit", "K");
set_param(outlet, "reservoir_pressure", "101325", "reservoir_pressure_unit", "Pa", ...
    "reservoir_temperature", "350", "reservoir_temperature_unit", "K");
set_param(pipe, "length", "1.15", "length_unit", "m", ...
    "area", "0.002827", "area_unit", "m^2", "Dh", "0.06", "Dh_unit", "m", ...
    "dynamic_compressibility", "true", "inertia", "true", "p_init", "150000", ...
    "p_init_unit", "Pa", "T_init", "700", "T_init_unit", "K");

gasPorts = get_param(gasProperties, "PortHandles");
inletPorts = get_param(inlet, "PortHandles");
pipePorts = get_param(pipe, "PortHandles");
outletPorts = get_param(outlet, "PortHandles");
solverPorts = get_param(solver, "PortHandles");
thermalPorts = get_param(thermalReference, "PortHandles");

add_line(modelName, inletPorts.LConn, pipePorts.LConn(1), "autorouting", "on");
add_line(modelName, pipePorts.RConn, outletPorts.LConn, "autorouting", "on");
add_line(modelName, gasPorts.RConn, inletPorts.LConn, "autorouting", "on");
add_line(modelName, solverPorts.RConn, inletPorts.LConn, "autorouting", "on");
add_line(modelName, pipePorts.LConn(2), thermalPorts.LConn, "autorouting", "on");

set_param(modelName, "Description", [ ...
    "Low-frequency C63 V6 exhaust thermal plant. It uses Simscape Gas Pipe (G) ", ...
    "for pressure, temperature, compressibility, inertia, and wall heat exchange. ", ...
    "The 96 kHz audio waveguide is deliberately solved in MATLAB V6 code."]);
save_system(modelName, modelPath);
close_system(modelName);
fprintf("Created V6 Simscape exhaust plant: %s\n", modelPath);
