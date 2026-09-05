"""
engine_sim_acoustics.py - Physics-based Engine Acoustic Simulator
Ported and synthesized from AngeTheGreat Engine Simulator (C++) acoustics pipeline:
- Physical cylinder blowdown pressure shockwave generation
- Variable RPM cycle phase integration (720 deg 4-stroke)
- Crankshaft geometry, throw angles & cylinder firing order for:
    * Ferrari 458 Italia (4.5L NA Flat-plane V8, 9000 RPM)
    * Dodge Challenger SRT Hellcat (6.2L SC Cross-plane V8, 6500 RPM)
    * Lexus LFA (4.8L NA 72° V10, 9500 RPM)
    * Nissan GT-R R35 (3.8L Twin-Turbo 60° V6, 7200 RPM)
- Exhaust primary runner propagation delays (speed of sound)
- Acoustic velocity derivative df/dt + 2000 Hz turbulence flow noise modulation
- Authentic exhaust impulse response FFT convolution (mild_exhaust_reverb, test_engine_14, test_engine_16)
- Load-dependent throttle response, shift ignition cut, overrun crackles, afterfire
- Supercharger whine (Hellcat) & Twin-turbo spool + BOV dump (GT-R)
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
        self.has_supercharger = False
        self.has_turbo = False
        
        if vehicle_type == "ferrari_458":
            # 4.5L Flat-plane V8 (Ferrari F136 FL)
            # Firing Order: 1-5-3-7-4-8-2-6 (8 cyl)
            self.cylinders = 8
            self.firing_angles = np.array([0, 540, 180, 360, 90, 630, 270, 450], dtype=np.float64) * (np.pi / 180.0)
            self.cyl_bank = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=int)
            self.primary_lengths = np.array([0.02, 0.01, 0.03, 0.05, 0.01, 0.05, 0.07, 0.00], dtype=np.float64)
            self.exhaust_length = 2.54
            self.redline = 9000.0
            self.ir = load_impulse_response("mild_exhaust_reverb", target_sr=sr, max_samples=12000)
            self.ir_volume = 0.015
            self.dF_F_mix = 0.012
            self.air_noise_amount = 0.70
            self.exhaust_gain = 1.6
            self.mechanical_resonance_freq = 135.0
            
        elif vehicle_type == "hellcat":
            # 6.2L Supercharged Cross-plane V8 (HEMI Hellcat)
            # Firing Order: 1-8-7-2-6-5-4-3 (8 cyl)
            self.cylinders = 8
            self.firing_angles = np.array([0, 270, 630, 540, 450, 360, 180, 90], dtype=np.float64) * (np.pi / 180.0)
            self.cyl_bank = np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype=int)
            self.primary_lengths = np.array([0.05, 0.02, 0.04, 0.06, 0.03, 0.05, 0.02, 0.04], dtype=np.float64)
            self.exhaust_length = 2.80
            self.has_supercharger = True
            self.redline = 6500.0
            self.ir = load_impulse_response("test_engine_16_eq_adjusted_16", target_sr=sr, max_samples=12000)
            self.ir_volume = 0.012
            self.dF_F_mix = 0.018
            self.air_noise_amount = 0.85
            self.exhaust_gain = 2.2
            self.mechanical_resonance_freq = 95.0
            
        elif vehicle_type == "lfa":
            # 4.8L Even-Firing 72° Naturally Aspirated V10 (1LR-GUE)
            # Firing Order: 1-2-3-4-7-8-9-10-5-6 (10 cyl, 72° equal interval)
            self.cylinders = 10
            # Firing angles for 10 cylinders (0 to 720 deg):
            # 1: 0, 2: 72, 3: 144, 4: 216, 7: 288, 8: 360, 9: 432, 10: 504, 5: 576, 6: 648
            self.firing_angles = np.array([0, 72, 144, 216, 576, 648, 288, 360, 432, 504], dtype=np.float64) * (np.pi / 180.0)
            self.cyl_bank = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1], dtype=int)
            # Primary runner lengths (m)
            self.primary_lengths = np.array([0.04, 0.02, 0.05, 0.03, 0.06, 0.02, 0.05, 0.03, 0.04, 0.02], dtype=np.float64)
            self.exhaust_length = 2.60
            self.redline = 9500.0
            self.ir = load_impulse_response("mild_exhaust_reverb", target_sr=sr, max_samples=12000)
            self.ir_volume = 0.014
            self.dF_F_mix = 0.010
            self.air_noise_amount = 0.65
            self.exhaust_gain = 1.8
            self.mechanical_resonance_freq = 380.0 # Yamaha acoustic chamber resonance
            
        elif vehicle_type == "gtr_r35":
            # 3.8L 60° Twin-Turbo V6 (VR38DETT)
            # Firing Order: 1-2-3-4-5-6 (6 cyl, 120° equal interval)
            self.cylinders = 6
            self.firing_angles = np.array([0, 120, 240, 360, 480, 600], dtype=np.float64) * (np.pi / 180.0)
            self.cyl_bank = np.array([0, 1, 0, 1, 0, 1], dtype=int)
            self.primary_lengths = np.array([0.03, 0.02, 0.04, 0.02, 0.05, 0.03], dtype=np.float64)
            self.exhaust_length = 2.40
            self.has_turbo = True
            self.redline = 7200.0
            self.ir = load_impulse_response("test_engine_14_eq_adjusted_16", target_sr=sr, max_samples=12000)
            self.ir_volume = 0.016
            self.dF_F_mix = 0.015
            self.air_noise_amount = 0.80
            self.exhaust_gain = 1.9
            self.mechanical_resonance_freq = 145.0
            
        else:
            raise ValueError(f"Unknown vehicle type: {vehicle_type}")

        # Precompute delays
        c_sound = 343.0
        self.delays_sec = (self.primary_lengths + self.exhaust_length) / c_sound

    def render_track(self, rpm_curve: np.ndarray, throttle_curve: np.ndarray, duration: float, 
                     shift_events: list = None, afterfire_events: list = None, bov_events: list = None) -> np.ndarray:
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
        
        # Cylinder combustion variability (subtle 0.5% jitter)
        rng = np.random.RandomState(42)
        cyl_gain_jitter = 1.0 + rng.normal(0.0, 0.035, self.cylinders)
        
        bank_signals = [np.zeros(N, dtype=np.float64), np.zeros(N, dtype=np.float64)]
        
        # Calculate pressure pulse for each cylinder
        for cyl in range(self.cylinders):
            cyl_angle = (cycle_phase - self.firing_angles[cyl]) % (2.0 * np.pi)
            
            ev_center = 1.0 * np.pi
            rel_angle = (cyl_angle - ev_center) % (2.0 * np.pi)
            
            pulse = np.zeros(N, dtype=np.float64)
            pulse_width = (2.0 * np.pi / self.cylinders) * 1.15
            active_mask = rel_angle < pulse_width
            tau = rel_angle[active_mask] / pulse_width
            
            # Asymmetric blowdown pulse shape
            pulse_shape = (tau / 0.12) * np.exp(-(tau - 0.12) / 0.24) + 0.12 * np.sin(np.pi * tau)
            
            load_factor = 0.35 + 0.65 * (throttle_curve[active_mask] ** 0.8)
            pulse[active_mask] = np.maximum(0.0, pulse_shape * load_factor * cyl_gain_jitter[cyl])
            
            # Primary runner delay
            delay_samples = int(self.delays_sec[cyl] * self.sr)
            delayed_pulse = np.roll(pulse, delay_samples)
            
            bank = self.cyl_bank[cyl]
            bank_signals[bank] += delayed_pulse
            
        # Combine dual banks
        left_raw = bank_signals[0] + 0.35 * bank_signals[1]
        right_raw = bank_signals[1] + 0.35 * bank_signals[0]
        
        # Shift ignition cut
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
                            np.random.normal(0, 1.3, crack_len) * np.exp(-np.linspace(0, 5, crack_len))
                        )
                        
        left_raw = left_raw * shift_mask + shift_pops
        right_raw = right_raw * shift_mask + shift_pops
        
        # Afterfire crackles and pops on overrun/lift
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
        
        # Synthesizer acoustic pipeline
        out_left = self._synthesize_channel(left_raw, t, throttle_curve, rpm_curve)
        out_right = self._synthesize_channel(right_raw, t, throttle_curve, rpm_curve)
        
        # Supercharger Whine (Hellcat)
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
            
        # Twin Turbo Whine & BOV (GT-R R35)
        if self.has_turbo:
            # Turbine speed: 18x to 26x engine RPM under load
            turbo_ratio = 18.0 + 8.0 * throttle_curve
            turbo_rev_freq = (rpm_curve / 60.0) * turbo_ratio
            turbo_phase = 2.0 * np.pi * np.cumsum(turbo_rev_freq) / self.sr
            turbo_gain = 0.04 * (throttle_curve ** 1.2) * (rpm_curve / self.redline)
            # High-pitch aerodynamic turbine spool hiss & blade pass tone
            turbo_spool = (
                0.7 * np.sin(turbo_phase) + 
                0.3 * np.sin(2.0 * turbo_phase) +
                0.5 * np.random.normal(0, 0.3, N) * np.sin(turbo_phase)
            ) * turbo_gain
            out_left += turbo_spool
            out_right += np.roll(turbo_spool, 10)
            
            # Blow-Off Valve (BOV) air release hiss
            if bov_events:
                for b_time, b_dur in bov_events:
                    b_idx = int(b_time * self.sr)
                    b_len = int(b_dur * self.sr)
                    if b_idx + b_len < N:
                        # Multi-frequency air burst flutter
                        b_t = np.linspace(0, b_dur, b_len)
                        bov_flutter = np.sin(2.0 * np.pi * 32.0 * b_t) # 32 Hz valve flutter
                        bov_hiss = (
                            np.random.normal(0, 0.8, b_len) * 
                            np.exp(-b_t * 6.0) * 
                            (1.0 + 0.6 * bov_flutter)
                        )
                        # Bandpass filter around 2500 - 5500 Hz
                        sos_bov = signal.butter(2, [2200.0, 5800.0], 'bandpass', fs=self.sr, output='sos')
                        bov_filtered = signal.sosfilt(sos_bov, bov_hiss) * 0.45
                        out_left[b_idx:b_idx + b_len] += bov_filtered
                        out_right[b_idx:b_idx + b_len] += bov_filtered
            
        # Mechanical Bass Chest-Resonator
        firing_orders_per_rev = self.cylinders / 2.0
        firing_freq = (rpm_curve / 60.0) * firing_orders_per_rev
        bass_phase = 2.0 * np.pi * np.cumsum(firing_freq) / self.sr
        bank_phase = bass_phase * 0.5
        
        bass_body = (
            0.50 * np.sin(bass_phase) + 
            0.35 * np.sin(bank_phase + 0.4) + 
            0.15 * np.sin(bass_phase * 2.0)
        ) * (0.45 + 0.55 * throttle_curve) * (self.exhaust_gain * 0.16)
        
        out_left += bass_body
        out_right += np.roll(bass_body, 16)
        
        # Soft analog valve saturation
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
