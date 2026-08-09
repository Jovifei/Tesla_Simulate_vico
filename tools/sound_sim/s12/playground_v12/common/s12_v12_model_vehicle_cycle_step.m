function state = s12_v12_model_vehicle_cycle_step(time, profileId)
%S12_V12_MODEL_VEHICLE_CYCLE_STEP Fixed-size Simulink cycle adapter.

if ~isnumeric(time) || ~isscalar(time) || ~isfinite(time)
    error("S12:EngineSoundV12:ModelVehicleCycle", ...
        "Simulation time must be one finite scalar.");
end
vehicleState = s12_v12_vehicle_cycle_state(double(time), string(profileId));
state = [vehicleState; double(time)];
end
