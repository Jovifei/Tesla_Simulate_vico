# S12 Stage W Frozen PTR/Radiation Integration (W3)

Status: `FROZEN_PTR_INTEGRATION_PASS / RAW_POST_PTR_SPLIT / NOT_R1_QUALIFIED`

Stage W now exposes an optional `ptr_enabled=True` path on
`PersistentEventDomainEngine`. The signal chain is:

```text
persistent event-domain raw source
  -> FrozenPtrStereo (one immutable RuntimePtrAdapter per channel)
  -> post-PTR raw PCM
  -> persistent audition monitor
```

The accepted package and recurrence are reused without changing their source,
state-space values, delays or losses. `FrozenPtrStereo` records the adapter
file SHA, radiation package SHA and accepted source commit in every diagnostic
result. Snapshot/restore includes both adapter channel states.

## Frozen evidence

- Adapter source SHA-256: `2BDCD21182EA083D2079239179EC6CE749B9519C8EA40095D9F202FE86036CFA`
- Package file SHA-256: `0F4B2CA494CD44F79D05968513759578D04E6AB38B1EE37F7621158ABB0D2D6F`
- Package asset SHA: `7DA7AAFDF51BE57ECEE75D98948B7D6C94BEC0944A6316D8A29C9B675D621446`
- Accepted source commit: `4afe65a67ed21822422f1eb6dbf43fdd627072d3`
- W3 focused tests: `2 passed`

The default Stage-V raw path remains unchanged. The new post-PTR path is
explicit and opt-in; it is not a full FVM/PTR network and does not establish
real-time, Android, ESP32 or vehicle qualification.
