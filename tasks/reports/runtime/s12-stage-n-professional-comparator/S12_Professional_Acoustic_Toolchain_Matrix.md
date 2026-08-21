# S12 Professional Acoustic Toolchain Matrix

`PROFESSIONAL_COMPARATOR_TOOLCHAIN_PARTIAL` / `REAL_REFERENCE_CALIBRATION_BLOCKED`.

| Tool | Version | Invoked | Fixture validated | Project data | Status | Limitation |
| --- | --- | --- | --- | --- | --- | --- |
| MATLAB Signal Processing Toolbox: rpmordermap | R2026a executable detected; no safe user-started Desktop session | False | False | False | BLOCKED | MATLAB.exe is absent while pre-existing MATLAB-MCP servers are active; Stage N did not start, stop, or reconnect MATLAB. |
| MATLAB Signal Processing Toolbox: ordertrack | R2026a executable detected; no safe user-started Desktop session | False | False | False | BLOCKED | MATLAB.exe is absent while pre-existing MATLAB-MCP servers are active; Stage N did not start, stop, or reconnect MATLAB. |
| MATLAB Signal Processing Toolbox: orderspectrum | R2026a executable detected; no safe user-started Desktop session | False | False | False | BLOCKED | MATLAB.exe is absent while pre-existing MATLAB-MCP servers are active; Stage N did not start, stop, or reconnect MATLAB. |
| MoSQITo | 1.2.1 | True | True | False | VALIDATED | Fixture input is digital-domain relative; it is not calibrated SPL or a real-reference comparison. |
| MATLAB Signal Processing Toolbox: rpmfreqmap | R2026a executable detected; no safe user-started Desktop session | False | False | False | BLOCKED | MATLAB.exe is absent while pre-existing MATLAB-MCP servers are active; Stage N did not start, stop, or reconnect MATLAB. |
| MATLAB Audio Toolbox: acousticLoudness | R2026a executable detected; toolbox availability unqueried without safe Desktop session | False | False | False | BLOCKED | No safe manually opened MATLAB Desktop session is available; proxy metrics are not substituted. |
| MATLAB Audio Toolbox: acousticSharpness | R2026a executable detected; toolbox availability unqueried without safe Desktop session | False | False | False | BLOCKED | No safe manually opened MATLAB Desktop session is available; proxy metrics are not substituted. |
| MATLAB Audio Toolbox: acousticRoughness | R2026a executable detected; toolbox availability unqueried without safe Desktop session | False | False | False | BLOCKED | No safe manually opened MATLAB Desktop session is available; proxy metrics are not substituted. |
| MATLAB Audio Toolbox: acousticFluctuation | R2026a executable detected; toolbox availability unqueried without safe Desktop session | False | False | False | BLOCKED | No safe manually opened MATLAB Desktop session is available; proxy metrics are not substituted. |
| MATLAB Audio Toolbox: acousticToneToNoiseRatio | R2026a executable detected; toolbox availability unqueried without safe Desktop session | False | False | False | BLOCKED | No safe manually opened MATLAB Desktop session is available; proxy metrics are not substituted. |
| MATLAB Audio Toolbox: acousticProminenceRatio | R2026a executable detected; toolbox availability unqueried without safe Desktop session | False | False | False | BLOCKED | No safe manually opened MATLAB Desktop session is available; proxy metrics are not substituted. |
| MATLAB Audio Test Bench | unqueried | False | False | False | BLOCKED | AUDIO_TEST_BENCH_NOT_INTEGRATED; no audioPlugin bridge exists. |
| Essentia | not detected | False | False | False | OPTIONAL_NOT_INSTALLED | Windows Python binding was not installed; it is not a core dependency. |
| ViSQOL | not detected | False | False | False | OPTIONAL_NOT_INSTALLED | No official source checkout/build with commit and SHA is available; PyPI installation is prohibited. |
| webMUSHRA | upstream commit recorded in external tool receipt | True | True | False | VALIDATED | External Docker server served the config/audio and a PHP fixture export was SHA/file-ID imported; it is not human feedback or a real-reference study. |

## Industry references

- `HEAD ArtemiS`: `INDUSTRY_REFERENCE_NOT_INSTALLED`.
- `Simcenter Testlab`: `INDUSTRY_REFERENCE_NOT_INSTALLED`.
- `BK Connect`: `INDUSTRY_REFERENCE_NOT_INSTALLED`.
