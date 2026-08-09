"""v0.5 content gate for the already accepted PTR/radiation package.

This module does not implement or alter PTR/radiation mathematics. It only
refuses a v0.5 product export when the accepted package bytes drift.
"""

from __future__ import annotations

import hashlib

from s12_ptr_network import DEFAULT_PACKAGE_PATH, QUALIFICATION_COMMIT, load_radiation_package


EXPECTED_RADIATION_PACKAGE_SHA256 = "0f4b2ca494cd44f79d05968513759578d04e6ab38b1ee37f7621158abb0d2d6f"


def verify_frozen_radiation_package() -> dict:
    raw = DEFAULT_PACKAGE_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_RADIATION_PACKAGE_SHA256:
        raise ValueError("accepted radiation package content hash drifted")
    package = load_radiation_package(DEFAULT_PACKAGE_PATH)
    if package.source_commit != QUALIFICATION_COMMIT:
        raise ValueError("accepted radiation package source commit drifted")
    return {
        "configuration": "existing_immutable_v04_ptr_radiation",
        "frozen_math": True,
        "radiation_package_sha256": digest,
        "radiation_source_commit": package.source_commit,
    }
