#!/usr/bin/env python3
"""
vico_vehicle_synth.py - Python 参考合成 (镜像 Kotlin VehicleSoundModel, 保证调参=App 播放)

用法:
  python vico_vehicle_synth.py v8_crossplane.json v8.wav                  # 固定 2500rpm 试听
  python vico_vehicle_synth.py v8_crossplane.json v8.wav --rpm 4000
  python vico_vehicle_synth.py v8_crossplane.json v8.wav --sweep           # 0->redline 扫频
  python vico_vehicle_synth.py v8_crossplane.json v8.wav --duration 4

用途: (1) 离线试听调参 (2) 生成参考 WAV 供 Android parity 单测比对
Parity: Kotlin VehicleSoundModel 用同一 JSON + 同一 RPM 序列渲染, 逐样本比对此 WAV。
        (注: 含 combJitter 时随机源不同, parity 测试请用 combJitter=0)
"""

import json, math, os, sys, random, wave, struct, argparse

G = 9.80665
TWO_PI = 2.0 * math.pi


def load_profile(path):
    o = json.load(open(path, encoding="utf-8"))
    e = o.get("engine", {})
    s = o.get("synthesis", {})
    lay = o.get("layers", {})
    mp = o.get("mapping", {})
    p = {
        "name": o.get("name", "Vehicle"),
        "cylinders": e.get("cylinders", 8),
        "stroke": e.get("stroke", 4),
        "idleRpm": e.get("idleRpm", 700.0),
        "redlineRpm": e.get("redlineRpm", 6800.0),
        "motorFreqMult": e.get("motorFreqMult", 0.0),
        "harmonics": s.get("harmonics", [1.0, 0.55, 0.32, 0.18, 0.09]),
        "harmMult": s.get("harmMult", [1, 2, 3, 4, 5]),
        "waveform": s.get("waveform", "sawtooth"),
        "combJitter": s.get("combJitter", 0.03),
        "exhaustResonance": s.get("exhaustResonance", 0.97),
        "exhaustWindow": s.get("exhaustWindow", 0.5),
        "decayRad": s.get("decayRad", 0.6),
        "overspeedMuteKmh": mp.get("overspeedMuteKmh", 150.0),
    }
    fo = e.get("firingOrderDegrees")
    if fo:
        p["firingTiming"] = [d * math.pi / 180.0 for d in fo]
    else:
        cyc = cycle_angle(p)
        p["firingTiming"] = [i * cyc / p["cylinders"] for i in range(p["cylinders"])]
    t = lay.get("turbo", {})
    p["turbo"] = t if (t and t.get("enabled", True)) else None
    return p


def cycle_angle(p):
    return 4.0 * math.pi if p["stroke"] == 4 else 2.0 * math.pi


def fires_per_rev(p):
    return p["cylinders"] * 2.0 / p["stroke"]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def wave_of(typ, ph):
    x = ph % TWO_PI
    if typ == "square":
        return 1.0 if math.sin(x) >= 0 else -1.0
    if typ in ("saw", "sawtooth"):
        return 2.0 * (x / TWO_PI) - 1.0
    return math.sin(x)


def map_point(p, time_s, speed_kmh, throttle, accel, brake, smooth_rpm):
    """与 Kotlin VehicleSoundModel.mapPoint 同构。返回 (rpm, amplitude, brightness, harmonics, muted, fFire)。"""
    idle = p["idleRpm"]
    red = p["redlineRpm"]
    throttle = clamp(throttle, 0.0, 1.0)
    speed = max(0.0, speed_kmh)
    positive_accel = clamp(accel / 3.0, 0.0, 1.0)
    braking = brake or accel < -1.2

    speed_rpm = idle + clamp(speed / 180.0, 0.0, 1.0) * (6000.0 - idle)
    throttle_factor = 0.30 + 0.70 * throttle
    target_rpm = idle + (speed_rpm - idle) * throttle_factor + positive_accel * 850.0
    if braking:
        target_rpm = max(idle, target_rpm * 0.45)
    target_rpm = clamp(target_rpm, idle, red)
    smooth_rpm += 0.18 * (target_rpm - smooth_rpm)

    brightness = clamp(0.20 + throttle * 0.45 + positive_accel * 0.35, 0.0, 1.0)
    amplitude = clamp(0.12 + throttle * 0.32 + positive_accel * 0.18, 0.0, 0.72)
    if braking:
        brightness *= 0.55
        amplitude *= 0.65

    if p["motorFreqMult"] > 0:
        f_fire = (smooth_rpm / 60.0) * p["motorFreqMult"]
    else:
        f_fire = (smooth_rpm / 60.0) * fires_per_rev(p)
    muted = speed >= p["overspeedMuteKmh"]
    if muted:
        amplitude = 0.0
    return smooth_rpm, amplitude, brightness, f_fire, muted


def render(p, rpm_seq, throttle, accel, brake, sample_rate=44100):
    """逐样本合成 (与 Kotlin renderState 同构)。返回 int16 列表。"""
    cycle = cycle_angle(p)
    window = p["exhaustWindow"] * cycle
    norm = max(p["cylinders"] / 2.0, 1.0)
    turbo = p["turbo"]
    rnd = random.Random(0xC0FFEE)

    cycle_phase = 0.0
    harm_phase = 0.0
    turbo_phase = 0.0
    prev_pulse = 0.0
    smooth_rpm = p["idleRpm"]
    out = []

    for i in range(len(rpm_seq)):
        rpm = rpm_seq[i]
        # 状态: 用固定 throttle/accel 推 mapPoint (试听模式)
        smooth_rpm, amplitude, brightness, f_fire, muted = map_point(
            p, i / sample_rate, 0.0, throttle, accel, brake, smooth_rpm
        )
        # 覆盖 rpm 为序列值 (扫频/固定), 重算 f_fire
        smooth_rpm = rpm
        if p["motorFreqMult"] > 0:
            f_fire = (rpm / 60.0) * p["motorFreqMult"]
        else:
            f_fire = (rpm / 60.0) * fires_per_rev(p)

        if muted or amplitude <= 0.0:
            out.append(0)
            continue

        crank_freq = rpm / 60.0
        d_phase = TWO_PI * crank_freq / sample_rate
        d_harm = TWO_PI * f_fire / sample_rate
        cycle_phase = (cycle_phase + d_phase) % cycle

        # per-cylinder 排气脉冲
        pulse = 0.0
        for c in range(p["cylinders"]):
            d = cycle_phase - p["firingTiming"][c]
            if d < 0:
                d += cycle
            if d < window:
                pulse += math.exp(-d / p["decayRad"])
        throttle_mod = 0.5 + 0.5 * brightness
        pulse = pulse / norm * throttle_mod
        pulse *= 1.0 + (rnd.random() - 0.5) * p["combJitter"]

        exhaust = pulse - p["exhaustResonance"] * prev_pulse
        prev_pulse = pulse

        harm_phase = (harm_phase + d_harm) % TWO_PI
        harm = 0.0
        for h in range(min(len(p["harmonics"]), len(p["harmMult"]))):
            harm += p["harmonics"][h] * wave_of(p["waveform"], p["harmMult"][h] * harm_phase)

        sig = harm if p["cylinders"] <= 0 else exhaust * 0.7 + harm * 0.3

        if turbo and rpm > turbo["thresholdRpm"]:
            t_gain = clamp(
                (rpm - turbo["thresholdRpm"]) / max(p["redlineRpm"] - turbo["thresholdRpm"], 1.0),
                0.0,
                1.0,
            )
            turbo_phase = (turbo_phase + TWO_PI * f_fire * turbo["freqMult"] / sample_rate) % TWO_PI
            sig += turbo["gain"] * t_gain * math.sin(turbo_phase)

        v = math.tanh(sig * amplitude * 2.2)
        out.append(int(clamp(v * 32767.0, -32768, 32767)))

    return out


def write_wav(path, samples, sample_rate):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("outwav")
    ap.add_argument("--rpm", type=float, default=2500.0)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--duration", type=float, default=3.0)
    ap.add_argument("--sr", type=int, default=44100)
    a = ap.parse_args()

    p = load_profile(a.profile)
    N = int(a.duration * a.sr)
    if a.sweep:
        rpm_seq = [p["idleRpm"] + (p["redlineRpm"] - p["idleRpm"]) * i / (N - 1) for i in range(N)]
    else:
        rpm_seq = [a.rpm] * N

    samples = render(p, rpm_seq, throttle=0.5, accel=0.5, brake=False, sample_rate=a.sr)
    write_wav(a.outwav, samples, a.sr)
    peak = max(abs(s) for s in samples) if samples else 0
    print(f"Wrote {a.outwav}  ({N} samples, {a.duration:.1f}s, peak={peak})  [{p['name']}]")


if __name__ == "__main__":
    main()
