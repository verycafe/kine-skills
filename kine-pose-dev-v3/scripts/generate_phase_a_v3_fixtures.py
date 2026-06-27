#!/usr/bin/env python3
"""Generate deterministic fixtures for the Kine Pose Dev V3 contract validator."""

from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


FIXTURE_NAMES = [
    "minimal-pass",
    "bad-missing-director-brief",
    "bad-missing-semantic-motion-plan",
    "bad-missing-occlusion-plan",
    "bad-selected-frame-missing-contract",
    "bad-missing-moving-owner",
    "bad-missing-stable-owner",
    "bad-missing-contact-anchor",
    "bad-missing-overlap-expectation",
    "bad-missing-provenance",
    "bad-programmatic-character-pixels",
    "bad-local-repair-promoted",
    "bad-local-transform-selected",
    "bad-missing-stable-action-gate",
    "bad-final-preview-source",
    "bad-source-pose-snapback-not-blocked",
    "bad-detached-child-not-blocked",
    "bad-component-sheet-selected",
]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_placeholder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder artifact for deterministic V3 contract tests\n", encoding="utf-8")


def base_task() -> dict[str, Any]:
    task_id = "phase-a-v3-fixture"
    frame_id = "pose_00"
    return {
        "files": {
            "phase-a-v3/source.png": "placeholder",
            "phase-a-v3/intake.json": {
                "taskId": task_id,
                "motionRequest": "high knee march with stable left foot contact",
                "targetOutput": ["selected_frames", "gif", "strip", "board"],
                "status": "recorded",
            },
            "phase-a-v3/animation-director-brief.json": {
                "taskId": task_id,
                "subjectType": "character",
                "motionIntent": "high knee march",
                "normalizedAction": "right knee lifts while left foot supports the character",
                "durationSeconds": 1.0,
                "fps": 24,
                "selectedActionFrameCount": 1,
                "exposurePolicy": "blocking_fixture",
                "actionGateProfiles": ["action_plan_gate", "alternating_locomotion_gate", "contact_support_gate"],
                "requiredVisualVerdicts": [
                    "actionPlan",
                    "motionBeatsCovered",
                    "noEndpointTeleport",
                    "phaseOwnership",
                    "phaseDistinctness",
                    "oppositeLimbCoordination",
                    "contactStability",
                    "supportContactAccuracy",
                ],
                "largePoseOrStateChange": True,
                "actionBeats": ["right knee lifts", "left foot supports"],
                "primaryStableAnchor": "left_foot_ground",
                "motionBudget": {"body": "medium", "arms": "small", "head": "stable"},
                "sourceFramingPolicy": "preserve full character",
                "hardRejects": ["source_pose_snapback", "detached_child", "joint_hole"],
                "status": "ready",
            },
            "phase-a-v3/semantic-motion-plan.json": {
                "taskId": task_id,
                "owners": ["head", "torso", "right_leg", "left_leg", "left_foot", "right_arm", "prop_none"],
                "movingOwners": ["right_leg", "right_arm"],
                "stableOwners": ["left_foot", "torso"],
                "ownerChildRules": [{"owner": "right_leg", "children": ["right_knee", "right_foot"]}],
                "propOwners": ["none"],
                "contactOwners": ["left_foot"],
                "secondaryOwners": ["hair"],
                "forbiddenOwnerChanges": ["right_foot_detached", "left_foot_sliding"],
                "status": "ready",
            },
            "phase-a-v3/per-frame-occlusion-plan.json": {
                "taskId": task_id,
                "frames": [
                    {
                        "frameId": frame_id,
                        "subjectType": "character",
                        "actionBeat": "right knee lifts while left foot supports",
                        "movingOwners": ["right_leg", "right_arm"],
                        "stableOwners": ["left_foot", "torso"],
                        "actionGateProfiles": ["action_plan_gate", "alternating_locomotion_gate", "contact_support_gate"],
                        "requiredVisualVerdicts": [
                            "actionPlan",
                            "motionBeatsCovered",
                            "noEndpointTeleport",
                            "phaseOwnership",
                            "phaseDistinctness",
                            "oppositeLimbCoordination",
                            "contactStability",
                            "supportContactAccuracy",
                        ],
                        "contactAnchors": ["left_foot_ground"],
                        "occlusionExpectations": [
                            {"frontOwner": "right_thigh", "backOwner": "torso", "risk": "hip_overlap"}
                        ],
                        "overlapExpectations": ["right_hip_overlap", "left_foot_ground_contact"],
                        "propContinuity": ["none"],
                        "forbiddenFailures": ["source_pose_snapback", "detached_child", "joint_hole"],
                    }
                ],
            },
            "soft_controls/pose_00-control.png": "placeholder",
            "candidates_unverified/pose_00-candidate.png": "placeholder",
            "frames_selected/pose_00-selected.png": "placeholder",
            "check/final.gif": "placeholder",
            "check/final-strip.png": "placeholder",
            "sheets/final-board.png": "placeholder",
            "qa/semantic-owner-review-board.svg": "placeholder",
            "qa/occlusion-overlap-review-board.svg": "placeholder",
            "qa/contact-anchor-review-board.svg": "placeholder",
            "qa/sequence-motion-stability-board.svg": "placeholder",
            "visual_gates/pose_00.json": {
                "taskId": task_id,
                "frameId": frame_id,
                "status": "pass",
                "selectedImage": "frames_selected/pose_00-selected.png",
                "candidateImage": "candidates_unverified/pose_00-candidate.png",
                "controlImage": "soft_controls/pose_00-control.png",
                "failures": [],
                "actionGateProfiles": ["action_plan_gate", "alternating_locomotion_gate", "contact_support_gate"],
                "requiredVisualVerdicts": [
                    "actionPlan",
                    "motionBeatsCovered",
                    "noEndpointTeleport",
                    "phaseOwnership",
                    "phaseDistinctness",
                    "oppositeLimbCoordination",
                    "contactStability",
                    "supportContactAccuracy",
                ],
                "verdict": {
                    "actionPlan": "pass",
                    "motionBeatsCovered": "pass",
                    "noEndpointTeleport": "pass",
                    "phaseOwnership": "pass",
                    "phaseDistinctness": "pass",
                    "oppositeLimbCoordination": "pass",
                    "contactStability": "pass",
                    "supportContactAccuracy": "pass",
                    "actionReadability": "pass",
                    "identityPreserved": "pass",
                    "originalCharacterTreatment": "pass",
                    "notPoseProxy": "pass",
                    "ownerMotionCoherence": "pass",
                    "occlusionOverlapPlausibility": "pass",
                    "contactContinuity": "pass",
                    "propContinuity": "pass",
                    "provenanceValidity": "pass",
                    "wholeSubjectActionFrame": "pass",
                },
            },
            "phase-a-v3/frame-generation-provenance.json": {
                "taskId": task_id,
                "frames": {
                    frame_id: {
                        "method": "imagegen",
                        "model": "fixture-image-model",
                        "sourceImages": ["phase-a-v3/source.png"],
                        "controlImages": ["soft_controls/pose_00-control.png"],
                        "programmaticSubjectPixels": False,
                    }
                },
            },
            "selected-frame-registry.json": {
                "taskId": task_id,
                "frames": [
                    {
                        "frameId": frame_id,
                        "status": "selected",
                        "selectedImage": "frames_selected/pose_00-selected.png",
                        "candidateSource": "candidates_unverified/pose_00-candidate.png",
                        "visualGate": "visual_gates/pose_00.json",
                        "doNotRegenerate": False,
                    }
                ],
            },
            "phase-a-v3/phase-a-v3-qa.json": {
                "taskId": task_id,
                "frameQa": {
                    frame_id: {
                        "frameId": frame_id,
                        "status": "pass",
                        "failures": [],
                        "evidence": {
                            "semanticOwnerReviewBoard": "qa/semantic-owner-review-board.svg",
                            "occlusionOverlapReviewBoard": "qa/occlusion-overlap-review-board.svg",
                            "contactAnchorReviewBoard": "qa/contact-anchor-review-board.svg",
                        },
                    }
                },
                "sequenceQa": {
                    "status": "pass",
                    "failures": [],
                    "evidence": {"sequenceMotionStabilityBoard": "qa/sequence-motion-stability-board.svg"},
                },
                "reviewer": "independent_fixture_review",
                "reviewIndependence": "independent",
                "status": "deliverable_candidate",
                "failures": [],
                "evidence": {
                    "semanticOwnerReviewBoard": "qa/semantic-owner-review-board.svg",
                    "occlusionOverlapReviewBoard": "qa/occlusion-overlap-review-board.svg",
                    "contactAnchorReviewBoard": "qa/contact-anchor-review-board.svg",
                    "sequenceMotionStabilityBoard": "qa/sequence-motion-stability-board.svg",
                },
            },
            "qa/final-preview-source.json": {
                "taskId": task_id,
                "previews": [
                    {"role": "final_sequence_gif", "path": "check/final.gif"},
                    {"role": "final_sequence_gif_strip", "path": "check/final-strip.png"},
                    {"role": "final_sequence_board", "path": "sheets/final-board.png"},
                    {"role": "selected_frames_preview", "path": "frames_selected/pose_00-selected.png"},
                ],
            },
            "phase-a-v3/manifest.json": {
                "taskId": task_id,
                "artifacts": [
                    {"role": "intake", "path": "phase-a-v3/intake.json"},
                    {"role": "director_brief", "path": "phase-a-v3/animation-director-brief.json"},
                    {"role": "semantic_motion_plan", "path": "phase-a-v3/semantic-motion-plan.json"},
                    {"role": "per_frame_occlusion_plan", "path": "phase-a-v3/per-frame-occlusion-plan.json"},
                    {"role": "frame_generation_provenance", "path": "phase-a-v3/frame-generation-provenance.json"},
                    {"role": "phase_a_v3_qa", "path": "phase-a-v3/phase-a-v3-qa.json"},
                ],
            },
        }
    }


def remove_file(task: dict[str, Any], path: str) -> None:
    task["files"].pop(path, None)


def mutate_frame(task: dict[str, Any], callback: Callable[[dict[str, Any]], None]) -> None:
    frame = task["files"]["phase-a-v3/per-frame-occlusion-plan.json"]["frames"][0]
    callback(frame)


def mutate_gate(task: dict[str, Any], callback: Callable[[dict[str, Any]], None]) -> None:
    callback(task["files"]["visual_gates/pose_00.json"])


def mutate_qa(task: dict[str, Any], callback: Callable[[dict[str, Any]], None]) -> None:
    callback(task["files"]["phase-a-v3/phase-a-v3-qa.json"])


def mutate_provenance(task: dict[str, Any], callback: Callable[[dict[str, Any]], None]) -> None:
    callback(task["files"]["phase-a-v3/frame-generation-provenance.json"]["frames"]["pose_00"])


def task_for_fixture(name: str) -> dict[str, Any]:
    task = base_task()
    if name == "minimal-pass":
        return task
    if name == "bad-missing-director-brief":
        remove_file(task, "phase-a-v3/animation-director-brief.json")
    elif name == "bad-missing-semantic-motion-plan":
        remove_file(task, "phase-a-v3/semantic-motion-plan.json")
    elif name == "bad-missing-occlusion-plan":
        remove_file(task, "phase-a-v3/per-frame-occlusion-plan.json")
    elif name == "bad-selected-frame-missing-contract":
        mutate_frame(task, lambda frame: frame.__setitem__("frameId", "pose_99"))
    elif name == "bad-missing-moving-owner":
        mutate_frame(task, lambda frame: frame.__setitem__("movingOwners", []))
    elif name == "bad-missing-stable-owner":
        mutate_frame(task, lambda frame: frame.__setitem__("stableOwners", []))
    elif name == "bad-missing-contact-anchor":
        mutate_frame(task, lambda frame: frame.__setitem__("contactAnchors", []))
    elif name == "bad-missing-overlap-expectation":
        mutate_frame(task, lambda frame: frame.__setitem__("overlapExpectations", []))
    elif name == "bad-missing-provenance":
        remove_file(task, "phase-a-v3/frame-generation-provenance.json")
    elif name == "bad-programmatic-character-pixels":
        mutate_provenance(task, lambda prov: prov.__setitem__("programmaticSubjectPixels", True))
    elif name == "bad-local-repair-promoted":
        task["files"]["local_repair_candidates/pose_00-repaired.png"] = "placeholder"
        task["files"]["selected-frame-registry.json"]["frames"][0]["candidateSource"] = "local_repair_candidates/pose_00-repaired.png"
        task["files"]["selected-frame-registry.json"]["frames"][0]["localRepairCandidate"] = True
        mutate_provenance(task, lambda prov: prov.__setitem__("method", "local_repair_model_edit"))
        mutate_gate(task, lambda gate: gate.__setitem__("localRepairCandidate", True))
    elif name == "bad-local-transform-selected":
        mutate_provenance(task, lambda prov: prov.__setitem__("method", "manual_source_preserving_edit"))
        mutate_provenance(task, lambda prov: prov.__setitem__("model", "PIL/Numpy local warp fixture"))
    elif name == "bad-missing-stable-action-gate":
        mutate_gate(task, lambda gate: gate["verdict"].pop("actionPlan", None))
    elif name == "bad-final-preview-source":
        task["files"]["qa/final-preview-source.json"]["previews"][0] = {
            "role": "character_candidate",
            "path": "candidates_unverified/pose_00-candidate.png",
        }
    elif name == "bad-source-pose-snapback-not-blocked":
        mutate_gate(task, lambda gate: gate.__setitem__("observedFailures", ["source_pose_snapback"]))
    elif name == "bad-detached-child-not-blocked":
        def bad_child(qa: dict[str, Any]) -> None:
            qa["frameQa"]["pose_00"]["observedFailures"] = ["detached_child"]

        mutate_qa(task, bad_child)
    elif name == "bad-component-sheet-selected":
        task["files"]["component_sheets/pose_00-component-sheet.png"] = "placeholder"
        task["files"]["selected-frame-registry.json"]["frames"][0]["selectedImage"] = "frames_selected/pose_00-component-sheet.png"
        task["files"]["frames_selected/pose_00-component-sheet.png"] = "placeholder"
        mutate_gate(
            task,
            lambda gate: (
                gate.__setitem__("selectedImage", "frames_selected/pose_00-component-sheet.png"),
                gate["verdict"].__setitem__("wholeSubjectActionFrame", "fail"),
            ),
        )
    else:
        raise ValueError(f"Unknown fixture: {name}")
    return task


def write_task(root: Path, task: dict[str, Any]) -> None:
    for relative, value in task["files"].items():
        path = root / relative
        if isinstance(value, dict):
            write_json(path, value)
        else:
            write_placeholder(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="fixtures/phase-a-v3", help="Fixture output root.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing fixture root.")
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    if root.exists():
        if not args.force:
            raise SystemExit(f"Fixture root already exists: {root}. Pass --force to replace it.")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    for name in FIXTURE_NAMES:
        write_task(root / name, deepcopy(task_for_fixture(name)))

    write_json(
        root / "fixture-index.json",
        {
            "format": "kinePoseDevV3.fixtureIndex",
            "version": "0.1",
            "fixtures": FIXTURE_NAMES,
            "rule": "Fixtures are deterministic contract tests, not visual truth tests.",
        },
    )
    print(json.dumps({"status": "generated", "root": str(root), "fixtures": FIXTURE_NAMES}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
