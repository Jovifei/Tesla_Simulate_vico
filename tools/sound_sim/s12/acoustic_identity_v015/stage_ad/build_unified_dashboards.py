"""Compatibility entrypoint for the old Stage-AD four-car dashboard command.

The previous implementation rendered candidates through a second EngineAcoustics
renderer and normalized each scene independently.  Stage AE intentionally removes
that as the default path.  New candidate audio is rendered by the canonical S12
PersistentEventDomainEngine via stage_ae.package_audition.
"""
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.package_audition import main

if __name__ == "__main__":
    raise SystemExit(main())
