function profile = hellcat_v6_profile
%HELLCAT_V6_PROFILE Return the independent Hellcat physical-acoustics profile.

profile = struct();
profile.schema = "jovi.engine_sound.v6";
profile.name = "hellcat";
profile.display_name = "Dodge Challenger SRT Hellcat 6.2 Supercharged V8";
profile.seed = 6208;
profile.audio.sample_rate_hz = 96000;
profile.audio.export_sample_rate_hz = 48000;
profile.audio.peak_limit = 0.89;
profile.audio.master_gain = 0.86;

profile.engine.cylinders = 8;
profile.engine.cycle_revolutions = 2;
profile.engine.displacement_l = 6.166;
profile.engine.bore_m = 0.1039;
profile.engine.stroke_m = 0.0909;
profile.engine.compression_ratio = 9.5;
profile.engine.idle_rpm = 750;
profile.engine.redline_rpm = 6200;
profile.engine.firing_order = [1, 8, 4, 3, 6, 5, 7, 2];
profile.engine.bank_by_cylinder = [1, 2, 1, 2, 1, 2, 1, 2];
profile.engine.torque_rpm = [750, 1500, 2500, 3500, 4000, 5000, 5800, 6200];
profile.engine.torque_nm = [420, 610, 790, 860, 881, 850, 770, 700];
profile.engine.wiebe_a = 5.0;
profile.engine.wiebe_m = 2.0;
profile.engine.combustion_duration_deg = 52;
profile.engine.evo_deg_bbdc = 48;
profile.engine.equivalent_inertia_kgm2 = 0.28;

profile.driveline.gear_ratios = [4.714, 3.143, 2.106];
profile.driveline.final_drive = 2.62;
profile.driveline.wheel_radius_m = 0.347;
profile.driveline.launch_rpm = 2100;
profile.driveline.max_accel_mps2 = 7.8;
profile.driveline.shift_rpm = 6100;
profile.driveline.shift_attack_s = 0.025;
profile.driveline.shift_hold_s = 0.045;
profile.driveline.shift_recovery_s = 0.090;
profile.driveline.shift_settle_s = 0.060;
profile.driveline.shift_min_torque = 0.10;
profile.driveline.shift_reengage_gain = 1.10;

profile.ecu.full_load_spark_deg = [6, 11, 15, 17, 18];
profile.ecu.spark_rpm = [750, 2000, 3500, 5000, 6200];
profile.ecu.full_load_lambda = 0.80;
profile.ecu.dfco_throttle = 0.06;
profile.ecu.dfco_rpm = 2200;
profile.ecu.dfco_delay_s = 0.120;
profile.ecu.fuel_film_tau_s = 0.180;

profile.thermal.load_axis = [0.10, 0.40, 0.70, 1.00];
profile.thermal.rpm_axis = [750, 2000, 3500, 5000, 6200];
profile.thermal.egt_table_k = [ ...
    520, 560, 610, 650, 680; ...
    600, 660, 730, 790, 820; ...
    680, 750, 830, 900, 930; ...
    740, 840, 930, 1010, 1050];
profile.thermal.cooling_tau_s = 1.8;
profile.thermal.gamma = 1.33;
profile.thermal.gas_constant = 287.0;

profile.blowdown.evo_pressure_pa = 430000;
profile.blowdown.exhaust_temperature_k = 1100;
profile.blowdown.valve_area_m2 = 850e-6;
profile.blowdown.attack_s = 0.00025;
profile.blowdown.fast_decay_s = 0.0018;
profile.blowdown.slow_decay_s = 0.0055;
profile.blowdown.fast_weight = 0.72;
profile.blowdown.pulse_sharpness = 30;

profile.combustion_variation.start_rpm = 1200;
profile.combustion_variation.full_rpm = 4500;
profile.combustion_variation.depth = 0.16;
profile.combustion_variation.correlation = 0.40;
profile.combustion_variation.timing_jitter_deg = 1.8;
profile.combustion_variation.timing_correlation = 0.25;
profile.combustion_variation.notch_probability = 0.045;
profile.combustion_variation.notch_depth = 0.35;
profile.combustion_variation.minimum_gain = 0.50;
profile.combustion_variation.maximum_gain = 1.35;
profile.combustion_variation.cylinder_gain = ...
    [1.04, 0.95, 1.00, 0.94, 1.03, 0.97, 1.01, 0.96];

profile.exhaust.primary_left_m = [0.42, 0.47, 0.52, 0.56];
profile.exhaust.primary_right_m = [0.43, 0.46, 0.53, 0.55];
profile.exhaust.primary_diameter_m = 0.044;
profile.exhaust.collector_length_m = 0.27;
profile.exhaust.collector_diameter_m = 0.066;
profile.exhaust.catalyst_length_m = 0.31;
profile.exhaust.catalyst_diameter_m = 0.072;
profile.exhaust.midpipe_length_m = 1.32;
profile.exhaust.midpipe_diameter_m = 0.070;
profile.exhaust.muffler_main_length_m = 0.48;
profile.exhaust.muffler_bypass_length_m = 0.68;
profile.exhaust.tailpipe_length_m = 0.58;
profile.exhaust.tailpipe_diameter_m = 0.076;
profile.exhaust.catalyst_reflection = -0.22;
profile.exhaust.catalyst_transmission = 0.68;
profile.exhaust.crossover_coupling = 0.14;
profile.exhaust.muffler_reflection = -0.50;
profile.exhaust.tail_reflection = -0.88;
profile.exhaust.loss_frequency_hz = [125, 500, 2000, 8000, 16000];
profile.exhaust.loss_db_per_m = [0.08, 0.18, 0.55, 1.80, 4.20];
profile.exhaust.dry_gain = 0.10;
profile.exhaust.body_modes_hz = [62, 76, 145, 246];
profile.exhaust.body_q = [1.1, 1.4, 1.9, 2.5];
profile.exhaust.body_gain = [4.00, 3.00, 0.10, 0.00];

profile.afterfire.egt_threshold_k = 800;
profile.afterfire.minimum_rpm = 2400;
profile.afterfire.overrun_duration_s = 0.90;
profile.afterfire.base_interval_s = 0.080;
profile.afterfire.cluster_size = 5;
profile.afterfire.calibration = "hellcat";
profile.afterfire.body_hz = [72, 145, 246];
profile.afterfire.metal_hz = [246, 340, 434, 545];
profile.afterfire.body_gain = 1.10;
profile.afterfire.metal_gain = 0.38;
profile.afterfire.crack_gain = 0.62;
profile.afterfire.attack_s = 0.0047;
profile.afterfire.body_decay_s = 0.120;
profile.afterfire.metal_decay_s = 0.045;
profile.afterfire.crack_decay_s = 0.006;

profile.mix.exhaust_gain = 4.0;
profile.mix.mechanical_gain = 0.65;
profile.mix.afterfire_gain = 0.58;
profile.mix.afterfire_peak_over_exhaust_db = 8.5;

profile.rasp.start_rpm = 1400;
profile.rasp.full_rpm = 4800;
profile.rasp.nonlinear_drive = 2.4;
profile.rasp.nonlinear_gain = 0.045;
profile.rasp.texture_gain = 0.004;
profile.rasp.jitter_gain = 0.16;
profile.rasp.jitter_hz = 90;
profile.rasp.highpass_hz = 550;
profile.rasp.lowpass_hz = 4500;

profile.induction.enabled = true;
profile.induction.speed_ratio = 2.36;
profile.induction.start_rpm = 1500;
profile.induction.orders = [3, 6, 9, 12];
profile.induction.gains = [0.165, 0.330, 0.242, 0.132];

profile.mechanical.orders = [24, 40, 64];
profile.mechanical.band_gain_db = [-34, -40, -46];
profile.mechanical.noise_gain_db = -50;

profile.propagation.direct_distance_m = 1.0;
profile.propagation.ground_delay_s = 0.0048;
profile.propagation.ground_gain = -0.45;
profile.propagation.body_delay_s = 0.0085;
profile.propagation.body_gain = -0.30;
end
