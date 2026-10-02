# N2 reference calculation driver contract

Offline-only driver contract:

fixture input -> frozen T reference -> N2 transform -> candidate PCM export

Every export records:

- fixture hash
- artifact hash
- profile hash
- calibration hash
- branch identity
- mode identity
- source stem hashes
- event observation hash

Branches:

- T
- S
- E-on
- E-off
- SE-on
- SE-off

Validation matrix includes deterministic 333+297 and 960 partition replay.

No install path is provided by this driver.
