# S12 Stage W Persistent Engine (W1/W2)

Status: `STAGE_W_PERSISTENT_ENGINE_PASS / FROZEN_PTR_AVAILABLE`

## Implemented contract

`PersistentEventDomainEngine` holds one `CrankPhasePLL`, event tails, per-path
delay histories, collector histories, afterfire reservoir/cooldown, monitor
envelope and sample counter for the lifetime of the object. `process()` accepts
one or many 20 ms state frames; the one-frame and multi-frame paths use the same
internal loop.

The measured-RPM mode uses a soft PLL. The free-dynamics mode removes the hard
RPM tracking torque and lets inertia, friction, load, governor, acceleration
and scheduled combustion torque evolve the angular state. A scheduled event
packet contributes torque at its event samples through a deterministic PLL
replay; any packet tail crossing a block is retained in a bounded queue.

Piston event phases are now derived from `firing_order_evidence` plus cycle
slots. Rotary configurations retain their eccentric-shaft phase list. Snapshot
and restore include PLL, event tails, path histories, collector histories,
afterfire state and monitor gain.

## Fresh evidence

- Fast W1/W2/W4/W5 suite: `23 passed, 1 skipped` (Stage-W focused is
  `91 passed, 1 skipped`).
- Slow gate: `1 passed in 77.09s`; 3000 calls × 960 samples
  matched one-shot processing byte-for-byte and remained under the bounded
  state-memory assertion.
- Scope remains source-domain only: `synthetic`, `uncalibrated`,
  `vehicle-inspired`, `not OEM reproduction`, `NOT_R1_QUALIFIED`,
  `NOT_PROFILE_FREEZE_READY`.

## Current boundary

W3 has now reused the existing `RuntimePtrAdapter` and accepted radiation
package without modifying their source or parameters. The frozen path remains
an explicit post-PTR option; this document does not claim a full FVM/PTR
network or real-time/device qualification.
