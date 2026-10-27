# Public real-engine pool: read-only feature analysis

ffmpeg mono 48 kHz F32LE; 1 s windows; no gain/time manipulation; decimated autocorrelation candidates

| ID | duration | RMS | peak | 1 s RMS CV | centroid median | best candidate lag | corr | state |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `bmw-m57` | 19.55 s | 0.05948 | 0.94736 | 1.327 | 2712.3 Hz | 2.75 s | 0.0387 | `UNKNOWN` |
| `ferrari-250-gto` | 59.88 s | 0.18115 | 0.94946 | 0.372 | 1852.8 Hz | 3.75 s | 0.0067 | `UNKNOWN` |
| `honda-f20c` | 137.07 s | 0.10758 | 1.36261 | 0.641 | 946.9 Hz | 3.5 s | 0.0103 | `UNKNOWN` |
| `triumph-i6` | 11.44 s | 0.19827 | 0.98170 | 0.096 | 1706.2 Hz | 4.5 s | 0.0230 | `UNKNOWN` |
| `volvo-850-t5` | 32.60 s | 0.12730 | 1.04517 | 0.503 | 958.6 Hz | 3.5 s | 0.0129 | `UNKNOWN` |

Candidate autocorrelation is a texture diagnostic only; it is not RPM, engine order, or 720-degree phase evidence.
