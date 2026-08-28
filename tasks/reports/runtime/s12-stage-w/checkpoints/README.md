# Stage W checkpoints

Checkpoint files record durable local integration points and must identify the exact safe commit and evidence boundary.

The checkpointed Hellcat recovery API writes its sidecar outside the strict evidence root, beside that root in `checkpoints/`, as `<root-name>-<sha256(resolved-root)[:16]>.resume.json`. The payload binds the canonical resolved root, root identity, requested duration, long-window flag, `REFERENCE_POINTER_ONLY`, null selection, and completed executable architectures. A mismatch is rejected closed.

The sidecar is published atomically. Per-scene staging directories are also outside the evidence root and are removed after publication; no checkpoint or staging file is valid inside the final root because the strict bake-off manifest inventory rejects unknown files. Final summaries and `bakeoff_manifest.json` are emitted only after P1, P2, P2H, P3, and P5 are all verified complete.
