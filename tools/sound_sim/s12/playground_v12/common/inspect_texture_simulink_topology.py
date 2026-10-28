"""Read-only archive audit for the v1.2 vehicle Simulink topology."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path


EXPECTED = {
    "90 s Synthetic Vehicle Cycle": "17",
    "Hellcat Synthetic Source": "11",
    "Frozen 4D-B Radiation Adapter": "12",
    "Renderer Input Mux": "14",
    "Stereo Renderer": "15",
    "PCM Output": "16",
}


def audit(model: Path) -> dict:
    with zipfile.ZipFile(model) as archive:
        xml = archive.read("simulink/systems/system_root.xml").decode("utf-8")
    blocks = {}
    for match in re.finditer(r'<Block BlockType="([^"]+)" Name="([^"]+)" SID="([^"]+)">(.*?)</Block>', xml, re.S):
        blocks[match.group(2)] = {"type": match.group(1), "sid": match.group(3)}
    lines = []
    for match in re.finditer(r"<Line>(.*?)</Line>", xml, re.S):
        body = match.group(1)
        source = re.search(r'<P Name="Src">(.*?)</P>', body)
        destinations = re.findall(r'<P Name="Dst">(.*?)</P>', body)
        if source:
            lines.append({"source": source.group(1), "destinations": destinations})
    missing = [name for name in EXPECTED if name not in blocks]
    expected_sids = {name: blocks.get(name, {}).get("sid") for name in EXPECTED}
    source_to_radiation = any(line["source"] == "11#out:1" and any("12#in:1" in dst for dst in line["destinations"]) for line in lines)
    radiation_to_mux = any(line["source"] == "12#out:1" and any("14#in:1" in dst for dst in line["destinations"]) for line in lines)
    return {
        "schema": "s12.v12.texture.simulink.topology.audit.v1",
        "model": str(model),
        "status": "PASS" if not missing and source_to_radiation and radiation_to_mux else "FAIL",
        "expectedBlocks": EXPECTED,
        "actualBlocks": expected_sids,
        "missingBlocks": missing,
        "sourceToFrozenRadiation": source_to_radiation,
        "frozenRadiationToRendererMux": radiation_to_mux,
        "lines": lines,
        "textureInsertionPlan": {
            "copyModel": True,
            "newBlocks": [
                {"type": "In", "name": "Texture Residual", "dimensions": "[960,1]"},
                {"type": "In", "name": "Texture Weight", "dimensions": "[1,1]"},
                {"type": "MATLAB Function", "name": "Texture Mixer", "function": "s12_v12_model_texture_step"},
            ],
            "replaceConnection": "Hellcat Synthetic Source -> Texture Mixer -> Frozen 4D-B Radiation Adapter",
            "defaultWeight": 0,
            "sourceModelUnchanged": True,
            "requiresRuntime": ["Cold Reload", "Update Diagram", "Active Compile", "90s Simulation x2"],
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.model)
    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
