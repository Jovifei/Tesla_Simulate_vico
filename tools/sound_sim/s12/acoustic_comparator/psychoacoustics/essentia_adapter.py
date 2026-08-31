"""Optional Essentia subprocess detection; it is never a core dependency."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def detect_essentia(executable: str = "essentia_streaming_extractor_music") -> dict[str, object]:
    """Return the actual optional availability; do not install or vendor Essentia."""

    resolved = shutil.which(executable)
    if not resolved:
        return {
            "tool": "Essentia",
            "license": "AGPL-3.0-only",
            "status": "OPTIONAL_NOT_INSTALLED",
            "actually_invoked": False,
            "limitation": "no isolated Essentia executable detected; Windows Python bindings are not used",
        }
    try:
        version = subprocess.run([resolved, "--version"], check=False, capture_output=True, text=True, timeout=15)
    except OSError as error:
        return {"tool": "Essentia", "license": "AGPL-3.0-only", "status": "OPTIONAL_NOT_INSTALLED", "actually_invoked": False, "limitation": str(error)}
    return {
        "tool": "Essentia",
        "license": "AGPL-3.0-only",
        "status": "RESEARCHED_ONLY",
        "actually_invoked": True,
        "executable": str(Path(resolved)),
        "version_output": (version.stdout + version.stderr).strip(),
        "limitation": "adapter detection only; an explicit isolated analysis invocation is still required",
    }
