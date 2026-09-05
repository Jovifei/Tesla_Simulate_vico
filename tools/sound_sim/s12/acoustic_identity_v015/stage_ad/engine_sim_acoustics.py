"""
engine_sim_acoustics.py - Physics-based Engine Acoustic Simulator
Ported and synthesized from AngeTheGreat Engine Simulator (C++) acoustics pipeline:
- Physical cylinder blowdown pressure shockwave generation
- Variable RPM cycle phase integration (720 deg 4-stroke)
- Exact crankshaft throw angles & cylinder firing order (Flat-plane V8 vs Cross-plane V8)
- Exhaust primary runner propagation delays (speed of sound)
- Acoustic velocity derivative df/dt + 2000 Hz turbulence flow noise modulation
- Authentic exhaust impulse response FFT convolution (mild_exhaust_reverb, test_engine_16)
- Load-dependent throttle response, DCT/8AT shift ignition cut, overrun crackles & afterfire
- Hellcat twin-screw supercharger whine synthesis
"""

import os
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal

SOUND_LIB_DIR = r"E:\project\engine-sim\runtime\v0.1.11a\engine-sim-build_0_1_11a\es\sound-library"

def load_impulse_response(ir_name: str, target_sr: int = 48000, max_samples: int = 12000) -> np.ndarray:
    """Load an impulse response from the engine-sim sound library and resample to target_sr."""
    candidates = [
        os.path.join(SOUND_LIB_DIR, "new", f"{ir_name}.wav"),
        os.path.join(SOUND_LIB_DIR, "archive", f"{ir_name}.wav"),
        os.path.join(SOUND_LIB_DIR, "smooth", f"{ir_name}.wav"),
        os.path.join(SOUND_LIB_DIR, f"{ir_name}.wav")
    ]
    path = None
    for c in candidates:
        if os.path.exists(c):
            path = c
            break
    if path is None:
        raise FileNotFoundError(f"Could not find impulse response: {ir_name} in {SOUND_LIB_DIR}")
    
    sr, data = wavfile.read(path)
    if data.ndim > 1:
        data = data[:, 0]
    data = data.astype(np.float64) / 32768.0
    
    if sr != target_sr:
        num_samples = int(len(data) * target_sr / sr)
        data = signal.resample(data, num_samples)
        
    data = data[:min(len(data), max_samples)]
    return data

class EngineAcoustics:
    def __init__(self, vehicle_type: str = "ferrari_458", sr: int = 48000):
        self.sr = sr
        self.vehicle_type = vehicle_type
        
        if vehicle_type == "ferrari_458":
            # 4.5L Flat-plane V8 (Ferrari F136 FL)
            # Firing Order: 1-5-3-7-4-8-2-6
            # Cylinders: 8
            # Even 90 deg overall, alternating banks: L(1,2,3,4) - R(5,6,7,8)
            # Crank angles (0 to 720 deg):
            self.firing_angles = np.array([0, 540, 180, 360, 90, 630, 270, 450], dtype=np.float64) * (np.pi / 180.0)
            # Bank index per cylinder: 0=Left, 1=Right
            self.cyl_bank = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=int)
            # Primary runner lengths (meters) from 08_ferrari_f136_v8.mr
            self.primary_lengths = np.array([0.02, 0.01, 0.03, 0.05, 0.01, 0.05, 0.07, 0.00], dtype=np.float64)
            self.exhaust_length = 2.54 # 100 inches in meters
            self.has_supercharger = False
            self.redline = 9000.0
            self.ir = load_impulse_response("mild_exhaust_reverb", target_sr=sr, max_samples=12000)
            self.ir_volume = 0.015
            self.dF_F_mix = 0.012
            self.air_noise_amount = 0.70
            self.exhaust_gain = 1.6
            self.mechanical_resonance_freq = 135.0
            
        elif vehicle_type == "hellcat":
            # 6.2L Supercharged Cross-plane V8 (HEMI Hellcat)
            # Firing Order: 1-8-7-2-6-5-4-3 (GM LS / HEMI standard)
            # Cylinders: 8
            # Firing angles:
            # 1: 0 deg
            # 8: 90 deg
            # 7: 180 deg
            # 2: 270 deg
            # 6: 360 deg
            # 5: 450 deg
            # 4: 540 deg
            # 3: 630 deg
            self.firing_angles = np.array([0, 270, 630, 540, 450, 360, 180, 90], dtype=np.float64) * (np.pi / 180.0)
            self.cyl_bank = np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype=int)
            self.primary_lengths = np.array([0.05, 0.02, 0.04, 0.06, 0.03, 0.05, 0.02, 0.04], dtype=np.float64)
            self.exhaust_length = 2.80 # meters (large muscle car exhaust)
            self.has_supercharger = True
            self.redline = 6500.0
            # Use test_engine_16 / mild_exhaust for deep chest rumble
            self.ir = load_impulse_response("test_engine_16_eq_adjusted_16", target_sr=sr, max_samples=12000)
            self.ir_volume = 0.012
            self.dF_F_mix = 0.018
            self.air_noise_amount = 0.85
            self.exhaust_gain = 2.2
            self.mechanical_resonance_freq = 95.0
        else:
            raise ValueError(f"Unknown vehicle type: {vehicle_type}")

        # Precompute delays
        c_sound = 343.0
        self.delays_sec = (self.primary_lengths + self.exhaust_length) / c_sound

    def render_track(self, rpm_curve: np.ndarray, throttle_curve: np.ndarray, duration: float, 
                     shift_events: list = None, afterfire_events: list = None) -> np.ndarray:
        """
        Synthesize full track audio given RPM and throttle trajectories over duration.
        """
        N = int(self.sr * duration)
        t = np.linspace(0, duration, N, endpoint=False)
        
        # Ensure curves have length N
        if len(rpm_curve) != N:
            rpm_curve = np.interp(np.linspace(0, 1, N), np.linspace(0, 1, len(rpm_curve)), rpm_curve)
        if len(throttle_curve) != N:
            throttle_curve = np.interp(np.linspace(0, 1, N), np.linspace(0, 1, len(throttle_curve)), throttle_curve)
            
        # 4-stroke cycle frequency f_cycle = (RPM / 60) / 2
        f_cycle = (rpm_curve / 60.0) / 2.0
        cycle_phase = 2.0 * np.pi * np.cumsum(f_cycle) / self.sr
        
        # Cylinder combustion variability (subtle 0.5% jitter to avoid sterile comb filter)
        rng = np.random.RandomState(42)
        cyl_gain_jitter = 1.0 + rng.normal(0.0, 0.04, 8)
        
        bank_signals = [np.zeros(N, dtype=np.float64), np.zeros(N, dtype=np.float64)]
        
        # Calculate pressure pulse for each cylinder
        for cyl in range(8):
            cyl_angle = (cycle_phase - self.firing_angles[cyl]) % (2.0 * np.pi)
            
            # Exhaust valve opens at ~140 deg ATDC
            ev_center = 1.0 * np.pi
            rel_angle = (cyl_angle - ev_center) % (2.0 * np.pi)
            
            pulse = np.zeros(N, dtype=np.float64)
            pulse_width = 0.85 # radians (~48 degrees crank)
            active_mask = rel_angle < pulse_width
            tau = rel_angle[active_mask] / pulse_width
            
            # Asymmetric physical blowdown pulse shape: steep rise (0.12), exponential decay (0.24)
            pulse_shape = (tau / 0.12) * np.exp(-(tau - 0.12) / 0.24) + 0.15 * np.sin(np.pi * tau)
            
            # Scale pulse amplitude by engine load/throttle
            load_factor = 0.35 + 0.65 * (throttle_curve[active_mask] ** 0.8)
            pulse[active_mask] = np.maximum(0.0, pulse_shape * load_factor * cyl_gain_jitter[cyl])
            
            # Apply primary runner delay
            delay_samples = int(self.delays_sec[cyl] * self.sr)
            delayed_pulse = np.roll(pulse, delay_samples)
            
            bank = self.cyl_bank[cyl]
            bank_signals[bank] += delayed_pulse
            
        # Combine dual banks with spatial stereo separation
        left_raw = bank_signals[0] + 0.35 * bank_signals[1]
        right_raw = bank_signals[1] + 0.35 * bank_signals[0]
        
        # Apply shift ignition cut (momentary silence followed by torque pop)
        shift_mask = np.ones(N, dtype=np.float64)
        shift_pops = np.zeros(N, dtype=np.float64)
        if shift_events:
            for s_time, s_dur in shift_events:
                s_idx = int(s_time * self.sr)
                d_len = int(s_dur * self.sr)
                if s_idx < N:
                    cut_len = min(d_len, N - s_idx)
                    window = 0.5 * (1.0 - np.cos(2.0 * np.pi * np.linspace(0, 1, cut_len)))
                    shift_mask[s_idx:s_idx + cut_len] *= (0.05 + 0.95 * window)
                    crack_idx = min(s_idx + cut_len, N - 1)
                    crack_len = int(0.04 * self.sr)
                    if crack_idx + crack_len < N:
                        shift_pops[crack_idx:crack_idx + crack_len] += (
                            np.random.normal(0, 1.2, crack_len) * np.exp(-np.linspace(0, 5, crack_len))
                        )
                        
        left_raw = left_raw * shift_mask + shift_pops
        right_raw = right_raw * shift_mask + shift_pops
        
        # Apply afterfire crackles and pops on overrun/lift
        afterfire_pops = np.zeros(N, dtype=np.float64)
        if afterfire_events:
            for af_time, af_intensity in afterfire_events:
                af_idx = int(af_time * self.sr)
                pop_len = int(0.06 * self.sr)
                if af_idx + pop_len < N:
                    pop_wave = np.random.normal(0, af_intensity * 2.5, pop_len) * np.exp(-np.linspace(0, 6, pop_len))
                    afterfire_pops[af_idx:af_idx + pop_len] += pop_wave
                    
        left_raw += afterfire_pops
        right_raw += afterfire_pops
        
        # Process channels through Engine Simulator Synthesizer acoustic pipeline
        out_left = self._synthesize_channel(left_raw, t, throttle_curve, rpm_curve)
        out_right = self._synthesize_channel(right_raw, t, throttle_curve, rpm_curve)
        
        # Add Hellcat supercharger whine if applicable
        if self.has_supercharger:
            sc_drive_ratio = 2.36
            sc_rev_freq = (rpm_curve / 60.0) * sc_drive_ratio
            sc_phase = 2.0 * np.pi * np.cumsum(sc_rev_freq) / self.sr
            
            whine_gain = 0.08 * (throttle_curve ** 1.5) + 0.015 * (rpm_curve / self.redline)
            
            sc_tone = (
                0.60 * np.sin(3.0 * sc_phase) +
                0.40 * np.sin(5.0 * sc_phase + 0.5) +
                0.25 * np.sin(7.08 * sc_phase + 1.2) +
                0.15 * np.sin(11.8 * sc_phase + 2.1)
            ) * whine_gain
            
            whine_rasp = np.random.normal(0.0, 0.1, N) * whine_gain * np.sin(3.0 * sc_phase)
            
            out_left += (sc_tone + whine_rasp)
            out_right += (sc_tone + whine_rasp)
            
        # Add deep mechanical bass chest-resonator (40-100 Hz physical tube acoustic resonance)
        firing_freq = (rpm_curve / 60.0) * 4.0
        bass_phase = 2.0 * np.pi * np.cumsum(firing_freq) / self.sr
        bank_phase = bass_phase * 0.5
        
        bass_body = (
            0.50 * np.sin(bass_phase) + 
            0.35 * np.sin(bank_phase + 0.4) + 
            0.15 * np.sin(bass_phase * 2.0)
        ) * (0.45 + 0.55 * throttle_curve) * (self.exhaust_gain * 0.18)
        
        out_left += bass_body
        out_right += np.roll(bass_body, 16)
        
        # Final leveler / soft saturation
        stereo = np.column_stack([out_left, out_right])
        peak = np.max(np.abs(stereo))
        if peak > 0:
            stereo = stereo / peak
            stereo = np.tanh(stereo * 1.5) / np.tanh(1.5)
            stereo = stereo * 0.94
            
        out_int16 = (stereo * 32767).astype(np.int16)
        return out_int16

    def _synthesize_channel(self, raw_signal: np.ndarray, t: np.ndarray, 
                            throttle: np.ndarray, rpm: np.ndarray) -> np.ndarray:
        """Process raw cylinder pulse stream through Synthesizer C++ acoustic filters."""
        N = len(raw_signal)
        
        # 1. 10 Hz DC blocking high-pass filter
        sos_dc = signal.butter(1, 10.0, 'highpass', fs=self.sr, output='sos')
        f_in = signal.sosfilt(sos_dc, raw_signal)
        
        # 2. Derivative filter (acoustic velocity front df/dt)
        dt = 1.0 / self.sr
        f_p = np.gradient(f_in, dt) * 0.0005
        
        # 3. 2200 Hz low-pass turbulent air noise modulation
        sos_air = signal.butter(1, 2200.0, 'lowpass', fs=self.sr, output='sos')
        white_noise = np.random.uniform(-1.0, 1.0, N)
        lp_noise = signal.sosfilt(sos_air, white_noise)
        r_mixed = self.air_noise_amount * lp_noise + (1.0 - self.air_noise_amount)
        
        # 4. Mix acoustic pressure velocity front & turbulent pressure wave
        v_in = f_p * self.dF_F_mix + f_in * r_mixed * (1.0 - self.dF_F_mix)
        
        # 5. FFT Convolution with authentic exhaust impulse response
        ir_scaled = self.ir * self.ir_volume
        v_conv = signal.fftconvolve(v_in, ir_scaled, mode='same')
        
        # 6. Blend convolved resonance and direct wave
        conv_amount = 0.88
        v_out = conv_amount * v_conv + (1.0 - conv_amount) * v_in
        
        # 7. Add mechanical body tone at exhaust resonance
        sos_body = signal.butter(2, [self.mechanical_resonance_freq * 0.7, self.mechanical_resonance_freq * 1.5], 
                                 'bandpass', fs=self.sr, output='sos')
        body_ring = signal.sosfilt(sos_body, v_in) * 0.35
        v_out += body_ring
        
        return v_out
