# Reproduce the rejected candidates

Use an exact955b135 checkout and the project's SHA-pinned JVM dependencies. The runner checks58 required source/bank files before copying the minimal inputs to a new output directory. It does not edit the input checkout, install software, change gain or route any audio to a device.

```bash
python reproduce.py --repo /path/to/955b135-checkout --deps /path/to/pinned-jvm-jars --output-dir /tmp/vico-rejected-replay-new --stage all
```

`--stage phase` or `--stage guards` reproduces one branch. `--prepare-only` validates/copies inputs and exits without DSP; this mode was separately executed successfully. The phase branch of the assembled wrapper was executed end-to-end after freezing: all161 raw output files match the original hashes exactly. The guards branch was independently rerun end-to-end: all4 candidate WAVs,36 source controls,72 renderer PCM files plus blend.csv and the final gate JSON matched the frozen bytes. Analyzer CLIs were rerun against retained PCM after the path argument was added. No Android/controller dynamics are exercised by these steady-state harnesses.

Results deliberately contain failed admission gates. Successful script execution means the experiment ran, not that a candidate passed. No mobile install or bank promotion is performed.

The recipe baseline rebuilds all16 original loops. Phase generation creates only6800/7200 rotations; guards add only5400/5600. The two Kotlin harness snapshots execute the real published renderer and exact bank data classes, without an acoustic surrogate. Android AudioTrack/platform adapters are outside this offline runner.

The original measurement files are in evidence/, raw-evidence/phase and raw-evidence/guards. Source controls are in source-holdouts/ and guard-source-holdouts/. Compare numeric gate outputs and recorded input/PCM hashes; compiled jar bytes can vary with source paths and are not the acoustic equality claim.

The earlier broad all-loop phase scan is diagnostic history, not a product candidate; the retained `broad-original-vs-all-rotations.csv` and receipt bind it. Its low-RPM regression caused scope rejection before held-out evaluation. Additional diagnostic path captures after the two failures are excluded from the frozen candidate conclusions and do not constitute another candidate.

Archive packaging note: raw-evidence PCM and source-control PCM were retained for independent review but are not committed in this compact Git archive. Their hashes and recipes are included; run reproduce.py in a new directory to regenerate them. No failed WAV is added to app assets.

The early broad scan has its own preserved harness, with the original all-loop diagnostic rotation (including the later-rejected318-sample7200 start). To reproduce that historical diagnostic only: `python broad-diagnostic/run_replay.py --repo /path/to/955b135-checkout --deps /path/to/pinned-jvm-jars --output-dir /tmp/vico-broad-history-new --variant candidate`. It is not a third product candidate or the final high-phase recipe.
