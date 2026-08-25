# S12 Stage W Persistent Engine (W1/W2)

Status: `STAGE_W_PERSISTENT_ENGINE_PASS / PTR_PENDING`

## Implemented contract

`PersistentEventDomainEngine` holds one `CrankPhasePLL`, event tails, per-path
delay histories, collector histories, afterfire reservoir/cooldown, monitor
envelope and sample counter for the lifetime of the object. `process()` accepts
one or many 20 ms state frames; the one-frame and multi-frame paths use the same
internal loop.

The measured-RPM mode uses a soft PLL. The free-dynamics mode removes the hard
RPM tracking torque and lets inertia, friction, load, governor, acceleration
and prior scheduled combustion torque evolve the angular state. A scheduled
event packet contributes torque to the next frame, so it affects subsequent
omega and phase rather than only being a post-render diagnostic.

Piston event phases are now derived from `firing_order_evidence` plus cycle
slots. Rotary configurations retain their eccentric-shaft phase list. Snapshot
and restore include PLL, event tails, path histories, collector histories,
afterfire state and monitor gain.

## Fresh evidence

- Fast W1/W2 suite: `5 passed, 1 skipped` (slow gate is separately enabled).
- Slow gate: `1 passed, 5 deselected in 385.63s`; 3000 calls × 960 samples
  matched one-shot processing byte-for-byte and remained under the bounded
  state-memory assertion.
- Scope remains source-domain only: `synthetic`, `uncalibrated`,
  `vehicle-inspired`, `not OEM reproduction`, `NOT_R1_QUALIFIED`,
  `NOT_PROFILE_FREEZE_READY`.

## Remaining boundary

The W1/W2 output is not yet passed through frozen PTR/Radiation. W3 must reuse
the existing `RuntimePtrAdapter` and accepted radiation package without
modifying their source or parameters.
