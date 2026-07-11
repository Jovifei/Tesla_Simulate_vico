function profile = vehicle_profile(profileName)
%VEHICLE_PROFILE Return one evidence-based engine and drivetrain profile.

name = lower(string(profileName));
switch name
    case "hellcat"
        profile = base_profile(name, "Dodge Hellcat 6.2 Supercharged V8", 8, 750, 6200, 1101);
        profile.induction = "supercharger";
        profile.firing_order = [1, 8, 4, 3, 6, 5, 7, 2];
        profile.bank_by_cylinder = [1, 2, 1, 2, 1, 2, 1, 2];
        profile.pulse_sharpness = 22;
        profile.resonance_hz = [72, 145, 290, 580];
        profile.resonance_q = [1.3, 1.9, 2.8, 4.0];
        profile.resonance_gain = [0.62, 0.48, 0.26, 0.10];
        profile.induction_gain = 0.26;
        profile.induction_order = 26;
        profile.backfire_style = "low_boom";
        profile.shift_style = "zf_burble";
        profile.gear_ratios = [4.714, 3.143, 2.106];
        profile.final_drive = 2.62;
        profile.wheel_radius_m = 0.347;
        profile.shift_rpm = 6100;
        profile.shift_duration_s = 0.16;
        profile.shift_cut_s = 0.065;
        profile.launch_rpm = 2100;
        profile.max_accel_mps2 = 7.8;
        profile.backfire_overrun_s = 1.20;
        profile.shift_reengage_gain = 1.10;
    case "gtr_r35"
        profile = base_profile(name, "Nissan R35 GT-R VR38DETT", 6, 700, 7000, 2302);
        profile.induction = "twin_turbo";
        profile.firing_order = [1, 2, 3, 4, 5, 6];
        profile.bank_by_cylinder = [1, 2, 1, 2, 1, 2];
        profile.pulse_sharpness = 17;
        profile.resonance_hz = [112, 225, 455, 910];
        profile.resonance_q = [1.5, 2.2, 3.2, 4.8];
        profile.resonance_gain = [0.25, 0.48, 0.42, 0.22];
        profile.induction_gain = 0.24;
        profile.induction_order = 0;
        profile.backfire_style = "metallic_crackle";
        profile.shift_style = "dct_cut";
        profile.gear_ratios = [4.056, 2.301, 1.595];
        profile.final_drive = 3.700;
        profile.wheel_radius_m = 0.349;
        profile.shift_rpm = 6800;
        profile.shift_duration_s = 0.09;
        profile.shift_cut_s = 0.040;
        profile.launch_rpm = 3500;
        profile.max_accel_mps2 = 9.4;
        profile.backfire_overrun_s = 0.75;
        profile.shift_reengage_gain = 1.04;
    case "c63_w204"
        profile = base_profile(name, "Mercedes-Benz W204 C63 6.2 V8", 8, 700, 7200, 3303);
        profile.induction = "naturally_aspirated";
        profile.firing_order = [1, 5, 4, 2, 6, 3, 7, 8];
        profile.bank_by_cylinder = [1, 2, 1, 2, 1, 2, 1, 2];
        profile.pulse_sharpness = 34;
        profile.resonance_hz = [88, 178, 355, 710, 1420];
        profile.resonance_q = [1.4, 2.1, 3.1, 4.5, 5.5];
        profile.resonance_gain = [0.34, 0.54, 0.46, 0.31, 0.16];
        profile.induction_gain = 0.18;
        profile.induction_order = 4;
        profile.backfire_style = "amg_bang";
        profile.shift_style = "mct_bark";
        profile.gear_ratios = [4.38, 2.86, 1.92];
        profile.final_drive = 2.85;
        profile.wheel_radius_m = 0.335;
        profile.shift_rpm = 7000;
        profile.shift_duration_s = 0.11;
        profile.shift_cut_s = 0.10;
        profile.launch_rpm = 2300;
        profile.max_accel_mps2 = 7.2;
        profile.backfire_overrun_s = 1.25;
        profile.shift_reengage_gain = 1.12;
        profile.texture_noise_gain = 0.012;
    case "supra_jza80"
        profile = base_profile(name, "Toyota Supra JZA80 2JZ-GTE", 6, 700, 6800, 4404);
        profile.layout = "inline_6";
        profile.induction = "sequential_turbo";
        profile.firing_order = [1, 5, 3, 6, 2, 4];
        profile.bank_by_cylinder = ones(1, 6);
        profile.pulse_sharpness = 20;
        profile.resonance_hz = [92, 184, 370, 740, 1480];
        profile.resonance_q = [1.5, 2.1, 3.2, 4.2, 5.2];
        profile.resonance_gain = [0.30, 0.52, 0.46, 0.24, 0.10];
        profile.induction_gain = 0.22;
        profile.backfire_style = "turbo_burble";
        profile.shift_style = "manual_clutch";
        profile.gear_ratios = [3.827, 2.360, 1.685];
        profile.final_drive = 3.133;
        profile.wheel_radius_m = 0.3175;
        profile.shift_rpm = 6650;
        profile.shift_duration_s = 0.18;
        profile.launch_rpm = 2600;
        profile.max_accel_mps2 = 6.2;
        profile.backfire_overrun_s = 1.10;
        profile.shift_reengage_gain = 1.14;
    case "corvette_ls3"
        profile = base_profile(name, "Chevrolet Corvette C6 LS3 V8", 8, 650, 6500, 9909);
        profile.layout = "cross_plane_v8";
        profile.induction = "naturally_aspirated";
        profile.firing_order = [1, 8, 7, 2, 6, 5, 4, 3];
        profile.bank_by_cylinder = [1, 2, 1, 2, 1, 2, 1, 2];
        profile.pulse_sharpness = 24;
        profile.resonance_hz = [62, 124, 248, 496, 992];
        profile.resonance_q = [1.2, 1.8, 2.7, 3.8, 5.0];
        profile.resonance_gain = [0.66, 0.50, 0.30, 0.14, 0.06];
        profile.induction_gain = 0.15;
        profile.induction_order = 4;
        profile.backfire_style = "american_v8_burble";
        profile.backfire_calibration = "hellcat";
        profile.shift_style = "manual_clutch";
        profile.gear_ratios = [2.97, 2.07, 1.43];
        profile.final_drive = 3.42;
        profile.wheel_radius_m = 0.33909;
        profile.shift_rpm = 6350;
        profile.shift_duration_s = 0.18;
        profile.launch_rpm = 2200;
        profile.max_accel_mps2 = 6.8;
        profile.backfire_overrun_s = 1.0;
        profile.shift_reengage_gain = 1.14;
        profile.texture_noise_gain = 0.006;
    case "rx7_fd"
        profile = base_profile(name, "Mazda RX-7 FD 13B-REW", 6, 850, 8000, 5505);
        profile.layout = "twin_rotor";
        profile.cycle_revolutions = 3;
        profile.induction = "sequential_turbo";
        profile.firing_order = 1:6;
        profile.bank_by_cylinder = [1, 2, 1, 2, 1, 2];
        profile.pulse_sharpness = 42;
        profile.resonance_hz = [118, 236, 472, 945, 1890];
        profile.resonance_q = [1.4, 2.0, 3.0, 4.4, 5.8];
        profile.resonance_gain = [0.18, 0.36, 0.56, 0.38, 0.17];
        profile.induction_gain = 0.20;
        profile.backfire_style = "rotary_flame";
        profile.shift_style = "manual_clutch";
        profile.gear_ratios = [3.483, 2.015, 1.391];
        profile.final_drive = 4.10;
        profile.wheel_radius_m = 0.316;
        profile.shift_rpm = 7800;
        profile.shift_duration_s = 0.17;
        profile.launch_rpm = 3200;
        profile.max_accel_mps2 = 6.5;
        profile.backfire_overrun_s = 1.45;
        profile.shift_reengage_gain = 1.15;
    case "lexus_lfa"
        profile = base_profile(name, "Lexus LFA 1LR-GUE V10", 10, 800, 9000, 6606);
        profile.layout = "v10_72";
        profile.induction = "naturally_aspirated";
        profile.firing_order = [1, 2, 3, 4, 7, 8, 9, 10, 5, 6];
        profile.bank_by_cylinder = [1, 2, 1, 2, 1, 2, 1, 2, 1, 2];
        profile.pulse_sharpness = 30;
        profile.resonance_hz = [180, 360, 720, 1440, 2880];
        profile.resonance_q = [1.8, 2.8, 4.2, 6.0, 8.0];
        profile.resonance_gain = [0.16, 0.34, 0.58, 0.54, 0.25];
        profile.induction_gain = 0.25;
        profile.induction_order = 5;
        profile.backfire_style = "v10_overrun";
        profile.shift_style = "asg_jerk";
        profile.gear_ratios = [3.231, 2.188, 1.609];
        profile.final_drive = 4.30;
        profile.wheel_radius_m = 0.34544;
        profile.shift_rpm = 8800;
        profile.shift_duration_s = 0.20;
        profile.launch_rpm = 3000;
        profile.max_accel_mps2 = 8.2;
        profile.backfire_overrun_s = 0.55;
        profile.shift_reengage_gain = 1.18;
        profile.texture_noise_gain = 0.006;
    case "ferrari_458"
        profile = base_profile(name, "Ferrari 458 Italia F136 F V8", 8, 900, 9000, 7707);
        profile.layout = "flat_plane_v8";
        profile.induction = "naturally_aspirated";
        profile.firing_order = [1, 5, 3, 7, 4, 8, 2, 6];
        profile.bank_by_cylinder = [1, 1, 1, 1, 2, 2, 2, 2];
        profile.pulse_sharpness = 38;
        profile.resonance_hz = [165, 330, 660, 1320, 2640];
        profile.resonance_q = [1.7, 2.7, 4.0, 5.8, 7.5];
        profile.resonance_gain = [0.15, 0.33, 0.57, 0.48, 0.22];
        profile.induction_gain = 0.22;
        profile.induction_order = 4;
        profile.backfire_style = "flatplane_crack";
        profile.shift_style = "f1_dct";
        profile.gear_ratios = [3.08, 2.19, 1.63];
        profile.final_drive = 5.14;
        profile.wheel_radius_m = 0.357;
        profile.shift_rpm = 8800;
        profile.shift_duration_s = 0.065;
        profile.launch_rpm = 3500;
        profile.max_accel_mps2 = 9.0;
        profile.backfire_overrun_s = 0.90;
        profile.shift_reengage_gain = 1.06;
        profile.texture_noise_gain = 0.008;
    case "aventador_lp700"
        profile = base_profile(name, "Lamborghini Aventador LP700-4 L539 V12", 12, 850, 8000, 8808);
        profile.layout = "v12_60";
        profile.induction = "naturally_aspirated";
        profile.firing_order = [1, 12, 4, 9, 2, 11, 6, 7, 3, 10, 5, 8];
        profile.bank_by_cylinder = [1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2];
        profile.pulse_sharpness = 28;
        profile.resonance_hz = [135, 270, 540, 1080, 2160];
        profile.resonance_q = [1.6, 2.5, 3.8, 5.3, 7.0];
        profile.resonance_gain = [0.24, 0.43, 0.55, 0.37, 0.16];
        profile.induction_gain = 0.20;
        profile.induction_order = 6;
        profile.backfire_style = "v12_bark";
        profile.shift_style = "isr_kick";
        profile.gear_ratios = [3.909, 2.438, 1.810];
        profile.final_drive = 3.54;
        profile.wheel_radius_m = 0.3545;
        profile.shift_rpm = 7850;
        profile.shift_duration_s = 0.12;
        profile.launch_rpm = 3200;
        profile.max_accel_mps2 = 8.8;
        profile.backfire_overrun_s = 0.70;
        profile.shift_reengage_gain = 1.16;
        profile.texture_noise_gain = 0.008;
    otherwise
        error("jovi:sound:UnknownProfile", "Unknown vehicle profile: %s", name);
end
end

function profile = base_profile(name, displayName, cylinders, idleRpm, redlineRpm, seed)
profile = struct( ...
    "name", name, ...
    "display_name", string(displayName), ...
    "cylinders", cylinders, ...
    "layout", "piston", ...
    "cycle_revolutions", 2, ...
    "idle_rpm", idleRpm, ...
    "redline_rpm", redlineRpm, ...
    "seed", seed, ...
    "induction", "", ...
    "firing_order", [], ...
    "bank_by_cylinder", [], ...
    "pulse_sharpness", 20, ...
    "resonance_hz", [], ...
    "resonance_q", [], ...
    "resonance_gain", [], ...
    "induction_gain", 0, ...
    "induction_order", 0, ...
    "backfire_style", "", ...
    "backfire_calibration", name, ...
    "backfire_enabled", true, ...
    "shift_style", "", ...
    "gear_ratios", [], ...
    "final_drive", 1, ...
    "wheel_radius_m", 0.34, ...
    "shift_rpm", redlineRpm - 150, ...
    "shift_duration_s", 0.1, ...
    "shift_cut_s", 0.06, ...
    "launch_rpm", 2200, ...
    "max_accel_mps2", 7.0);
profile.backfire_overrun_s = 0.8;
profile.shift_reengage_gain = 1.08;
profile.texture_noise_gain = 0.02;
end
