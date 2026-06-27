#!/usr/bin/env python3
"""Build text-first QA evidence boards for a Kine Pose Dev V3 task.

The generated SVG boards summarize the V3 contracts. They are QA evidence only
and must never be listed as final-preview sources.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import date
from pathlib import Path
from typing import Any


BOARD_WIDTH = 1280
LINE_HEIGHT = 28
MARGIN = 32


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if path.is_dir():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def first_existing(root: Path, *relative_paths: str) -> Path | None:
    for relative in relative_paths:
        path = root / relative
        if path.exists():
            return path
    return None


def as_text(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(as_text(item) for item in value) or "none"
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(f"{key}: {as_text(item)}")
        return "; ".join(parts) or "none"
    return str(value)


def frame_rows(root: Path) -> list[dict[str, Any]]:
    plan_path = first_existing(
        root,
        "per-frame-occlusion-plan.json",
        "phase-a-v3/per-frame-occlusion-plan.json",
        "phase_a/per_frame_occlusion_plan/per-frame-occlusion-plan.json",
    )
    plan = read_json(plan_path) if plan_path else {}
    frames = plan.get("frames", [])
    return frames if isinstance(frames, list) else []


def selected_rows(root: Path) -> list[dict[str, Any]]:
    registry = read_json(root / "selected-frame-registry.json")
    frames = registry.get("frames", [])
    if not isinstance(frames, list):
        return []
    return [frame for frame in frames if isinstance(frame, dict) and frame.get("status") == "selected"]


def svg_board(title: str, lines: list[str]) -> str:
    escaped_lines = [html.escape(line) for line in lines]
    height = max(240, MARGIN * 2 + 54 + len(escaped_lines) * LINE_HEIGHT)
    text_nodes = []
    y = MARGIN + 64
    for line in escaped_lines:
        text_nodes.append(f'<text x="{MARGIN}" y="{y}" class="line">{line}</text>')
        y += LINE_HEIGHT
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{BOARD_WIDTH}" height="{height}" viewBox="0 0 {BOARD_WIDTH} {height}">',
            "<style>",
            "rect.bg{fill:#f8f7f3} text.title{font:700 30px Arial,sans-serif;fill:#14213d}",
            "text.meta{font:14px Arial,sans-serif;fill:#5c677d} text.line{font:18px Menlo,Consolas,monospace;fill:#1f2937}",
            "</style>",
            f'<rect class="bg" x="0" y="0" width="{BOARD_WIDTH}" height="{height}"/>',
            f'<text x="{MARGIN}" y="{MARGIN + 18}" class="title">{html.escape(title)}</text>',
            f'<text x="{MARGIN}" y="{MARGIN + 42}" class="meta">Kine Pose Dev V3 Phase A QA evidence. Not final preview.</text>',
            *text_nodes,
            "</svg>",
        ]
    )


def write_svg(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg_board(title, lines), encoding="utf-8")


def artifact_path(path: Path) -> str:
    return str(path.expanduser().resolve())


def build_boards(task_root: Path, output_dir: Path) -> list[dict[str, str]]:
    frames = frame_rows(task_root)
    selected = selected_rows(task_root)
    semantic_path = first_existing(
        task_root,
        "phase-a-v3/semantic-motion-plan.json",
        "semantic-motion-plan.json",
        "phase_a/semantic_motion_plan/semantic-motion-plan.json",
    )
    semantic = read_json(semantic_path) if semantic_path else {}
    qa_path = first_existing(task_root, "phase-a-v3/phase-a-v3-qa.json", "phase-a-v3-qa.json", "qa/phase-a-v3-qa.json")
    qa = read_json(qa_path) if qa_path else {}
    provenance_path = first_existing(task_root, "phase-a-v3/frame-generation-provenance.json", "frame-generation-provenance.json")
    provenance = read_json(provenance_path) if provenance_path else {}

    selected_ids = {str(item.get("frameId")) for item in selected}
    artifacts: list[dict[str, str]] = []

    semantic_lines = [
        f"task: {semantic.get('taskId', task_root.name)}",
        f"moving owners: {as_text(semantic.get('movingOwners'))}",
        f"stable owners: {as_text(semantic.get('stableOwners'))}",
        f"owner-child rules: {as_text(semantic.get('ownerChildRules'))}",
        f"forbidden owner changes: {as_text(semantic.get('forbiddenOwnerChanges'))}",
        "",
        "selected frame owner checks:",
    ]
    for frame in frames:
        frame_id = str(frame.get("frameId") or "<missing>")
        marker = "SELECTED" if frame_id in selected_ids else "planned"
        semantic_lines.append(
            f"{marker} {frame_id}: moving={as_text(frame.get('movingOwners'))} | stable={as_text(frame.get('stableOwners'))}"
        )
    path = output_dir / "semantic-owner-review-board.svg"
    write_svg(path, "Semantic Owner Review", semantic_lines)
    artifacts.append({"role": "semantic_owner_review_board", "path": artifact_path(path)})

    occlusion_lines = []
    for frame in frames:
        frame_id = str(frame.get("frameId") or "<missing>")
        occlusion_lines.append(f"{frame_id} beat: {as_text(frame.get('actionBeat'))}")
        occlusion_lines.append(f"  occlusion: {as_text(frame.get('occlusionExpectations'))}")
        occlusion_lines.append(f"  overlap:   {as_text(frame.get('overlapExpectations'))}")
        occlusion_lines.append(f"  forbidden: {as_text(frame.get('forbiddenFailures'))}")
    path = output_dir / "occlusion-overlap-review-board.svg"
    write_svg(path, "Occlusion And Overlap Review", occlusion_lines or ["no frame rows"])
    artifacts.append({"role": "occlusion_overlap_review_board", "path": artifact_path(path)})

    contact_lines = []
    for frame in frames:
        frame_id = str(frame.get("frameId") or "<missing>")
        contact_lines.append(f"{frame_id}: contact={as_text(frame.get('contactAnchors'))} | prop={as_text(frame.get('propContinuity'))}")
    path = output_dir / "contact-anchor-review-board.svg"
    write_svg(path, "Contact Anchor Review", contact_lines or ["no contact rows"])
    artifacts.append({"role": "contact_anchor_review_board", "path": artifact_path(path)})
    path = output_dir / "contact-anchor-crop-sheet.svg"
    write_svg(
        path,
        "Contact Anchor Crop Sheet",
        [
            "Text-first crop-sheet manifest. Attach real crop paths in frame QA when available.",
            *contact_lines,
        ]
        or ["no contact rows"],
    )
    artifacts.append({"role": "contact_anchor_crop_sheet", "path": artifact_path(path)})

    repair_lines = []
    provenance_frames = provenance.get("frames", {})
    for entry in selected:
        frame_id = str(entry.get("frameId") or "<missing>")
        frame_prov = provenance_frames.get(frame_id, {}) if isinstance(provenance_frames, dict) else {}
        method = frame_prov.get("method") or entry.get("method") or "unknown"
        local = "yes" if "repair" in str(method).lower() or entry.get("localRepairCandidate") else "no"
        repair_lines.append(f"{frame_id}: localRepair={local} | method={method} | gate={entry.get('visualGate')}")
    path = output_dir / "local-repair-review-board.svg"
    write_svg(path, "Local Repair Review", repair_lines or ["no selected local-repair rows"])
    artifacts.append({"role": "local_repair_review_board", "path": artifact_path(path)})
    path = output_dir / "local-repair-before-after-sheet.svg"
    write_svg(
        path,
        "Local Repair Before/After Sheet",
        [
            "Text-first before/after manifest. Attach candidate and repaired image paths when available.",
            *repair_lines,
        ]
        or ["no selected local-repair rows"],
    )
    artifacts.append({"role": "local_repair_before_after_sheet", "path": artifact_path(path)})

    sequence = qa.get("sequenceQa", {}) if isinstance(qa.get("sequenceQa"), dict) else {}
    sequence_lines = [
        f"sequence status: {sequence.get('status', 'unknown')}",
        f"sequence failures: {as_text(sequence.get('failures'))}",
        f"sequence evidence: {as_text(sequence.get('evidence'))}",
        "",
        "selected order:",
    ]
    for idx, entry in enumerate(selected, start=1):
        sequence_lines.append(f"{idx:02d}. {entry.get('frameId')} -> {entry.get('selectedImage')}")
    path = output_dir / "sequence-motion-stability-board.svg"
    write_svg(path, "Sequence Motion Stability Review", sequence_lines)
    artifacts.append({"role": "sequence_motion_stability_board", "path": artifact_path(path)})
    return artifacts


def update_qa_evidence(task_root: Path, artifacts: list[dict[str, str]]) -> None:
    qa_path = first_existing(task_root, "phase-a-v3/phase-a-v3-qa.json", "phase-a-v3-qa.json", "qa/phase-a-v3-qa.json")
    if not qa_path:
        return
    qa = read_json(qa_path)
    evidence = qa.setdefault("evidence", {})
    if isinstance(evidence, dict):
        for artifact in artifacts:
            evidence[artifact["role"]] = artifact["path"]
    sequence = qa.setdefault("sequenceQa", {})
    if isinstance(sequence, dict):
        seq_evidence = sequence.setdefault("evidence", {})
        if isinstance(seq_evidence, dict):
            for artifact in artifacts:
                if artifact["role"] == "sequence_motion_stability_board":
                    seq_evidence["sequenceMotionStabilityBoard"] = artifact["path"]
    write_json(qa_path, qa)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_root", help="Phase A V3 task root.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to <task_root>/qa.")
    parser.add_argument("--no-update-qa", action="store_true", help="Do not attach generated evidence to phase-a-v3-qa.json.")
    args = parser.parse_args()

    task_root = Path(args.task_root).expanduser()
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else task_root / "qa"
    artifacts = build_boards(task_root, output_dir)
    manifest = {
        "format": "kinePoseDevV3.qaEvidenceManifest",
        "version": "0.1",
        "date": date.today().isoformat(),
        "taskRoot": str(task_root),
        "rule": "These boards are QA evidence only and are forbidden as final-preview sources.",
        "artifacts": artifacts,
    }
    manifest_path = output_dir / "phase-a-v3-evidence-manifest.json"
    write_json(manifest_path, manifest)
    if not args.no_update_qa:
        update_qa_evidence(task_root, artifacts)
    print(json.dumps({"status": "built", "manifest": str(manifest_path), "artifacts": artifacts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
