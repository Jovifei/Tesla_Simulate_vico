---
title: FiveM EngineSound License Boundary
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-W
document_type: license_boundary
status: reuse_blocked
source_url: https://github.com/MushroomFleet/Fivem-EngineSound-Simulator
source_commit: f0c12aa5a09d56344f9d96ce989299e900d76b70
license: Apache-2.0-file-conflicts-with-README-MIT
s12_git_branch: agent/s12-stage-w-ecosystem-bakeoff
s12_git_commit: working_tree_pending_next_commit

The Apache LICENSE SHA is `1EB85FC97224598DAD1852B5D6483BBCF0AA8608790DCC657A5A2A761AE9C8C6`,
but README claims MIT. `npm ci && npm run build` passed, yet the conflict blocks
all code reuse; GTA/FiveM parsers and audio assets are prohibited.
