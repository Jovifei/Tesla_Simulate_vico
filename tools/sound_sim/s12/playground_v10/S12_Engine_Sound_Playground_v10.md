# S12 Multi-Configuration Engine Sound Playground v1.0

## Boundary

This is a **synthetic, uncalibrated, offline, not realtime-qualified** sound-design prototype. It does not contain vehicle recordings, OEM calibration data, or an OEM sound clone. `hellcat_style_supercharged_v8` and `ferrari_style_high_rev_v8` are synthetic style directions only.

The frozen v0.9 model and the FVM, HLLC, MUSCL, positivity, SSP-RK3, PTR-core, and radiation-boundary mathematics are outside this package and are not modified.

## Architecture

`Vehicle Cycle or Interactive State -> Engine Excitation and Overrun Burst -> Shared PTR/Radiation Model Reference -> Stereo PCM -> WAV/device audition`

Each top model uses `S12_PTR_Renderer_Core_v10.slx` by Model Reference. The top model writes deterministic `[960, 2]` PCM frames; the public audition API renders the same 48 kHz stereo path to 24-bit WAV and can play it through the MATLAB Desktop audio device.

## Built-in synthetic profiles

| Profile | Top model | Idle/redline RPM | Synthetic firing order | Default overrun |
|---|---|---:|---|---|
| `inline3_turbo` | `S12_I3_Turbo_v10.slx` | 850 / 6500 | 1-3-2 | subtle |
| `inline4_sport` | `S12_I4_Sport_v10.slx` | 800 / 7000 | 1-3-4-2 | subtle |
| `inline5_character` | `S12_I5_Character_v10.slx` | 850 / 7200 | 1-2-4-5-3 | subtle |
| `inline6_smooth` | `S12_I6_Smooth_v10.slx` | 700 / 7000 | 1-5-3-6-2-4 | off |
| `v6_sport` | `S12_V6_Sport_v10.slx` | 750 / 7500 | 1-4-2-5-3-6 | subtle |
| `hellcat_style_supercharged_v8` | `S12_V8_Muscle_v10.slx` | 700 / 6500 | 1-8-4-3-6-5-7-2 | aggressive |
| `ferrari_style_high_rev_v8` | `S12_V8_HighRev_v10.slx` | 1000 / 9000 | 1-5-4-8-3-7-2-6 | subtle |

All JSON leaf parameters carry `value`, `unit`, `range`, `source_level: "C"`, and `source: "synthetic"`. The primary synthetic firing frequency is `cylinders / 2 * RPM / 60`.

## Listen to a complete drive cycle

In the single shared visible MATLAB Desktop:

```matlab
addpath('E:\Tesla_speed\prj\tools\sound_sim\s12\playground_v10')
addpath('E:\Tesla_speed\prj\tools\sound_sim\s12\playground')
rehash

result = s12_engine_sound_audition( ...
    "hellcat_style_supercharged_v8", ...
    "BackfireLevel", "aggressive", ...
    "Play", true);
```

`Play=true` plays the 90-second complete cycle. The same output directory contains `full_drive_cycle.wav`, `idle.wav`, `acceleration.wav`, `deceleration.wav`, and `overrun_backfire.wav` for repeat listening. Outputs are written only beneath `E:\Tesla_speed\tasks\reports\runtime\s12-engine-sound-v10`.

Render every profile without playback:

```matlab
results = s12_engine_sound_render_all();
```

## Simulink tuning

```matlab
s12_engine_sound_open_model("ferrari_style_high_rev_v8")
```

The default **Qualification** path uses the deterministic 90-second vehicle cycle. Switch `Interactive Mode Dashboard` to **On** to use the manual-state controls. Then tune:

- Vehicle: `RPM Dashboard`, `Load Dashboard`, `Acceleration Dashboard`, `Throttle Dashboard`.
- Engine: `Order Balance Dashboard`, `Transient Dashboard`, `Backfire Dashboard`.
- PTR/renderer: `Pipe Length Dashboard`, `Area Dashboard`, `Reflection Dashboard`, `Damping Dashboard`, `Gain Dashboard`.

The interactive top model exposes PCM rather than silently starting an unqualified real-time sink. Use the public audition API above to publish/play the matching offline WAV evidence.

## Advanced custom profile

Copy an existing file from `profiles/`, preserve every provenance descriptor, and validate before rendering:

```matlab
profile = s12_engine_sound_load_profile('E:\path\to\my_synthetic_profile.json');
profile.engine.cylinder_count.value = 6;
profile.engine.firing_order.value = [1 5 3 6 2 4];
profile.engine.firing_phase_deg.value = [0 120 240 360 480 600];
profile.engine.bank_map.value = [1 1 1 2 2 2];
s12_engine_sound_validate_profile(profile)
result = s12_engine_sound_audition(profile, "BackfireLevel", "subtle", "Play", true);
```

`BackfireLevel` is limited to `off`, `subtle`, or `aggressive`. A rendered package writes the validated `profile_snapshot.json`, trace, analysis, manifest, and SHA256 list alongside the WAV files.

## Fixed 90-second qualification cycle

0-2 start, 2-12 idle, 12-22 pull-away, 22-32 cruise, 32-48 full-throttle acceleration, 48-54 high-load hold, 54-66 lift/overrun, 66-72 downshift blip, 72-82 acceleration, 82-88 rapid lift/overrun, 88-90 idle recovery.
