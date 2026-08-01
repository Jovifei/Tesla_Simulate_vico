# v0.15 Vehicle Sound Character Matrix

This is a synthetic design and evidence-boundary matrix, not an OEM recording
catalogue, measured target, and not OEM reproduction. `A` is direct manufacturer
topology evidence; `B` is supporting technical/service/listening context; `C`
is a synthetic, uncalibrated design or metric. A source may support architecture
without supporting timing, bank pattern, level, spectrum, or calibration.

## Ferrari 458 Italia

| Topic | Direction or fact | Class and evidence | Limitation |
|---|---|---|---|
| Architecture | 4497 cc 90-degree V8 and 9000-rpm power peak. | A — [Ferrari official model page](https://www.ferrari.com/en-EN/auto/458-italia) | Supports topology, not an acoustic transfer function. |
| Ignition, pulse, and attack | Flat-plane timing, alternating-bank ignition/pulse attack, and clean naturally aspirated attack are C design directions. | C — synthetic/uncalibrated | No direct source here establishes timing or pressure-pulse shape. |
| High-frequency growth | RPM-linked high-frequency metallic growth is C; the 1.35 ratio and 0.98 order-sweep correlation are C gates. | C — synthetic target profile | Not OEM measured or Ferrari calibration. |
| Exhaust state | A load-dependent bypass path supports topology only; its acoustic transition remains C. | A — [Ferrari history entry](https://www.ferrari.com/it-IT/history/garage/2009/458-italia); C direction | Exact valve schedule, pipes, and levels are unknown. |

## Dodge Challenger SRT Hellcat

| Topic | Direction or fact | Class and evidence | Limitation |
|---|---|---|---|
| Architecture | 6.2 L 90-degree V8, 2.4 L twin-screw blower, and 2.36 drive ratio. | A — [FCA Canada powertrain material](https://www.fcapresskit.ca/2015/Contents/Press-Releases/PDFs/Chrysler-Canada/CN_2015_SAFETY-TECH_Powertrain.pdf) | Supports components, not bank acoustic behavior. |
| Exhaust and bank pattern | Cross-plane/bank pattern and a low-band exhaust body are C source-design directions. | C — synthetic/uncalibrated | No direct evidence in this package establishes bank timing or exhaust spectrum. |
| Blower, mechanical, and intake | Separate blower, mechanical, and intake stems; RPM-derived blower phase and load/bypass energy are C design directions. | C — synthetic/uncalibrated | [Stellantis technical blog](https://blog.stellantisnorthamerica.com/2014/05/23/2015-dodge-challenger-srt-by-the-numbers/) supports hardware context only. |
| Low-band and load | The 0.10 low-band, 3.0 energy-ratio, and 0.80 correlation gates are C. | C — synthetic target profile | Not OEM measured behavior or hardware audibility. |

## Mazda RX-7 FD

| Topic | Direction or fact | Class and evidence | Limitation |
|---|---|---|---|
| Architecture | 13B two-rotor rotary and sequential twin-turbo topology. | A — [Mazda RX-7 history](https://www2.mazda.com/en/stories/craftmanship/greatcar/p15.html); B — [SAE 941030](https://doi.org/10.4271/941030) | No acoustic pressure target is supplied. |
| Non-piston phase and integer order | Non-piston phase-offset event trains and integer-order emphasis are C design directions. | C — synthetic/uncalibrated | No direct source establishes phase, order spectrum, or pulse shape. |
| Turbo sequence | Stateful primary spool, secondary engagement, turbine phase, and lift decay are C design directions. | C — synthetic/uncalibrated | [Mazda technical review](https://www.mazda.com/content/dam/mazda/corporate/mazda-com/en/pdf/innovation/monozukuri/technology/tech-review/2003/2003_no002.pdf) supplies technical context, not acoustic timing. |
| Lift analysis | Analyze turbo rise/lift decay as C state behavior. | C — synthetic/uncalibrated | [Mazda service-information portal](https://www.mazdaserviceinfo.com/) is not a calibration source. |

## Exact public-video observation table

Every entry below is `B` / `R2` / listening-only / inconclusive for
calibration. The table prevents generic-channel-only references from passing
review. It has no OEM measured acoustic parameter.

| Vehicle | Title | Configuration caveat | Qualitative cues | Permitted use | Exclusion |
|---|---|---|---|---|---|
| Ferrari context | [POV: Novitec Exhaust on a Ferrari 812 GTS (V12 Heaven)](https://www.youtube.com/watch?v=1fzUnAUarNI) | Modified Novitec-exhaust 812 GTS V12; not a 458 stock configuration. | High-RPM tonal aspiration. | Listening-only inspiration for high-RPM tonal aspiration. | Non-target, non-calibration, non-OEM; not evidence for 458 architecture. |
| Ferrari 458 | [Ferrari 458 Italia stock exhaust note and acceleration](https://www.youtube.com/watch?v=R6e_5v2aps4) | Description says what seems to be stock; configuration unverified and inconclusive. | Qualitative acceleration/exhaust-note observation. | Qualitative acceleration observation only. | Not calibration, not OEM measurement, and not proof of stock configuration. |
| Ferrari comparison | [Ferrari 458 straight-pipe comparison](https://www.youtube.com/watch?v=GzeRNBmH2vY) | Full straight pipe; description says sound is manipulated. | Modified contrast only. | Contrast/exclusion review only. | Excluded from calibration and stock-target inference. |
| Hellcat | [2016 Dodge Challenger SRT Hellcat - SOUND!](https://www.youtube.com/watch?v=cKx-cb0fzeo) | Uploader claim of stock exhaust revving/accelerating; unverified. | Qualitative revving and accelerating contrast. | Listening-only qualitative revving/acceleration observation. | Not calibration, not OEM measurement, uploader claim unverified. |
| RX-7 FD | [Mazda RX-7 sound compilation](https://www.youtube.com/watch?v=hCz1YS5yJkw) | Compilation includes modified, bridgeported, and antilag clips; stock configuration is not isolated. | Rotary/turbo contrast only. | Contrast-only listening discussion. | Excluded from stock calibration, numerical targets, and OEM inference. |

## Limitations

Public videos cannot establish microphone position, distance, environment,
signal processing, vehicle configuration, OEM calibration, or target level.
They may support a blind listening discussion only. All numerical synthesis
targets remain `C`, synthetic, uncalibrated, and not OEM measured; automated
separation gates do not remove those limitations.
