# S12 Professional Acoustic Toolchain Matrix

`PROFESSIONAL_COMPARATOR_TOOLCHAIN_PARTIAL` / `REAL_REFERENCE_CALIBRATION_BLOCKED`.

| Tool | Version | Invoked | Fixture validated | Project data | Status | Limitation |
| --- | --- | --- | --- | --- | --- | --- |
| MATLAB Signal Processing Toolbox: rpmordermap | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; no external reference RPM/state metadata is available. |
| MATLAB Signal Processing Toolbox: ordertrack | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; no external reference RPM/state metadata is available. |
| MATLAB Signal Processing Toolbox: orderspectrum | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; no external reference RPM/state metadata is available. |
| MoSQITo | 1.2.1 | True | True | True | VALIDATED | Fixture and eight hash-bound synthetic candidates were processed in the digital domain; no absolute SPL or real-reference residual is claimed. |
| MATLAB Signal Processing Toolbox: rpmfreqmap | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; no external reference RPM/state metadata is available. |
| MATLAB Audio Toolbox: acousticLoudness | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; metrics are digital-domain relative only. |
| MATLAB Audio Toolbox: acousticSharpness | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; metrics are digital-domain relative only. |
| MATLAB Audio Toolbox: acousticRoughness | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; metrics are digital-domain relative only. |
| MATLAB Audio Toolbox: acousticFluctuation | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; metrics are digital-domain relative only. |
| MATLAB Audio Toolbox: acousticToneToNoiseRatio | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; metrics are digital-domain relative only. |
| MATLAB Audio Toolbox: acousticProminenceRatio | 2026a | True | True | True | VALIDATED | Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; metrics are digital-domain relative only. |
| MATLAB Audio Test Bench | unqueried | False | False | False | BLOCKED | AUDIO_TEST_BENCH_NOT_INTEGRATED; no audioPlugin bridge exists. |
| Essentia | not detected | False | False | False | OPTIONAL_NOT_INSTALLED | Windows Python binding was not installed; it is not a core dependency. |
| ViSQOL | not detected | False | False | False | OPTIONAL_NOT_INSTALLED | No official source checkout/build with commit and SHA is available; PyPI installation is prohibited. |
| webMUSHRA | upstream commit recorded in external tool receipt | True | True | False | VALIDATED | External Docker server served the config/audio and a PHP fixture export was SHA/file-ID imported; it is not human feedback or a real-reference study. |

## Industry references

- `HEAD ArtemiS`: `INDUSTRY_REFERENCE_NOT_INSTALLED`.
- `Simcenter Testlab`: `INDUSTRY_REFERENCE_NOT_INSTALLED`.
- `BK Connect`: `INDUSTRY_REFERENCE_NOT_INSTALLED`.
