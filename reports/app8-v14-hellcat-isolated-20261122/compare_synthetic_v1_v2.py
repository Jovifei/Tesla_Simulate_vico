"""Apply the predeclared V2 energy guard without altering either run."""
import hashlib
import json
from pathlib import Path
import sys


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main(root):
    root = Path(root)
    v1_path = root / "synthetic_diagnostic" / "analysis.json"
    v2_path = root / "synthetic_diagnostic_v2" / "analysis.json"
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    if len(v1["conditions"]) != 2 or len(v2["conditions"]) != 2:
        raise ValueError("Expected exactly two conditions")
    comparisons = []
    passed = True
    for old, new in zip(v1["conditions"], v2["conditions"], strict=True):
        if (old["rpm"], old["load"]) != (new["rpm"], new["load"]):
            raise ValueError("Condition order or values changed")
        item = {"rpm": old["rpm"], "load": old["load"], "stems": {}}
        for stem in ("source", "frozen", "combined"):
            a, b = old[stem], new[stem]
            rms_delta = b["rms_dbfs"] - a["rms_dbfs"]
            bass_delta = b["bands"]["20_80_hz_dbfs"] - a["bands"]["20_80_hz_dbfs"]
            stem_passed = rms_delta <= 0 and bass_delta <= 0 and b["clip_count"] == 0
            passed &= stem_passed
            item["stems"][stem] = {
                "rms_delta_db": rms_delta,
                "20_80_delta_db": bass_delta,
                "v1_order_8_over_4_db": a["orders"]["8"]["power_dbfs"] - a["orders"]["4"]["power_dbfs"],
                "v2_order_8_over_4_db": b["orders"]["8"]["power_dbfs"] - b["orders"]["4"]["power_dbfs"],
                "v1_order_to_residual_db": a["order_to_residual_db"],
                "v2_order_to_residual_db": b["order_to_residual_db"],
                "v1_peak_dbfs": a["peak_dbfs"],
                "v2_peak_dbfs": b["peak_dbfs"],
                "clip_count": b["clip_count"],
                "guard_passed": stem_passed,
            }
        comparisons.append(item)
    result = {
        "status": "PASS" if passed else "FAIL_ENERGY_GUARD",
        "qualification": "SYNTHETIC_DIAGNOSTIC_NO_ACOUSTIC_ACCEPTANCE",
        "guard": "1-3s RMS and 20-80Hz power do not increase for any stem or condition",
        "v1_analysis_sha256": digest(v1_path),
        "v2_analysis_sha256": digest(v2_path),
        "conditions": comparisons,
    }
    destination = root / "synthetic_diagnostic_v2" / "v1_v2_comparison.json"
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"SYNTHETIC_V2_GUARD_{result['status']} {destination}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: compare_synthetic_v1_v2.py ABSOLUTE_ARTIFACT_ROOT")
    main(sys.argv[1])
