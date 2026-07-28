function profile = s12_engine_sound_assign_model_workspace(model, profileInput, backfireLevel)
%S12_ENGINE_SOUND_ASSIGN_MODEL_WORKSPACE Bind one JSON profile to one top model.

model = string(model);
if ~isscalar(model) || strlength(model) == 0
    error("S12:EngineSoundV10:ModelName", "Model must be one nonempty text scalar.");
end
if ~bdIsLoaded(model)
    load_system(model);
end
if isstruct(profileInput)
    profile = profileInput;
    s12_engine_sound_validate_profile(profile);
else
    profile = s12_engine_sound_load_profile(profileInput);
end
sources = s12_engine_sound_simulink_sources(profile, backfireLevel);
workspace = get_param(model, "ModelWorkspace");
assignin(workspace, "v10_profile_id", profile.profile_id.value);
assignin(workspace, "v10_cylinder_count", profile.engine.cylinder_count.value);
assignin(workspace, "v10_firing_order", profile.engine.firing_order.value);
assignin(workspace, "v10_firing_phase_deg", profile.engine.firing_phase_deg.value);
assignin(workspace, "v10_bank_map", profile.engine.bank_map.value);
assignin(workspace, "v10_order_gains", profile.synthesis.order_gains.value);
assignin(workspace, "v10_pulse_sharpness", profile.synthesis.pulse_sharpness.value);
assignin(workspace, "v10_harmonic_tilt", profile.synthesis.harmonic_tilt.value);
assignin(workspace, "v10_intake_tone", profile.synthesis.intake_tone.value);
assignin(workspace, "v10_supercharger_tone", profile.synthesis.supercharger_tone.value);
assignin(workspace, "v10_attack", profile.transient.attack.value);
assignin(workspace, "v10_decay", profile.transient.decay.value);
assignin(workspace, "v10_acceleration_gain", profile.transient.acceleration_gain.value);
assignin(workspace, "v10_lift_gain", profile.transient.lift_gain.value);
assignin(workspace, "v10_pipe_length_m", profile.ptr.pipe_length_m.value);
assignin(workspace, "v10_area_m2", profile.ptr.area_m2.value);
assignin(workspace, "v10_reflection", profile.ptr.reflection_coefficient.value);
assignin(workspace, "v10_damping", profile.ptr.damping.value);
assignin(workspace, "v10_gain_db", profile.renderer.gain_db.value);
assignin(workspace, "v10_interactive_mode", false);
assignin(workspace, "v10_dashboard_rpm", profile.engine.idle_rpm.value);
assignin(workspace, "v10_dashboard_load", 0.10);
assignin(workspace, "v10_dashboard_acceleration", 0.0);
assignin(workspace, "v10_dashboard_throttle", 0.10);
assignin(workspace, "v10_dashboard_speed_kph", 0.0);
assignin(workspace, "v10_dashboard_overrun", 0.0);
assignin(workspace, "v10_dashboard_order_balance", 1.0);
assignin(workspace, "v10_dashboard_transient_scale", 1.0);
assignin(workspace, "v10_dashboard_backfire_scale", 1.0);
assignin(workspace, "v10_vehicle_state", sources.vehicle_state);
assignin(workspace, "v10_reset", sources.reset);
assignin(workspace, "v10_backfire", sources.backfire_energy);
end
