#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description="Initialize a KINE SVG DEV task.")
    parser.add_argument("--source", required=True, help="Source image path.")
    parser.add_argument("--out-dir", required=True, help="Task output directory.")
    parser.add_argument("--slug", required=True, help="Task slug.")
    parser.add_argument(
        "--intent",
        default="source_master_only",
        choices=["source_master_only", "animation_ready_plan", "runtime_or_animation"],
    )
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as img:
        width, height = img.size
        alpha = img.mode in {"RGBA", "LA"} or ("transparency" in img.info)

    manifest_name = f"{args.slug}-manifest.json"
    ledger_name = f"{args.slug}-component-ledger.json"
    audit_name = f"{args.slug}-source-audit.json"
    qa_name = f"{args.slug}-qa.json"
    readiness_name = f"{args.slug}-kine-readiness.json"
    svg_name = f"{args.slug}-layered.svg"
    preview_name = f"{args.slug}-preview.png"
    compare_name = f"{args.slug}-compare.png"

    manifest = {
        "taskId": args.slug,
        "source": {
            "path": str(source),
            "width": width,
            "height": height,
            "alpha": alpha,
            "sourceType": "raster_only",
        },
        "intent": args.intent,
        "outputs": {
            "sourceAudit": audit_name,
            "componentLedger": ledger_name,
            "layeredSvg": svg_name,
            "previewPng": preview_name,
            "comparePng": compare_name,
            "qaJson": qa_name,
            "kineReadiness": readiness_name,
        },
        "status": "wip",
    }

    ledger = {
        "coordinateConvention": "screen_left_right",
        "components": [
            {
                "id": "character",
                "parent": None,
                "drawOrder": 10,
                "bbox": [0, 0, width, height],
                "pivot": [width / 2, height / 2],
                "movable": False,
                "sourceConfidence": "visible",
                "role": "full visible subject",
            }
        ],
    }

    audit = {
        "status": "wip",
        "sourcePath": str(source),
        "canvas": {"width": width, "height": height, "alpha": alpha},
        "identityMarkers": [],
        "silhouetteCriticalParts": [],
        "missingHiddenSurfaces": [],
        "driftRisks": [],
    }

    qa = {
        "status": "wip",
        "checks": {
            "canvasMatchesSource": "not_checked",
            "transparentBackground": "not_checked",
            "identityPreserved": "not_checked",
            "ledgerGroupsPresent": "not_checked",
            "riskySvgFeaturesAbsent": "not_checked",
        },
        "failures": [],
        "notes": [],
    }

    readiness = {
        "status": "wip",
        "pivotCandidates": [],
        "ownerHierarchy": [],
        "drawOrderNotes": [],
        "hiddenSurfaceNeeds": [],
        "transformOnlySafeParts": [],
        "requiresMeshSkinOrConstraintsLater": [],
    }

    for name, data in [
        (manifest_name, manifest),
        (ledger_name, ledger),
        (audit_name, audit),
        (qa_name, qa),
        (readiness_name, readiness),
    ]:
        (out_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    print(json.dumps({"taskDir": str(out_dir), "manifest": str(out_dir / manifest_name)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
