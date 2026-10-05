# C63 high-RPM rejected experiments

Both candidates are rejected. This archive changes no production bank, renderer, source emitter, gain or route. Start with [findings and limitations](REVIEW.md), then [reproduction commands](REPRODUCE.md).

Git contains the exact scripts, numeric results, source/PCM hashes and generation recipes, but deliberately excludes failed candidate WAVs and large raw PCM. Reproduction creates them in a new isolated output directory. The review archive retained the original last3-second PCM tails; 30-second summaries came from the executed renderer harness. No microphone recording or private trip data is involved.

The source authority remains commit955b1355839f4b233e56c9ec9213fb86ae1927a6 and the58 input hashes in input-pins.json. Source files are copied only after verification. Existing SHA-pinned JVM dependencies are required; the tool does not install them.

The two `*-replay-frozen` directories preserve the actual experiment helpers and harnesses needed by reproduce.py. Their controller types compile for compatibility but the experiment feeds steady SoundState directly into the actual renderer. It does not establish dynamic REAL, Android, device or human acceptance.

[next-design/DESIGN.md](next-design/DESIGN.md) is a research comparison, not permission or admission to generate a third production candidate. Its numeric grid examples explicitly include origin/offset dependence.
