function profile = c63_w204_v6_profile
%C63_W204_V6_PROFILE Return the independent C63 physical-acoustics profile.

profile = struct();
profile.schema = "jovi.engine_sound.v6";
profile.name = "c63_w204";
profile.display_name = "Mercedes-Benz W204 C63 AMG M156 V8";
profile.seed = 6306;
profile.audio.sample_rate_hz = 96000;
profile.audio.export_sample_rate_hz = 48000;
profile.audio.peak_limit = 0.89;
profile.audio.master_gain = 0.98;

profile.engine.cylinders = 8;
profile.engine.cycle_revolutions = 2;
profile.engine.displacement_l = 6.208;
profile.engine.bore_m = 0.1022;
profile.engine.stroke_m = 0.0946;
profile.engine.compression_ratio = 11.3;
profile.engine.idle_rpm = 700;
profile.engine.redline_rpm = 7200;
profile.engine.firing_order = [1, 5, 4, 2, 6, 3, 7, 8];
profile.engine.bank_by_cylinder = [1, 2, 1, 2, 1, 2, 1, 2];
profile.engine.torque_rpm = [700, 1500, 2500, 3500, 4500, 5000, 6000, 6800, 7200];
profile.engine.torque_nm = [280, 390, 500, 555, 590, 600, 550, 472, 430];
profile.engine.wiebe_a = 5.0;
profile.engine.wiebe_m = 2.0;
profile.engine.combustion_duration_deg = 48;
profile.engine.evo_deg_bbdc = 50;
profile.engine.equivalent_inertia_kgm2 = 0.22;

profile.driveline.gear_ratios = [4.38, 2.86, 1.92];
profile.driveline.final_drive = 2.85;
profile.driveline.wheel_radius_m = 0.335;
profile.driveline.launch_rpm = 2300;
profile.driveline.max_accel_mps2 = 7.2;
profile.driveline.shift_rpm = 7000;
profile.driveline.shift_attack_s = 0.018;
profile.driveline.shift_hold_s = 0.032;
profile.driveline.shift_recovery_s = 0.075;
profile.driveline.shift_settle_s = 0.055;
profile.driveline.shift_min_torque = 0.22;
profile.driveline.shift_reengage_gain = 1.08;

profile.ecu.full_load_spark_deg = [8, 16, 21, 24, 25];
profile.ecu.spark_rpm = [700, 2000, 4000, 6000, 7200];
profile.ecu.full_load_lambda = 0.87;
profile.ecu.dfco_throttle = 0.06;
profile.ecu.dfco_rpm = 2200;
profile.ecu.dfco_delay_s = 0.120;
profile.ecu.fuel_film_tau_s = 0.180;

profile.thermal.load_axis = [0.10, 0.40, 0.70, 1.00];
profile.thermal.rpm_axis = [700, 2000, 4000, 6000, 7200];
profile.thermal.egt_table_k = [ ...
    520, 560, 610, 650, 680; ...
    600, 660, 730, 790, 820; ...
    680, 750, 830, 900, 930; ...
    720, 810, 900, 970, 1000];
profile.thermal.cooling_tau_s = 1.8;
profile.thermal.gamma = 1.33;
profile.thermal.gas_constant = 287.0;

profile.blowdown.evo_pressure_pa = 350000;
profile.blowdown.exhaust_temperature_k = 1050;
profile.blowdown.valve_area_m2 = 750e-6;
profile.blowdown.attack_s = 0.00025;
profile.blowdown.fast_decay_s = 0.0018;
profile.blowdown.slow_decay_s = 0.0055;
profile.blowdown.fast_weight = 0.72;
profile.blowdown.pulse_sharpness = 54;

profile.exhaust.primary_left_m = [0.46, 0.50, 0.53, 0.57];
profile.exhaust.primary_right_m = [0.47, 0.49, 0.54, 0.56];
profile.exhaust.primary_diameter_m = 0.041;
profile.exhaust.collector_length_m = 0.24;
profile.exhaust.collector_diameter_m = 0.060;
profile.exhaust.catalyst_length_m = 0.28;
profile.exhaust.catalyst_diameter_m = 0.068;
profile.exhaust.midpipe_length_m = 1.15;
profile.exhaust.midpipe_diameter_m = 0.060;
profile.exhaust.muffler_main_length_m = 0.42;
profile.exhaust.muffler_bypass_length_m = 0.62;
profile.exhaust.tailpipe_length_m = 0.52;
profile.exhaust.tailpipe_diameter_m = 0.0635;
profile.exhaust.catalyst_reflection = -0.18;
profile.exhaust.catalyst_transmission = 0.72;
profile.exhaust.crossover_coupling = 0.20;
profile.exhaust.muffler_reflection = -0.42;
profile.exhaust.tail_reflection = -0.92;
profile.exhaust.loss_frequency_hz = [125, 500, 2000, 8000, 16000];
profile.exhaust.loss_db_per_m = [0.08, 0.18, 0.55, 1.80, 4.20];

profile.afterfire.egt_threshold_k = 760;
profile.afterfire.minimum_rpm = 2600;
profile.afterfire.overrun_duration_s = 1.25;
profile.afterfire.base_interval_s = 0.029;
profile.afterfire.cluster_size = 8;
profile.afterfire.calibration = "c63_w204";
profile.afterfire.body_hz = [92, 146, 178];
profile.afterfire.metal_hz = [425, 524, 624, 724, 882];
profile.afterfire.body_gain = 0.58;
profile.afterfire.metal_gain = 0.82;
profile.afterfire.crack_gain = 1.78;
profile.afterfire.attack_s = 0.00035;
profile.afterfire.body_decay_s = 0.060;
profile.afterfire.metal_decay_s = 0.018;
profile.afterfire.crack_decay_s = 0.003;

profile.mix.exhaust_gain = 5.2;
profile.mix.mechanical_gain = 0.55;
profile.mix.afterfire_gain = 0.72;
profile.mix.afterfire_peak_over_exhaust_db = 8.0;

profile.rasp.start_rpm = 1700;
profile.rasp.full_rpm = 5600;
profile.rasp.nonlinear_drive = 3.0;
profile.rasp.nonlinear_gain = 0.24;
profile.rasp.texture_gain = 0.058;
profile.rasp.jitter_gain = 0.22;
profile.rasp.jitter_hz = 120;
profile.rasp.highpass_hz = 1000;
profile.rasp.lowpass_hz = 8500;

profile.mechanical.orders = [32, 56, 88];
profile.mechanical.band_gain_db = [-32, -38, -44];
profile.mechanical.noise_gain_db = -48;

profile.propagation.direct_distance_m = 1.0;
profile.propagation.ground_delay_s = 0.0048;
profile.propagation.ground_gain = -0.45;
profile.propagation.body_delay_s = 0.0085;
profile.propagation.body_gain = -0.30;
end
