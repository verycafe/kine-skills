#!/usr/bin/env python3
"""Validate a Kine Pose Dev V3 Phase A task contract.

This validator checks records and evidence paths. It does not judge artistic
truth; it requires explicit independent QA records that prevent known visual
failures from entering selected-frame or final-preview evidence.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_DIRECTOR_FIELDS = [
    "taskId",
    "subjectType",
    "motionIntent",
    "normalizedAction",
    "durationSeconds",
    "fps",
    "selectedActionFrameCount",
    "exposurePolicy",
    "actionGateProfiles",
    "requiredVisualVerdicts",
    "actionBeats",
    "primaryStableAnchor",
    "motionBudget",
    "sourceFramingPolicy",
    "hardRejects",
    "status",
]

REQUIRED_SEMANTIC_FIELDS = [
    "taskId",
    "owners",
    "movingOwners",
    "stableOwners",
    "ownerChildRules",
    "propOwners",
    "contactOwners",
    "secondaryOwners",
    "forbiddenOwnerChanges",
    "status",
]

REQUIRED_FRAME_FIELDS = [
    "frameId",
    "subjectType",
    "actionBeat",
    "movingOwners",
    "stableOwners",
    "actionGateProfiles",
    "requiredVisualVerdicts",
    "contactAnchors",
    "occlusionExpectations",
    "overlapExpectations",
    "forbiddenFailures",
]

REQUIRED_QA_FIELDS = [
    "taskId",
    "frameQa",
    "sequenceQa",
    "reviewer",
    "reviewIndependence",
    "status",
    "failures",
    "evidence",
]

ALLOWED_FINAL_PREVIEW_ROLES = {
    "final_sequence_gif",
    "final_sequence_gif_strip",
    "final_sequence_board",
    "selected_frames_preview",
    "selected_frame_preview",
}

DISALLOWED_FINAL_PREVIEW_PARTS = {
    "candidates_unverified",
    "local_repair_candidates",
    "rejected",
    "soft_controls",
    "control-vs-candidate",
    "control_vs_candidate",
    "component_sheets",
    "parts_sheets",
    "pose_proxy",
    "placeholder",
}

ALLOWED_GENERATION_METHODS = {
    "imagegen",
    "imggen",
    "model_edit",
    "masked_model_edit",
    "source_preserving_edit",
    "manual_source_preserving_edit",
    "local_repair_model_edit",
}

LOCAL_TRANSFORM_METHODS = {
    "source_preserving_edit",
    "manual_source_preserving_edit",
    "local_cutout",
    "local_warp",
    "warp",
    "mesh_deformation",
    "pil_numpy_deformation",
    "pseudo_rig",
    "pseudo-rig",
}

LOCAL_REPAIR_METHODS = {
    "local_repair",
    "masked_repair",
    "local_repair_model_edit",
}

DISALLOWED_SELECTED_HINTS = {
    "component_sheet",
    "component-sheet",
    "parts_sheet",
    "parts-sheet",
    "rgba_layer",
    "layered_reference",
    "mask_layer",
    "pose_proxy",
    "placeholder",
}

BLOCKING_FAILURES = {
    "unreadable_action",
    "source_pose_snapback",
    "identity_drift",
    "owner_motion_incoherent",
    "joint_hole",
    "detached_child",
    "bad_contact",
    "bad_overlap",
    "prop_discontinuity",
    "wrong_side_motion",
    "local_repair_overpaint",
    "source_state_snapback",
    "bad_pivot",
    "local_transform_selected_for_large_action",
    "missing_stable_action_gate",
}


@dataclass
class Finding:
    code: str
    message: str
    severity: str = "error"

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "severity": self.severity}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if isinstance(value, (list, tuple, set, dict)) and not value:
        return True
    return False


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [value]


def string_values(value: Any) -> list[str]:
    result: list[str] = []
    for item in as_list(value):
        if isinstance(item, dict):
            for key in ("code", "id", "name", "reason", "failure"):
                if key in item:
                    result.extend(string_values(item.get(key)))
                    break
        elif str(item).strip():
            result.append(str(item).strip())
    return result


def explicit_expectation_present(value: Any) -> bool:
    values = string_values(value)
    return bool(values)


def verdict_pass(verdict: dict[str, Any], *aliases: str) -> bool:
    return any(verdict.get(alias) == "pass" for alias in aliases)


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "large", "required"}
    return bool(value)


class V3ContractValidator:
    def __init__(self, task_root: Path) -> None:
        self.task_root = task_root.expanduser()
        self.errors: list[Finding] = []
        self.warnings: list[Finding] = []
        self.director: dict[str, Any] = {}
        self.semantic: dict[str, Any] = {}
        self.occlusion_plan: dict[str, Any] = {}
        self.provenance: dict[str, Any] = {}
        self.qa: dict[str, Any] = {}
        self.registry: dict[str, Any] = {}
        self.sidecar_manifest: dict[str, Any] = {}

    def error(self, code: str, message: str) -> None:
        self.errors.append(Finding(code, message))

    def warn(self, code: str, message: str) -> None:
        self.warnings.append(Finding(code, message, "warning"))

    def resolve_path(self, raw: Any) -> Path | None:
        if isinstance(raw, dict):
            raw = raw.get("path") or raw.get("file") or raw.get("selectedImage")
        if not raw:
            return None
        path = Path(str(raw)).expanduser()
        if path.is_absolute():
            return path
        if path.exists():
            return path
        return self.task_root / path

    def path_exists(self, raw: Any) -> bool:
        path = self.resolve_path(raw)
        return bool(path and path.exists())

    def load_optional_json(self, *relative_paths: str) -> dict[str, Any]:
        for relative in relative_paths:
            path = self.task_root / relative
            if path.exists():
                data = read_json(path)
                return data if isinstance(data, dict) else {}
        return {}

    def load_required_json(self, code: str, *relative_paths: str) -> dict[str, Any]:
        data = self.load_optional_json(*relative_paths)
        if data:
            return data
        label = " or ".join(relative_paths)
        self.error(code, f"Missing required file: {label}")
        return {}

    def validate_required_fields(
        self,
        label: str,
        data: dict[str, Any],
        fields: list[str],
        code: str,
        allow_empty: set[str] | None = None,
    ) -> None:
        if not data:
            return
        allow_empty = allow_empty or set()
        for field in fields:
            if field not in data or (field not in allow_empty and is_missing(data.get(field))):
                self.error(code, f"{label} missing required field: {field}")

    def load(self) -> None:
        self.director = self.load_required_json(
            "missing_director_brief",
            "animation-director-brief.json",
            "phase-a-v3/animation-director-brief.json",
            "phase_a/director_brief/animation-director-brief.json",
        )
        self.semantic = self.load_required_json(
            "missing_semantic_motion_plan",
            "semantic-motion-plan.json",
            "phase-a-v3/semantic-motion-plan.json",
            "phase_a/semantic_motion_plan/semantic-motion-plan.json",
        )
        self.occlusion_plan = self.load_required_json(
            "missing_occlusion_plan",
            "per-frame-occlusion-plan.json",
            "phase-a-v3/per-frame-occlusion-plan.json",
            "phase_a/per_frame_occlusion_plan/per-frame-occlusion-plan.json",
        )
        self.provenance = self.load_required_json(
            "missing_generation_provenance",
            "frame-generation-provenance.json",
            "phase-a-v3/frame-generation-provenance.json",
        )
        self.qa = self.load_required_json(
            "missing_phase_a_v3_qa",
            "phase-a-v3-qa.json",
            "phase-a-v3/phase-a-v3-qa.json",
            "qa/phase-a-v3-qa.json",
        )
        self.registry = self.load_required_json(
            "missing_selected_frame_registry",
            "selected-frame-registry.json",
        )
        self.sidecar_manifest = self.load_optional_json("phase-a-v3/manifest.json")

    def validate_top_level_contracts(self) -> None:
        self.validate_required_fields(
            "animation-director-brief.json",
            self.director,
            REQUIRED_DIRECTOR_FIELDS,
            "incomplete_director_brief",
        )
        self.validate_required_fields(
            "semantic-motion-plan.json",
            self.semantic,
            REQUIRED_SEMANTIC_FIELDS,
            "incomplete_semantic_motion_plan",
        )
        self.validate_required_fields(
            "phase-a-v3-qa.json",
            self.qa,
            REQUIRED_QA_FIELDS,
            "incomplete_phase_a_v3_qa",
            allow_empty={"failures"},
        )
        if self.qa:
            status = str(self.qa.get("status") or "")
            if status in {"blocked", "visual_rejected", "wip"} and self.selected_entries():
                self.error("selected_frames_with_nonfinal_qa", f"Selected frames exist while phase-a-v3-qa status is {status}")
            if status not in {"blocked", "visual_rejected", "wip"} and string_values(self.qa.get("failures")):
                for code in string_values(self.qa.get("failures")):
                    self.error(code if code in BLOCKING_FAILURES else "qa_has_failures", f"phase-a-v3-qa contains failure: {code}")
        if self.sidecar_manifest:
            for item in as_list(self.sidecar_manifest.get("artifacts")):
                if isinstance(item, dict) and item.get("path") and not self.path_exists(item.get("path")):
                    self.error("missing_evidence_path", f"phase-a-v3 manifest path missing: {item.get('path')}")

    def sequence_status(self) -> str:
        sequence_status = self.load_optional_json("selected-sequence-status.json")
        for source in (self.qa, sequence_status):
            status = str(source.get("status") or "").strip()
            if status:
                return status
        return ""

    def is_nonfinal_status(self) -> bool:
        return self.sequence_status() in {"blocked", "visual_rejected", "wip", "blocked_pending_motion_contract"}

    def large_pose_or_state_change(self, plan: dict[str, Any] | None = None) -> bool:
        plan = plan or {}
        for source in (plan, self.director, self.occlusion_plan):
            for key in (
                "largePoseOrStateChange",
                "largePoseChange",
                "largeStateChange",
                "requiresModelGeneratedWholeSubject",
                "requiresModelGeneratedWholeCharacter",
            ):
                if key in source:
                    return truthy(source.get(key))
        return False

    def required_stable_verdicts(self, entry: dict[str, Any], gate: dict[str, Any], plan: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for source in (self.director, plan, entry, gate):
            values.extend(string_values(source.get("requiredVisualVerdicts") if isinstance(source, dict) else None))
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    def action_gate_profiles(self, entry: dict[str, Any], gate: dict[str, Any], plan: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for source in (self.director, plan, entry, gate):
            values.extend(string_values(source.get("actionGateProfiles") if isinstance(source, dict) else None))
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    def plan_frames(self) -> dict[str, dict[str, Any]]:
        frames = self.occlusion_plan.get("frames", [])
        if not isinstance(frames, list):
            self.error("missing_occlusion_plan", "per-frame-occlusion-plan.json field frames must be a list")
            return {}
        result: dict[str, dict[str, Any]] = {}
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            frame_id = str(frame.get("frameId") or "")
            if not frame_id:
                self.error("selected_frame_missing_contract", "Occlusion plan contains a frame without frameId")
                continue
            result[frame_id] = frame
            for field in REQUIRED_FRAME_FIELDS:
                if is_missing(frame.get(field)):
                    if field == "movingOwners":
                        self.error("missing_moving_owner", f"{frame_id}: missing movingOwners")
                    elif field == "stableOwners":
                        self.error("missing_stable_owner", f"{frame_id}: missing stableOwners")
                    elif field == "contactAnchors":
                        self.error("missing_contact_anchor", f"{frame_id}: missing contactAnchors")
                    elif field == "overlapExpectations":
                        self.error("missing_overlap_expectation", f"{frame_id}: missing overlapExpectations")
                    elif field == "occlusionExpectations":
                        self.error("missing_occlusion_expectation", f"{frame_id}: missing occlusionExpectations")
                    else:
                        self.error("selected_frame_missing_contract", f"{frame_id}: missing {field}")
        return result

    def selected_entries(self) -> list[dict[str, Any]]:
        frames = self.registry.get("frames", [])
        if not isinstance(frames, list):
            self.error("missing_selected_frame_registry", "selected-frame-registry.json field frames must be a list")
            return []
        return [frame for frame in frames if isinstance(frame, dict) and frame.get("status") == "selected"]

    def provenance_for_frame(self, frame_id: str, entry: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
        for source in [entry.get("generationProvenance"), gate.get("generationProvenance")]:
            if isinstance(source, dict):
                return source

        frames = self.provenance.get("frames")
        if isinstance(frames, dict):
            value = frames.get(frame_id)
            return value if isinstance(value, dict) else {}
        if isinstance(frames, list):
            for item in frames:
                if isinstance(item, dict) and item.get("frameId") == frame_id:
                    return item
        value = self.provenance.get(frame_id)
        return value if isinstance(value, dict) else {}

    def load_gate(self, frame_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        gate_path = self.resolve_path(entry.get("visualGate") or entry.get("visualGatePath"))
        if not gate_path or not gate_path.exists():
            self.error("missing_visual_gate", f"{frame_id}: missing visual gate JSON")
            return {}
        try:
            data = read_json(gate_path)
        except json.JSONDecodeError as exc:
            self.error("invalid_visual_gate", f"{frame_id}: visual gate is not valid JSON: {exc}")
            return {}
        return data if isinstance(data, dict) else {}

    def is_local_repair(self, entry: dict[str, Any], gate: dict[str, Any], provenance: dict[str, Any]) -> bool:
        method = str(provenance.get("method") or entry.get("method") or gate.get("method") or "")
        text = " ".join(
            str(value or "")
            for value in [
                method,
                entry.get("selectedImage"),
                entry.get("candidateSource"),
                gate.get("selectedImage"),
                gate.get("candidateImage"),
                entry.get("localRepairCandidate"),
                gate.get("localRepairCandidate"),
                provenance.get("localRepairCandidate"),
            ]
        ).lower()
        return any(marker in text for marker in LOCAL_REPAIR_METHODS) or "local_repair_candidates" in text

    def is_local_transform(self, entry: dict[str, Any], gate: dict[str, Any], provenance: dict[str, Any]) -> bool:
        method = str(provenance.get("method") or entry.get("method") or gate.get("method") or "")
        text = " ".join(
            str(value or "")
            for value in [
                method,
                provenance.get("model"),
                provenance.get("notes"),
                entry.get("selectedImage"),
                entry.get("candidateSource"),
                gate.get("selectedImage"),
                gate.get("candidateImage"),
            ]
        ).lower()
        return any(marker in text for marker in LOCAL_TRANSFORM_METHODS)

    def validate_generation_provenance(self, frame_id: str, provenance: dict[str, Any]) -> None:
        if not provenance:
            self.error("missing_generation_provenance", f"{frame_id}: missing generationProvenance")
            return
        method = str(provenance.get("method") or "").strip()
        if method not in ALLOWED_GENERATION_METHODS:
            self.error("invalid_generation_provenance", f"{frame_id}: invalid generation method: {method}")
        if not str(provenance.get("model") or "").strip():
            self.error("missing_generation_provenance", f"{frame_id}: generationProvenance.model is required")
        programmatic_subject_pixels = provenance.get(
            "programmaticSubjectPixels",
            provenance.get("programmaticCharacterPixels"),
        )
        if programmatic_subject_pixels is not False:
            self.error("programmatic_subject_pixels", f"{frame_id}: selected subject pixels cannot be programmatic")

        source_images = string_values(provenance.get("sourceImages") or provenance.get("sourceImage"))
        control_images = string_values(provenance.get("controlImages") or provenance.get("controlImage"))
        if not source_images or not control_images:
            self.error("missing_generation_provenance", f"{frame_id}: sourceImages and controlImages are required")
        for label, paths in [("sourceImages", source_images), ("controlImages", control_images)]:
            for raw in paths:
                if not self.path_exists(raw):
                    self.error("missing_generation_provenance", f"{frame_id}: {label} path missing: {raw}")

    def collect_frame_qa(self, frame_id: str) -> dict[str, Any]:
        frame_qa = self.qa.get("frameQa", {})
        if isinstance(frame_qa, dict):
            value = frame_qa.get(frame_id)
            return value if isinstance(value, dict) else {}
        if isinstance(frame_qa, list):
            for item in frame_qa:
                if isinstance(item, dict) and item.get("frameId") == frame_id:
                    return item
        return {}

    def collect_failures(self, *records: dict[str, Any]) -> list[str]:
        failures: list[str] = []
        for record in records:
            for key in ("failures", "failureReasons", "observedFailures", "blockingFailures"):
                failures.extend(string_values(record.get(key)))
        return failures

    def validate_visual_gate(self, frame_id: str, entry: dict[str, Any], gate: dict[str, Any], plan: dict[str, Any]) -> None:
        if not gate:
            return
        if gate.get("status") != "pass":
            self.error("visual_gate_not_pass", f"{frame_id}: visual gate status must be pass")
        gate_failures = self.collect_failures(gate)
        if gate_failures:
            self.error("visual_gate_has_failures", f"{frame_id}: pass gate contains failures: {', '.join(gate_failures)}")

        selected_path = self.resolve_path(entry.get("selectedImage") or entry.get("taskScopedSelectedImage"))
        if not selected_path or not selected_path.exists():
            self.error("selected_frame_missing_contract", f"{frame_id}: selected image path missing")
        elif "frames_selected" not in selected_path.parts:
            self.error("selected_frame_missing_contract", f"{frame_id}: selected image must live under frames_selected")
        else:
            selected_text = " ".join(
                str(value or "")
                for value in [
                    selected_path.name,
                    entry.get("selectedImage"),
                    gate.get("selectedImage"),
                    entry.get("assetRole"),
                    gate.get("assetRole"),
                ]
            ).lower()
            if any(hint in selected_text for hint in DISALLOWED_SELECTED_HINTS):
                self.error(
                    "selected_frame_not_whole_subject",
                    f"{frame_id}: selected frame looks like component/layer/proxy evidence, not a whole-subject frame",
                )

        gate_selected = self.resolve_path(gate.get("selectedImage"))
        if gate_selected and selected_path and gate_selected.exists() and gate_selected.resolve() != selected_path.resolve():
            self.error("selected_frame_missing_contract", f"{frame_id}: gate selectedImage does not match registry")

        verdict = gate.get("verdict", {})
        if not isinstance(verdict, dict):
            self.error("visual_gate_not_pass", f"{frame_id}: visual gate verdict must be an object")
            return
        required = [
            ("actionReadability", ("actionReadability", "actionReads")),
            ("identityPreserved", ("identityPreserved", "identity")),
            ("originalCharacterTreatment", ("originalCharacterTreatment",)),
            ("notPoseProxy", ("notPoseProxy",)),
            ("ownerMotionCoherence", ("ownerMotionCoherence",)),
            ("occlusionOverlapPlausibility", ("occlusionOverlapPlausibility",)),
            ("provenanceValidity", ("provenanceValidity",)),
            ("wholeSubjectActionFrame", ("wholeSubjectActionFrame", "wholeCharacterActionFrame")),
        ]
        for label, aliases in required:
            if not verdict_pass(verdict, *aliases):
                self.error("visual_gate_not_pass", f"{frame_id}: verdict.{label} must be pass")

        action_profiles = self.action_gate_profiles(entry, gate, plan)
        stable_required = self.required_stable_verdicts(entry, gate, plan)
        if not action_profiles or not stable_required:
            self.error("missing_stable_action_gate", f"{frame_id}: selected frame must record stable action gate profiles and required verdicts")
        for required_verdict in stable_required:
            if verdict.get(required_verdict) != "pass":
                self.error("missing_stable_action_gate", f"{frame_id}: required stable verdict {required_verdict} must be pass")

        if explicit_expectation_present(plan.get("contactAnchors")) and not verdict_pass(verdict, "contactContinuity"):
            self.error("bad_contact", f"{frame_id}: contact anchors require verdict.contactContinuity=pass")
        if explicit_expectation_present(plan.get("propContinuity")) and not verdict_pass(verdict, "propContinuity"):
            self.error("prop_discontinuity", f"{frame_id}: prop continuity requires verdict.propContinuity=pass")

    def validate_local_repair_gate(
        self,
        frame_id: str,
        entry: dict[str, Any],
        gate: dict[str, Any],
        provenance: dict[str, Any],
    ) -> None:
        if not self.is_local_repair(entry, gate, provenance):
            return
        verdict = gate.get("verdict", {}) if isinstance(gate.get("verdict"), dict) else {}
        review = gate.get("localRepairReview", {})
        if (
            gate.get("status") != "pass"
            or self.collect_failures(gate)
            or not verdict_pass(verdict, "wholeSubjectActionFrame", "wholeCharacterActionFrame")
            or verdict.get("localRepairNotOverpaint") != "pass"
            or not isinstance(review, dict)
            or review.get("status") != "pass"
        ):
            self.error(
                "local_repair_promoted_without_clean_gate",
                f"{frame_id}: local repair output promoted without clean whole-subject repair gate",
            )

    def validate_local_transform_gate(
        self,
        frame_id: str,
        entry: dict[str, Any],
        gate: dict[str, Any],
        provenance: dict[str, Any],
        plan: dict[str, Any],
    ) -> None:
        if not self.large_pose_or_state_change(plan):
            return
        if self.is_local_transform(entry, gate, provenance):
            self.error(
                "local_transform_selected_for_large_action",
                f"{frame_id}: local source transform cannot be selected for a large pose/state change",
            )

    def validate_selected_frames(self) -> None:
        plan_by_id = self.plan_frames()
        selected = self.selected_entries()
        if not selected:
            if not self.is_nonfinal_status():
                self.error("selected_frame_missing_contract", "No selected frames found in selected-frame-registry.json")
            return

        for entry in selected:
            frame_id = str(entry.get("frameId") or "")
            if not frame_id:
                self.error("selected_frame_missing_contract", "Selected registry entry missing frameId")
                continue
            plan = plan_by_id.get(frame_id)
            if not plan:
                self.error("selected_frame_missing_contract", f"{frame_id}: no per-frame contract")
                continue
            for field in REQUIRED_FRAME_FIELDS:
                if is_missing(plan.get(field)):
                    if field == "movingOwners":
                        self.error("missing_moving_owner", f"{frame_id}: missing moving owner")
                    elif field == "stableOwners":
                        self.error("missing_stable_owner", f"{frame_id}: missing stable owner")
                    elif field == "contactAnchors":
                        self.error("missing_contact_anchor", f"{frame_id}: missing contact anchor")
                    elif field == "overlapExpectations":
                        self.error("missing_overlap_expectation", f"{frame_id}: missing overlap expectation")
                    elif field == "occlusionExpectations":
                        self.error("missing_occlusion_expectation", f"{frame_id}: missing occlusion expectation")
                    else:
                        self.error("selected_frame_missing_contract", f"{frame_id}: missing {field}")

            gate = self.load_gate(frame_id, entry)
            provenance = self.provenance_for_frame(frame_id, entry, gate)
            self.validate_generation_provenance(frame_id, provenance)
            self.validate_visual_gate(frame_id, entry, gate, plan)
            self.validate_local_repair_gate(frame_id, entry, gate, provenance)
            self.validate_local_transform_gate(frame_id, entry, gate, provenance, plan)

            frame_qa = self.collect_frame_qa(frame_id)
            failures = self.collect_failures(frame_qa, gate)
            for failure in failures:
                if failure in BLOCKING_FAILURES:
                    self.error(failure, f"{frame_id}: blocking visual failure is not blocked: {failure}")
            if frame_qa:
                if frame_qa.get("status") not in {"pass", "selected"}:
                    self.error("visual_gate_not_pass", f"{frame_id}: frame QA status is {frame_qa.get('status')}")
                evidence = frame_qa.get("evidence", {})
                if isinstance(evidence, dict):
                    for label, raw in evidence.items():
                        if raw and not self.path_exists(raw):
                            self.error("missing_evidence_path", f"{frame_id}: frame QA evidence missing {label}: {raw}")

    def validate_final_preview_source(self) -> None:
        if self.is_nonfinal_status() and not self.selected_entries():
            return
        preview = self.load_optional_json("qa/final-preview-source.json", "final-preview-source.json")
        if not preview:
            self.error("final_preview_not_selected_source", "Missing qa/final-preview-source.json")
            return
        previews = preview.get("previews", [])
        if not isinstance(previews, list):
            previews = []
        sequence_status = self.load_optional_json("selected-sequence-status.json")
        for key in ("userFacingPreviews", "finalPreviews"):
            extra = sequence_status.get(key)
            if isinstance(extra, list):
                previews.extend(extra)
        if not isinstance(previews, list) or not previews:
            self.error("final_preview_not_selected_source", "final-preview-source.json must list previews")
            return
        for item in previews:
            if not isinstance(item, dict):
                self.error("final_preview_not_selected_source", "final preview entry must be an object")
                continue
            role = str(item.get("role") or "")
            raw_path = item.get("path")
            if role not in ALLOWED_FINAL_PREVIEW_ROLES:
                self.error("final_preview_not_selected_source", f"Disallowed final preview role: {role}")
            path = self.resolve_path(raw_path)
            if not path or not path.exists():
                self.error("final_preview_not_selected_source", f"Final preview path missing: {raw_path}")
                continue
            lowered_parts = {part.lower() for part in path.parts}
            lowered_name = path.name.lower()
            if lowered_parts & DISALLOWED_FINAL_PREVIEW_PARTS or any(part in lowered_name for part in DISALLOWED_FINAL_PREVIEW_PARTS):
                self.error("final_preview_not_selected_source", f"Final preview points to non-selected/review source: {raw_path}")

    def validate_sequence_qa(self) -> None:
        sequence = self.qa.get("sequenceQa", {})
        if not isinstance(sequence, dict):
            self.error("incomplete_phase_a_v3_qa", "phase-a-v3-qa.sequenceQa must be an object")
            return
        if self.is_nonfinal_status() and not self.selected_entries():
            evidence = sequence.get("evidence", {})
            if isinstance(evidence, dict):
                for label, raw in evidence.items():
                    if raw and not self.path_exists(raw):
                        self.error("missing_evidence_path", f"Sequence QA evidence missing {label}: {raw}")
            return
        if sequence.get("status") not in {"pass", "deliverable_candidate", "accepted"}:
            self.error("sequence_qa_not_pass", f"sequenceQa.status is {sequence.get('status')}")
        for failure in self.collect_failures(sequence):
            if failure in BLOCKING_FAILURES:
                self.error(failure, f"Sequence QA contains blocking failure: {failure}")
            else:
                self.error("sequence_qa_not_pass", f"Sequence QA contains failure: {failure}")
        evidence = sequence.get("evidence", {})
        if isinstance(evidence, dict):
            for label, raw in evidence.items():
                if raw and not self.path_exists(raw):
                    self.error("missing_evidence_path", f"Sequence QA evidence missing {label}: {raw}")

    def run(self) -> dict[str, Any]:
        if not self.task_root.exists():
            self.error("missing_task_root", f"Task root does not exist: {self.task_root}")
        else:
            self.load()
            self.validate_top_level_contracts()
            self.validate_selected_frames()
            self.validate_sequence_qa()
            self.validate_final_preview_source()
        return {
            "format": "kinePoseDevV3.contractValidation",
            "version": "0.1",
            "taskRoot": str(self.task_root),
            "status": "fail" if self.errors else "pass",
            "errors": [finding.as_dict() for finding in self.errors],
            "warnings": [finding.as_dict() for finding in self.warnings],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_root", help="Phase A V3 task root to validate.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output. Enabled by default.")
    args = parser.parse_args()

    result = V3ContractValidator(Path(args.task_root)).run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
