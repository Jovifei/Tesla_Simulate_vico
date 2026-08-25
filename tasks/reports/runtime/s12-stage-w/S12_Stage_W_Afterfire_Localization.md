# S12 Stage W Localized Afterfire (W5)

Status: `AFTERFIRE_LOCATIONIZED_PASS / PTR_PENDING`

Persistent W5 afterfire state now consumes RPM derivative, throttle closure,
fuel reservoir, oxygen proxy, exhaust temperature, cooldown and a configurable
ignition delay. `primary` events enter an entity event tail before the normal
path delay; `collector` events enter the collector state. The two policies
produce different arrival/SHA evidence under equal event energy.

Focused tests: `3 passed`.

The event is still synthetic and source-domain; final post-PTR event metrics and
R1/reference qualification remain pending.
