#!/usr/bin/env python3
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


RISKY_TAGS = {
    "filter",
    "mask",
    "foreignObject",
    "script",
    "iframe",
    "video",
    "audio",
    "image",
}


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def main():
    parser = argparse.ArgumentParser(description="Audit a layered SVG against a component ledger.")
    parser.add_argument("--svg", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--manifest")
    args = parser.parse_args()

    svg_path = Path(args.svg)
    ledger_path = Path(args.ledger)

    failures = []
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError as exc:
        print(json.dumps({"status": "fail", "failures": [f"invalid XML: {exc}"]}, indent=2))
        return 1

    if local_name(root.tag) != "svg":
        failures.append("root element is not svg")
    if "viewBox" not in root.attrib:
        failures.append("missing root viewBox")

    ids = {el.attrib["id"] for el in root.iter() if "id" in el.attrib}
    risky = sorted({local_name(el.tag) for el in root.iter() if local_name(el.tag) in RISKY_TAGS})
    if risky:
        failures.append("risky SVG elements present: " + ", ".join(risky))

    ledger = json.loads(ledger_path.read_text())
    component_ids = [item["id"] for item in ledger.get("components", []) if item.get("id")]
    missing = [component_id for component_id in component_ids if component_id not in ids]
    if missing:
        failures.append("ledger component ids missing from SVG: " + ", ".join(missing))

    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text())
        expected_svg = manifest.get("outputs", {}).get("layeredSvg")
        if expected_svg and Path(expected_svg).name != svg_path.name:
            failures.append("manifest layeredSvg does not match SVG filename")

    result = {
        "status": "pass" if not failures else "fail",
        "svg": str(svg_path),
        "componentCount": len(component_ids),
        "svgIdCount": len(ids),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
