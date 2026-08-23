"""Pinned timbral_models runner: research descriptor only, never a Stage U hard gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _jsonable(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def run(audio_path: Path, *, extractor: Any | None = None) -> dict[str, Any]:
    """Run descriptors or return the explicit optional-unavailable state."""
    try:
        if extractor is None:
            import timbral_models

            extractor = timbral_models.timbral_extractor
        descriptors = extractor(str(audio_path), output_type="dictionary", verbose=False)
    except ImportError as exc:
        return {
            "classification": "OPTIONAL_RESEARCH_METRIC",
            "project_status": "PROJECT_UNMAINTAINED",
            "hard_gate": False,
            "tool": "AudioCommons timbral_models",
            "version": "0.4.0",
            "status": "PROJECT_UNMAINTAINED_NOT_AVAILABLE",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    except Exception as exc:
        return {
            "classification": "OPTIONAL_RESEARCH_METRIC",
            "project_status": "PROJECT_UNMAINTAINED",
            "hard_gate": False,
            "tool": "AudioCommons timbral_models",
            "version": "0.4.0",
            "status": "PROJECT_UNMAINTAINED_NOT_AVAILABLE",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    return {
        "classification": "OPTIONAL_RESEARCH_METRIC",
        "project_status": "PROJECT_UNMAINTAINED",
        "hard_gate": False,
        "tool": "AudioCommons timbral_models",
        "version": "0.4.0",
        "status": "OPTIONAL_RESEARCH_METRIC_AVAILABLE",
        "descriptors": _jsonable(descriptors),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AudioCommons timbral_models")
    parser.add_argument("--audio", type=Path, required=True)
    arguments = parser.parse_args(argv)
    print(json.dumps(run(arguments.audio), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
