# Vico P2/P3 Execution Plan

## Goal

Complete the implementable engineering portion of continuous sound and Android runtime integration while preserving qualification boundaries.

## P2 Continuous Sound Stage

### Candidate management

- Keep HY1 frozen as failed historical evidence.
- Create new candidate IDs before implementation.
- Never improve a failed candidate by hidden retuning.

### Implementation areas

1. Renderer/source/profile
   - Separate continuous source state from event layers.
   - Keep profile selection deterministic.
   - Add explicit candidate metadata.

2. Afterfire
   - Make enable/disable state explicit.
   - Avoid fixed event triggering independent of engine state.
   - Keep event qualification separate from continuous tone qualification.

3. Qualification tests

Required future local execution:

- Kotlin state matrix tests.
- Four branch mode tests.
- 630 regression tests.
- Candidate export/report generation.

## P3 Android Runtime Stage

### Audio engine

Required implementation review:

- fixed sample rate/channel contract.
- deterministic PCM routing.
- buffer and lifecycle handling.
- fallback to stable path on invalid candidate/input.

### Bridge/controller

Required behavior:

- model selection is explicit.
- start/stop/restart are idempotent.
- background recovery is verified.
- invalid input does not create unsafe output.

## Testing contract

Remote GitHub-only review:

- Code review: AVAILABLE.
- Build: NOT_RUN.
- Tests: NOT_RUN.
- APK: NOT_RUN.
- Device: NOT_RUN.
- Human listening: PENDING_HUMAN.

## Local execution handoff

After this branch is reviewed locally:

1. Build Android project.
2. Run existing unit tests.
3. Install APK from resulting commit.
4. Capture device lifecycle evidence.
5. Compare PCM/output evidence against the selected candidate.

Completion of these steps does not replace acoustic and human gates.
