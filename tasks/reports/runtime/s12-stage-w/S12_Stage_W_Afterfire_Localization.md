# S12 Stage W Localized Afterfire (W5)

Status: `AFTERFIRE_LOCATIONIZED_PASS / POST_PTR_RENDERED`

Persistent W5 afterfire state now consumes RPM derivative, throttle closure,
fuel reservoir, oxygen proxy, exhaust temperature, cooldown and a configurable
ignition delay. `primary` events enter an entity event tail before the normal
path delay; `collector` events enter the collector state. The two policies
produce different arrival/SHA evidence under equal event energy.

Focused Stage-W tests: `43 passed, 1 skipped`; the three configured routes
(`primary`, `bank_collector`, `central_collector`) expose path id, bank,
collector pressure and arrival-sample diagnostics and are snapshot-safe.

The event remains synthetic and source-domain. The current bake-off emits
post-PTR raw PCM and monitor outputs with the event traces; R1/reference
qualification remains closed.
