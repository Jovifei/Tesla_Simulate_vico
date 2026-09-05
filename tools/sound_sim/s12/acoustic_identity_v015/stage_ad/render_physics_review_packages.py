"""
render_physics_review_packages.py
Batch renders all 10 standard evaluation cases for Ferrari 458 and Dodge Hellcat
using the physics-based engine acoustic simulator.
"""

import os
import shutil
import numpy as np
import scipy.io.wavfile as wavfile
from engine_sim_acoustics import EngineAcoustics

def generate_cases_for_vehicle(vehicle_type: str, out_dir: str):
    print(f"=== Rendering 10 Physics Cases for {vehicle_type.upper()} ===")
    sim = EngineAcoustics(vehicle_type=vehicle_type, sr=48000)
    sr = sim.sr
    
    web_audio_dir = os.path.join(out_dir, "web_audio")
    os.makedirs(web_audio_dir, exist_ok=True)
    
    is_ferrari = (vehicle_type == "ferrari_458")
    idle_rpm = 1000.0 if is_ferrari else 720.0
    redline_rpm = 9000.0 if is_ferrari else 6500.0
    pull_start = 2200.0 if is_ferrari else 1500.0
    pull_end = 8800.0 if is_ferrari else 6200.0
    
    cases = {}
    
    # 1. 01_afterfire (7.0s)
    dur = 7.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.zeros(N)
    # Ramp up to 70% redline in 2.0s, then cut to 0
    t_cut = 2.2
    mask_acc = t < t_cut
    rpm[mask_acc] = idle_rpm + (0.75 * redline_rpm - idle_rpm) * (t[mask_acc] / t_cut) ** 1.3
    thr[mask_acc] = 0.85
    # Decay back to idle
    mask_dec = t >= t_cut
    tau_dec = (t[mask_dec] - t_cut) / (dur - t_cut)
    rpm[mask_dec] = idle_rpm + (0.75 * redline_rpm - idle_rpm) * np.exp(-tau_dec * 3.5)
    thr[mask_dec] = 0.0
    # Afterfire pops
    af_events = [(2.5, 0.9), (2.8, 0.7), (3.2, 1.0), (3.6, 0.8), (4.2, 0.6), (4.9, 0.5), (5.5, 0.4)]
    cases["01_afterfire"] = (rpm, thr, dur, None, af_events)
    
    # 2. 02_full_pull (7.0s)
    dur = 7.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    # Full pull from pull_start to pull_end
    rpm = pull_start + (pull_end - pull_start) * ((t / dur) ** 1.15)
    thr = np.ones(N) * 1.0
    cases["02_full_pull"] = (rpm, thr, dur, None, None)
    
    # 3. 03_hot_idle (6.0s)
    dur = 6.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    # Subtle idle hunting (+-15 RPM)
    rpm = idle_rpm + 12.0 * np.sin(2.0 * np.pi * 0.4 * t) + 8.0 * np.sin(2.0 * np.pi * 0.9 * t)
    thr = np.zeros(N)
    cases["03_hot_idle"] = (rpm, thr, dur, None, None)
    
    # 4. 04_idle_return (6.0s)
    dur = 6.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.zeros(N)
    # Rev blip at t=1.0s to t=2.0s
    t1, t2 = 1.0, 2.2
    m1 = t < t1
    rpm[m1] = idle_rpm
    thr[m1] = 0.0
    m2 = (t >= t1) & (t < t2)
    blip_peak = 0.55 * redline_rpm
    rpm[m2] = idle_rpm + (blip_peak - idle_rpm) * np.sin(np.pi * (t[m2] - t1) / (t2 - t1))
    thr[m2] = 0.70 * np.sin(np.pi * (t[m2] - t1) / (t2 - t1))
    m3 = t >= t2
    tau = (t[m3] - t2) / (dur - t2)
    rpm[m3] = idle_rpm + (blip_peak - idle_rpm) * 0.2 * np.exp(-tau * 4.0)
    thr[m3] = 0.0
    cases["04_idle_return"] = (rpm, thr, dur, None, None)
    
    # 5. 05_lift (7.0s)
    dur = 7.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.zeros(N)
    # Cruise at high load until t=2.0s, then sudden lift
    t_lift = 2.0
    m_hold = t < t_lift
    rpm[m_hold] = 0.65 * redline_rpm
    thr[m_hold] = 0.60
    m_lift = t >= t_lift
    tau_lift = (t[m_lift] - t_lift) / (dur - t_lift)
    rpm[m_lift] = idle_rpm + (0.65 * redline_rpm - idle_rpm) * np.exp(-tau_lift * 2.5)
    thr[m_lift] = 0.0
    # Overrun pops
    af_events_lift = [(2.2, 0.6), (2.6, 0.8), (3.1, 0.5), (3.7, 0.4)]
    cases["05_lift"] = (rpm, thr, dur, None, af_events_lift)
    
    # 6. 06_shift (6.0s)
    dur = 6.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.ones(N) * 0.95
    # Accelerate in 1st gear to 2.8s, shift, drop RPM, accelerate in 2nd gear
    t_shift = 2.8
    shift_cut = 0.08 if is_ferrari else 0.12 # DCT vs 8AT
    m_g1 = t < t_shift
    rpm[m_g1] = 3000.0 + (0.85 * redline_rpm - 3000.0) * (t[m_g1] / t_shift)
    m_g2 = t >= t_shift
    rpm_after = 0.55 * redline_rpm
    rpm[m_g2] = rpm_after + (0.80 * redline_rpm - rpm_after) * ((t[m_g2] - t_shift) / (dur - t_shift))
    shift_events = [(t_shift, shift_cut)]
    cases["06_shift"] = (rpm, thr, dur, shift_events, None)
    
    # 7. 07_steady_high (6.0s)
    dur = 6.0
    N = int(sr * dur)
    rpm = np.ones(N) * (0.75 * redline_rpm)
    thr = np.ones(N) * 0.45
    cases["07_steady_high"] = (rpm, thr, dur, None, None)
    
    # 8. 08_steady_low (6.0s)
    dur = 6.0
    N = int(sr * dur)
    rpm = np.ones(N) * (idle_rpm + 800.0)
    thr = np.ones(N) * 0.20
    cases["08_steady_low"] = (rpm, thr, dur, None, None)
    
    # 9. 09_steady_mid (6.0s)
    dur = 6.0
    N = int(sr * dur)
    rpm = np.ones(N) * (0.45 * redline_rpm)
    thr = np.ones(N) * 0.35
    cases["09_steady_mid"] = (rpm, thr, dur, None, None)
    
    # 10. 10_tip_in (6.0s)
    dur = 6.0
    N = int(sr * dur)
    t = np.linspace(0, dur, N, endpoint=False)
    rpm = np.zeros(N)
    thr = np.zeros(N)
    # Low throttle cruising until t=2.0s, then instantaneous 100% WOT snap
    t_snap = 2.0
    m_pre = t < t_snap
    rpm[m_pre] = 2500.0 if is_ferrari else 1800.0
    thr[m_pre] = 0.15
    m_post = t >= t_snap
    # Rapid RPM acceleration post tip-in
    r_start = 2500.0 if is_ferrari else 1800.0
    rpm[m_post] = r_start + (0.85 * redline_rpm - r_start) * (((t[m_post] - t_snap) / (dur - t_snap)) ** 1.2)
    thr[m_post] = 1.0
    cases["10_tip_in"] = (rpm, thr, dur, None, None)
    
    # Render all cases
    for name, (r_curve, t_curve, d, s_ev, a_ev) in cases.items():
        print(f"  Rendering {name}.wav ...")
        audio_data = sim.render_track(
            rpm_curve=r_curve,
            throttle_curve=t_curve,
            duration=d,
            shift_events=s_ev,
            afterfire_events=a_ev
        )
        
        # Save to web_audio and out_dir root
        f_web = os.path.join(web_audio_dir, f"{name}.wav")
        f_root = os.path.join(out_dir, f"{name}.wav")
        wavfile.write(f_web, sr, audio_data)
        wavfile.write(f_root, sr, audio_data)
        
    print(f"Finished rendering all cases for {vehicle_type} into {out_dir}\n")

if __name__ == "__main__":
    ferrari_dir = r"E:\Tesla_speed\review_packages\s12-stage-ad-ferrari-458-closed-loop-v1"
    hellcat_dir = r"E:\Tesla_speed\review_packages\s12-stage-ad-hellcat-closed-loop-v1"
    
    generate_cases_for_vehicle("ferrari_458", ferrari_dir)
    generate_cases_for_vehicle("hellcat", hellcat_dir)
    print("All review packages successfully updated with physical acoustics!")
