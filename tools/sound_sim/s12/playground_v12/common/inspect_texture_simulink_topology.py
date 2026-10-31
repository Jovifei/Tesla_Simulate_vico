"""Read-only archive audit for the v1.2 vehicle Simulink topology."""

from __future__ import annotations

import json
import hashlib
import zipfile
import xml.etree.ElementTree as ET
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
    model = Path(model)
    plan_path = Path(__file__).resolve().parents[5] / "reports" / "simulink-texture-topology-20261028" / "MODEL_EDIT_PLAN.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    with zipfile.ZipFile(model) as archive:
        root = ET.fromstring(archive.read("simulink/systems/system_root.xml"))
    blocks = {block.get("Name"): {"type": block.get("BlockType"), "sid": block.get("SID"),
              "parameters": {p.get("Name"): p.text for p in block.findall("P")}}
              for block in root.findall("Block")}
    lines = []
    for line in root.findall("Line"):
        source = line.find("P[@Name='Src']")
        if source is not None:
            lines.append({"source": source.text, "destinations": [p.text for p in line.findall(".//P[@Name='Dst']")]})
    edges = {(line["source"], dst) for line in lines for dst in line["destinations"]}
    def connected(source, target):
        return (source, target) in edges
    missing = [name for name in EXPECTED if name not in blocks]
    expected_sids = {name: blocks.get(name, {}).get("sid") for name in EXPECTED}
    source_to_radiation = connected("11#out:1", "12#in:1")
    radiation_to_mux = connected("12#out:1", "14#in:1")
    frozen_chain = radiation_to_mux and connected("14#out:1", "15#in:1") and connected("15#out:1", "16#in:1")
    inports = {name: block for name, block in blocks.items() if block["type"] == "Inport"}
    # SLX omits the built-in Inport Port=1 default from its serialized P list.
    for block in inports.values():
        if "Port" not in block["parameters"]:
            block["parameters"]["Port"] = "1"
            block["archiveDefaultParameters"] = ["Port"]
    additions = [op for op in plan["operations"] if op["op"] == "add_block"]
    mixer_op = next(op for op in additions if op["ref"] == "textureMixer")
    mixer = blocks.get(mixer_op["name"])
    candidate_connections = False
    input_contract = not inports
    if mixer:
        refs = {op["ref"]: blocks.get(op["name"], {}).get("sid") for op in additions}
        refs.update({key: value.removeprefix("blk_") for key, value in plan["confirmedSourceBlocks"].items()})
        def endpoint(value):
            block, port = value.split(".")
            sid = refs.get(block[1:]) if block.startswith("#") else block.removeprefix("blk_")
            return f"{sid}#{'out' if port[0] == 'y' else 'in'}:{port[1:]}"
        candidate_connections = all(connected(*(endpoint(e.strip()) for e in op["target"].split("->")))
                                    for op in plan["operations"] if op["op"] == "connect")
        input_ops = [op for op in additions if op["type"] == "In"]
        input_contract = set(inports) == {op["name"] for op in input_ops} and all(
            all(inports[op["name"]]["parameters"].get(key) == value for key, value in op["params"].items())
            for op in input_ops)
    topology = "candidate" if mixer else "source"
    passed = not missing and expected_sids == EXPECTED and frozen_chain and input_contract and (
        candidate_connections and not source_to_radiation if mixer else source_to_radiation)
    return {
        "schema": "s12.v12.texture.simulink.topology.audit.v1",
        "model": str(model),
        "status": "PASS" if passed else "FAIL",
        "evidenceLevel": "SLX_ARCHIVE_ONLY_NOT_COMPILE_OR_SIMULATION",
        "modelSha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        "topology": topology,
        "rootBlocks": blocks,
        "rootInports": inports,
        "rootInputContract": input_contract,
        "sourceThroughMixerToFrozenRadiation": candidate_connections,
        "frozenOutputChainUnchanged": frozen_chain,
        "expectedBlocks": EXPECTED,
        "actualBlocks": expected_sids,
        "missingBlocks": missing,
        "sourceToFrozenRadiation": source_to_radiation,
        "frozenRadiationToRendererMux": radiation_to_mux,
        "lines": lines,
        "textureInsertionPlan": plan,
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
