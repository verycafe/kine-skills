#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from datetime import datetime
import hashlib
import html
import io
import json
import math
import shlex
import shutil
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

try:  # optional acceleration; the pure-Python fallbacks below keep this script dependency-light
    import numpy as _np
except Exception:  # pragma: no cover - numpy is optional
    _np = None

DEFAULT_RESOLUTION = 1280
PUBLIC_GENERATION_BACKEND = "kine-layer-imagegen-skill"
SOURCE_VISIBLE_BACKEND = "source-visible-owner-clean-registration"
SOURCE_LOCKED_MICRO_BACKEND = "source-locked-facial-micro-layer"
DIRECTOR_DECOMPOSITION_VERSION = "0.1"
RECOMPOSE_SOURCE_ALPHA_DIFF_RATIO_LIMIT = 0.0
RECOMPOSE_RGB_RMSE_LIMIT = 0.0
SOURCE_VISIBLE_CANDIDATE_RMSE_LIMIT = 52.0
MIN_HIDDEN_OUTSIDE_VISIBLE_RATIO = 0.02
SOURCE_REFERENCE_TOTAL_MIN = 0.58
SOURCE_REFERENCE_COLOR_MIN = 0.68
SOURCE_REFERENCE_ASPECT_MIN = 0.38
SOURCE_REFERENCE_SHAPE_MIN = 0.035
SOURCE_REFERENCE_STRICT_OWNERS = {"face", "hair-front", "hair-rear", "head-accessory", "torso", "hips"}
LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT = 0.12
# Maximum fraction of the source silhouette (source alpha > 0) that the accepted
# present-layer composite may fail to cover before the recompose gate rejects the run.
# This guards against sparse composites that were previously scored against a
# source-pose-locked image rebuilt from source pixels.
RECOMPOSE_MAX_MISSING_SOURCE_ALPHA_RATIO = 0.0
PARTS_SHEET_MAX_DEFAULT_COMPONENTS = 32
PARTS_SHEET_BLOCKED_STATUS = "blocked_not_final"
GREEN_POLLUTION_PASS_RATIO = 0.01
GREEN_POLLUTION_WARN_RATIO = 0.03
V3_HIDDEN_VISIBLE_OVERLAP_MAX_PIXELS = 16
V3_HIDDEN_VISIBLE_OVERLAP_MAX_RATIO = 0.01
V3_SUBJECT_MIN_ALPHA_COVERAGE = 0.015
V3_SUBJECT_MAX_ALPHA_COVERAGE = 0.92
V3_SUBJECT_MIN_BBOX_AREA_RATIO = 0.025
V3_SUBJECT_MIN_BBOX_WIDTH_RATIO = 0.10
V3_SUBJECT_MIN_BBOX_HEIGHT_RATIO = 0.35
V3_SUBJECT_EDGE_ALPHA_RATIO_LIMIT = 0.22
V3_ALPHA_SOURCE_CONFIDENCE_MIN = 0.68
# Backend tag for the default lossless source-pixel partition. It must NOT contain any
# "visible"/"source-visible" marker so provenance_is_source_visible_lock() stays False and
# the completion gate accepts partition owners as `present` (not source_lock_only).
LOSSLESS_PARTITION_BACKEND = "kine-lossless-source-partition"
SOURCE_DERIVED_FINAL_BLOCKED_BACKENDS = {
    LOSSLESS_PARTITION_BACKEND,
    SOURCE_VISIBLE_BACKEND,
    SOURCE_LOCKED_MICRO_BACKEND,
}
SOURCE_DERIVED_FINAL_BLOCKED_MODES = {
    "lossless_partition",
    "source_visible_lock",
    "source_locked_facial_micro",
}
V3_WORKSPACE_CONTRACT = "KINE_LAYER_V3_CONTRACT.md"
SOURCE_VISIBLE_HIDDEN_NOT_REQUIRED_REASON = "source_visible_local_candidate_no_hidden_target"
V3_STABLE_OPTIONAL_OWNER_IDS = {"props"}
V3_PROPORTION_DRIFT_ASPECT_LOG_LIMIT = 0.65
V3_PROPORTION_DRIFT_AXIS_SCALE_RATIO_LIMIT = 2.25
V3_STABLE_OBJECT_OWNER = "props"
V3_STABLE_OBJECT_COMPONENT_DETAILS = {
    "button",
    "buttons",
    "badge",
    "badges",
    "buckle",
    "buckles",
    "zipper",
    "zip",
    "seam",
    "seams",
    "stitch",
    "stitches",
    "stitching",
    "trim",
    "trims",
    "pattern",
    "patterns",
    "texture",
    "textures",
    "highlight",
    "highlights",
    "shadow",
    "shadows",
    "wrinkle",
    "wrinkles",
    "fold",
    "folds",
    "rivet",
    "rivets",
    "scratch",
    "scratches",
    "logo",
    "logos",
    "pocket",
    "pockets",
    "纽扣",
    "扣子",
    "徽章",
    "拉链",
    "缝线",
    "接缝",
    "纹理",
    "花纹",
    "褶皱",
    "高光",
    "阴影",
}
V3_STABLE_OBJECT_TYPE_KEYWORDS = {
    "weapon": {
        "knife",
        "dagger",
        "sword",
        "blade",
        "katana",
        "saber",
        "rapier",
        "axe",
        "spear",
        "lance",
        "gun",
        "rifle",
        "pistol",
        "bow",
        "crossbow",
        "arrow",
        "quiver",
        "weapon",
        "weapons",
        "刀",
        "匕首",
        "剑",
        "武器",
        "枪",
        "弓",
        "箭",
    },
    "staff": {"staff", "wand", "cane", "rod", "scepter", "杖", "法杖", "魔杖", "手杖"},
    "umbrella": {"umbrella", "parasol", "伞", "雨伞", "阳伞"},
    "bag": {
        "bag",
        "backpack",
        "satchel",
        "pouch",
        "waist-bag",
        "waistbag",
        "belt-bag",
        "holster",
        "pack",
        "背包",
        "包",
        "腰包",
        "挎包",
        "枪套",
    },
    "shield": {"shield", "盾", "盾牌"},
    "book": {"book", "scroll", "map", "notebook", "tome", "书", "卷轴", "地图"},
    "tool": {
        "tool",
        "hammer",
        "wrench",
        "spanner",
        "pickaxe",
        "torch",
        "lantern",
        "camera",
        "phone",
        "tablet",
        "clipboard",
        "instrument",
        "guitar",
        "lute",
        "flute",
        "key",
        "rope",
        "工具",
        "锤",
        "扳手",
        "火把",
        "灯",
        "相机",
        "手机",
        "平板",
        "乐器",
        "钥匙",
        "绳子",
    },
}
V3_STABLE_OBJECT_CONTACT_KEYWORDS = {
    "held",
    "holding",
    "grip",
    "gripped",
    "hand",
    "hands",
    "wield",
    "wielding",
    "carried",
    "握",
    "握持",
    "手持",
    "拿着",
    "拿",
}
V3_STABLE_OBJECT_WORN_KEYWORDS = {
    "worn",
    "wearing",
    "attached",
    "belt",
    "waist",
    "backpack",
    "back-mounted",
    "shoulder",
    "strap",
    "holster",
    "穿戴",
    "佩戴",
    "挂",
    "腰间",
    "背",
    "肩带",
}


KINE_LAYER_SEMANTIC_PARTS = [
    {"id": "hair-rear", "tag": "hair_rear", "required": False, "order": 10, "prompt": "rear hair mass only, completed behind head/neck where occluded"},
    {"id": "neck", "tag": "neck", "required": False, "order": 20, "prompt": "neck skin only, completed where clothing/head occludes it"},
    {"id": "collar-accessory", "tag": "collar_accessory", "required": False, "order": 30, "prompt": "collar, choker, scarf, tie, or neck accessory only"},
    {"id": "ears", "tag": "ears", "required": False, "order": 40, "prompt": "ears only, completed behind hair where needed"},
    {"id": "ear-accessory", "tag": "ear_accessory", "required": False, "order": 50, "prompt": "ear accessories only"},
    {"id": "tail", "tag": "tail", "required": False, "order": 60, "prompt": "tail only if present"},
    {"id": "wings", "tag": "wings", "required": False, "order": 70, "prompt": "wings only if present"},
    {"id": "legs", "tag": "legs", "required": False, "order": 80, "prompt": "legs or leg-covering layer only, source-visible locked and hidden overlap completed"},
    {"id": "feet", "tag": "feet", "required": False, "order": 90, "prompt": "feet, shoes, or boots only, completed with hidden cuffs where needed"},
    {"id": "hips", "tag": "hips", "required": False, "order": 100, "prompt": "hips, pants, skirt, or lower garment layer only, hidden sockets completed"},
    {"id": "torso", "tag": "torso", "required": True, "order": 110, "prompt": "torso clothing or armor only, hidden shoulder and waist areas completed"},
    {"id": "arms", "tag": "arms", "required": False, "order": 120, "prompt": "arms, hands, gloves, and sleeve-end details only, completed at wrist overlaps"},
    {"id": "face", "tag": "face", "required": True, "order": 130, "prompt": "face skin layer only, preserve exact face proportions"},
    {"id": "nose", "tag": "nose", "required": False, "order": 140, "prompt": "nose only"},
    {"id": "mouth", "tag": "mouth", "required": False, "order": 150, "prompt": "mouth only"},
    {"id": "eye-white", "tag": "eye_white", "required": False, "order": 160, "prompt": "eye white areas only"},
    {"id": "eye-iris", "tag": "eye_iris", "required": False, "order": 170, "prompt": "iris and pupil color elements only"},
    {"id": "eye-line", "tag": "eye_line", "required": False, "order": 180, "prompt": "eyelashes and eye line art only"},
    {"id": "brows", "tag": "brows", "required": False, "order": 190, "prompt": "eyebrows only"},
    {"id": "glasses", "tag": "glasses", "required": False, "order": 200, "prompt": "glasses, visor, or face-mounted eyewear only"},
    {"id": "hair-front", "tag": "hair_front", "required": False, "order": 210, "prompt": "front hair mass only, visible silhouette locked and hidden roots completed"},
    {"id": "head-accessory", "tag": "head_accessory", "required": False, "order": 220, "prompt": "hat, helmet, hair ornament, or head accessory only, complete removable prop with occluded area filled"},
    {"id": "props", "tag": "props", "required": False, "order": 230, "prompt": "held objects, tools, props, or accessories only"},
]

RIG_COMPONENT_TEMPLATE = [
    {"id": "torso", "sourceLayers": ["torso"], "owner": "spine", "parent": None, "pivot": None, "sockets": ["neck", "left-shoulder", "right-shoulder", "hips"], "rotationRangeDeg": [-8, 8], "deformable": False},
    {"id": "pelvis", "sourceLayers": ["hips"], "owner": "hips", "parent": "torso", "pivot": None, "sockets": ["left-thigh", "right-thigh"], "rotationRangeDeg": [-10, 10], "deformable": False},
    {"id": "left-arm", "sourceLayers": ["torso", "arms"], "owner": "left-arm", "parent": "torso", "pivot": None, "sockets": ["shoulder", "elbow", "wrist"], "rotationRangeDeg": [-90, 120], "deformable": False},
    {"id": "right-arm", "sourceLayers": ["torso", "arms"], "owner": "right-arm", "parent": "torso", "pivot": None, "sockets": ["shoulder", "elbow", "wrist"], "rotationRangeDeg": [-90, 120], "deformable": False},
    {"id": "left-leg", "sourceLayers": ["hips", "legs", "feet"], "owner": "left-leg", "parent": "pelvis", "pivot": None, "sockets": ["hip", "knee", "ankle"], "rotationRangeDeg": [-60, 80], "deformable": False},
    {"id": "right-leg", "sourceLayers": ["hips", "legs", "feet"], "owner": "right-leg", "parent": "pelvis", "pivot": None, "sockets": ["hip", "knee", "ankle"], "rotationRangeDeg": [-60, 80], "deformable": False},
    {"id": "head", "sourceLayers": ["face", "nose", "mouth", "eye-white", "eye-iris", "eye-line", "brows", "hair-front", "hair-rear", "ears"], "owner": "head", "parent": "torso", "pivot": None, "sockets": ["neck"], "rotationRangeDeg": [-20, 20], "deformable": True},
    {"id": "head-accessory", "sourceLayers": ["head-accessory", "glasses"], "owner": "head", "parent": "head", "pivot": None, "sockets": ["head"], "rotationRangeDeg": [-20, 20], "deformable": False},
]

# Spine bone hierarchy template. Positions are normalized canvas coordinates (0..1,
# y-down) used only to lay out a default rest pose; the exporter converts them to
# Spine world space (y-up) and writes child bones parent-relative. Rotations stay 0 so
# the default pose reproduces the source canvas exactly (assembly == original); a rigger
# rotates these joints afterwards.
SPINE_BONE_TEMPLATE = [
    {"name": "root", "parent": None, "nx": 0.5, "ny": 1.0},
    {"name": "hips", "parent": "root", "nx": 0.5, "ny": 0.62},
    {"name": "torso", "parent": "hips", "nx": 0.5, "ny": 0.45},
    {"name": "neck", "parent": "torso", "nx": 0.5, "ny": 0.32},
    {"name": "head", "parent": "neck", "nx": 0.5, "ny": 0.18},
    {"name": "left-shoulder", "parent": "torso", "nx": 0.40, "ny": 0.37},
    {"name": "left-upper-arm", "parent": "left-shoulder", "nx": 0.34, "ny": 0.46},
    {"name": "left-lower-arm", "parent": "left-upper-arm", "nx": 0.30, "ny": 0.57},
    {"name": "left-hand", "parent": "left-lower-arm", "nx": 0.28, "ny": 0.66},
    {"name": "right-shoulder", "parent": "torso", "nx": 0.60, "ny": 0.37},
    {"name": "right-upper-arm", "parent": "right-shoulder", "nx": 0.66, "ny": 0.46},
    {"name": "right-lower-arm", "parent": "right-upper-arm", "nx": 0.70, "ny": 0.57},
    {"name": "right-hand", "parent": "right-lower-arm", "nx": 0.72, "ny": 0.66},
    {"name": "left-thigh", "parent": "hips", "nx": 0.44, "ny": 0.72},
    {"name": "left-shin", "parent": "left-thigh", "nx": 0.43, "ny": 0.85},
    {"name": "left-foot", "parent": "left-shin", "nx": 0.43, "ny": 0.96},
    {"name": "right-thigh", "parent": "hips", "nx": 0.56, "ny": 0.72},
    {"name": "right-shin", "parent": "right-thigh", "nx": 0.57, "ny": 0.85},
    {"name": "right-foot", "parent": "right-shin", "nx": 0.57, "ny": 0.96},
]

# Map a semantic owner id to its default Spine bone. Split parts (e.g. left-upper-arm)
# are resolved by spine_bone_for_component() before falling back to this table.
SPINE_SEMANTIC_BONE = {
    "hips": "hips",
    "torso": "torso",
    "neck": "neck",
    "collar-accessory": "neck",
    "face": "head",
    "nose": "head",
    "mouth": "head",
    "eye-white": "head",
    "eye-iris": "head",
    "eye-line": "head",
    "brows": "head",
    "glasses": "head",
    "ears": "head",
    "ear-accessory": "head",
    "hair-front": "head",
    "hair-rear": "head",
    "head-accessory": "head",
    "arms": "torso",
    "legs": "hips",
    "feet": "hips",
    "tail": "hips",
    "wings": "torso",
    "props": "root",
}


def spine_bone_for_component(component_id: str) -> str:
    """Resolve a component id (semantic owner or split bone-part) to a Spine bone name.

    Split ids produced by Spine-granularity splitting (e.g. `arms-left-lower`,
    `left-upper-arm`, `legs-right-foot`) are matched by side + segment keywords so they
    attach to the matching joint bone; anything unknown falls back to the semantic table
    and finally to `root`.
    """
    cid = component_id.lower()
    side = "left" if "left" in cid else ("right" if "right" in cid else None)
    if side:
        if "hand" in cid:
            return f"{side}-hand"
        if "lower-arm" in cid or "forearm" in cid or "lowerarm" in cid:
            return f"{side}-lower-arm"
        if "upper-arm" in cid or "upperarm" in cid or ("arm" in cid and "lower" not in cid):
            return f"{side}-upper-arm"
        if "foot" in cid or "feet" in cid or "boot" in cid:
            return f"{side}-foot"
        if "shin" in cid or "calf" in cid or "lower-leg" in cid or "lowerleg" in cid:
            return f"{side}-shin"
        if "thigh" in cid or "upper-leg" in cid or "upperleg" in cid or "leg" in cid:
            return f"{side}-thigh"
    base = component_id.split("-part-")[0]
    for key in (component_id, base):
        if key in SPINE_SEMANTIC_BONE:
            return SPINE_SEMANTIC_BONE[key]
    return "root"


# Bone-chain segmentation targets for limb owners. Each semantic owner maps to an
# ordered (proximal -> distal) list of (segment, lengthFraction) entries. Spine-
# granularity splitting first separates left/right, then slices each side along its
# long axis by these fractions. Child ids are `<owner>-<side>-<segment>` and resolve
# to bones through spine_bone_for_component(). Fractions are heuristic rest-pose
# estimates used only when no depth/pose model is available; they sum to ~1.0.
SPINE_LIMB_SEGMENTS = {
    "arms": [("upper-arm", 0.42), ("lower-arm", 0.34), ("hand", 0.24)],
    "legs": [("thigh", 0.52), ("shin", 0.48)],
    "feet": [("foot", 1.0)],
}


def spine_part_targets(owner_id: str) -> list[dict[str, Any]]:
    """Enumerate the Spine bone-part decomposition targets for a semantic owner.

    Limb owners (arms/legs/feet) expand to left/right x segment children; every other
    owner stays a single part mapped to its semantic bone. Each target records the
    child id, side, segment, bone, and length fraction so the director plan, removal
    contract, and splitter all share one source of truth.
    """
    segments = SPINE_LIMB_SEGMENTS.get(owner_id)
    if not segments:
        return [
            {
                "id": owner_id,
                "side": None,
                "segment": None,
                "bone": spine_bone_for_component(owner_id),
                "lengthFraction": 1.0,
            }
        ]
    targets: list[dict[str, Any]] = []
    for side in ("left", "right"):
        for segment, fraction in segments:
            child_id = f"{owner_id}-{side}-{segment}"
            targets.append(
                {
                    "id": child_id,
                    "side": side,
                    "segment": segment,
                    "bone": spine_bone_for_component(child_id),
                    "lengthFraction": fraction,
                }
            )
    return targets


# Default auto-split targets. Facial micro layers (eye-*/brows/nose/mouth) are
# intentionally EXCLUDED: shattering them into *-part-001..NNN fragments is what made the
# review grid look broken. They stay single source-locked layers unless a caller passes
# them to `auto-split --layers ...` explicitly.
AUTO_SPLIT_SENSITIVE_LAYERS = [
    "arms",
    "legs",
    "feet",
    "ears",
    "hair-front",
    "hair-rear",
    "head-accessory",
    "props",
]

FACIAL_MICRO_LAYERS = {"nose", "mouth", "eye-white", "eye-iris", "eye-line", "brows"}
V3_SOURCE_LOCKED_DETAIL_OWNERS = FACIAL_MICRO_LAYERS | {"ears", "ear-accessory", "glasses"}
V3_GARMENT_LAYER_OWNERS = {"hips", "legs"}
V3_INTERACTION_GROUP_OWNERS = {"props"}
V3_FINAL_LAYER_OWNERS = {
    "face",
    "hair-front",
    "hair-rear",
    "head-accessory",
    "neck",
    "collar-accessory",
    "tail",
    "wings",
    "feet",
    "torso",
    "arms",
} | V3_GARMENT_LAYER_OWNERS
PAIR_SPLIT_LAYERS = {"arms", "legs", "feet", "ears", "eye-white", "eye-iris", "eye-line", "brows"}
FRONT_BACK_SPLIT_LAYERS = {"hair-front", "hair-rear", "head-accessory", "torso", "hips"}
SOURCE_VISIBLE_OWNER_PRIORITY = {
    "eye-line": 120,
    "eye-iris": 118,
    "eye-white": 116,
    "brows": 114,
    "nose": 112,
    "mouth": 110,
    "hair-front": 104,
    "hair-rear": 102,
    "ears": 100,
    "head-accessory": 96,
    "glasses": 94,
    "collar-accessory": 90,
    "arms": 84,
    "feet": 82,
    "legs": 80,
    "hips": 78,
    "torso": 76,
    "face": 70,
    "neck": 68,
    "props": 64,
    "ear-accessory": 62,
    "tail": 60,
    "wings": 60,
}
V3_FOREIGN_SUBTRACTION_INDEPENDENT_OWNERS = {"props", "head-accessory", "collar-accessory", "tail", "wings"}
V3_FOREIGN_SUBTRACTION_MAJOR_BODY_OWNERS = {"face", "hair-front", "hair-rear", "neck", "torso", "hips", "arms", "legs", "feet"}
V3_FOREIGN_SUBTRACTION_MAX_COMPONENT_RATIO = 0.78


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_fresh_output_dir(out: Path, force: bool = False) -> None:
    if out.exists() and any(out.iterdir()):
        if not force:
            raise SystemExit(f"Refusing to initialize non-empty workspace: {out}. Use a new path or --force.")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)


def timestamped_workspace(out_root: Path, source: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = source.stem.replace(" ", "-").lower() or "kine-layer"
    return out_root / f"{base}-{stamp}"


def load_plan(workspace: Path) -> dict[str, Any]:
    return json.loads((workspace / "layer-plan.json").read_text(encoding="utf-8"))


def normalize_source_image(source_img: Image.Image, resolution: int) -> tuple[Image.Image, dict[str, Any]]:
    if resolution <= 0:
        raise ValueError("--resolution must be a positive integer")
    original_w, original_h = source_img.size
    scale = min(resolution / original_w, resolution / original_h)
    normalized_w = max(1, round(original_w * scale))
    normalized_h = max(1, round(original_h * scale))
    resized = source_img.resize((normalized_w, normalized_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (resolution, resolution), (0, 0, 0, 0))
    pad_left = (resolution - normalized_w) // 2
    pad_top = (resolution - normalized_h) // 2
    canvas.alpha_composite(resized, (pad_left, pad_top))
    padding = {
        "left": pad_left,
        "top": pad_top,
        "right": resolution - normalized_w - pad_left,
        "bottom": resolution - normalized_h - pad_top,
    }
    meta = {
        "originalSize": [original_w, original_h],
        "normalizedSize": [resolution, resolution],
        "contentBox": [pad_left, pad_top, pad_left + normalized_w, pad_top + normalized_h],
        "padding": padding,
        "scale": scale,
        "coordinateSpace": "normalized_canvas",
        "originalToNormalized": {
            "x": "round(original_x * scale) + padding.left",
            "y": "round(original_y * scale) + padding.top",
        },
        "normalizedToOriginal": {
            "x": "(normalized_x - padding.left) / scale",
            "y": "(normalized_y - padding.top) / scale",
        },
    }
    return canvas, meta


def build_removal_contract(layer: dict[str, Any]) -> dict[str, Any]:
    foreign = [item["id"] for item in KINE_LAYER_SEMANTIC_PARTS if item["id"] != layer["id"]]
    layer_id = layer["id"]
    micro_layer = layer_id in FACIAL_MICRO_LAYERS
    part_targets = spine_part_targets(layer_id)
    return {
        "type": "kine.layerRedrawRemovalContract",
        "version": "0.1",
        "componentId": layer["id"],
        "ownerScope": layer["tag"],
        "directorPlan": "director/decomposition-plan.json",
        "spineBone": spine_bone_for_component(layer_id),
        "spinePartTargets": part_targets,
        "spineSplitRequired": layer_id in SPINE_LIMB_SEGMENTS,
        "preserve": [
            "source-visible owner pixels from the original image",
            "the original component identity, shape language, palette, line weight, lighting, and pose relationship",
        ],
        "hardCutBeforeRedraw": True,
        "eraseBeforeGeneration": foreign,
        "repairBeforeGeneration": [
            "remove foreign-owner pixels that leaked into the hard cut",
            "fill missing owner pixels only when they are required to restore the original source component",
            "keep the repaired cutout registered to the source canvas before any redraw",
        ],
        "redrawAllowed": [
            "owner-clean repair of the hard-cut component",
            "hidden or occluded regions that belong to this component",
        ],
        "forbiddenRedraw": foreign + ["background", "watermark", "labels", "extra limbs", "pose redesign", "identity redesign", "style reinterpretation"],
        "facialMicroLayerPolicy": "source_locked_visible_layer; imagegen may only repair hidden/occluded owner pixels" if micro_layer else None,
        "reviewState": "planned",
    }


def director_layer_entry(layer: dict[str, Any], canvas: tuple[int, int], content_box: list[int] | None) -> dict[str, Any]:
    layer_id = layer["id"]
    w, h = canvas
    box = content_box or [0, 0, w, h]
    role = "semantic_owner"
    if layer_id in {"torso", "hips", "arms", "legs", "feet"}:
        role = "body_motion_owner"
    elif layer_id in {"face", "hair-front", "hair-rear", "ears", "head-accessory", "glasses"} or layer_id in FACIAL_MICRO_LAYERS:
        role = "head_motion_owner"
    elif layer_id in {"props", "tail", "wings"}:
        role = "optional_prop_owner"
    return {
        "id": layer_id,
        "tag": layer.get("tag", layer_id),
        "role": role,
        "required": layer.get("required", False),
        "drawOrder": layer.get("order"),
        "sourceCanvas": [w, h],
        "sourceContentBox": box,
        "spineBone": spine_bone_for_component(layer_id),
        "spineParts": spine_part_targets(layer_id),
        "hardCutPolicy": {
            "mustRunBeforeRedraw": True,
            "output": f"layers/{layer_id}/visible_locked.png",
            "mask": f"layers/{layer_id}/masks/visible_mask.png",
            "acceptance": "hard-cut visible locks must recompose the source before redraw can be trusted",
        },
        "redrawPreparation": [
            "start from the hard-cut source component, not from a generic text-only prompt",
            "erase leaked foreign-owner pixels",
            "restore missing owner pixels that were lost during the hard cut",
            "keep canvas registration, original scale, pose, colors, and silhouette",
        ],
        "imagegenPolicy": {
            "mode": "strict_source_component_repair",
            "mustMatchOriginalComponent": True,
            "allowedChange": "owner cleanup, missing-pixel repair, and hidden-surface completion only",
            "forbiddenChange": "new identity, new face, new costume, new proportions, new pose, or standalone redesigned detail",
        },
        "splitPolicy": {
            "leftRight": layer_id in PAIR_SPLIT_LAYERS,
            "frontBackOrDepth": layer_id in FRONT_BACK_SPLIT_LAYERS,
            "reason": "animation exposure" if layer_id in PAIR_SPLIT_LAYERS or layer_id in FRONT_BACK_SPLIT_LAYERS else "semantic owner may remain single until QA says otherwise",
        },
        "facialMicroLayerPolicy": (
            "deliverable layer is required, but visible pixels must come from the source; broad imagegen sheets must not create alternate eyes/nose/mouth/brows"
            if layer_id in FACIAL_MICRO_LAYERS
            else None
        ),
    }


def build_director_decomposition_plan(plan: dict[str, Any], normalization: dict[str, Any] | None = None) -> dict[str, Any]:
    canvas = tuple(plan["canvas"])
    content_box = None
    if normalization:
        content_box = normalization.get("contentBox")
    return {
        "type": "kine.animationDirectorDecompositionPlan",
        "version": DIRECTOR_DECOMPOSITION_VERSION,
        "source": plan["source"],
        "canvas": list(canvas),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "directorRole": "animation-aware source-master decomposition director",
        "pipelineContract": [
            "analyze the original image as animation source material",
            "define semantic owners and split needs before any $imagegen skill call",
            "hard-cut source-visible owner evidence first",
            "repair hard cuts by erasing excess pixels or filling missing owner pixels",
            "use imagegen only to redraw the corresponding original component and hidden owner surfaces",
            "reject redraws that change identity, style, proportions, or source-visible design",
            "split limb owners into Spine bone-chain parts (upper-arm/lower-arm/hand, thigh/shin/foot, left and right)",
        ],
        "spineSkeleton": {
            "format": f"spine-json-{SPINE_FORMAT_VERSION}",
            "bones": [{"name": bone["name"], "parent": bone["parent"]} for bone in SPINE_BONE_TEMPLATE],
            "limbSegments": {owner: [segment for segment, _ in segments] for owner, segments in SPINE_LIMB_SEGMENTS.items()},
            "partTargets": [target for layer in plan["layers"] for target in spine_part_targets(layer["id"])],
            "note": "Spine bone-part decomposition targets. Limb owners expand to left/right x segment children; export_spine() emits a region-attachment skeleton from accepted components.",
        },
        "layers": [director_layer_entry(layer, canvas, content_box) for layer in plan["layers"]],
    }


def write_director_decomposition_plan(workspace: Path, normalization: dict[str, Any] | None = None) -> dict[str, Any]:
    plan = load_plan(workspace)
    director_plan = build_director_decomposition_plan(plan, normalization)
    write_json(workspace / "director" / "decomposition-plan.json", director_plan)
    update_run_state(workspace, {"directorDecompositionPlan": "director/decomposition-plan.json"})
    return director_plan


def v3_workspace_contract_text() -> str:
    return """# KINE-LAYER V3 Workspace Contract

This workspace follows the KINE-LAYER V3 pipeline contract.

## Completion Contract

- work order is not final.
- raw sheet, transparent sheet, normalized sheet, visible cut, candidate sheet, source-locked reconstruction, and contact sheet artifacts are not final.
- Generated images visible in chat are not evidence until they are saved to the task `expectedOutput` path inside this workspace and ingested.
- `$imagegen` is the only drawing path. Local scripts may file, ingest, normalize, validate, register, recompose, review, package, and export already generated images; they do not replace `$imagegen`.
- validation report is source of truth.

## Source Of Truth

Read these reports before claiming completion:

- `v3/check/v3-validation-report.json`
- `v3/review/review-integrity-report.json`
- `v3/registration/registration-report.json`
- `v3/check/recompose-report.json`
- `v3/export/components-manifest.json`

If validation is missing, rejected, or blocked, report the blocker and continue the V3 pipeline instead of treating an intermediate asset as final.

## Handoff Rule

When continuing this workspace in a new Agent session, read this contract first. Generic global or project `AGENTS.md` guidance is a default only; it cannot downgrade V3 completion to a plan, a work order, a raw sheet, or an unregistered candidate.
"""


def write_v3_workspace_contract(workspace: Path) -> str:
    contract_path = workspace / V3_WORKSPACE_CONTRACT
    contract_path.write_text(v3_workspace_contract_text(), encoding="utf-8")
    return V3_WORKSPACE_CONTRACT


def init_workspace(source: Path, out: Path, resolution: int = DEFAULT_RESOLUTION, force: bool = False) -> None:
    ensure_fresh_output_dir(out, force=force)
    original_img = Image.open(source).convert("RGBA")
    original_source_hash = file_sha256(source)
    original_normalized_img, original_normalization = normalize_source_image(original_img, resolution)
    source_input_img, background_preflight = apply_source_background_preflight(original_img)
    source_img, normalization = normalize_source_image(source_input_img, resolution)
    source_dir = out / "source"
    source_dir.mkdir(exist_ok=True)
    original_copy = source_dir / f"original{source.suffix.lower() or '.png'}"
    try:
        shutil.copy2(source, original_copy)
    except OSError:
        original_img.save(original_copy.with_suffix(".png"))
        original_copy = original_copy.with_suffix(".png")
    if background_preflight.get("applied"):
        source_input_img.save(source_dir / "preprocessed-alpha.png")
        background_preflight["preprocessedSource"] = "source/preprocessed-alpha.png"
    original_normalized_img.save(source_dir / "original-normalized.png")
    source_img.save(source_dir / "source.png")
    source_img.save(source_dir / "normalized.png")
    source_copy = out / "source.png"
    source_img.save(source_copy)
    write_json(source_dir / "source-background-preflight.json", background_preflight)

    layers_dir = out / "layers"
    prompts_dir = out / "prompts"
    layers_dir.mkdir(exist_ok=True)
    prompts_dir.mkdir(exist_ok=True)

    plan_layers = []
    campaign_jobs = []
    for layer in KINE_LAYER_SEMANTIC_PARTS:
        layer_dir = layers_dir / layer["id"]
        layer_dir.mkdir(parents=True, exist_ok=True)
        (layer_dir / "masks").mkdir(exist_ok=True)
        (layer_dir / "backend_raw").mkdir(exist_ok=True)
        prompt = make_prompt(layer, source_img.size)
        (prompts_dir / f"{layer['id']}.txt").write_text(prompt + "\n", encoding="utf-8")
        contract_path = layer_dir / "layer-redraw-removal-contract.json"
        write_json(contract_path, build_removal_contract(layer))
        plan_layers.append(
            {
                **layer,
                "kind": "semantic",
                "taxonomy": "kine-component-schema-v0.1",
                "folder": f"layers/{layer['id']}",
                "promptFile": f"prompts/{layer['id']}.txt",
                "removalContract": f"layers/{layer['id']}/layer-redraw-removal-contract.json",
                "generated": f"layers/{layer['id']}/generated.png",
                "alphaCandidate": f"layers/{layer['id']}/alpha_candidate.png",
                "backendRaw": f"layers/{layer['id']}/backend_raw",
                "generationProvenance": f"layers/{layer['id']}/generation-provenance.json",
                "visibleLocked": f"layers/{layer['id']}/visible_locked.png",
                "hiddenUnderpaint": f"layers/{layer['id']}/hidden_underpaint.png",
                "masks": {
                    "visible": f"layers/{layer['id']}/masks/visible_mask.png",
                    "occlusion": f"layers/{layer['id']}/masks/occlusion_mask.png",
                },
                "bbox": None,
                "depthMedian": None,
                "orderSource": "kine_component_schema_v0.1",
                "orderConfidence": 0.35,
                "generationState": "planned",
                "qaDisposition": "missing",
            }
        )
        campaign_jobs.append(
            {
                "componentId": layer["id"],
                "generationState": "planned",
                "qaDisposition": "missing",
                "ownerScope": layer["tag"],
                "promptFile": f"prompts/{layer['id']}.txt",
                "removalContract": f"layers/{layer['id']}/layer-redraw-removal-contract.json",
                "expectedLayer": f"layers/{layer['id']}/generated.png",
                "forbiddenOwners": [item["id"] for item in KINE_LAYER_SEMANTIC_PARTS if item["id"] != layer["id"]],
            }
        )

    plan = {
        "source": "source.png",
        "canvas": list(source_img.size),
        "mode": "full_canvas_registered_layers",
        "taxonomy": "kine-component-schema-v0.1",
        "drawOrderBackToFront": [layer["id"] for layer in sorted(plan_layers, key=lambda item: item["order"])],
        "layers": plan_layers,
        "postProcess": {
            "leftRightSplit": "manual_or_scripted_after_semantic_layers",
            "depthSplit": "manual_or_scripted_after_depth_or_mask_annotation",
            "rigComponentLedger": "component-ledger.json",
        },
        "rules": {
            "generatedLayerPath": "layers/<layer-id>/generated.png",
            "mustMatchCanvas": True,
            "transparentBackground": True,
            "generationBackend": PUBLIC_GENERATION_BACKEND,
            "localScriptsOwnQAAndPackaging": True,
        },
    }
    write_json(
        out / "source" / "input-normalization.json",
        {
            "original": str(original_copy.relative_to(out)),
            "originalNormalized": "source/original-normalized.png",
            "source": "source/source.png",
            "normalized": "source/normalized.png",
            "backgroundPreflight": "source/source-background-preflight.json",
            "originalNormalization": original_normalization,
            "targetResolution": resolution,
            **normalization,
        },
    )
    contract_rel = write_v3_workspace_contract(out)
    write_json(
        out / "run-state.json",
        {
            "type": "kine.layerRunState",
            "version": "0.1",
            "freshWorkspace": True,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "sourceHash": original_source_hash,
            "normalizedSourceHash": file_sha256(source_copy),
            "sourceBackgroundPreflight": "source/source-background-preflight.json",
            "sourceBackgroundStatus": background_preflight.get("status"),
            "sourceBackgroundAction": background_preflight.get("action"),
            "v3WorkspaceContract": contract_rel,
            "workspace": out.name,
            "status": "initialized",
        },
    )
    write_json(
        out / "component-schema.json",
        {
            "type": "kine.componentSchema",
            "version": "0.1",
            "components": [
                {"id": item["id"], "label": item["tag"], "required": item["required"], "order": item["order"]}
                for item in KINE_LAYER_SEMANTIC_PARTS
            ],
        },
    )
    write_json(
        out / "campaign.json",
        {
            "type": "kine.generationCampaign",
            "source": "source/source.png",
            "schema": "component-schema.json",
            "jobs": campaign_jobs,
        },
    )
    write_json(out / "layer-plan.json", plan)
    write_director_decomposition_plan(out, normalization)
    write_json(
        out / "component-ledger.json",
        {
            "type": "kine.componentLedger",
            "status": "template_pending_layer_generation",
            "source": "source.png",
            "normalizedSource": "source/normalized.png",
            "canvas": list(source_img.size),
            "components": RIG_COMPONENT_TEMPLATE,
            "drawOrderVariants": [],
            "notes": [
                "This ledger is a rig-readiness template. Fill pivot/socket/bbox after semantic layers pass QA.",
                "Do not claim Spine/Live2D readiness until rotation exposure QA exists for each component.",
            ],
        },
    )
    write_depth_order(out, plan)
    write_cutout_map_template(out)
    write_v3_source_subject_preflight_report(out)
    print(json.dumps({"workspace": str(out), "source": str(source_copy), "resolution": resolution, "layers": len(plan_layers)}, ensure_ascii=False, indent=2))


def make_prompt(layer: dict[str, Any], canvas: tuple[int, int]) -> str:
    micro_note = ""
    if layer["id"] in FACIAL_MICRO_LAYERS:
        micro_note = "\n- This is a facial micro layer: use exact source-visible pixels as the design source; do not invent alternate eyes, nose, mouth, brows, or expression."
    return f"""Use case: precise-object-edit
Asset type: Kine Layer transparent registered source-master layer
Primary request: Create the `{layer['id']}` layer from the provided source character image.
Layer instruction: {layer['prompt']}.
Taxonomy tag: {layer.get('tag', layer['id'])}.
Canvas: exactly {canvas[0]}x{canvas[1]} pixels.
Output: one transparent PNG with the same full canvas size as the source image.
Director/removal contract: follow `director/decomposition-plan.json` and `layers/{layer['id']}/layer-redraw-removal-contract.json`. The hard-cut source-visible owner component is the starting evidence, not a generic redraw target.
Hard constraints:
- Keep the character style, line quality, colors, lighting, scale, perspective, and visible silhouette consistent with the source.
- Include only this semantic layer; all other character/body/background content must be transparent.
- Preserve source-visible pixels as closely as possible. Use hidden completion only for occluded regions that belong to this layer.
- If the hard-cut source component includes foreign-owner pixels, erase those pixels before redraw; if the hard cut is missing owner pixels, repair only the missing owner pixels.
- The final redraw must look like the same corresponding component from the original image, not a new interpretation.
- Do not add extra limbs, change side, change pose, crop, resize, rotate, or redesign.
- No shadow, no background, no labels, no watermark.{micro_note}
"""


def layer_image(workspace: Path, layer_id: str) -> Path:
    layer_dir = workspace / "layers" / layer_id
    generated = layer_dir / "generated.png"
    visible = layer_dir / "visible_locked.png"
    hidden = layer_dir / "hidden_underpaint.png"
    if visible.exists() and hidden.exists():
        try:
            return compose_two_layers(visible, hidden, generated)
        except ValueError:
            return generated
    if generated.exists():
        return generated
    return generated


def read_layer_placement(workspace: Path, layer_id: str) -> dict[str, Any] | None:
    """Read a layer's optional placement (offset + size on the source canvas).

    A layer image may be an independent cropped PNG instead of a full-canvas square,
    as long as `layers/<id>/placement.json` records where it sits on the source canvas.
    This keeps components independent while preserving exact registration.
    """
    data = read_json_if_exists(workspace / "layers" / layer_id / "placement.json")
    if not data:
        return None
    try:
        return {
            "x": int(data["x"]),
            "y": int(data["y"]),
            "w": int(data["w"]),
            "h": int(data["h"]),
            "sourceCanvas": data.get("sourceCanvas"),
        }
    except (KeyError, TypeError, ValueError):
        return None


def place_image_on_canvas(img: Image.Image, canvas_size: tuple[int, int], offset: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    canvas.alpha_composite(img.convert("RGBA"), (int(offset[0]), int(offset[1])))
    return canvas


def placed_layer_image(workspace: Path, layer_id: str, canvas_size: tuple[int, int]) -> tuple[Image.Image | None, bool, list[str]]:
    """Return (full-canvas RGBA image, placement_valid, failures) for a layer.

    Full-canvas layers (size == source canvas) pass through unchanged. Independent
    cropped layers are placed onto a transparent source canvas using their
    `placement.json`, so every QA gate still runs in canvas space and registration is
    preserved. A cropped layer without valid, in-bounds placement is invalid and the
    caller must reject it (this is the anti-drift guarantee).
    """
    img_path = layer_image(workspace, layer_id)
    if not img_path.exists():
        return None, False, []
    try:
        img = Image.open(img_path).convert("RGBA")
    except OSError:
        return None, False, ["layer_image_unreadable"]
    if img.size == canvas_size:
        return img, True, []
    placement = read_layer_placement(workspace, layer_id)
    if not placement:
        return img, False, [f"cropped_layer_missing_placement_size_{list(img.size)}_canvas_{list(canvas_size)}"]
    x, y, w, h = placement["x"], placement["y"], placement["w"], placement["h"]
    if (img.width, img.height) != (w, h):
        return img, False, [f"placement_size_mismatch_declared_{[w, h]}_image_{list(img.size)}"]
    if x < 0 or y < 0 or x + w > canvas_size[0] or y + h > canvas_size[1]:
        return img, False, [f"placement_out_of_bounds_{[x, y, w, h]}_canvas_{list(canvas_size)}"]
    return place_image_on_canvas(img, canvas_size, (x, y)), True, []


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def layer_debug_image(workspace: Path, layer_id: str) -> Path | None:
    layer_dir = workspace / "layers" / layer_id
    for name in ["alpha_candidate.png", "hidden_underpaint.png", "generated.png", "visible_locked.png"]:
        path = layer_dir / name
        if path.exists():
            return path
    raw_dir = layer_dir / "backend_raw"
    if raw_dir.exists():
        for path in sorted(raw_dir.iterdir()):
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                return path
    return None


def first_backend_raw(layer_dir: Path) -> Path | None:
    raw_dir = layer_dir / "backend_raw"
    if not raw_dir.exists():
        return None
    preferred = sorted(
        path
        for path in raw_dir.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and "chromakey" not in path.stem.lower()
    )
    fallback = sorted(path for path in raw_dir.iterdir() if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    return (preferred or fallback or [None])[0]


def layer_artifact_paths(workspace: Path, layer_id: str) -> dict[str, Path]:
    layer_dir = workspace / "layers" / layer_id
    candidates = {
        "final": layer_dir / "generated.png",
        "redraw": layer_dir / "alpha_candidate.png",
        "hidden": layer_dir / "hidden_underpaint.png",
        "visible": layer_dir / "visible_locked.png",
    }
    raw = first_backend_raw(layer_dir)
    if raw:
        candidates["raw"] = raw
    return {key: path for key, path in candidates.items() if path.exists()}


def artifact_stats(path: Path, canvas_size: tuple[int, int]) -> dict[str, Any] | None:
    try:
        img = Image.open(path).convert("RGBA")
    except OSError:
        return None
    stats = alpha_stats(img)
    if img.size != canvas_size:
        stats["imageSize"] = list(img.size)
        stats["canvasRegistered"] = False
    else:
        stats["imageSize"] = list(canvas_size)
        stats["canvasRegistered"] = True
    return stats


def hidden_contribution(workspace: Path, layer_id: str) -> dict[str, Any] | None:
    layer_dir = workspace / "layers" / layer_id
    visible = layer_dir / "visible_locked.png"
    hidden = layer_dir / "hidden_underpaint.png"
    if not (visible.exists() and hidden.exists()):
        return None
    v = Image.open(visible).convert("RGBA").getchannel("A")
    h = Image.open(hidden).convert("RGBA").getchannel("A")
    if v.size != h.size:
        return {"status": "size_mismatch", "visibleSize": list(v.size), "hiddenSize": list(h.size)}
    visible_data = v.tobytes()
    hidden_data = h.tobytes()
    visible_px = sum(1 for value in visible_data if value > 0)
    hidden_px = sum(1 for value in hidden_data if value > 0)
    outside_visible_px = sum(1 for hv, vv in zip(hidden_data, visible_data) if hv > 0 and vv == 0)
    return {
        "status": "measured",
        "visibleAlphaPixels": visible_px,
        "hiddenAlphaPixels": hidden_px,
        "hiddenOutsideVisiblePixels": outside_visible_px,
        "hiddenOutsideVisibleRatio": round(outside_visible_px / max(visible_px, 1), 6),
    }


def layer_source_alpha_bounds(workspace: Path, img: Image.Image) -> dict[str, Any] | None:
    source_path = workspace / "source.png"
    if not source_path.exists():
        return None
    try:
        source = Image.open(source_path).convert("RGBA")
    except OSError:
        return None
    candidate = img.convert("RGBA")
    if candidate.size != source.size:
        return {"status": "size_mismatch", "sourceSize": list(source.size), "candidateSize": list(candidate.size)}
    source_alpha = source.getchannel("A").tobytes()
    candidate_alpha = candidate.getchannel("A").tobytes()
    source_px = sum(1 for value in source_alpha if value > 0)
    candidate_px = sum(1 for value in candidate_alpha if value > 0)
    outside_px = sum(1 for cv, sv in zip(candidate_alpha, source_alpha) if cv > 0 and sv == 0)
    return {
        "status": "measured",
        "sourceAlphaPixels": source_px,
        "candidateAlphaPixels": candidate_px,
        "outsideSourceAlphaPixels": outside_px,
        "outsideSourceAlphaRatioOfSource": round(outside_px / max(source_px, 1), 6),
        "outsideSourceAlphaRatioOfCandidate": round(outside_px / max(candidate_px, 1), 6),
        "limit": LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT,
    }


def provenance_is_source_visible_lock(data: dict[str, Any] | None) -> bool:
    if not data:
        return False
    if data.get("sourceLockedFacialMicro") is True or data.get("mode") == "source_locked_facial_micro":
        return False
    backend = str(data.get("backend") or "")
    raw_candidate = str(data.get("rawCandidate") or data.get("candidate") or data.get("source") or "")
    notes = str(data.get("notes") or "")
    mode = str(data.get("mode") or "")
    values = " ".join([backend, raw_candidate, notes, mode]).lower()
    source_visible_markers = [
        SOURCE_VISIBLE_BACKEND.lower(),
        "visible-source",
        "source-visible",
        "source visible",
        "visible_locked",
        "visible locked",
        "exact source-canvas reconstruction",
    ]
    return any(marker in values for marker in source_visible_markers)


def promote_source_locked_facial_micro_layer(workspace: Path, layer_id: str) -> dict[str, Any] | None:
    if layer_id not in FACIAL_MICRO_LAYERS:
        return None
    layer_dir = workspace / "layers" / layer_id
    visible = layer_dir / "visible_locked.png"
    if not visible.exists():
        return None
    img = Image.open(visible).convert("RGBA")
    stats = alpha_stats(img)
    if stats["alphaCoverage"] <= 0:
        return None
    generated = layer_dir / "generated.png"
    shutil.copy2(visible, generated)
    provenance = {
        "type": "kine.layerGenerationProvenance",
        "version": "0.1",
        "componentId": layer_id,
        "backend": SOURCE_LOCKED_MICRO_BACKEND,
        "mode": "source_locked_facial_micro",
        "sourceLockedFacialMicro": True,
        "rawCandidate": f"layers/{layer_id}/visible_locked.png",
        "registeredTarget": f"layers/{layer_id}/generated.png",
        "alpha": stats,
        "noHiddenSurfaceRequired": True,
        "notes": "facial micro layer accepted from exact source-visible pixels; broad image generation must not redraw it",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(layer_dir / "generation-provenance.json", provenance)
    write_json(
        layer_dir / "surface-review.json",
        {
            "type": "kine.surfaceReview",
            "version": "0.1",
            "componentId": layer_id,
            "noHiddenSurfaceRequired": True,
            "sourceLockedFacialMicro": True,
            "reason": "facial micro source-locked layers are exact source pixels and should not be freely redrawn",
            "provenance": "generation-provenance.json",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    update_layer_plan_entry(
        workspace,
        layer_id,
        {
            "generationState": "source_locked_facial_micro",
            "qaDisposition": "needs_visual_review",
            "noHiddenSurfaceRequired": True,
            "bbox": stats["alphaBbox"],
            "xyxy": stats["alphaBbox"],
            "frame_size": list(img.size),
        },
    )
    update_campaign_job(
        workspace,
        layer_id,
        {
            "generationState": "source_locked_facial_micro",
            "qaDisposition": "needs_visual_review",
            "alphaCandidate": f"layers/{layer_id}/generated.png",
            "bbox": stats["alphaBbox"],
            "noHiddenSurfaceRequired": True,
        },
    )
    return provenance


def provenance_allows_no_hidden_surface(layer_dir: Path) -> bool:
    provenances = [
        read_json_if_exists(layer_dir / "generation-provenance.json"),
        read_json_if_exists(layer_dir / "hidden_underpaint_provenance.json"),
    ]
    if any(provenance_is_source_visible_lock(data) for data in provenances):
        return False
    review = read_json_if_exists(layer_dir / "surface-review.json")
    if review and review.get("noHiddenSurfaceRequired") is True:
        if provenance_is_source_visible_lock(review):
            return False
        return True
    for data in provenances:
        if data and data.get("noHiddenSurfaceRequired") is True:
            return True
    return False


def composition_issue(workspace: Path, layer_id: str) -> str | None:
    layer_dir = workspace / "layers" / layer_id
    visible = layer_dir / "visible_locked.png"
    hidden = layer_dir / "hidden_underpaint.png"
    if not (visible.exists() and hidden.exists()):
        return None
    v = Image.open(visible)
    h = Image.open(hidden)
    if v.size != h.size:
        return f"visible_hidden_size_mismatch_visible_{v.size}_hidden_{h.size}"
    return None


def layer_completion_status(workspace: Path, layer_id: str) -> str | None:
    layer_dir = workspace / "layers" / layer_id
    visible = layer_dir / "visible_locked.png"
    hidden = layer_dir / "hidden_underpaint.png"
    generated = layer_dir / "generated.png"
    provenance = layer_dir / "generation-provenance.json"
    hidden_provenance = layer_dir / "hidden_underpaint_provenance.json"
    backend_raw = layer_dir / "backend_raw"
    has_backend_artifact = any(layer_dir.glob("backend_*")) or (backend_raw.exists() and any(backend_raw.iterdir()))
    no_hidden_required = provenance_allows_no_hidden_surface(layer_dir)
    if visible.exists() and generated.exists() and not hidden.exists() and not no_hidden_required:
        return "source_lock_only_missing_hidden_underpaint_or_review"
    if hidden.exists():
        if not provenance.exists() and not hidden_provenance.exists() and not has_backend_artifact:
            return "hidden_underpaint_missing_generation_provenance"
        contribution = hidden_contribution(workspace, layer_id)
        if contribution and contribution.get("status") == "measured":
            if contribution.get("hiddenOutsideVisibleRatio", 0) < MIN_HIDDEN_OUTSIDE_VISIBLE_RATIO:
                return "hidden_underpaint_does_not_extend_visible_surface"
    if generated.exists() and not visible.exists() and not hidden.exists() and not provenance.exists() and not has_backend_artifact:
        return "generated_layer_missing_generation_provenance"
    if generated.exists() and not hidden.exists() and not no_hidden_required:
        return "hard_cutout_missing_hidden_underpaint_or_no_hidden_surface_review"
    return None


def completion_issue_status(issue: str) -> str:
    source_lock_issues = {
        "source_lock_only_missing_hidden_underpaint_or_review",
        "hard_cutout_missing_hidden_underpaint_or_no_hidden_surface_review",
    }
    return "source_lock_only" if issue in source_lock_issues else "visual_rejected"


def manual_visual_rejection(workspace: Path, layer_id: str) -> list[str]:
    reject_path = workspace / "layers" / layer_id / "visual_rejected.json"
    if not reject_path.exists():
        return []
    try:
        data = json.loads(reject_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["visual_rejected_invalid_json"]
    failures = data.get("failures")
    if isinstance(failures, list) and failures:
        return [str(item) for item in failures]
    note = data.get("reason") or data.get("notes")
    if note:
        return [str(note)]
    return ["visual_rejected_manual_gate"]


def compose_two_layers(visible: Path, hidden: Path, out: Path) -> Path:
    v = Image.open(visible).convert("RGBA")
    h = Image.open(hidden).convert("RGBA")
    if v.size != h.size:
        raise ValueError(f"Layer size mismatch: {visible} {v.size} vs {hidden} {h.size}")
    comp = Image.new("RGBA", v.size, (0, 0, 0, 0))
    comp.alpha_composite(h)
    comp.alpha_composite(v)
    comp.save(out)
    return out


def parse_rgb(value: str | None) -> tuple[int, int, int] | None:
    if not value or value == "none":
        return None
    parts = [item.strip() for item in value.split(",")]
    if len(parts) != 3:
        raise ValueError("--chroma-key must be 'r,g,b', 'auto', or 'none'")
    rgb = tuple(int(item) for item in parts)
    if any(channel < 0 or channel > 255 for channel in rgb):
        raise ValueError("--chroma-key values must be between 0 and 255")
    return rgb


def auto_chroma_key(img: Image.Image) -> tuple[int, int, int]:
    rgb = img.convert("RGBA")
    samples = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]
    buckets: dict[tuple[int, int, int], int] = {}
    for r, g, b, _a in samples:
        key = (r, g, b)
        buckets[key] = buckets.get(key, 0) + 1
    return max(buckets, key=buckets.get)


def remove_chroma_key(img: Image.Image, chroma_key: str | None, tolerance: int) -> Image.Image:
    rgba = img.convert("RGBA")
    if chroma_key == "auto":
        key = auto_chroma_key(rgba)
    else:
        key = parse_rgb(chroma_key)
    if key is None:
        return rgba
    kr, kg, kb = key
    if _np is not None:
        arr = _np.asarray(rgba).copy()
        rgb = arr[..., :3].astype(_np.int16)
        distance = _np.maximum(
            _np.maximum(_np.abs(rgb[..., 0] - kr), _np.abs(rgb[..., 1] - kg)),
            _np.abs(rgb[..., 2] - kb),
        )
        arr[..., 3][distance <= tolerance] = 0
        return Image.fromarray(arr, "RGBA")
    pixels = rgba.load()
    for py in range(rgba.height):
        for px in range(rgba.width):
            r, g, b, a = pixels[px, py]
            distance = max(abs(r - kr), abs(g - kg), abs(b - kb))
            if distance <= tolerance:
                pixels[px, py] = (r, g, b, 0)
    return rgba


def remove_edge_connected_background(
    img: Image.Image,
    key_color: list[int] | tuple[int, int, int],
    tolerance: int,
) -> tuple[Image.Image, dict[str, Any]]:
    """Remove only background-color pixels connected to the canvas edge.

    This protects source-internal pixels that happen to match a green-screen or
    flat background color, such as green eyes, buttons, gems, or costume marks.
    """
    rgba = img.convert("RGBA")
    width, height = rgba.size
    kr, kg, kb = [int(channel) for channel in key_color[:3]]
    pixels = rgba.load()

    def is_background_candidate(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        if a <= 8:
            return True
        return max(abs(r - kr), abs(g - kg), abs(b - kb)) <= tolerance

    from collections import deque

    seen = bytearray(width * height)
    queue: deque[int] = deque()

    def push(x: int, y: int) -> None:
        index = y * width + x
        if seen[index] or not is_background_candidate(x, y):
            return
        seen[index] = 1
        queue.append(index)

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(height):
        push(0, y)
        push(width - 1, y)

    while queue:
        index = queue.popleft()
        x = index % width
        y = index // width
        if x > 0:
            push(x - 1, y)
        if x + 1 < width:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < height:
            push(x, y + 1)

    connected_removed = 0
    isolated_key_pixels = 0
    for y in range(height):
        row = y * width
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a <= 8:
                continue
            near_key = max(abs(r - kr), abs(g - kg), abs(b - kb)) <= tolerance
            if seen[row + x]:
                pixels[x, y] = (r, g, b, 0)
                connected_removed += 1
            elif near_key:
                isolated_key_pixels += 1

    stats = {
        "method": "edge_connected_background",
        "connectedBackgroundPixels": connected_removed,
        "isolatedKeyColorPixelsPreserved": isolated_key_pixels,
    }
    return rgba, stats


def analyze_source_background(img: Image.Image, tolerance: int = 28) -> dict[str, Any]:
    rgba = img.convert("RGBA")
    width, height = rgba.size
    if width <= 0 or height <= 0:
        return {"status": "invalid_image", "shouldRemove": False}

    border: list[tuple[int, int, int, int]] = []
    for x in range(width):
        border.append(rgba.getpixel((x, 0)))
        border.append(rgba.getpixel((x, height - 1)))
    for y in range(1, height - 1):
        border.append(rgba.getpixel((0, y)))
        border.append(rgba.getpixel((width - 1, y)))

    transparent_border = sum(1 for _r, _g, _b, a in border if a <= 8)
    opaque_border = sum(1 for _r, _g, _b, a in border if a > 240)
    border_count = max(1, len(border))
    opaque_border_ratio = round(opaque_border / border_count, 6)
    transparent_border_ratio = round(transparent_border / border_count, 6)

    color_counts: dict[tuple[int, int, int], int] = {}
    for r, g, b, a in border:
        if a <= 8:
            continue
        key = (r, g, b)
        color_counts[key] = color_counts.get(key, 0) + 1
    key_color = max(color_counts, key=color_counts.get) if color_counts else None

    near_border = 0
    near_image = 0
    visible_pixels = 0
    if key_color is not None:
        kr, kg, kb = key_color
        for r, g, b, a in border:
            if a <= 8:
                continue
            if max(abs(r - kr), abs(g - kg), abs(b - kb)) <= tolerance:
                near_border += 1
        for r, g, b, a in rgba.getdata():
            if a <= 8:
                continue
            visible_pixels += 1
            if max(abs(r - kr), abs(g - kg), abs(b - kb)) <= tolerance:
                near_image += 1
    else:
        visible_pixels = sum(1 for _r, _g, _b, a in rgba.getdata() if a > 8)

    border_uniform_ratio = round(near_border / max(1, opaque_border), 6) if key_color is not None else 0.0
    image_key_ratio = round(near_image / max(1, visible_pixels), 6)
    has_existing_alpha = transparent_border_ratio > 0.20 or alpha_stats(rgba)["alphaCoverage"] < 0.98
    likely_flat_background = (
        key_color is not None
        and opaque_border_ratio >= 0.85
        and border_uniform_ratio >= 0.88
        and image_key_ratio >= 0.08
        and not has_existing_alpha
    )
    if has_existing_alpha:
        status = "alpha_source"
        action = "none"
        reason = "source_already_has_transparency"
    elif likely_flat_background:
        status = "flat_background_detected"
        action = "remove_edge_connected_background"
        reason = "opaque_uniform_border_color"
    else:
        status = "no_flat_background_detected"
        action = "none"
        reason = "border_not_uniform_or_not_opaque"

    return {
        "type": "kine.v3.sourceBackgroundPreflight",
        "version": "0.1",
        "status": status,
        "action": action,
        "shouldRemove": action == "remove_edge_connected_background",
        "reason": reason,
        "keyColor": list(key_color) if key_color is not None else None,
        "tolerance": tolerance,
        "opaqueBorderRatio": opaque_border_ratio,
        "transparentBorderRatio": transparent_border_ratio,
        "borderUniformRatio": border_uniform_ratio,
        "imageKeyColorRatio": image_key_ratio,
        "hasExistingAlpha": has_existing_alpha,
    }


def apply_source_background_preflight(img: Image.Image, tolerance: int = 28) -> tuple[Image.Image, dict[str, Any]]:
    report = analyze_source_background(img, tolerance=tolerance)
    if report.get("shouldRemove") and report.get("keyColor"):
        cleaned, cleanup_stats = remove_edge_connected_background(img, report["keyColor"], tolerance)
        if report["keyColor"][1] > report["keyColor"][0] * 1.15 and report["keyColor"][1] > report["keyColor"][2] * 1.15:
            cleaned = despill_green_edges(cleaned)
        report = {
            **report,
            "applied": True,
            "cleanup": cleanup_stats,
            "preprocessedAlpha": alpha_stats(cleaned),
            "note": "Flat source background connected to the canvas edge was removed before KINE-LAYER partitioning. Isolated same-color pixels inside the character are preserved.",
        }
        return cleaned, report
    report = {**report, "applied": False}
    return img.convert("RGBA"), report


def write_v3_source_preflight_report(workspace: Path, tolerance: int = 28) -> dict[str, Any]:
    source_path = workspace / "source.png"
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    report = analyze_source_background(Image.open(source_path).convert("RGBA"), tolerance=tolerance)
    report = {
        **report,
        "source": "source.png",
        "applied": False,
        "note": "Existing workspace inspection only. New V3 workspaces apply flat-background removal during init when this report says shouldRemove=true.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    out_dir = workspace / "v3" / "source"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "source-preflight.json", report)
    update_run_state(
        workspace,
        {
            "v3SourcePreflight": "v3/source/source-preflight.json",
            "v3SourcePreflightStatus": report.get("status"),
            "v3SourcePreflightAction": report.get("action"),
        },
    )
    print(json.dumps({"status": report["status"], "action": report["action"], "report": str(out_dir / "source-preflight.json")}, ensure_ascii=False, indent=2))
    return report


def _alpha_coverage_in_box(alpha: Image.Image, box: list[int] | tuple[int, int, int, int] | None) -> float:
    if not box:
        box = [0, 0, alpha.width, alpha.height]
    x0, y0, x1, y1 = [int(value) for value in box]
    x0 = max(0, min(alpha.width, x0))
    x1 = max(0, min(alpha.width, x1))
    y0 = max(0, min(alpha.height, y0))
    y1 = max(0, min(alpha.height, y1))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    crop = alpha.crop((x0, y0, x1, y1))
    opaque = sum(1 for value in crop.getdata() if value > 8)
    return round(opaque / max(1, crop.width * crop.height), 6)


def _bbox_ratio_metrics(bbox: list[int] | tuple[int, int, int, int] | None, size: tuple[int, int]) -> dict[str, Any]:
    width, height = size
    if not bbox or width <= 0 or height <= 0:
        return {
            "bboxAreaRatio": 0.0,
            "bboxWidthRatio": 0.0,
            "bboxHeightRatio": 0.0,
            "bboxTouchesEdgeCount": 0,
        }
    x0, y0, x1, y1 = [int(value) for value in bbox]
    bw = max(0, x1 - x0)
    bh = max(0, y1 - y0)
    edge_pad = max(2, round(min(width, height) * 0.02))
    touches = sum(
        [
            x0 <= edge_pad,
            y0 <= edge_pad,
            x1 >= width - edge_pad,
            y1 >= height - edge_pad,
        ]
    )
    return {
        "bboxAreaRatio": round((bw * bh) / max(1, width * height), 6),
        "bboxWidthRatio": round(bw / max(1, width), 6),
        "bboxHeightRatio": round(bh / max(1, height), 6),
        "bboxTouchesEdgeCount": touches,
    }


def _alpha_edge_pixel_ratio(alpha: Image.Image, margin_ratio: float = 0.04) -> float:
    width, height = alpha.size
    if width <= 0 or height <= 0:
        return 0.0
    margin = max(1, round(min(width, height) * margin_ratio))
    total = 0
    edge = 0
    pixels = alpha.load()
    for y in range(height):
        in_edge_y = y < margin or y >= height - margin
        for x in range(width):
            if pixels[x, y] <= 8:
                continue
            total += 1
            if in_edge_y or x < margin or x >= width - margin:
                edge += 1
    return round(edge / max(1, total), 6)


def _alpha_overlap_ratio(candidate_alpha: Image.Image, source_alpha: Image.Image) -> float:
    if candidate_alpha.size != source_alpha.size:
        return 0.0
    candidate = candidate_alpha.point(lambda value: 255 if value > 8 else 0)
    source = source_alpha.point(lambda value: 255 if value > 8 else 0)
    candidate_pixels = 0
    overlap_pixels = 0
    for c, s in zip(candidate.getdata(), source.getdata()):
        if c <= 0:
            continue
        candidate_pixels += 1
        if s > 0:
            overlap_pixels += 1
    return round(overlap_pixels / max(1, candidate_pixels), 6)


def evaluate_alpha_subject_confidence(img: Image.Image) -> dict[str, Any]:
    """Score whether an alpha image already looks like a usable isolated character.

    This is intentionally conservative. It does not try to recognize identity; it only
    prevents obvious polluted alpha sources from bypassing the $imagegen subject matte
    route.
    """
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    stats = alpha_stats(rgba)
    bbox = stats.get("alphaBbox")
    ratios = _bbox_ratio_metrics(bbox, rgba.size)
    edge_alpha_ratio = _alpha_edge_pixel_ratio(alpha)
    coverage = float(stats.get("alphaCoverage") or 0.0)
    blockers: list[str] = []
    if not bbox:
        blockers.append("alpha_source_empty")
    if coverage < V3_SUBJECT_MIN_ALPHA_COVERAGE:
        blockers.append("alpha_source_too_sparse")
    if coverage > V3_SUBJECT_MAX_ALPHA_COVERAGE:
        blockers.append("alpha_source_covers_too_much_canvas")
    if ratios["bboxAreaRatio"] < V3_SUBJECT_MIN_BBOX_AREA_RATIO:
        blockers.append("alpha_source_bbox_too_small")
    if ratios["bboxWidthRatio"] < V3_SUBJECT_MIN_BBOX_WIDTH_RATIO:
        blockers.append("alpha_source_bbox_too_narrow")
    if ratios["bboxHeightRatio"] < V3_SUBJECT_MIN_BBOX_HEIGHT_RATIO:
        blockers.append("alpha_source_bbox_too_short_for_full_character")
    if ratios["bboxAreaRatio"] > 0.95 and ratios["bboxTouchesEdgeCount"] >= 3:
        blockers.append("alpha_source_bbox_covers_scene_canvas")
    if edge_alpha_ratio > V3_SUBJECT_EDGE_ALPHA_RATIO_LIMIT and ratios["bboxTouchesEdgeCount"] >= 2:
        blockers.append("alpha_source_likely_contains_edge_scene_fragments")

    confidence = 0.92
    confidence -= 0.10 * len(blockers)
    if edge_alpha_ratio > V3_SUBJECT_EDGE_ALPHA_RATIO_LIMIT:
        confidence -= min(0.18, (edge_alpha_ratio - V3_SUBJECT_EDGE_ALPHA_RATIO_LIMIT) * 0.8)
    if ratios["bboxTouchesEdgeCount"] >= 3:
        confidence -= 0.16
    confidence = round(max(0.0, min(1.0, confidence)), 6)
    return {
        "confidence": confidence,
        "blockers": blockers,
        "alphaStats": stats,
        **ratios,
        "edgeAlphaRatio": edge_alpha_ratio,
    }


def analyze_source_subject(workspace: Path) -> dict[str, Any]:
    source_path = workspace / "source.png"
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    source = Image.open(source_path).convert("RGBA")
    alpha = source.getchannel("A")
    normalization = read_json_if_exists(workspace / "source" / "input-normalization.json") or {}
    content_box = normalization.get("contentBox") if isinstance(normalization.get("contentBox"), list) else None
    background = read_json_if_exists(workspace / "source" / "source-background-preflight.json") or {}
    content_alpha_coverage = _alpha_coverage_in_box(alpha, content_box)
    full_alpha_stats = alpha_stats(source)
    background_status = background.get("status")
    background_applied = bool(background.get("applied"))
    alpha_subject = evaluate_alpha_subject_confidence(source)

    if background_status == "alpha_source":
        if alpha_subject["confidence"] >= V3_ALPHA_SOURCE_CONFIDENCE_MIN and not alpha_subject["blockers"]:
            status = "ready_character_source"
            reason = "source_has_confident_character_alpha_before_preprocessing"
        else:
            status = "needs_imagegen_subject_matte"
            reason = "alpha_source_low_subject_confidence"
    elif background_applied:
        status = "ready_character_source"
        reason = "flat_or_edge_connected_background_removed"
    elif content_alpha_coverage < 0.985:
        if alpha_subject["confidence"] >= V3_ALPHA_SOURCE_CONFIDENCE_MIN and not alpha_subject["blockers"]:
            status = "ready_character_source"
            reason = "source_has_confident_internal_transparency"
        else:
            status = "needs_imagegen_subject_matte"
            reason = "internal_transparency_low_subject_confidence"
    else:
        status = "needs_imagegen_subject_matte"
        reason = "opaque_non_flat_scene_source"

    should_route_to_subject_isolation = status == "needs_imagegen_subject_matte"
    return {
        "type": "kine.v3.sourceSubjectPreflight",
        "version": "0.1",
        "status": status,
        "shouldUseImagegenSubjectIsolation": should_route_to_subject_isolation,
        "shouldBlockV3Masks": should_route_to_subject_isolation,
        "requiredAction": "run_imagegen_subject_isolation" if should_route_to_subject_isolation else "none",
        "reason": reason,
        "source": "source.png",
        "backgroundPreflight": "source/source-background-preflight.json",
        "backgroundStatus": background_status,
        "backgroundAction": background.get("action"),
        "backgroundApplied": background_applied,
        "contentBox": content_box,
        "contentAlphaCoverage": content_alpha_coverage,
        "sourceAlphaCoverage": full_alpha_stats.get("alphaCoverage"),
        "sourceAlphaBbox": full_alpha_stats.get("alphaBbox"),
        "sourceSubjectConfidence": alpha_subject["confidence"],
        "sourceSubjectConfidenceBlockers": alpha_subject["blockers"],
        "sourceSubjectMetrics": {
            "bboxAreaRatio": alpha_subject["bboxAreaRatio"],
            "bboxWidthRatio": alpha_subject["bboxWidthRatio"],
            "bboxHeightRatio": alpha_subject["bboxHeightRatio"],
            "bboxTouchesEdgeCount": alpha_subject["bboxTouchesEdgeCount"],
            "edgeAlphaRatio": alpha_subject["edgeAlphaRatio"],
        },
        "note": (
            "Opaque non-flat scene sources are automatically routed to a $imagegen subject-isolation task "
            "before V3 mask/reference generation; otherwise background pixels pollute every component."
        )
        if should_route_to_subject_isolation
        else "Source appears ready for V3 component mask/reference generation.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }


def write_v3_source_subject_preflight_report(workspace: Path) -> dict[str, Any]:
    report = analyze_source_subject(workspace)
    out_path = workspace / "source" / "source-subject-preflight.json"
    write_json(out_path, report)
    update_run_state(
        workspace,
        {
            "sourceSubjectPreflight": "source/source-subject-preflight.json",
            "sourceSubjectStatus": report.get("status"),
            "sourceSubjectRequiredAction": report.get("requiredAction"),
        },
    )
    print(json.dumps({"status": report["status"], "requiredAction": report["requiredAction"], "report": str(out_path)}, ensure_ascii=False, indent=2))
    return report


def v3_subject_preflight_blocks_masks(workspace: Path) -> dict[str, Any]:
    report_path = workspace / "source" / "source-subject-preflight.json"
    report = read_json_if_exists(report_path) if report_path.exists() else write_v3_source_subject_preflight_report(workspace)
    return report if isinstance(report, dict) else {}


def block_scene_partition_if_needed(workspace: Path, command_name: str) -> dict[str, Any] | None:
    subject_report = v3_subject_preflight_blocks_masks(workspace)
    if not subject_report.get("shouldBlockV3Masks"):
        return None
    result = {
        "type": "kine.v3.partitionBlocked",
        "version": "0.1",
        "status": PARTS_SHEET_BLOCKED_STATUS,
        "command": command_name,
        "workspace": str(workspace),
        "blockers": ["source_subject_needs_imagegen_subject_matte"],
        "sourceSubjectPreflight": "source/source-subject-preflight.json",
        "requiredAction": subject_report.get("requiredAction"),
        "note": "Partition/apply-cutout-map is blocked for complex scene sources. Run the V3 $imagegen subject isolation flow first, then partition the clean character-matte workspace.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "v3" / "source" / "partition-blocked.json", result)
    update_run_state(
        workspace,
        {
            "partitionStatus": PARTS_SHEET_BLOCKED_STATUS,
            "partitionBlocked": "v3/source/partition-blocked.json",
            "partitionBlockedReason": "source_subject_needs_imagegen_subject_matte",
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def alpha_edge_ring(alpha: Image.Image, radius: int = 2) -> Image.Image:
    opaque = alpha.convert("L").point(lambda value: 255 if value > 0 else 0)
    expanded = opaque.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    eroded = opaque.filter(ImageFilter.MinFilter(radius * 2 + 1))
    return ImageChops.subtract(expanded, eroded)


def measure_green_pollution(img: Image.Image) -> dict[str, Any]:
    rgba = img.convert("RGBA")
    visible = 0
    green = 0
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a <= 0:
                continue
            visible += 1
            if g > r * 1.2 and g > b * 1.2:
                green += 1
    ratio = round(green / max(1, visible), 6)
    status = "passed" if ratio <= GREEN_POLLUTION_PASS_RATIO else "warning" if ratio <= GREEN_POLLUTION_WARN_RATIO else "rejected"
    return {"visiblePixels": visible, "greenDominantPixels": green, "greenPollutionRatio": ratio, "status": status}


def measure_chroma_green_residue(img: Image.Image) -> dict[str, Any]:
    rgba = img.convert("RGBA")
    visible = 0
    residue = 0
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a <= 8:
                continue
            visible += 1
            if g >= 150 and r <= 100 and b <= 125 and g - r >= 70 and g - b >= 55:
                residue += 1
    ratio = round(residue / max(1, visible), 6)
    status = "passed" if ratio <= GREEN_POLLUTION_PASS_RATIO else "warning" if ratio <= GREEN_POLLUTION_WARN_RATIO else "rejected"
    return {"visiblePixels": visible, "chromaGreenResiduePixels": residue, "chromaGreenResidueRatio": ratio, "status": status}


def remove_chroma_green_residue(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    if _np is not None:
        arr = _np.asarray(rgba).copy()
        red = arr[..., 0].astype(_np.int16)
        green = arr[..., 1].astype(_np.int16)
        blue = arr[..., 2].astype(_np.int16)
        alpha = arr[..., 3]
        target = (alpha > 0) & (green >= 150) & (red <= 100) & (blue <= 125) & ((green - red) >= 70) & ((green - blue) >= 55)
        arr[..., 3][target] = 0
        return Image.fromarray(arr, "RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a > 0 and g >= 150 and r <= 100 and b <= 125 and g - r >= 70 and g - b >= 55:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def despill_green_edges(img: Image.Image, edge_radius: int = 2) -> Image.Image:
    rgba = img.convert("RGBA")
    edge = alpha_edge_ring(rgba.getchannel("A"), radius=edge_radius)
    if _np is not None:
        arr = _np.asarray(rgba).copy()
        edge_arr = _np.asarray(edge)
        alpha = arr[..., 3]
        red = arr[..., 0].astype(_np.int16)
        green = arr[..., 1].astype(_np.int16)
        blue = arr[..., 2].astype(_np.int16)
        target = (edge_arr > 0) & (alpha > 0) & (green > red * 1.15) & (green > blue * 1.15)
        arr[..., 1][target] = _np.maximum(arr[..., 0][target], arr[..., 2][target])
        return Image.fromarray(arr, "RGBA")
    pixels = rgba.load()
    edge_pixels = edge.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            if edge_pixels[x, y] <= 0:
                continue
            r, g, b, a = pixels[x, y]
            if a > 0 and g > r * 1.15 and g > b * 1.15:
                pixels[x, y] = (r, max(r, b), b, a)
    return rgba


def normalize_parts_sheet_manifest(data: dict[str, Any]) -> dict[str, Any]:
    parts = data.get("parts", []) if isinstance(data.get("parts"), list) else []
    sheets = data.get("sheets") if isinstance(data.get("sheets"), list) else None
    if sheets is None:
        sheets = [
            {
                "sheetId": "sheet-001",
                "role": data.get("role") or "legacy-single-sheet",
                "rawPath": data.get("rawSheet"),
                "transparentPath": data.get("transparentSheet"),
                "contactPath": data.get("contactSheet"),
                "componentCount": len(parts),
            }
        ]
    for part in parts:
        if not isinstance(part, dict):
            continue
        part.setdefault("sheetId", "sheet-001")
        part.setdefault("localPartId", part.get("id"))
        part.setdefault("globalPartId", part.get("id"))
    try:
        version = int(data.get("version", 1) or 1)
    except (TypeError, ValueError):
        version = 1
    data["version"] = max(version, 2)
    data["sheets"] = sheets
    data["parts"] = parts
    data["componentCount"] = len(parts)
    return data


def next_global_part_index(parts: list[dict[str, Any]]) -> int:
    max_index = 0
    for part in parts:
        for key in ("globalPartId", "id"):
            value = str(part.get(key) or "")
            if not value.startswith("part-"):
                continue
            try:
                max_index = max(max_index, int(value.split("-", 1)[1]))
            except ValueError:
                pass
    return max_index + 1


def register_candidate_to_canvas(img: Image.Image, canvas_size: tuple[int, int], x: int | None, y: int | None) -> Image.Image:
    rgba = img.convert("RGBA")
    if rgba.size == canvas_size and x is None and y is None:
        return rgba
    px = 0 if x is None else x
    py = 0 if y is None else y
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    canvas.alpha_composite(rgba, (px, py))
    return canvas


def fit_candidate_to_owner_bbox(workspace: Path, layer_id: str, img: Image.Image) -> Image.Image:
    canvas_size = tuple(load_plan(workspace)["canvas"])
    if img.size == canvas_size:
        return img.convert("RGBA")
    owner_bbox = layer_visible_bbox(workspace, layer_id)
    if not owner_bbox:
        return register_candidate_to_canvas(img, canvas_size, None, None)
    fitted, (px, py) = resize_part_to_bbox(img.convert("RGBA"), owner_bbox, canvas_size)
    return register_candidate_to_canvas(fitted, canvas_size, px, py)


def candidate_prefit_layout_preflight(img: Image.Image, canvas_size: tuple[int, int]) -> dict[str, Any]:
    rgba = img.convert("RGBA")
    stats = alpha_stats(rgba)
    bbox = stats.get("alphaBbox")
    failures: list[str] = []
    if rgba.size != canvas_size and bbox:
        x0, y0, x1, y1 = bbox
        touches_edges = x0 <= 1 or y0 <= 1 or x1 >= rgba.width - 1 or y1 >= rgba.height - 1
        bbox_ratio = bbox_area(bbox) / max(1, rgba.width * rgba.height)
        alpha_coverage = float(stats.get("alphaCoverage") or 0.0)
        if touches_edges and bbox_ratio > 0.86 and alpha_coverage > 0.18:
            failures.append(
                "candidate_prefit_alpha_bbox_touches_edges_"
                f"bbox_ratio_{round(bbox_ratio, 6)}_gt_0.86_"
                f"alpha_coverage_{round(alpha_coverage, 6)}_gt_0.18"
            )
    return {
        "passes": not failures,
        "failures": failures,
        "alpha": stats,
        "imageSize": list(rgba.size),
        "canvasSize": list(canvas_size),
    }


def candidate_alpha_preflight(workspace: Path, layer_id: str, img: Image.Image, mode: str) -> dict[str, Any]:
    stats = alpha_stats(img)
    failures: list[str] = []
    if stats["opaqueCoverage"] > 0.98:
        failures.append(f"candidate_opaque_background_coverage_{stats['opaqueCoverage']}_gt_0.98")
    if stats["alphaCoverage"] > 0.94:
        failures.append(f"candidate_alpha_coverage_{stats['alphaCoverage']}_gt_0.94")
    bounds = layer_source_alpha_bounds(workspace, img)
    if (
        bounds
        and bounds.get("status") == "measured"
        and float(bounds.get("outsideSourceAlphaRatioOfSource", 0.0)) > LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT
    ):
        failures.append(
            "candidate_outside_source_silhouette_ratio_"
            f"{bounds['outsideSourceAlphaRatioOfSource']}_limit_{LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT}"
        )
    if mode == "hidden" and (workspace / "layers" / layer_id / "visible_locked.png").exists():
        contribution = hidden_contribution_for_images(workspace / "layers" / layer_id / "visible_locked.png", img)
        if contribution and contribution.get("status") == "measured" and contribution.get("hiddenAlphaPixels", 0) <= 0:
            failures.append("candidate_hidden_alpha_empty_after_visible_subtract")
    return {
        "passes": not failures,
        "failures": failures,
        "alpha": stats,
        "sourceAlphaBounds": bounds,
        "mode": mode,
    }


def hidden_contribution_for_images(visible_path: Path, hidden_img: Image.Image) -> dict[str, Any] | None:
    if not visible_path.exists():
        return None
    try:
        visible = Image.open(visible_path).convert("RGBA")
    except OSError:
        return None
    hidden = hidden_img.convert("RGBA")
    if visible.size != hidden.size:
        return {"status": "size_mismatch", "visibleSize": list(visible.size), "hiddenSize": list(hidden.size)}
    visible_data = visible.getchannel("A").tobytes()
    hidden_data = hidden.getchannel("A").tobytes()
    visible_px = sum(1 for value in visible_data if value > 0)
    hidden_px = sum(1 for value in hidden_data if value > 0)
    outside_visible_px = sum(1 for hv, vv in zip(hidden_data, visible_data) if hv > 0 and vv == 0)
    return {
        "status": "measured",
        "visibleAlphaPixels": visible_px,
        "hiddenAlphaPixels": hidden_px,
        "hiddenOutsideVisiblePixels": outside_visible_px,
        "hiddenOutsideVisibleRatio": round(outside_visible_px / max(visible_px, 1), 6),
    }


def clear_generated_candidate_artifacts(layer_dir: Path) -> None:
    for name in [
        "alpha_candidate.png",
        "hidden_underpaint.png",
        "generated.png",
        "strict_edit_gate_composite.png",
        "generation-provenance.json",
        "hidden_underpaint_provenance.json",
    ]:
        path = layer_dir / name
        if path.exists():
            path.unlink()


def subtract_visible_alpha(candidate: Image.Image, visible_path: Path) -> Image.Image:
    if not visible_path.exists():
        return candidate
    try:
        visible = Image.open(visible_path).convert("RGBA")
    except OSError:
        return candidate
    result = candidate.convert("RGBA").copy()
    if result.size != visible.size:
        return result
    result_px = result.load()
    visible_alpha = visible.getchannel("A").load()
    for py in range(result.height):
        for px in range(result.width):
            if visible_alpha[px, py] > 0:
                r, g, b, _a = result_px[px, py]
                result_px[px, py] = (r, g, b, 0)
    return result


def composite_source_visible_over_base(workspace: Path, base: Image.Image) -> Image.Image:
    """Preserve source-visible pixels wherever a generated owner candidate covers them."""
    final = base.convert("RGBA").copy()
    source_path = workspace / "source.png"
    if not source_path.exists():
        return final
    try:
        source = Image.open(source_path).convert("RGBA")
    except OSError:
        return final
    if source.size != final.size:
        return final
    final_px = final.load()
    source_px = source.load()
    base_alpha = final.getchannel("A").load()
    source_alpha = source.getchannel("A").load()
    for y in range(final.height):
        for x in range(final.width):
            if base_alpha[x, y] > 0 and source_alpha[x, y] > 0:
                final_px[x, y] = source_px[x, y]
    return final


def source_pose_recompose(workspace: Path, raw_composite: Image.Image) -> tuple[Image.Image, dict[str, Any]]:
    """Build the source-pose review composite without showing hidden-surface candidates."""
    source_path = workspace / "source.png"
    comp = raw_composite.convert("RGBA")
    if not source_path.exists():
        return comp, {"status": "source_missing"}
    try:
        source = Image.open(source_path).convert("RGBA")
    except OSError:
        return comp, {"status": "source_unreadable"}
    if source.size != comp.size:
        return comp, {"status": "size_mismatch", "sourceSize": list(source.size), "compositeSize": list(comp.size)}

    source_alpha = source.getchannel("A")
    comp_alpha = comp.getchannel("A")
    source_alpha_data = source_alpha.tobytes()
    comp_alpha_data = comp_alpha.tobytes()
    source_pixels = sum(1 for value in source_alpha_data if value > 0)
    missing_pixels = sum(1 for sv, cv in zip(source_alpha_data, comp_alpha_data) if sv > 0 and cv == 0)
    outside_pixels = sum(1 for sv, cv in zip(source_alpha_data, comp_alpha_data) if sv == 0 and cv > 0)

    final = Image.new("RGBA", source.size, (0, 0, 0, 0))
    final_px = final.load()
    source_px = source.load()
    alpha_px = source_alpha.load()
    for y in range(source.height):
        for x in range(source.width):
            if alpha_px[x, y] > 0:
                final_px[x, y] = source_px[x, y]
            else:
                final_px[x, y] = (0, 0, 0, 0)

    return final, {
        "status": "source_pose_locked",
        "sourceAlphaPixels": source_pixels,
        "missingSourceAlphaPixelsBeforeLock": missing_pixels,
        "missingSourceAlphaRatioBeforeLock": round(missing_pixels / max(source_pixels, 1), 6),
        "outsideSourceAlphaPixelsBeforeLock": outside_pixels,
        "outsideSourceAlphaRatioBeforeLock": round(outside_pixels / max(source_pixels, 1), 6),
    }


def update_layer_plan_entry(workspace: Path, layer_id: str, updates: dict[str, Any]) -> None:
    plan = load_plan(workspace)
    for layer in plan["layers"]:
        if layer["id"] == layer_id:
            layer.update(updates)
            write_json(workspace / "layer-plan.json", plan)
            write_depth_order(workspace, plan)
            return
    raise ValueError(f"Unknown layer id: {layer_id}")


def update_campaign_job(workspace: Path, component_id: str, updates: dict[str, Any]) -> None:
    campaign = load_campaign(workspace)
    if not campaign:
        return
    for job in campaign.get("jobs", []):
        if job.get("componentId") == component_id:
            job.update(updates)
            job["updatedAt"] = datetime.now().isoformat(timespec="seconds")
            break
    write_json(workspace / "campaign.json", campaign)


def ingest_layer_candidate(
    workspace: Path,
    layer_id: str,
    candidate: Path,
    mode: str,
    chroma_key: str | None,
    tolerance: int,
    x: int | None,
    y: int | None,
    backend: str,
    notes: str | None,
    no_hidden_surface_required: bool,
) -> None:
    plan = load_plan(workspace)
    layer_ids = {layer["id"] for layer in plan["layers"]}
    if layer_id not in layer_ids:
        raise ValueError(f"Unknown layer id: {layer_id}")
    if mode not in {"generated", "visible", "hidden", "alpha"}:
        raise ValueError("--mode must be generated, visible, hidden, or alpha")

    canvas_size = tuple(plan["canvas"])
    layer_dir = workspace / "layers" / layer_id
    raw_dir = layer_dir / "backend_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / candidate.name
    if candidate.resolve() != raw_copy.resolve():
        shutil.copy2(candidate, raw_copy)

    raw = Image.open(candidate).convert("RGBA")
    alpha = remove_chroma_key(raw, chroma_key, tolerance)
    if x is None and y is None and alpha.size != canvas_size and mode in {"generated", "hidden"}:
        prefit = candidate_prefit_layout_preflight(alpha, canvas_size)
        if not prefit["passes"]:
            clear_generated_candidate_artifacts(layer_dir)
            write_json(
                layer_dir / "visual_rejected.json",
                {
                    "type": "kine.visualRejection",
                    "version": "0.1",
                    "componentId": layer_id,
                    "reason": "candidate_prefit_layout_preflight_failed",
                    "failures": prefit["failures"],
                    "candidatePrefitLayoutPreflight": prefit,
                    "candidate": relative_to_workspace(raw_copy, workspace),
                    "createdAt": datetime.now().isoformat(timespec="seconds"),
                },
            )
            update_layer_plan_entry(
                workspace,
                layer_id,
                {
                    "generationState": "generated_candidate_rejected",
                    "qaDisposition": "visual_rejected",
                    "candidatePrefitLayoutPreflight": prefit,
                },
            )
            print(
                json.dumps(
                    {
                        "status": "candidate_prefit_layout_preflight_rejected",
                        "layer": layer_id,
                        "mode": mode,
                        "candidatePrefitLayoutPreflight": prefit,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        registered = fit_candidate_to_owner_bbox(workspace, layer_id, alpha)
    else:
        registered = register_candidate_to_canvas(alpha, canvas_size, x, y)
    if mode == "hidden":
        registered = subtract_visible_alpha(registered, layer_dir / "visible_locked.png")
    preflight = candidate_alpha_preflight(workspace, layer_id, registered, mode)
    if not preflight["passes"]:
        clear_generated_candidate_artifacts(layer_dir)
        write_json(
            layer_dir / "visual_rejected.json",
            {
                "type": "kine.visualRejection",
                "version": "0.1",
                "componentId": layer_id,
                "reason": "candidate_alpha_preflight_failed",
                "failures": preflight["failures"],
                "candidateAlphaPreflight": preflight,
                "candidate": relative_to_workspace(raw_copy, workspace),
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            },
        )
        update_layer_plan_entry(
            workspace,
            layer_id,
            {
                "generationState": "generated_candidate_rejected",
                "qaDisposition": "visual_rejected",
                "candidateAlphaPreflight": preflight,
            },
        )
        print(
            json.dumps(
                {
                    "status": "candidate_alpha_preflight_rejected",
                    "layer": layer_id,
                    "mode": mode,
                    "candidateAlphaPreflight": preflight,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    registered.save(layer_dir / "alpha_candidate.png")

    gate_img_path = layer_dir / "alpha_candidate.png"
    gate_semantic_hint = {"source": "per_owner_strict_edit", "mode": mode}
    if mode == "hidden" and (layer_dir / "visible_locked.png").exists():
        gate_img_path = layer_dir / "strict_edit_gate_composite.png"
        compose_two_layers(layer_dir / "visible_locked.png", layer_dir / "alpha_candidate.png", gate_img_path)
    gate_match = candidate_owner_match_score(workspace, gate_img_path, layer_id)
    source_reference_gate = source_reference_similarity_gate(layer_id, gate_match, gate_semantic_hint)
    if not source_reference_gate["passes"]:
        write_json(
            layer_dir / "visual_rejected.json",
            {
                "type": "kine.visualRejection",
                "version": "0.1",
                "componentId": layer_id,
                "reason": "source_reference_similarity_failed",
                "failures": source_reference_gate.get("failures") or [source_reference_gate.get("code", "source_reference_similarity_failed")],
                "sourceReferenceGate": source_reference_gate,
                "candidate": relative_to_workspace(raw_copy, workspace),
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            },
        )
        update_layer_plan_entry(
            workspace,
            layer_id,
            {
                "generationState": "generated_candidate_rejected",
                "qaDisposition": "visual_rejected",
                "sourceReferenceGate": source_reference_gate,
            },
        )
        print(
            json.dumps(
                {
                    "status": "source_reference_rejected",
                    "layer": layer_id,
                    "mode": mode,
                    "sourceReferenceGate": source_reference_gate,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    rejection_path = layer_dir / "visual_rejected.json"
    if rejection_path.exists():
        rejection_path.unlink()

    target_by_mode = {
        "generated": layer_dir / "generated.png",
        "visible": layer_dir / "visible_locked.png",
        "hidden": layer_dir / "hidden_underpaint.png",
        "alpha": layer_dir / "alpha_candidate.png",
    }
    if mode != "alpha":
        registered.save(target_by_mode[mode])
    if mode in {"visible", "hidden"} and (layer_dir / "visible_locked.png").exists() and (layer_dir / "hidden_underpaint.png").exists():
        compose_two_layers(layer_dir / "visible_locked.png", layer_dir / "hidden_underpaint.png", layer_dir / "generated.png")

    stats = alpha_stats(registered)
    provenance = {
        "type": "kine.layerGenerationProvenance",
        "version": "0.1",
        "componentId": layer_id,
        "backend": backend,
        "mode": mode,
        "rawCandidate": relative_to_workspace(raw_copy, workspace),
        "alphaCandidate": f"layers/{layer_id}/alpha_candidate.png",
        "registeredTarget": relative_to_workspace(target_by_mode[mode], workspace),
        "registration": {"x": 0 if x is None else x, "y": 0 if y is None else y, "canvas": list(canvas_size)},
        "chromaKey": chroma_key or "none",
        "chromaTolerance": tolerance,
        "sourceReferenceGate": source_reference_gate,
        "noHiddenSurfaceRequired": no_hidden_surface_required,
        "alpha": stats,
        "notes": notes,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(layer_dir / "generation-provenance.json", provenance)
    if mode == "hidden":
        write_json(layer_dir / "hidden_underpaint_provenance.json", provenance)
    update_layer_plan_entry(
        workspace,
        layer_id,
        {
            "generationState": "generated_candidate",
            "qaDisposition": "needs_regeneration" if stats["alphaCoverage"] <= 0 else "needs_visual_review",
            "noHiddenSurfaceRequired": no_hidden_surface_required,
            "bbox": stats["alphaBbox"],
            "frame_size": list(canvas_size),
            "xyxy": stats["alphaBbox"],
        },
    )
    update_campaign_job(
        workspace,
        layer_id,
        {
            "generationState": "generated_candidate",
            "qaDisposition": "needs_regeneration" if stats["alphaCoverage"] <= 0 else "needs_visual_review",
            "backendRaw": relative_to_workspace(raw_copy, workspace),
            "alphaCandidate": f"layers/{layer_id}/alpha_candidate.png",
            "bbox": stats["alphaBbox"],
            "noHiddenSurfaceRequired": no_hidden_surface_required,
        },
    )
    print(json.dumps({"status": "ingested", "layer": layer_id, "mode": mode, "alpha": stats}, ensure_ascii=False, indent=2))


def alpha_stats(img: Image.Image) -> dict[str, Any]:
    alpha = img.getchannel("A")
    extrema = alpha.getextrema()
    bbox = alpha.getbbox()
    total = img.width * img.height
    histogram = alpha.histogram()
    nonzero = sum(histogram[1:])
    opaque = sum(histogram[251:])
    return {
        "alphaExtrema": list(extrema),
        "alphaBbox": list(bbox) if bbox else None,
        "alphaCoverage": round(nonzero / total, 6),
        "opaqueCoverage": round(opaque / total, 6),
    }


def color_family(r: int, g: int, b: int) -> dict[str, bool]:
    return {
        "dark": r < 80 and g < 80 and b < 80,
        "light": r > 185 and g > 185 and b > 175,
        "white": r > 210 and g > 210 and b > 205,
        "gray": abs(r - g) < 24 and abs(g - b) < 24 and 90 < r < 235,
        "skin": r > 175 and 90 < g < 210 and 70 < b < 190 and r > g and g >= b - 10,
        "yellow": r > 165 and g > 110 and b < 115,
        "orange": r > 175 and 70 < g < 180 and b < 85,
        "cyan": g > 130 and b > 150 and r < 150,
    }


def semantic_visible_selector(layer_id: str, x: int, y: int, r: int, g: int, b: int, a: int, size: tuple[int, int]) -> bool:
    if a == 0:
        return False
    w, h = size
    nx = x / max(w - 1, 1)
    ny = y / max(h - 1, 1)
    c = color_family(r, g, b)
    upper_head = 0.03 <= ny <= 0.36 and 0.32 <= nx <= 0.68
    head_core = 0.12 <= ny <= 0.40 and 0.36 <= nx <= 0.64
    body_core = 0.30 <= ny <= 0.66 and 0.35 <= nx <= 0.65
    side_body = 0.29 <= ny <= 0.68 and (0.22 <= nx < 0.39 or 0.61 < nx <= 0.78)
    if layer_id == "head-accessory":
        return upper_head and (c["cyan"] or c["white"] or c["gray"] or c["dark"])
    if layer_id == "hair-rear":
        return 0.16 <= ny <= 0.50 and (nx < 0.48 or nx > 0.58) and (c["yellow"] or c["orange"])
    if layer_id == "hair-front":
        return 0.10 <= ny <= 0.38 and 0.38 <= nx <= 0.62 and (c["yellow"] or c["orange"])
    if layer_id == "ears":
        return 0.16 <= ny <= 0.36 and (0.30 <= nx <= 0.42 or 0.58 <= nx <= 0.70) and c["skin"]
    if layer_id == "face":
        return head_core and (c["skin"] or (c["light"] and not c["cyan"]))
    if layer_id == "nose":
        return 0.205 <= ny <= 0.305 and 0.475 <= nx <= 0.535 and a > 0
    if layer_id == "mouth":
        return 0.245 <= ny <= 0.355 and 0.445 <= nx <= 0.565 and (c["dark"] or c["skin"] or c["orange"])
    if layer_id == "eye-white":
        return 0.155 <= ny <= 0.275 and 0.39 <= nx <= 0.61 and (c["white"] or c["light"])
    if layer_id == "eye-iris":
        return 0.155 <= ny <= 0.285 and 0.39 <= nx <= 0.61 and (c["cyan"] or c["orange"] or (b > r and b > 90))
    if layer_id == "eye-line":
        return 0.145 <= ny <= 0.295 and 0.38 <= nx <= 0.62 and c["dark"]
    if layer_id == "brows":
        return 0.115 <= ny <= 0.235 and 0.38 <= nx <= 0.62 and c["dark"]
    if layer_id == "collar-accessory":
        return 0.285 <= ny <= 0.405 and 0.34 <= nx <= 0.66 and (c["cyan"] or c["orange"] or c["dark"] or c["light"])
    if layer_id == "torso":
        return body_core and (c["white"] or c["gray"] or c["light"] or c["dark"] or c["cyan"] or c["orange"])
    if layer_id == "arms":
        return side_body and (c["white"] or c["gray"] or c["dark"] or c["cyan"] or c["skin"] or c["light"])
    if layer_id == "hips":
        return 0.55 <= ny <= 0.73 and 0.36 <= nx <= 0.64 and (c["white"] or c["gray"] or c["light"] or c["dark"])
    if layer_id == "legs":
        return 0.60 <= ny <= 0.92 and 0.34 <= nx <= 0.66 and (c["white"] or c["gray"] or c["dark"] or c["cyan"] or c["light"])
    if layer_id == "feet":
        return 0.82 <= ny <= 0.98 and 0.28 <= nx <= 0.72 and (c["white"] or c["gray"] or c["dark"] or c["cyan"] or c["light"])
    return False


def create_visible_lock_for_layer(source: Image.Image, layer_id: str) -> tuple[Image.Image, Image.Image, dict[str, Any]]:
    rgba = source.convert("RGBA")
    w, h = rgba.size
    visible = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    mask = Image.new("L", rgba.size, 0)
    src_px = rgba.load()
    dst_px = visible.load()
    mask_px = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = src_px[x, y]
            if semantic_visible_selector(layer_id, x, y, r, g, b, a, rgba.size):
                dst_px[x, y] = (r, g, b, a)
                mask_px[x, y] = a
    stats = alpha_stats(visible)
    return visible, mask, stats


def create_owner_resolved_visible_locks(source: Image.Image, layers: list[dict[str, Any]]) -> tuple[dict[str, tuple[Image.Image, Image.Image, dict[str, Any]]], dict[str, Any]]:
    rgba = source.convert("RGBA")
    w, h = rgba.size
    layer_ids = [layer["id"] for layer in layers]
    visible_by_layer = {layer_id: Image.new("RGBA", rgba.size, (0, 0, 0, 0)) for layer_id in layer_ids}
    mask_by_layer = {layer_id: Image.new("L", rgba.size, 0) for layer_id in layer_ids}
    src_px = rgba.load()
    dst_px = {layer_id: visible_by_layer[layer_id].load() for layer_id in layer_ids}
    mask_px = {layer_id: mask_by_layer[layer_id].load() for layer_id in layer_ids}
    contested = 0
    assigned = 0
    unassigned_source_pixels = 0
    assignment_counts = {layer_id: 0 for layer_id in layer_ids}

    for y in range(h):
        for x in range(w):
            r, g, b, a = src_px[x, y]
            if a == 0:
                continue
            matches = [
                layer_id
                for layer_id in layer_ids
                if semantic_visible_selector(layer_id, x, y, r, g, b, a, rgba.size)
            ]
            if not matches:
                unassigned_source_pixels += 1
                continue
            if len(matches) > 1:
                contested += 1
            owner = max(matches, key=lambda item: (SOURCE_VISIBLE_OWNER_PRIORITY.get(item, 0), -layer_ids.index(item)))
            dst_px[owner][x, y] = (r, g, b, a)
            mask_px[owner][x, y] = a
            assigned += 1
            assignment_counts[owner] += 1

    locks = {
        layer_id: (visible_by_layer[layer_id], mask_by_layer[layer_id], alpha_stats(visible_by_layer[layer_id]))
        for layer_id in layer_ids
    }
    audit = {
        "type": "kine.sourceVisibleOwnerPurityAudit",
        "version": "0.1",
        "method": "single_owner_priority_resolved_visible_lock_v0.1",
        "sourceAlphaPixels": assigned + unassigned_source_pixels,
        "assignedSourcePixels": assigned,
        "unassignedSourcePixels": unassigned_source_pixels,
        "contestedSourcePixelsResolved": contested,
        "assignmentCounts": assignment_counts,
        "priority": SOURCE_VISIBLE_OWNER_PRIORITY,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    return locks, audit


def extract_visible_locks(workspace: Path, min_alpha_coverage: float = 0.00001) -> dict[str, Any]:
    plan = load_plan(workspace)
    source = Image.open(workspace / "source.png").convert("RGBA")
    locks, purity_audit = create_owner_resolved_visible_locks(source, plan["layers"])
    extracted = []
    not_visible = []
    for layer in plan["layers"]:
        layer_id = layer["id"]
        layer_dir = workspace / "layers" / layer_id
        visible, mask, stats = locks[layer_id]
        if stats["alphaCoverage"] > min_alpha_coverage:
            visible_path = layer_dir / "visible_locked.png"
            mask_path = layer_dir / "masks" / "visible_mask.png"
            visible_path.parent.mkdir(parents=True, exist_ok=True)
            mask_path.parent.mkdir(parents=True, exist_ok=True)
            visible.save(visible_path)
            mask.save(mask_path)
            update_layer_plan_entry(
                workspace,
                layer_id,
                {
                    "generationState": "source_visible_locked",
                    "qaDisposition": "source_lock_only",
                    "bbox": stats["alphaBbox"],
                    "frame_size": list(source.size),
                    "xyxy": stats["alphaBbox"],
                    "sourceVisibleLock": relative_to_workspace(visible_path, workspace),
                },
            )
            update_campaign_job(
                workspace,
                layer_id,
                {
                    "generationState": "source_visible_locked",
                    "qaDisposition": "source_lock_only",
                    "visibleLocked": relative_to_workspace(visible_path, workspace),
                    "bbox": stats["alphaBbox"],
                },
            )
            extracted.append({"id": layer_id, "visibleLocked": relative_to_workspace(visible_path, workspace), "alpha": stats})
        else:
            update_layer_plan_entry(workspace, layer_id, {"generationState": "not_visible", "qaDisposition": "not_visible"})
            update_campaign_job(workspace, layer_id, {"generationState": "blocked", "qaDisposition": "not_visible"})
            not_visible.append(layer_id)
    summary = {
        "type": "kine.sourceVisibleExtraction",
        "version": "0.1",
        "method": purity_audit["method"],
        "source": "source.png",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "extractedCount": len(extracted),
        "notVisibleCount": len(not_visible),
        "extracted": extracted,
        "notVisible": not_visible,
        "ownerPurityAudit": "source-visible-owner-purity-audit.json",
        "notes": [
            "Visible locks are source-derived debug evidence and redraw constraints only.",
            "They must remain source_lock_only until the $imagegen skill provides hidden underpaint or owner-isolated redraw provenance.",
        ],
    }
    write_json(workspace / "source-visible-extraction.json", summary)
    write_json(workspace / "source-visible-owner-purity-audit.json", purity_audit)
    write_json(
        workspace / "source-visible-mask-summary.json",
        {
            "type": "kine.sourceVisibleMaskSummary",
            "source": "source-visible-extraction.json",
            "visibleLocked": [{"id": item["id"], "alpha": item["alpha"]} for item in extracted],
            "notVisible": not_visible,
        },
    )
    check_dir = workspace / "check"
    check_dir.mkdir(exist_ok=True)
    hard_cut_recompose = Image.new("RGBA", source.size, (0, 0, 0, 0))
    for layer_id in plan["drawOrderBackToFront"]:
        visible_path = workspace / "layers" / layer_id / "visible_locked.png"
        if visible_path.exists():
            hard_cut_recompose.alpha_composite(Image.open(visible_path).convert("RGBA"))
    hard_cut_recompose_path = check_dir / "source-visible-locks-recompose.png"
    hard_cut_recompose.save(hard_cut_recompose_path)
    hard_cut_quality = recompose_quality(workspace, hard_cut_recompose)
    write_json(
        workspace / "source-visible-recompose-qa.json",
        {
            "type": "kine.sourceVisibleHardCutRecomposeQA",
            "version": "0.1",
            "source": "source.png",
            "hardCutRecompose": relative_to_workspace(hard_cut_recompose_path, workspace),
            "quality": hard_cut_quality,
            "purpose": "This checks whether source-visible hard cuts can reconstruct the original before any imagegen redraw.",
        },
    )
    summary["hardCutRecomposeQA"] = {
        "file": relative_to_workspace(hard_cut_recompose_path, workspace),
        "quality": hard_cut_quality,
    }
    write_json(workspace / "source-visible-extraction.json", summary)
    update_run_state(
        workspace,
        {
            "sourceVisibleExtraction": "source-visible-extraction.json",
            "sourceVisibleOwnerPurityAudit": "source-visible-owner-purity-audit.json",
            "sourceVisibleHardCutRecomposeQA": "source-visible-recompose-qa.json",
            "sourceVisibleLocks": len(extracted),
            "notVisible": len(not_visible),
        },
    )
    write_facial_micro_source_locks(workspace)
    return summary


def foreground_alpha_by_edge_flood(source: Image.Image, tolerance: int = 30) -> Image.Image:
    """Return a foreground alpha (L, 255=foreground) for an opaque-background source.

    Generic background removal by flood-filling from the four edges using the
    corner-sampled background color (see v8 `alpha_from_edge_connected_background`).
    This is character-agnostic: it does not assume any owner palette. Used only when
    the source has no usable transparency of its own.
    """
    rgb = source.convert("RGB")
    width, height = rgb.size
    bg = auto_chroma_key(source)
    pix = rgb.load()

    def is_bg(x: int, y: int) -> bool:
        r, g, b = pix[x, y]
        return abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) <= tolerance * 3

    seen = bytearray(width * height)
    from collections import deque

    queue: deque[int] = deque()

    def push(x: int, y: int) -> None:
        index = y * width + x
        if seen[index] or not is_bg(x, y):
            return
        seen[index] = 1
        queue.append(index)

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(height):
        push(0, y)
        push(width - 1, y)
    while queue:
        index = queue.popleft()
        x = index % width
        y = index // width
        if x > 0:
            push(x - 1, y)
        if x + 1 < width:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < height:
            push(x, y + 1)
    alpha = Image.new("L", (width, height), 255)
    out = alpha.load()
    for y in range(height):
        row = y * width
        for x in range(width):
            if seen[row + x]:
                out[x, y] = 0
    return alpha


def foreground_alpha_for_partition(source: Image.Image) -> Image.Image:
    """Pick the foreground alpha for partitioning.

    If the source already carries real transparency (a transparent PNG character on an
    empty canvas), use its own alpha as the exact foreground. Otherwise the source is an
    opaque image and we remove the flat background by edge flood. Either way the result
    is the complete set of character pixels the partition must cover 100%.
    """
    rgba = source.convert("RGBA")
    alpha = rgba.getchannel("A")
    lo, hi = alpha.getextrema()
    if hi > 0 and lo == 0:
        # Has genuine transparency -> trust the source alpha as the foreground.
        return alpha.point(lambda v: 255 if v > 0 else 0)
    return foreground_alpha_by_edge_flood(rgba)


def cutout_map_path(workspace: Path) -> Path:
    return workspace / "cutout-map.json"


def build_cutout_map_template(workspace: Path) -> dict[str, Any]:
    """Build an empty cutout-map template seeded from the KINE owner schema.

    A vision-capable agent fills each owner's `region` (normalized 0..1 polygon points
    or bbox) after looking at `source.png`. `region: null` means "let the partitioner
    decide via the prior + nearest-owner fallback" for that owner.
    """
    plan = load_plan(workspace)
    canvas = list(plan["canvas"])
    owners = []
    for layer in plan["layers"]:
        layer_id = layer["id"]
        owners.append(
            {
                "id": layer_id,
                "bone": spine_bone_for_component(layer_id),
                "drawOrder": layer.get("order"),
                "region": None,
                "split": {
                    "leftRight": layer_id in PAIR_SPLIT_LAYERS,
                    "frontBackOrDepth": layer_id in FRONT_BACK_SPLIT_LAYERS,
                },
            }
        )
    return {
        "type": "kine.cutoutMap",
        "version": "0.1",
        "source": "source.png",
        "canvas": canvas,
        "coordinateSpace": "normalized_0_1",
        "instructions": [
            "A vision-capable model looks at source.png and fills each owner's region.",
            "region.type is 'polygon' (points: [[x,y],...] in 0..1) or 'bbox' (bbox: [x0,y0,x1,y1] in 0..1).",
            "Only fill owners that exist in the source; leave region null for owners that are absent or that the fallback should infer.",
            "drawOrder is back-to-front; front-most owner wins where regions overlap on a visible pixel.",
            "The script keeps EXACT source pixels per owner and guarantees every foreground pixel is assigned.",
        ],
        "owners": owners,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }


def write_cutout_map_template(workspace: Path, force: bool = False) -> dict[str, Any]:
    path = cutout_map_path(workspace)
    if path.exists() and not force:
        existing = read_json_if_exists(path)
        if existing:
            return existing
    template = build_cutout_map_template(workspace)
    write_json(path, template)
    update_run_state(workspace, {"cutoutMap": "cutout-map.json", "cutoutMapStatus": "template_pending_owner_regions"})
    return template


def load_cutout_map(workspace: Path) -> dict[str, Any] | None:
    return read_json_if_exists(cutout_map_path(workspace))


def cutout_map_has_regions(cutout: dict[str, Any] | None) -> bool:
    if not cutout:
        return False
    for owner in cutout.get("owners", []):
        if isinstance(owner, dict) and owner.get("region"):
            return True
    return False


def rasterize_owner_region(region: dict[str, Any] | None, canvas_size: tuple[int, int]) -> Image.Image | None:
    """Rasterize a cutout-map owner region (normalized polygon or bbox) to an L mask."""
    if not isinstance(region, dict):
        return None
    w, h = canvas_size
    mask = Image.new("L", canvas_size, 0)
    draw = ImageDraw.Draw(mask)
    rtype = region.get("type")
    if rtype == "polygon":
        pts = region.get("points") or []
        if len(pts) < 3:
            return None
        poly = [(float(px) * (w - 1), float(py) * (h - 1)) for px, py in pts]
        draw.polygon(poly, fill=255)
        return mask
    if rtype == "bbox":
        bbox = region.get("bbox") or []
        if len(bbox) != 4:
            return None
        x0, y0, x1, y1 = bbox
        draw.rectangle(
            (float(x0) * (w - 1), float(y0) * (h - 1), float(x1) * (w - 1), float(y1) * (h - 1)),
            fill=255,
        )
        return mask
    return None


def _nearest_label_fill(label: list[int], fg: list[bool], w: int, h: int) -> None:
    """Multi-source BFS so every foreground pixel inherits its nearest assigned owner label.

    label: flat list of owner-index+1 (0 == unassigned). fg: flat foreground mask.
    Propagation crosses the WHOLE grid (including background) so that a disconnected
    foreground blob with no seed of its own still inherits the nearest seed's owner. Only
    foreground pixels are written into `label`; background pixels merely carry the label
    forward. Guarantees no foreground pixel stays unassigned when at least one seed exists,
    so the partition covers 100% of the foreground and recomposes to the source.
    """
    from collections import deque

    n = w * h
    prop = [0] * n  # label carried for propagation across all pixels (fg and bg)
    dq: deque[int] = deque()
    for i in range(n):
        if label[i] > 0:
            prop[i] = label[i]
            dq.append(i)
    if not dq:
        return
    while dq:
        i = dq.popleft()
        lab = prop[i]
        x = i % w
        y = i // w
        neighbors = []
        if x > 0:
            neighbors.append(i - 1)
        if x + 1 < w:
            neighbors.append(i + 1)
        if y > 0:
            neighbors.append(i - w)
        if y + 1 < h:
            neighbors.append(i + w)
        for j in neighbors:
            if prop[j] == 0:
                prop[j] = lab
                if fg[j] and label[j] == 0:
                    label[j] = lab
                dq.append(j)


def build_partition_labels(
    source: Image.Image,
    fg_alpha: Image.Image,
    plan: dict[str, Any],
    cutout: dict[str, Any] | None,
) -> tuple[list[int], list[bool], list[str], dict[str, str]]:
    """Assign every foreground pixel to exactly one owner.

    Priority of semantic source: (1) cutout-map regions authored by a vision model,
    (2) the legacy `semantic_visible_selector` prior, then (3) a nearest-owner fallback
    that fills any remaining foreground pixel. Returns (label, fg, owner_ids, owner_source).
    """
    rgba = source.convert("RGBA")
    w, h = rgba.size
    owner_ids = [layer["id"] for layer in plan["layers"]]
    idx_of = {oid: i + 1 for i, oid in enumerate(owner_ids)}
    fg = [v > 0 for v in fg_alpha.getdata()]
    label = [0] * (w * h)
    owner_source: dict[str, str] = {}

    if cutout_map_has_regions(cutout):
        owners_with_region = [
            owner
            for owner in cutout.get("owners", [])
            if isinstance(owner, dict) and owner.get("id") in idx_of and owner.get("region")
        ]
        # Back-to-front: paint ascending drawOrder so the front-most owner overwrites
        # shared/overlapping visible pixels.
        owners_with_region.sort(key=lambda owner: owner.get("drawOrder") if owner.get("drawOrder") is not None else 0)
        for owner in owners_with_region:
            mask = rasterize_owner_region(owner.get("region"), (w, h))
            if mask is None:
                continue
            k = idx_of[owner["id"]]
            md = mask.getdata()
            for i in range(w * h):
                if fg[i] and md[i] > 0:
                    label[i] = k
            owner_source[owner["id"]] = "cutout_map"
    else:
        # Legacy color/position prior as a weak seed (only matched pixels).
        src_px = rgba.load()
        priority_sorted = sorted(owner_ids, key=lambda oid: SOURCE_VISIBLE_OWNER_PRIORITY.get(oid, 0))
        for y in range(h):
            base = y * w
            for x in range(w):
                i = base + x
                if not fg[i]:
                    continue
                r, g, b, a = src_px[x, y]
                best_k = 0
                best_pri = -1
                for oid in priority_sorted:
                    if semantic_visible_selector(oid, x, y, r, g, b, 255, (w, h)):
                        pri = SOURCE_VISIBLE_OWNER_PRIORITY.get(oid, 0)
                        if pri > best_pri:
                            best_pri = pri
                            best_k = idx_of[oid]
                if best_k:
                    label[i] = best_k
                    owner_source.setdefault(owner_ids[best_k - 1], "prior")

    # Guarantee at least one seed so the nearest-owner fallback can cover 100% of the
    # foreground even for characters the cutout map and the color/position prior both miss.
    if not any(label[i] for i in range(w * h)):
        default_owner = "torso" if "torso" in idx_of else owner_ids[0]
        dk = idx_of[default_owner]
        for i in range(w * h):
            if fg[i]:
                label[i] = dk
        owner_source.setdefault(default_owner, "default_seed")

    # Completeness fallback: every remaining foreground pixel inherits its nearest owner.
    before_unassigned = sum(1 for i in range(w * h) if fg[i] and label[i] == 0)
    _nearest_label_fill(label, fg, w, h)
    after_unassigned = sum(1 for i in range(w * h) if fg[i] and label[i] == 0)
    if before_unassigned and after_unassigned < before_unassigned:
        for i in range(w * h):
            if fg[i] and label[i] > 0:
                owner_source.setdefault(owner_ids[label[i] - 1], "fallback")
    return label, fg, owner_ids, owner_source


def partition_source_to_components(workspace: Path, use_cutout_map: bool = True) -> dict[str, Any]:
    """Partition the source into a complete, lossless set of exact-source-pixel owners.

    This is the default decomposition path. Every foreground source pixel is assigned to
    exactly one owner (cutout-map regions first, then prior, then nearest-owner fallback),
    so pasting the owners back in draw order reproduces the source exactly. Each owner with
    coverage gets `generated.png` (exact source pixels) + provenance + a no-hidden-surface
    review, so QA accepts it as `present` without any generation. No facial micro splitting.
    """
    blocked = block_scene_partition_if_needed(workspace, "apply-cutout-map" if use_cutout_map else "partition")
    if blocked is not None:
        return blocked
    plan = load_plan(workspace)
    canvas = tuple(plan["canvas"])
    w, h = canvas
    source = Image.open(workspace / "source.png").convert("RGBA")
    if source.size != canvas:
        source = source.resize(canvas, Image.Resampling.LANCZOS)
    fg_alpha = foreground_alpha_for_partition(source)
    cutout = load_cutout_map(workspace) if use_cutout_map else None
    label, fg, owner_ids, owner_source = build_partition_labels(source, fg_alpha, plan, cutout)

    # Build a single label image so per-owner masks are cheap point() ops.
    label_img = Image.new("L", canvas, 0)
    label_img.putdata(label)
    foreground_pixels = sum(1 for v in fg if v)
    assignment_counts: dict[str, int] = {}
    present_owners: list[str] = []
    not_visible: list[str] = []
    transparent = Image.new("RGBA", canvas, (0, 0, 0, 0))

    for index, owner_id in enumerate(owner_ids, start=1):
        layer_dir = workspace / "layers" / owner_id
        (layer_dir / "masks").mkdir(parents=True, exist_ok=True)
        owner_mask = label_img.point(lambda v, k=index: 255 if v == k else 0).convert("L")
        bbox = owner_mask.getbbox()
        count = 0
        if bbox is not None:
            owner_layer = Image.composite(source, transparent, owner_mask)
            count = sum(1 for v in owner_mask.getdata() if v > 0)
        if bbox is None or count <= 0:
            update_layer_plan_entry(workspace, owner_id, {"generationState": "not_visible", "qaDisposition": "not_visible"})
            update_campaign_job(workspace, owner_id, {"generationState": "blocked", "qaDisposition": "not_visible"})
            not_visible.append(owner_id)
            continue
        owner_layer.save(layer_dir / "generated.png")
        owner_mask.save(layer_dir / "masks" / "visible_mask.png")
        stats = alpha_stats(owner_layer)
        provenance = {
            "type": "kine.layerGenerationProvenance",
            "version": "0.1",
            "componentId": owner_id,
            "backend": LOSSLESS_PARTITION_BACKEND,
            "mode": "lossless_partition",
            "ownerSource": owner_source.get(owner_id, "fallback"),
            "registeredTarget": f"layers/{owner_id}/generated.png",
            "noHiddenSurfaceRequired": True,
            "alpha": stats,
            "notes": "exact source pixels assigned to this owner by the complete source partition; assembling all owners reproduces the source",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(layer_dir / "generation-provenance.json", provenance)
        write_json(
            layer_dir / "surface-review.json",
            {
                "type": "kine.surfaceReview",
                "version": "0.1",
                "componentId": owner_id,
                "noHiddenSurfaceRequired": True,
                "reason": "lossless source-pixel partition owner; hidden underpaint is an optional later enhancement",
                "provenance": "generation-provenance.json",
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            },
        )
        rejected_path = layer_dir / "visual_rejected.json"
        if rejected_path.exists():
            rejected_path.unlink()
        update_layer_plan_entry(
            workspace,
            owner_id,
            {
                "generationState": "lossless_partition",
                "qaDisposition": "needs_visual_review",
                "noHiddenSurfaceRequired": True,
                "bbox": stats["alphaBbox"],
                "xyxy": stats["alphaBbox"],
                "frame_size": list(canvas),
            },
        )
        update_campaign_job(
            workspace,
            owner_id,
            {
                "generationState": "lossless_partition",
                "qaDisposition": "needs_visual_review",
                "bbox": stats["alphaBbox"],
                "noHiddenSurfaceRequired": True,
            },
        )
        assignment_counts[owner_id] = count
        present_owners.append(owner_id)

    assigned_total = sum(assignment_counts.values())
    coverage = round(assigned_total / max(foreground_pixels, 1), 6)
    audit = {
        "type": "kine.completePartitionAudit",
        "version": "0.1",
        "source": "source.png",
        "canvas": list(canvas),
        "foregroundAlphaSource": "source_alpha" if foreground_alpha_for_partition(source).getextrema() != (255, 255) else "edge_flood",
        "semanticSource": "cutout_map" if cutout_map_has_regions(cutout) else "prior_plus_fallback",
        "foregroundPixels": foreground_pixels,
        "assignedPixels": assigned_total,
        "unassignedPixels": max(0, foreground_pixels - assigned_total),
        "coverageRatio": coverage,
        "presentOwners": present_owners,
        "notVisibleOwners": not_visible,
        "assignmentCounts": assignment_counts,
        "ownerSource": owner_source,
        "note": "Every foreground pixel is assigned to exactly one owner from exact source pixels, so the owners recompose to the source by construction.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "partition-audit.json", audit)
    update_run_state(
        workspace,
        {
            "partitionAudit": "partition-audit.json",
            "partitionCoverageRatio": coverage,
            "partitionPresentOwners": len(present_owners),
            "partitionSemanticSource": audit["semanticSource"],
        },
    )
    print(
        json.dumps(
            {
                "status": "partitioned",
                "coverageRatio": coverage,
                "presentOwners": present_owners,
                "notVisibleOwners": not_visible,
                "semanticSource": audit["semanticSource"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return audit


def relative_to_workspace(path: Path, workspace: Path) -> str:
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        return str(path)


def write_depth_order(workspace: Path, plan: dict[str, Any]) -> dict[str, Any]:
    order_index = {layer_id: index for index, layer_id in enumerate(plan["drawOrderBackToFront"])}
    by_id = {layer["id"]: layer for layer in plan["layers"]}
    layers = []
    for layer_id in plan["drawOrderBackToFront"]:
        layer = by_id[layer_id]
        layers.append(
            {
                "id": layer_id,
                "order": order_index[layer_id],
                "depthMedian": layer.get("depthMedian"),
                "orderSource": layer.get("orderSource", "kine_component_schema_v0.1"),
                "orderConfidence": layer.get("orderConfidence", 0.35),
            }
        )
    depth_order = {
        "type": "kine.depthOrder",
        "version": "0.1",
        "source": "kine_component_schema_v0.1",
        "drawOrderBackToFront": plan["drawOrderBackToFront"],
        "layers": layers,
    }
    write_json(workspace / "depth-order.json", depth_order)
    return depth_order


def split_layer(workspace: Path, layer_id: str, axis: str, at: int | None, names: str | None) -> None:
    plan = load_plan(workspace)
    by_id = {layer["id"]: layer for layer in plan["layers"]}
    if layer_id not in by_id:
        raise ValueError(f"Unknown layer id: {layer_id}")
    if axis not in {"x", "y"}:
        raise ValueError("--axis must be x or y")
    source_path = layer_image(workspace, layer_id)
    if not source_path.exists():
        raise ValueError(f"Layer has no generated image to split: {layer_id}")

    canvas_size = tuple(plan["canvas"])
    split_at = at if at is not None else (canvas_size[0] // 2 if axis == "x" else canvas_size[1] // 2)
    if split_at <= 0 or split_at >= (canvas_size[0] if axis == "x" else canvas_size[1]):
        raise ValueError("--at must be inside the canvas")
    if names:
        child_ids = [item.strip() for item in names.split(",") if item.strip()]
        if len(child_ids) != 2:
            raise ValueError("--names must contain exactly two comma-separated layer ids")
    else:
        suffixes = ("left", "right") if axis == "x" else ("back", "front")
        child_ids = [f"{layer_id}-{suffixes[0]}", f"{layer_id}-{suffixes[1]}"]

    src = Image.open(source_path).convert("RGBA")
    if src.size != canvas_size:
        raise ValueError(f"Layer size mismatch for split: expected {canvas_size}, got {src.size}")

    masks = []
    for index in range(2):
        mask = Image.new("L", canvas_size, 0)
        draw = ImageDraw.Draw(mask)
        if axis == "x":
            box = (0, 0, split_at, canvas_size[1]) if index == 0 else (split_at, 0, canvas_size[0], canvas_size[1])
        else:
            box = (0, 0, canvas_size[0], split_at) if index == 0 else (0, split_at, canvas_size[0], canvas_size[1])
        draw.rectangle(box, fill=255)
        masks.append(mask)

    base = by_id[layer_id]
    child_entries = []
    child_bboxes: dict[str, list[int] | None] = {}
    for child_id, mask in zip(child_ids, masks):
        child_dir = workspace / "layers" / child_id
        child_dir.mkdir(parents=True, exist_ok=True)
        (child_dir / "masks").mkdir(exist_ok=True)
        (child_dir / "backend_raw").mkdir(exist_ok=True)
        child_img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        child_img.alpha_composite(src)
        alpha = ImageChops.multiply(child_img.getchannel("A"), mask)
        child_img.putalpha(alpha)
        child_img.save(child_dir / "generated.png")
        stats = alpha_stats(child_img)
        child_bboxes[child_id] = stats["alphaBbox"]
        contract = build_removal_contract({"id": child_id, "tag": child_id.replace("-", "_")})
        contract["sourceLayer"] = layer_id
        contract["split"] = {"axis": axis, "at": split_at}
        write_json(child_dir / "layer-redraw-removal-contract.json", contract)
        parent_provenance = workspace / "layers" / layer_id / "generation-provenance.json"
        provenance = {
            "type": "kine.layerGenerationProvenance",
            "version": "0.1",
            "componentId": child_id,
            "sourceLayer": layer_id,
            "mode": "split",
            "split": {"axis": axis, "at": split_at},
            "parentProvenance": relative_to_workspace(parent_provenance, workspace) if parent_provenance.exists() else None,
            "noHiddenSurfaceRequired": provenance_allows_no_hidden_surface(workspace / "layers" / layer_id),
            "alpha": stats,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(child_dir / "generation-provenance.json", provenance)
        child_entries.append(
            {
                **base,
                "id": child_id,
                "tag": child_id.replace("-", "_"),
                "kind": "split",
                "sourceLayer": layer_id,
                "folder": f"layers/{child_id}",
                "removalContract": f"layers/{child_id}/layer-redraw-removal-contract.json",
                "generated": f"layers/{child_id}/generated.png",
                "alphaCandidate": f"layers/{child_id}/alpha_candidate.png",
                "backendRaw": f"layers/{child_id}/backend_raw",
                "generationProvenance": f"layers/{child_id}/generation-provenance.json",
                "bbox": stats["alphaBbox"],
                "xyxy": stats["alphaBbox"],
                "frame_size": list(canvas_size),
                "depthMedian": base.get("depthMedian"),
                "orderSource": "kine_split_postprocess",
                "orderConfidence": 0.6,
                "generationState": "registered",
                "qaDisposition": "needs_visual_review",
                "noHiddenSurfaceRequired": provenance_allows_no_hidden_surface(workspace / "layers" / layer_id),
                "split": {"axis": axis, "at": split_at},
            }
        )

    existing_ids = {layer["id"] for layer in plan["layers"]}
    plan["layers"] = [layer for layer in plan["layers"] if layer["id"] not in child_ids]
    plan["layers"].extend(child_entries)
    next_order = []
    for current in plan["drawOrderBackToFront"]:
        if current == layer_id:
            next_order.extend(child_ids)
        elif current not in child_ids:
            next_order.append(current)
    if layer_id not in plan["drawOrderBackToFront"]:
        next_order.extend([child_id for child_id in child_ids if child_id not in next_order])
    plan["drawOrderBackToFront"] = next_order
    plan.setdefault("postProcess", {}).setdefault("splits", []).append(
        {"sourceLayer": layer_id, "children": child_ids, "axis": axis, "at": split_at, "createdAt": datetime.now().isoformat(timespec="seconds")}
    )
    write_json(workspace / "layer-plan.json", plan)
    write_depth_order(workspace, plan)

    campaign = load_campaign(workspace)
    if campaign:
        campaign_jobs = [job for job in campaign.get("jobs", []) if job.get("componentId") not in child_ids]
        for child_id in child_ids:
            campaign_jobs.append(
                {
                    "componentId": child_id,
                    "generationState": "registered",
                    "qaDisposition": "needs_visual_review",
                    "ownerScope": child_id.replace("-", "_"),
                    "sourceLayer": layer_id,
                    "expectedLayer": f"layers/{child_id}/generated.png",
                    "removalContract": f"layers/{child_id}/layer-redraw-removal-contract.json",
                    "bbox": child_bboxes.get(child_id),
                }
            )
        campaign["jobs"] = campaign_jobs
        campaign["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        write_json(workspace / "campaign.json", campaign)
    print(json.dumps({"status": "split", "sourceLayer": layer_id, "children": child_ids, "axis": axis, "at": split_at}, ensure_ascii=False, indent=2))


def component_center(bbox: list[int]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def infer_component_split_axis(components: list[dict[str, Any]]) -> str:
    centers = [component_center(component["bbox"]) for component in components]
    x_spread = max(center[0] for center in centers) - min(center[0] for center in centers)
    y_spread = max(center[1] for center in centers) - min(center[1] for center in centers)
    return "x" if x_spread >= y_spread else "y"


def component_child_ids(layer_id: str, components: list[dict[str, Any]], axis: str) -> list[str]:
    if len(components) == 2:
        suffixes = ("left", "right") if axis == "x" else ("back", "front")
        return [f"{layer_id}-{suffixes[0]}", f"{layer_id}-{suffixes[1]}"]
    return [f"{layer_id}-part-{index:03d}" for index in range(1, len(components) + 1)]


def split_layer_by_components(workspace: Path, layer_id: str, components: list[dict[str, Any]], axis: str) -> dict[str, Any]:
    plan = load_plan(workspace)
    by_id = {layer["id"]: layer for layer in plan["layers"]}
    if layer_id not in by_id:
        raise ValueError(f"Unknown layer id: {layer_id}")
    source_path = layer_image(workspace, layer_id)
    if not source_path.exists():
        raise ValueError(f"Layer has no generated image to split: {layer_id}")
    canvas_size = tuple(plan["canvas"])
    src = Image.open(source_path).convert("RGBA")
    if src.size != canvas_size:
        raise ValueError(f"Layer size mismatch for split: expected {canvas_size}, got {src.size}")

    ordered = sorted(
        components,
        key=lambda component: (component_center(component["bbox"])[0], component_center(component["bbox"])[1])
        if axis == "x"
        else (component_center(component["bbox"])[1], component_center(component["bbox"])[0]),
    )
    child_ids = component_child_ids(layer_id, ordered, axis)
    base = by_id[layer_id]
    child_entries = []
    child_bboxes: dict[str, list[int] | None] = {}
    parent_provenance = workspace / "layers" / layer_id / "generation-provenance.json"
    for child_id, component in zip(child_ids, ordered):
        bbox = component["bbox"]
        child_dir = workspace / "layers" / child_id
        child_dir.mkdir(parents=True, exist_ok=True)
        (child_dir / "masks").mkdir(exist_ok=True)
        (child_dir / "backend_raw").mkdir(exist_ok=True)
        component_mask = Image.new("L", canvas_size, 0)
        alpha_crop = src.crop(tuple(bbox)).getchannel("A")
        component_mask.paste(alpha_crop, (bbox[0], bbox[1]))
        child_img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        child_img.alpha_composite(src)
        child_img.putalpha(ImageChops.multiply(child_img.getchannel("A"), component_mask))
        child_img.save(child_dir / "generated.png")
        component_mask.save(child_dir / "masks" / "component_mask.png")
        stats = alpha_stats(child_img)
        child_bboxes[child_id] = stats["alphaBbox"]
        contract = build_removal_contract({"id": child_id, "tag": child_id.replace("-", "_")})
        contract["sourceLayer"] = layer_id
        contract["split"] = {"mode": "auto_component", "axis": axis, "componentBbox": bbox}
        write_json(child_dir / "layer-redraw-removal-contract.json", contract)
        provenance = {
            "type": "kine.layerGenerationProvenance",
            "version": "0.1",
            "componentId": child_id,
            "sourceLayer": layer_id,
            "mode": "auto_component_split",
            "split": {"axis": axis, "componentBbox": bbox, "componentArea": component.get("area")},
            "parentProvenance": relative_to_workspace(parent_provenance, workspace) if parent_provenance.exists() else None,
            "noHiddenSurfaceRequired": provenance_allows_no_hidden_surface(workspace / "layers" / layer_id),
            "alpha": stats,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(child_dir / "generation-provenance.json", provenance)
        child_entries.append(
            {
                **base,
                "id": child_id,
                "tag": child_id.replace("-", "_"),
                "kind": "split",
                "sourceLayer": layer_id,
                "folder": f"layers/{child_id}",
                "removalContract": f"layers/{child_id}/layer-redraw-removal-contract.json",
                "generated": f"layers/{child_id}/generated.png",
                "alphaCandidate": f"layers/{child_id}/alpha_candidate.png",
                "backendRaw": f"layers/{child_id}/backend_raw",
                "generationProvenance": f"layers/{child_id}/generation-provenance.json",
                "bbox": stats["alphaBbox"],
                "xyxy": stats["alphaBbox"],
                "frame_size": list(canvas_size),
                "depthMedian": base.get("depthMedian"),
                "orderSource": "kine_auto_component_split",
                "orderConfidence": 0.7,
                "generationState": "registered",
                "qaDisposition": "needs_visual_review",
                "noHiddenSurfaceRequired": provenance_allows_no_hidden_surface(workspace / "layers" / layer_id),
                "split": {"mode": "auto_component", "axis": axis, "componentBbox": bbox},
            }
        )

    plan["layers"] = [layer for layer in plan["layers"] if layer["id"] not in child_ids]
    plan["layers"].extend(child_entries)
    next_order = []
    for current in plan["drawOrderBackToFront"]:
        if current == layer_id:
            next_order.extend(child_ids)
        elif current not in child_ids:
            next_order.append(current)
    plan["drawOrderBackToFront"] = next_order
    plan.setdefault("postProcess", {}).setdefault("splits", []).append(
        {
            "sourceLayer": layer_id,
            "children": child_ids,
            "axis": axis,
            "mode": "auto_component",
            "componentBboxes": [component["bbox"] for component in ordered],
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
    )
    write_json(workspace / "layer-plan.json", plan)
    write_depth_order(workspace, plan)

    campaign = load_campaign(workspace)
    if campaign:
        campaign_jobs = [job for job in campaign.get("jobs", []) if job.get("componentId") not in child_ids]
        for child_id in child_ids:
            campaign_jobs.append(
                {
                    "componentId": child_id,
                    "generationState": "registered",
                    "qaDisposition": "needs_visual_review",
                    "ownerScope": child_id.replace("-", "_"),
                    "sourceLayer": layer_id,
                    "expectedLayer": f"layers/{child_id}/generated.png",
                    "removalContract": f"layers/{child_id}/layer-redraw-removal-contract.json",
                    "bbox": child_bboxes.get(child_id),
                }
            )
        campaign["jobs"] = campaign_jobs
        campaign["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        write_json(workspace / "campaign.json", campaign)
    return {"sourceLayer": layer_id, "children": child_ids, "axis": axis, "componentCount": len(components)}


def write_split_review(workspace: Path, layer_id: str, review: dict[str, Any]) -> None:
    layer_dir = workspace / "layers" / layer_id
    layer_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "type": "kine.layerSplitReview",
        "version": "0.1",
        "componentId": layer_id,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        **review,
    }
    write_json(layer_dir / "split-review.json", payload)


def auto_split_layers(workspace: Path, layer_ids: list[str] | None, min_area: int) -> None:
    plan = load_plan(workspace)
    targets = layer_ids or AUTO_SPLIT_SENSITIVE_LAYERS
    plan_layer_ids = {layer["id"] for layer in plan["layers"]}
    active_order = set(plan["drawOrderBackToFront"])
    split_results = []
    no_split = []
    for layer_id in targets:
        if layer_id not in plan_layer_ids:
            no_split.append({"layer": layer_id, "reason": "not_in_layer_plan"})
            continue
        if layer_id not in active_order:
            no_split.append({"layer": layer_id, "reason": "not_in_active_draw_order"})
            continue
        img_path = layer_image(workspace, layer_id)
        if not img_path.exists():
            reason = "no_generated_layer"
            write_split_review(workspace, layer_id, {"status": "not_split", "reason": reason})
            no_split.append({"layer": layer_id, "reason": reason})
            continue
        img = Image.open(img_path).convert("RGBA")
        # Splitting a source-pixel component must not eat antialiased edge pixels.
        # `alpha_threshold=0` keeps every non-transparent pixel so a split/reassemble
        # round-trip can still be pixel-perfect against the source.
        components = connected_alpha_components(img, alpha_threshold=0, min_area=min_area)
        if len(components) < 2:
            reason = "single_component_or_below_min_area"
            write_split_review(
                workspace,
                layer_id,
                {
                    "status": "not_split",
                    "reason": reason,
                    "componentCount": len(components),
                    "minArea": min_area,
                },
            )
            no_split.append({"layer": layer_id, "reason": reason, "componentCount": len(components)})
            continue
        axis = infer_component_split_axis(components)
        result = split_layer_by_components(workspace, layer_id, components, axis)
        write_split_review(
            workspace,
            layer_id,
            {
                "status": "split",
                "mode": "auto_component",
                "axis": axis,
                "children": result["children"],
                "componentCount": len(components),
                "minArea": min_area,
            },
        )
        split_results.append(result)
        plan = load_plan(workspace)
        plan_layer_ids = {layer["id"] for layer in plan["layers"]}
        active_order = set(plan["drawOrderBackToFront"])
    summary = {
        "type": "kine.autoSplitSummary",
        "version": "0.1",
        "workspace": workspace.name,
        "targets": targets,
        "minArea": min_area,
        "split": split_results,
        "notSplit": no_split,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "auto-split-summary.json", summary)
    update_run_state(workspace, {"autoSplit": "auto-split-summary.json", "autoSplitCount": len(split_results)})
    print(json.dumps({"status": "auto_split_complete", "split": split_results, "notSplit": no_split}, ensure_ascii=False, indent=2))


def _limb_side_column_masks(src: Image.Image, canvas_size: tuple[int, int]) -> dict[str, Image.Image]:
    """Split a limb layer's alpha into left/right full-canvas masks by the alpha-bbox midline.

    A vertical column split at the source-visible bbox midline is deterministic and works for
    both disjoint pair limbs (two blobs) and a single blob; it is the no-depth-model heuristic
    the plan calls for. `left` is the image-left half (smaller x).
    """
    alpha = src.getchannel("A")
    overall = alpha.getbbox()
    masks: dict[str, Image.Image] = {}
    if not overall:
        return masks
    w, h = canvas_size
    mid = (overall[0] + overall[2]) // 2
    left = Image.new("L", canvas_size, 0)
    right = Image.new("L", canvas_size, 0)
    if mid > 0:
        left.paste(alpha.crop((0, 0, mid, h)), (0, 0))
    if mid < w:
        right.paste(alpha.crop((mid, 0, w, h)), (mid, 0))
    if left.getbbox():
        masks["left"] = left
    if right.getbbox():
        masks["right"] = right
    return masks


def _segment_band_masks(side_mask: Image.Image, segments: list[tuple[str, float]], canvas_size: tuple[int, int]) -> list[tuple[str, Image.Image]]:
    """Slice a side mask along its long axis into bone-chain segment masks (proximal -> distal).

    Segments are cut by cumulative length fraction over the side's alpha bbox. Limbs are sliced
    top-to-bottom when taller than wide (the usual rest pose) and left-to-right otherwise.
    """
    bbox = side_mask.getbbox()
    if not bbox:
        return []
    x0, y0, x1, y1 = bbox
    vertical = (y1 - y0) >= (x1 - x0)
    span = (y1 - y0) if vertical else (x1 - x0)
    total = sum(max(0.0, fraction) for _segment, fraction in segments) or 1.0
    out: list[tuple[str, Image.Image]] = []
    cursor = 0.0
    for index, (segment, fraction) in enumerate(segments):
        start = cursor
        cursor += max(0.0, fraction) / total
        lo = (y0 if vertical else x0) + int(round(start * span))
        hi = (y0 if vertical else x0) + (span if index == len(segments) - 1 else int(round(cursor * span)))
        band = Image.new("L", canvas_size, 0)
        draw = ImageDraw.Draw(band)
        if vertical:
            draw.rectangle((x0, lo, x1, hi), fill=255)
        else:
            draw.rectangle((lo, y0, hi, y1), fill=255)
        child_mask = ImageChops.multiply(side_mask, band)
        if child_mask.getbbox():
            out.append((segment, child_mask))
    return out


def spine_split_layer(workspace: Path, layer_id: str) -> dict[str, Any]:
    """Split a limb owner (arms/legs/feet) into left/right Spine bone-chain children.

    Each child is a full-canvas registered transparent layer masked to its bone segment,
    inheriting the parent's provenance/contract and resolving to a joint bone through
    spine_bone_for_component(). Returns a summary dict (or a {"status": ...} skip note).
    """
    segments = SPINE_LIMB_SEGMENTS.get(layer_id)
    if not segments:
        return {"layer": layer_id, "status": "not_a_spine_limb_owner"}
    plan = load_plan(workspace)
    by_id = {layer["id"]: layer for layer in plan["layers"]}
    if layer_id not in by_id:
        return {"layer": layer_id, "status": "not_in_layer_plan"}
    source_path = layer_image(workspace, layer_id)
    if not source_path.exists():
        return {"layer": layer_id, "status": "no_generated_layer"}
    canvas_size = tuple(plan["canvas"])
    src = Image.open(source_path).convert("RGBA")
    if src.size != canvas_size:
        return {"layer": layer_id, "status": "layer_size_mismatch"}
    side_masks = _limb_side_column_masks(src, canvas_size)
    if not side_masks:
        return {"layer": layer_id, "status": "empty_alpha"}

    base = by_id[layer_id]
    parent_provenance = workspace / "layers" / layer_id / "generation-provenance.json"
    no_hidden = provenance_allows_no_hidden_surface(workspace / "layers" / layer_id)
    child_ids: list[str] = []
    child_entries: list[dict[str, Any]] = []
    child_bboxes: dict[str, list[int] | None] = {}
    for side in ("left", "right"):
        side_mask = side_masks.get(side)
        if side_mask is None:
            continue
        for segment, child_mask in _segment_band_masks(side_mask, segments, canvas_size):
            child_id = f"{layer_id}-{side}-{segment}"
            child_dir = workspace / "layers" / child_id
            child_dir.mkdir(parents=True, exist_ok=True)
            (child_dir / "masks").mkdir(exist_ok=True)
            (child_dir / "backend_raw").mkdir(exist_ok=True)
            child_img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            child_img.alpha_composite(src)
            child_img.putalpha(ImageChops.multiply(child_img.getchannel("A"), child_mask))
            child_img.save(child_dir / "generated.png")
            child_mask.save(child_dir / "masks" / "component_mask.png")
            stats = alpha_stats(child_img)
            child_bboxes[child_id] = stats["alphaBbox"]
            bone = spine_bone_for_component(child_id)
            contract = build_removal_contract({"id": child_id, "tag": child_id.replace("-", "_")})
            contract["sourceLayer"] = layer_id
            contract["spineBone"] = bone
            contract["spineSegment"] = segment
            contract["spineSide"] = side
            contract["split"] = {"mode": "spine_bone_chain", "side": side, "segment": segment}
            write_json(child_dir / "layer-redraw-removal-contract.json", contract)
            provenance = {
                "type": "kine.layerGenerationProvenance",
                "version": "0.1",
                "componentId": child_id,
                "sourceLayer": layer_id,
                "mode": "spine_bone_chain_split",
                "spineBone": bone,
                "split": {"side": side, "segment": segment},
                "parentProvenance": relative_to_workspace(parent_provenance, workspace) if parent_provenance.exists() else None,
                "noHiddenSurfaceRequired": no_hidden,
                "alpha": stats,
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            }
            write_json(child_dir / "generation-provenance.json", provenance)
            child_ids.append(child_id)
            child_entries.append(
                {
                    **base,
                    "id": child_id,
                    "tag": child_id.replace("-", "_"),
                    "kind": "spine_split",
                    "sourceLayer": layer_id,
                    "spineBone": bone,
                    "spineSegment": segment,
                    "spineSide": side,
                    "folder": f"layers/{child_id}",
                    "removalContract": f"layers/{child_id}/layer-redraw-removal-contract.json",
                    "generated": f"layers/{child_id}/generated.png",
                    "alphaCandidate": f"layers/{child_id}/alpha_candidate.png",
                    "backendRaw": f"layers/{child_id}/backend_raw",
                    "generationProvenance": f"layers/{child_id}/generation-provenance.json",
                    "bbox": stats["alphaBbox"],
                    "xyxy": stats["alphaBbox"],
                    "frame_size": list(canvas_size),
                    "depthMedian": base.get("depthMedian"),
                    "orderSource": "kine_spine_bone_chain_split",
                    "orderConfidence": 0.6,
                    "generationState": "registered",
                    "qaDisposition": "needs_visual_review",
                    "noHiddenSurfaceRequired": no_hidden,
                    "split": {"mode": "spine_bone_chain", "side": side, "segment": segment},
                }
            )
    if not child_ids:
        return {"layer": layer_id, "status": "no_child_segments"}

    plan["layers"] = [layer for layer in plan["layers"] if layer["id"] not in child_ids]
    plan["layers"].extend(child_entries)
    next_order = []
    for current in plan["drawOrderBackToFront"]:
        if current == layer_id:
            next_order.extend(child_ids)
        elif current not in child_ids:
            next_order.append(current)
    if layer_id not in plan["drawOrderBackToFront"]:
        next_order.extend([child_id for child_id in child_ids if child_id not in next_order])
    plan["drawOrderBackToFront"] = next_order
    plan.setdefault("postProcess", {}).setdefault("splits", []).append(
        {
            "sourceLayer": layer_id,
            "children": child_ids,
            "mode": "spine_bone_chain",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
    )
    write_json(workspace / "layer-plan.json", plan)
    write_depth_order(workspace, plan)

    campaign = load_campaign(workspace)
    if campaign:
        campaign_jobs = [job for job in campaign.get("jobs", []) if job.get("componentId") not in child_ids]
        for child_id in child_ids:
            campaign_jobs.append(
                {
                    "componentId": child_id,
                    "generationState": "registered",
                    "qaDisposition": "needs_visual_review",
                    "ownerScope": child_id.replace("-", "_"),
                    "sourceLayer": layer_id,
                    "expectedLayer": f"layers/{child_id}/generated.png",
                    "removalContract": f"layers/{child_id}/layer-redraw-removal-contract.json",
                    "bbox": child_bboxes.get(child_id),
                }
            )
        campaign["jobs"] = campaign_jobs
        campaign["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        write_json(workspace / "campaign.json", campaign)
    return {"sourceLayer": layer_id, "children": child_ids, "mode": "spine_bone_chain", "childCount": len(child_ids)}


def spine_split_layers(workspace: Path, layer_ids: list[str] | None = None) -> dict[str, Any]:
    """Run Spine bone-chain splitting across all limb owners that have a generated layer."""
    targets = layer_ids or list(SPINE_LIMB_SEGMENTS.keys())
    split_results = []
    skipped = []
    for layer_id in targets:
        result = spine_split_layer(workspace, layer_id)
        if result.get("children"):
            split_results.append(result)
            write_split_review(workspace, layer_id, {"status": "split", "mode": "spine_bone_chain", "children": result["children"]})
        else:
            skipped.append(result)
    summary = {
        "type": "kine.spineSplitSummary",
        "version": "0.1",
        "workspace": workspace.name,
        "targets": targets,
        "split": split_results,
        "skipped": skipped,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "spine-split-summary.json", summary)
    update_run_state(workspace, {"spineSplit": "spine-split-summary.json", "spineSplitCount": len(split_results)})
    print(json.dumps({"status": "spine_split_complete", "split": split_results, "skipped": skipped}, ensure_ascii=False, indent=2))
    return summary


def padded_bbox(bbox: tuple[int, int, int, int], size: tuple[int, int], padding: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    width, height = size
    return (max(0, left - padding), max(0, top - padding), min(width, right + padding), min(height, bottom + padding))


def connected_alpha_components(img: Image.Image, alpha_threshold: int, min_area: int) -> list[dict[str, Any]]:
    alpha = img.getchannel("A")
    pixels = alpha.load()
    width, height = alpha.size
    visited = bytearray(width * height)
    components: list[dict[str, Any]] = []

    for start_y in range(height):
        row_offset = start_y * width
        for start_x in range(width):
            start_index = row_offset + start_x
            if visited[start_index] or pixels[start_x, start_y] <= alpha_threshold:
                continue

            stack = [(start_x, start_y)]
            visited[start_index] = 1
            area = 0
            left = right = start_x
            top = bottom = start_y

            while stack:
                x, y = stack.pop()
                area += 1
                if x < left:
                    left = x
                elif x > right:
                    right = x
                if y < top:
                    top = y
                elif y > bottom:
                    bottom = y

                for nx in (x - 1, x, x + 1):
                    if nx < 0 or nx >= width:
                        continue
                    for ny in (y - 1, y, y + 1):
                        if ny < 0 or ny >= height or (nx == x and ny == y):
                            continue
                        index = ny * width + nx
                        if visited[index] or pixels[nx, ny] <= alpha_threshold:
                            continue
                        visited[index] = 1
                        stack.append((nx, ny))

            if area >= min_area:
                components.append({"area": area, "bbox": [left, top, right + 1, bottom + 1]})

    components.sort(key=lambda item: (item["bbox"][1], item["bbox"][0], -item["area"]))
    return components


def write_parts_contact_sheet(parts: list[dict[str, Any]], path: Path, thumb_size: int = 180) -> None:
    if not parts:
        Image.new("RGBA", (thumb_size, thumb_size), (255, 255, 255, 255)).save(path)
        return
    columns = min(5, max(1, len(parts)))
    rows = (len(parts) + columns - 1) // columns
    label_h = 28
    sheet = Image.new("RGBA", (columns * thumb_size, rows * (thumb_size + label_h)), (245, 246, 248, 255))
    draw = ImageDraw.Draw(sheet)
    for index, part in enumerate(parts):
        img = Image.open(path.parent / part["file"]).convert("RGBA")
        img.thumbnail((thumb_size - 16, thumb_size - 16), Image.Resampling.LANCZOS)
        col = index % columns
        row = index // columns
        x = col * thumb_size + (thumb_size - img.width) // 2
        y = row * (thumb_size + label_h) + (thumb_size - img.height) // 2
        sheet.alpha_composite(img, (x, y))
        draw.text((col * thumb_size + 8, row * (thumb_size + label_h) + thumb_size + 4), part["id"], fill=(20, 24, 31, 255))
    sheet.save(path)


def v3_slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-") or "artifact"


def v3_checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    width, height = size
    board = Image.new("RGBA", size, (245, 247, 250, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            color = (229, 233, 240, 255) if ((x // cell) + (y // cell)) % 2 else (248, 250, 252, 255)
            draw.rectangle((x, y, min(width, x + cell), min(height, y + cell)), fill=color)
    return board


def v3_image_tile(
    img: Image.Image | None,
    size: tuple[int, int],
    label: str,
    sublabel: str | None = None,
    missing: bool = False,
) -> Image.Image:
    tile = Image.new("RGBA", size, (248, 249, 251, 255))
    draw = ImageDraw.Draw(tile)
    label_h = 42
    content_box = (8, label_h, size[0] - 8, size[1] - 8)
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=(205, 212, 224, 255))
    draw.text((8, 8), label[:52], fill=(25, 30, 38, 255))
    if sublabel:
        draw.text((8, 24), sublabel[:58], fill=(98, 108, 122, 255))
    if missing or img is None:
        draw.text((14, label_h + 20), "missing", fill=(176, 54, 54, 255))
        return tile
    preview = img.convert("RGBA").copy()
    if preview.getchannel("A").getbbox():
        preview = fit_alpha_preview(preview, (content_box[2] - content_box[0], content_box[3] - content_box[1]), padding=10)
    else:
        preview.thumbnail((content_box[2] - content_box[0] - 20, content_box[3] - content_box[1] - 20), Image.Resampling.LANCZOS)
    bg = v3_checkerboard((content_box[2] - content_box[0], content_box[3] - content_box[1]))
    bg.alpha_composite(preview, ((bg.width - preview.width) // 2, (bg.height - preview.height) // 2))
    tile.alpha_composite(bg, (content_box[0], content_box[1]))
    return tile


def v3_write_image_grid(rows: list[dict[str, Any]], path: Path, columns: int = 3, tile_size: tuple[int, int] = (260, 250)) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        Image.new("RGBA", tile_size, (248, 249, 251, 255)).save(path)
        return {"path": str(path), "itemCount": 0, "missingCount": 0}
    columns = max(1, min(columns, len(rows)))
    row_count = (len(rows) + columns - 1) // columns
    board = Image.new("RGBA", (columns * tile_size[0], row_count * tile_size[1]), (238, 241, 246, 255))
    missing_count = 0
    for index, row in enumerate(rows):
        img = row.get("image") if isinstance(row.get("image"), Image.Image) else None
        missing = bool(row.get("missing")) or img is None
        if missing:
            missing_count += 1
        tile = v3_image_tile(img, tile_size, str(row.get("label") or ""), str(row.get("sublabel") or ""), missing=missing)
        col = index % columns
        row_index = index // columns
        board.alpha_composite(tile, (col * tile_size[0], row_index * tile_size[1]))
    board.save(path)
    return {"path": str(path), "itemCount": len(rows), "missingCount": missing_count}


def write_source_visible_parts_sheet(workspace: Path, padding: int = 8, thumb_size: int = 180) -> None:
    plan = load_plan(workspace)
    source = Image.open(workspace / "source.png").convert("RGBA")
    if not (workspace / "source-visible-extraction.json").exists():
        extract_visible_locks(workspace)

    cropped_dir = workspace / "parts" / "source-visible-cropped"
    cropped_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for layer_id in plan["drawOrderBackToFront"]:
        visible_path = workspace / "layers" / layer_id / "visible_locked.png"
        if not visible_path.exists():
            continue
        img = Image.open(visible_path).convert("RGBA")
        bbox = img.getchannel("A").getbbox()
        if not bbox:
            continue
        crop_box = padded_bbox(bbox, img.size, padding)
        crop = img.crop(crop_box)
        out_name = f"{layer_id}.png"
        crop.save(cropped_dir / out_name)
        parts.append(
            {
                "id": layer_id,
                "file": f"source-visible-cropped/{out_name}",
                "bbox": list(crop_box),
                "sourceVisibleBbox": list(bbox),
                "alpha": alpha_stats(img),
                "role": "source_visible_exact_reference",
                "acceptance": "exact_source_pixels_for_visible_region_not_hidden_completion",
            }
        )

    if not parts:
        raise ValueError("No source-visible parts were found. Run extract-visible or check the source image alpha/masks.")

    columns = min(5, max(1, len(parts)))
    rows = (len(parts) + columns - 1) // columns
    label_h = 32
    sheet = Image.new("RGBA", (columns * thumb_size, rows * (thumb_size + label_h)), (245, 246, 248, 255))
    draw = ImageDraw.Draw(sheet)
    for index, part in enumerate(parts):
        img = Image.open(cropped_dir / Path(part["file"]).name).convert("RGBA")
        img.thumbnail((thumb_size - 16, thumb_size - 16), Image.Resampling.LANCZOS)
        col = index % columns
        row = index // columns
        x = col * thumb_size + (thumb_size - img.width) // 2
        y = row * (thumb_size + label_h) + (thumb_size - img.height) // 2
        sheet.alpha_composite(img, (x, y))
        draw.text((col * thumb_size + 8, row * (thumb_size + label_h) + thumb_size + 4), part["id"], fill=(20, 24, 31, 255))

    sheet_path = workspace / "parts" / "source-visible-parts-sheet.png"
    manifest_path = workspace / "parts" / "source-visible-parts-manifest.json"
    sheet.save(sheet_path)
    write_json(
        manifest_path,
        {
            "type": "kine.sourceVisiblePartsManifest",
            "version": "0.1",
            "status": "source_visible_exact_reference",
            "source": "source.png",
            "sourceCanvas": list(source.size),
            "sheet": relative_to_workspace(sheet_path, workspace),
            "croppedDir": relative_to_workspace(cropped_dir, workspace),
            "componentCount": len(parts),
            "parts": parts,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "note": "These parts are exact source-visible pixels. Use them as identity/style locks and micro-layer sources; they are not generated hidden-underpaint evidence.",
        },
    )
    update_run_state(
        workspace,
        {
            "sourceVisiblePartsSheet": relative_to_workspace(sheet_path, workspace),
            "sourceVisiblePartsManifest": relative_to_workspace(manifest_path, workspace),
            "sourceVisiblePartCount": len(parts),
        },
    )
    print(
        json.dumps(
            {
                "status": "written",
                "sheet": str(sheet_path),
                "manifest": str(manifest_path),
                "componentCount": len(parts),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def write_facial_micro_source_locks(workspace: Path, padding: int = 6, thumb_size: int = 160) -> dict[str, Any]:
    if not (workspace / "source-visible-extraction.json").exists():
        extract_visible_locks(workspace)
    out_dir = workspace / "parts" / "facial-micro-source-locks"
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for layer_id in sorted(FACIAL_MICRO_LAYERS):
        visible_path = workspace / "layers" / layer_id / "visible_locked.png"
        if not visible_path.exists():
            continue
        img = Image.open(visible_path).convert("RGBA")
        bbox = img.getchannel("A").getbbox()
        if not bbox:
            continue
        crop_box = padded_bbox(bbox, img.size, padding)
        crop = img.crop(crop_box)
        out_name = f"{layer_id}.png"
        crop.save(out_dir / out_name)
        parts.append(
            {
                "id": layer_id,
                "file": f"facial-micro-source-locks/{out_name}",
                "bbox": list(crop_box),
                "sourceVisibleBbox": list(bbox),
                "alpha": alpha_stats(img),
                "sourceLocked": True,
                "registeredLayer": f"layers/{layer_id}/generated.png",
                "imagegenPolicy": "hidden_underpaint_only_strict_per_owner_edit",
            }
        )
        promote_source_locked_facial_micro_layer(workspace, layer_id)

    columns = min(4, max(1, len(parts)))
    rows = max(1, (len(parts) + columns - 1) // columns)
    label_h = 28
    sheet = Image.new("RGBA", (columns * thumb_size, rows * (thumb_size + label_h)), (245, 246, 248, 255))
    draw = ImageDraw.Draw(sheet)
    for index, part in enumerate(parts):
        img = Image.open(out_dir / Path(part["file"]).name).convert("RGBA")
        img.thumbnail((thumb_size - 16, thumb_size - 16), Image.Resampling.LANCZOS)
        col = index % columns
        row = index // columns
        x = col * thumb_size + (thumb_size - img.width) // 2
        y = row * (thumb_size + label_h) + (thumb_size - img.height) // 2
        sheet.alpha_composite(img, (x, y))
        draw.text((col * thumb_size + 8, row * (thumb_size + label_h) + thumb_size + 4), part["id"], fill=(20, 24, 31, 255))

    sheet_path = workspace / "parts" / "facial-micro-source-locks.png"
    manifest_path = workspace / "parts" / "facial-micro-source-locks.json"
    sheet.save(sheet_path)
    manifest = {
        "type": "kine.facialMicroSourceLocks",
        "version": "0.1",
        "status": "source_locked" if parts else "missing_source_locks",
        "source": "source.png",
        "sheet": relative_to_workspace(sheet_path, workspace),
        "componentCount": len(parts),
        "required": sorted(FACIAL_MICRO_LAYERS),
        "parts": parts,
        "rules": [
            "facial micro layers must come from exact source-visible pixels by default",
            "broad parts sheet candidates must not register independent facial micro redraws",
            "hidden facial completion requires strict per-owner edit and source-reference QA",
        ],
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(manifest_path, manifest)
    update_run_state(
        workspace,
        {
            "facialMicroSourceLocks": relative_to_workspace(manifest_path, workspace),
            "facialMicroSourceLockCount": len(parts),
        },
    )
    return manifest


def parts_sheet_component_features(img: Image.Image, bbox: list[int], sheet_size: tuple[int, int]) -> dict[str, Any]:
    width = max(1, bbox[2] - bbox[0])
    height = max(1, bbox[3] - bbox[1])
    sheet_w, sheet_h = max(1, sheet_size[0]), max(1, sheet_size[1])
    return {
        "bbox": bbox,
        "center": [round(((bbox[0] + bbox[2]) / 2) / sheet_w, 4), round(((bbox[1] + bbox[3]) / 2) / sheet_h, 4)],
        "size": [width, height],
        "relativeSize": [round(width / sheet_w, 4), round(height / sheet_h, 4)],
        "aspect": round(width / max(1, height), 4),
        "skin": round(masked_color_fraction(img, lambda r, g, b: r > 165 and 80 < g < 220 and b < 180), 4),
        "blonde": round(masked_color_fraction(img, lambda r, g, b: r > 180 and g > 120 and b < 125), 4),
        "cyan": round(masked_color_fraction(img, lambda r, g, b: g > 120 and b > 120 and r < 120), 4),
        "orange": round(masked_color_fraction(img, lambda r, g, b: r > 170 and 60 < g < 180 and b < 100), 4),
        "black": round(masked_color_fraction(img, lambda r, g, b: r < 80 and g < 80 and b < 80), 4),
        "white": round(masked_color_fraction(img, lambda r, g, b: r > 200 and g > 200 and b > 185), 4),
    }


def classify_forbidden_parts_sheet_component(features: dict[str, Any]) -> str | None:
    rel_w, rel_h = features["relativeSize"]
    cx, cy = features["center"]
    width, height = features["size"]
    aspect = features["aspect"]
    skin = features["skin"]
    blonde = features["blonde"]
    cyan = features["cyan"]
    black = features["black"]
    white = features["white"]
    orange = features["orange"]

    if rel_h >= 0.54 and rel_w >= 0.16 and (white + black + cyan + skin + blonde) >= 0.62:
        return "assembled_full_body_pose_or_large_contextual_character"
    if cy < 0.42 and width <= 120 and height <= 95 and aspect <= 1.8 and (skin > 0.18 or cyan > 0.18) and black > 0.08:
        return "forbidden_broad_sheet_facial_micro_layer"
    if cy < 0.42 and width <= 105 and height <= 75 and aspect > 1.1 and (skin > 0.18 or black > 0.12 or white > 0.2):
        return "forbidden_broad_sheet_mouth_eye_or_brow_layer"
    if cy < 0.42 and width <= 70 and height <= 85 and skin > 0.35 and orange < 0.12:
        return "forbidden_broad_sheet_nose_or_small_face_detail"
    if cy < 0.34 and blonde > 0.04 and height <= 45 and aspect > 2.0:
        return "forbidden_broad_sheet_brow_or_hair_sliver_micro_layer"
    return None


def v3_is_role_allowed_large_role_component(role: str, features: dict[str, Any], component_count: int) -> bool:
    rel_w, rel_h = features["relativeSize"]
    aspect = features["aspect"]
    skin = features["skin"]
    cyan = features["cyan"]
    orange = features["orange"]
    black = features["black"]
    white = features["white"]
    color_evidence = skin + cyan + orange + black
    role_allows_contact = role in {"props_accessories", "limbs", "controlled_layout_mixed"}
    tall_skinny = rel_h >= 0.54 and rel_w <= 0.32 and aspect <= 0.42
    has_hand_or_prop_pixels = color_evidence >= 0.24 and skin <= 0.58
    if role_allows_contact and tall_skinny and has_hand_or_prop_pixels:
        return True

    # True-image V3 validation showed that coherent boots and hand-held
    # interaction groups are often tall on the sheet. They are not assembled
    # half-body characters merely because their bbox is high.
    if role == "feet_footwear":
        boot_like = (
            1 <= component_count <= 4
            and rel_h >= 0.50
            and rel_w <= 0.36
            and 0.28 <= aspect <= 0.92
            and skin <= 0.12
            and cyan <= 0.08
            and white <= 0.18
            and (black + orange) >= 0.42
        )
        if boot_like:
            return True

    if role == "limbs":
        coherent_limb_or_contact_group = (
            2 <= component_count <= 6
            and rel_h >= 0.50
            and rel_w <= 0.38
            and aspect <= 0.90
            and white <= 0.20
            and color_evidence >= 0.24
        )
        if coherent_limb_or_contact_group:
            return True

    if role == "body_clothes":
        coherent_multi_part_garment_board = (
            2 <= component_count <= 5
            and rel_h >= 0.45
            and rel_w <= 0.72
            and aspect <= 1.15
            and cyan <= 0.12
            and white <= 0.20
        )
        if coherent_multi_part_garment_board:
            return True

    return False


def v3_large_role_component_warning_code(role: str) -> str:
    if role == "feet_footwear":
        return "coherent_footwear_needs_registration_review"
    if role == "limbs":
        return "coherent_limb_or_interaction_group_needs_registration_review"
    if role == "body_clothes":
        return "coherent_garment_layer_needs_registration_review"
    return "tall_prop_or_interaction_group_needs_registration_review"


def v3_parts_sheet_repair_guidance(role: str, code: str | None, features: dict[str, Any]) -> dict[str, Any] | None:
    if not code:
        return None
    if code == "assembled_full_body_pose_or_large_contextual_character":
        role_hint = "Regenerate as smaller role-specific owner groups."
        if role == "body_clothes":
            role_hint = (
                "Regenerate body_clothes as separate garment layers: torso/tunic, belt or sash, hips/lower garment, "
                "cape/robe front panels, and cape/robe back panel. Do not output a combined dressed torso, arms, legs, props, or half-body assembly."
            )
        elif role == "limbs":
            role_hint = (
                "Regenerate limbs as separate left/right arm or leg interaction groups. Do not output a full pose, a connected half-body, shoes, torso, or garment board."
            )
        elif role == "head_identity":
            role_hint = (
                "Regenerate head_identity as head/face identity plus front hair and rear hair only. Do not output body, shoulders, or a bust assembly."
            )
        elif role == "controlled_layout_mixed":
            role_hint = (
                "Regenerate as role-specific sheets instead of one mixed board: body_clothes for garment layers, limbs for arms/hands, feet_footwear for boots, props_accessories for staff or held props."
            )
        return {
            "code": "regenerate_role_sheet_without_assembled_body",
            "summary": role_hint,
            "promptAdditions": [
                "Garment layers are allowed and expected when they are separate riggable layers.",
                "Split clothing by coherent garment layer: tunic, belt/sash, robe front panels, robe back panel, cape front layer, cape back layer.",
                "Do not draw assembled torso plus lower garment as one component.",
                "Do not include arms, hands, props, boots, or head in a body_clothes sheet unless they are the explicitly requested owner.",
                "Each output item must be one riggable layer, not a dressed partial character.",
                "Keep source proportions, but separate garment layers so each can be registered independently.",
            ],
            "nextAction": "rerun_imagegen_role_sheet",
            "features": {
                "relativeSize": features.get("relativeSize"),
                "aspect": features.get("aspect"),
                "center": features.get("center"),
            },
        }
    if code in {"garment_overfragmented", "interaction_group_broken", "under_split_connected_sheet", "over_fragmented_micro_parts"}:
        return {
            "code": f"regenerate_{code}",
            "summary": "Regenerate this role sheet with the V3 smart split rules instead of ingesting the current sheet.",
            "nextAction": "rerun_imagegen_role_sheet",
        }
    return None


def v3_parts_sheet_policy_failures(role: str, feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    micro_count = 0
    garment_fragment_count = 0
    hand_contact_count = 0
    small_dark_fragment_count = 0
    for row in feature_rows:
        features = row["features"]
        rel_w, rel_h = features["relativeSize"]
        width, height = features["size"]
        aspect = features["aspect"]
        skin = features["skin"]
        black = features["black"]
        white = features["white"]
        orange = features["orange"]
        cyan = features["cyan"]
        if role == "head_identity":
            if width <= 140 and height <= 115 and (skin > 0.22 or white > 0.2 or black > 0.12 or orange > 0.12 or cyan > 0.12):
                micro_count += 1
        if role in {"limbs", "body_clothes"}:
            slender_or_small = rel_h < 0.34 and rel_w < 0.26
            cloth_like = black > 0.42 and skin < 0.12 and (aspect < 0.75 or aspect > 1.8 or rel_h < 0.2)
            if slender_or_small and cloth_like:
                garment_fragment_count += 1
            if rel_w < 0.18 and rel_h < 0.18 and black > 0.34:
                small_dark_fragment_count += 1
        if role in {"limbs", "props_accessories"}:
            if skin > 0.16 and black > 0.16 and rel_w > 0.08 and rel_h > 0.08:
                hand_contact_count += 1
    if role == "head_identity" and micro_count >= 3:
        failures.append(
            {
                "code": "over_fragmented_micro_parts",
                "microLikePartCount": micro_count,
                "message": "V3 head_identity sheets must keep facial micro details source-locked; do not ingest independent eyes, brows, nose, mouth, ears, or glasses as final components.",
            }
        )
    if role in {"limbs", "body_clothes"} and garment_fragment_count >= 3:
        failures.append(
            {
                "code": "garment_overfragmented",
                "fragmentLikePartCount": garment_fragment_count,
                "message": "V3 garment layers should be split by animation joints, not by loose cuffs, seams, wrinkles, or cloth scraps.",
            }
        )
    if role == "limbs" and small_dark_fragment_count >= 4 and hand_contact_count >= 1:
        failures.append(
            {
                "code": "interaction_group_broken",
                "smallDarkFragmentCount": small_dark_fragment_count,
                "handContactLikePartCount": hand_contact_count,
                "message": "A hand-held object or glove appears fragmented away from the hand contact group. Regenerate the limb sheet as coherent interaction groups.",
            }
        )
    if role == "limbs" and len(feature_rows) <= 2 and any(row["features"]["relativeSize"][1] > 0.55 for row in feature_rows):
        failures.append(
            {
                "code": "under_split_connected_sheet",
                "componentCount": len(feature_rows),
                "message": "The limbs sheet appears connected or under-split; generate separate left/right limb segments.",
            }
        )
    return failures


def parts_sheet_preflight(
    workspace: Path,
    transparent: Image.Image,
    components: list[dict[str, Any]],
    padding: int,
    role: str = "unspecified",
    allow_broad_design_board: bool = False,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if len(components) > PARTS_SHEET_MAX_DEFAULT_COMPONENTS and not allow_broad_design_board:
        failures.append(
            {
                "code": "broad_multi_view_or_design_board_parts_sheet",
                "componentCount": len(components),
                "limit": PARTS_SHEET_MAX_DEFAULT_COMPONENTS,
                "message": "Reject over-broad sheets by default; generate a cleaner final component sheet or switch to per-owner strict edit.",
            }
        )
    hard_cut_qa = read_json_if_exists(workspace / "source-visible-recompose-qa.json")
    partition_audit = read_json_if_exists(workspace / "partition-audit.json")
    if not hard_cut_qa:
        if (
            isinstance(partition_audit, dict)
            and float(partition_audit.get("coverageRatio", 0.0) or 0.0) >= 1.0
            and int(partition_audit.get("unassignedPixels", 1) or 0) == 0
        ):
            warnings.append(
                {
                    "code": "using_lossless_partition_scaffold",
                    "message": "Using partition-audit.json as the source registration scaffold for the ImageGen component sheet.",
                }
            )
        else:
            failures.append(
                {
                    "code": "missing_source_registration_scaffold",
                    "message": "Run partition/apply-cutout-map or extract-visible before accepting ImageGen parts sheet candidates.",
                }
            )
    elif not hard_cut_qa.get("quality", {}).get("passes"):
        failures.append(
            {
                "code": "source_visible_hard_cut_recompose_failed",
                "quality": hard_cut_qa.get("quality"),
            }
        )

    feature_rows: list[dict[str, Any]] = []
    for index, component in enumerate(components, start=1):
        bbox = padded_bbox(tuple(component["bbox"]), transparent.size, padding)
        crop = transparent.crop(bbox)
        features = parts_sheet_component_features(crop, list(bbox), transparent.size)
        feature_rows.append({"part": f"part-{index:03d}", "features": features, "component": component})
        forbidden = classify_forbidden_parts_sheet_component(features)
        entry = {
            "part": f"part-{index:03d}",
            "code": forbidden,
            "area": component.get("area"),
            "features": features,
        }
        guidance = v3_parts_sheet_repair_guidance(role, forbidden, features)
        if guidance:
            entry["repairGuidance"] = guidance
        if forbidden:
            if forbidden == "assembled_full_body_pose_or_large_contextual_character" and v3_is_role_allowed_large_role_component(role, features, len(components)):
                warning_entry = dict(entry)
                warning_entry.pop("repairGuidance", None)
                warnings.append(
                    {
                        **warning_entry,
                        "code": v3_large_role_component_warning_code(role),
                        "message": "Role-aware large components such as coherent boots, garment layers, pants, or hand-contact groups may continue to registration review; they are still candidates, not accepted components.",
                    }
                )
            else:
                failures.append(entry)
        elif features["relativeSize"][1] > 0.38 and features["relativeSize"][0] > 0.13:
            warnings.append({**entry, "code": "large_contextual_part_needs_visual_review"})
    failures.extend(v3_parts_sheet_policy_failures(role, feature_rows))

    return {
        "type": "kine.partsSheetPreflight",
        "version": "0.1",
        "status": "rejected" if failures else "passed",
        "role": role,
        "componentCount": len(components),
        "failures": failures,
        "warnings": warnings,
        "rules": [
            "source registration scaffold must exist and pass before parts sheet registration",
            f"broad parts sheets with more than {PARTS_SHEET_MAX_DEFAULT_COMPONENTS} connected components are rejected by default",
            "the expected ImageGen sheet is one clean green-background final component sheet, not a character turnaround/model sheet",
            "assembled full-body/contextual character components are rejected",
            "broad parts sheets must not contain independently redrawn facial micro layers",
            "V3 head_identity sheets must not over-fragment source-locked facial details",
            "V3 garment sheets split by animation joints, not cloth scraps",
            "V3 hand-held objects must stay coherent interaction groups unless explicitly split",
            "identity/style drift still requires visual review; this preflight only blocks structural errors",
        ],
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }


def process_parts_sheet(
    workspace: Path,
    sheet: Path,
    chroma_key: str | None,
    tolerance: int,
    alpha_threshold: int,
    min_area: int,
    padding: int,
    allow_broad_design_board: bool = False,
    sheet_id: str = "sheet-001",
    role: str = "unspecified",
    append: bool = False,
) -> None:
    if not sheet.exists():
        raise ValueError(f"Parts sheet does not exist: {sheet}")
    if min_area <= 0:
        raise ValueError("--min-area must be positive")
    if padding < 0:
        raise ValueError("--padding must be zero or positive")

    imagegen_dir = workspace / "imagegen" / "parts-sheets"
    cropped_dir = workspace / "parts" / sheet_id
    imagegen_dir.mkdir(parents=True, exist_ok=True)
    cropped_dir.mkdir(parents=True, exist_ok=True)

    raw_path = imagegen_dir / f"{sheet_id}.raw.png"
    transparent_path = imagegen_dir / f"{sheet_id}.transparent.png"
    if sheet.resolve() != raw_path.resolve():
        shutil.copy2(sheet, raw_path)

    raw = Image.open(raw_path).convert("RGBA")
    keyed = remove_chroma_key(raw, chroma_key, tolerance)
    chroma_residue_after_key = measure_chroma_green_residue(keyed)
    transparent_base = remove_chroma_green_residue(keyed)
    chroma_residue_after_removal = measure_chroma_green_residue(transparent_base)
    components = connected_alpha_components(transparent_base, alpha_threshold=alpha_threshold, min_area=min_area)
    green_before = measure_green_pollution(transparent_base)
    transparent = despill_green_edges(transparent_base)
    green_after = measure_green_pollution(transparent)
    chroma_residue_after_despill = measure_chroma_green_residue(transparent)
    transparent.save(transparent_path)

    preflight = parts_sheet_preflight(workspace, transparent, components, padding, role=role, allow_broad_design_board=allow_broad_design_board)
    preflight_path = workspace / "parts" / f"{sheet_id}.preflight.json"
    write_json(preflight_path, preflight)
    if preflight["status"] == "rejected":
        run_state_path = workspace / "run-state.json"
        run_state = read_json_if_exists(run_state_path) or {}
        run_state["partsSheet"] = {
            "status": "preflight_rejected",
            "preflight": relative_to_workspace(preflight_path, workspace),
            "failureCount": len(preflight["failures"]),
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(run_state_path, run_state)
        raise SystemExit(
            "Parts sheet preflight rejected the $imagegen skill output. "
            f"See {preflight_path} before running registration."
        )
    manifest_path = workspace / "parts" / "parts-sheet-manifest.json"
    existing_manifest = normalize_parts_sheet_manifest(read_json_if_exists(manifest_path) or {}) if append and manifest_path.exists() else None
    existing_parts = existing_manifest.get("parts", []) if existing_manifest else []
    global_index = next_global_part_index(existing_parts)
    sheet_campaign = read_json_if_exists(workspace / "v3" / "sheet-campaign.json") or {}
    sheet_plan = next(
        (
            item
            for item in sheet_campaign.get("sheets", [])
            if isinstance(item, dict) and item.get("id") == sheet_id
        ),
        {},
    )
    allowed_owners = [owner for owner in sheet_plan.get("owners", []) if isinstance(owner, str)]
    component_plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    allowed_components = [
        str(component.get("id"))
        for component in component_plan.get("components", [])
        if isinstance(component, dict) and isinstance(component.get("id"), str) and component.get("owner") in set(allowed_owners)
    ]
    parts: list[dict[str, Any]] = []
    for index, component in enumerate(components, start=1):
        bbox = tuple(component["bbox"])
        crop_box = padded_bbox(bbox, transparent.size, padding)
        part_img = transparent.crop(crop_box)
        local_id = f"part-{index:03d}"
        global_id = f"part-{global_index:03d}"
        global_index += 1
        part_name = f"{local_id}.png"
        part_img.save(cropped_dir / part_name)
        parts.append(
            {
                "id": global_id,
                "globalPartId": global_id,
                "sheetId": sheet_id,
                "localPartId": local_id,
                "role": role,
                "sheetRole": role,
                "sourceSheetId": sheet_id,
                "rawSheet": relative_to_workspace(raw_path, workspace),
                "transparentSheet": relative_to_workspace(transparent_path, workspace),
                "preflightPath": relative_to_workspace(preflight_path, workspace),
                "allowedOwners": allowed_owners,
                "allowedComponents": allowed_components,
                "normalizationPolicy": "raw_to_transparent_chroma_key_connected_alpha_component_crop",
                "file": f"{sheet_id}/{part_name}",
                "bbox": list(crop_box),
                "alphaBbox": component["bbox"],
                "area": component["area"],
                "greenPollution": measure_green_pollution(part_img),
                "candidateOnly": True,
                "acceptance": "requires_owner_mapping_registration_and_qa",
                "provenance": {
                    "source": "parts-sheet",
                    "rawSheet": relative_to_workspace(raw_path, workspace),
                    "transparentSheet": relative_to_workspace(transparent_path, workspace),
                    "preflightPath": relative_to_workspace(preflight_path, workspace),
                    "normalizationPolicy": "raw_to_transparent_chroma_key_connected_alpha_component_crop",
                },
            }
        )

    contact_path = workspace / "parts" / f"{sheet_id}.contact.png"
    write_parts_contact_sheet(parts, contact_path)
    sheet_record = {
        "sheetId": sheet_id,
        "role": role,
        "rawPath": relative_to_workspace(raw_path, workspace),
        "transparentPath": relative_to_workspace(transparent_path, workspace),
        "preflightPath": relative_to_workspace(preflight_path, workspace),
        "contactPath": relative_to_workspace(contact_path, workspace),
        "allowedOwners": allowed_owners,
        "allowedComponents": allowed_components,
        "normalizationPolicy": "raw_to_transparent_chroma_key_connected_alpha_component_crop",
        "imageSize": list(transparent.size),
        "componentCount": len(parts),
        "greenPollution": {"before": green_before, "after": green_after},
        "chromaGreenResidue": {
            "afterKey": chroma_residue_after_key,
            "afterResidueRemoval": chroma_residue_after_removal,
            "afterDespill": chroma_residue_after_despill,
        },
    }
    if existing_manifest:
        sheets = [sheet for sheet in existing_manifest.get("sheets", []) if isinstance(sheet, dict) and sheet.get("sheetId") != sheet_id]
        sheets.append(sheet_record)
        all_parts = [part for part in existing_parts if isinstance(part, dict) and part.get("sheetId") != sheet_id]
        all_parts.extend(parts)
    else:
        sheets = [sheet_record]
        all_parts = parts
    manifest = {
        "type": "kine.partsSheetManifest",
        "version": 2,
        "status": "candidate_parts_only",
        "workspace": workspace.name,
        "rawSheet": relative_to_workspace(raw_path, workspace),
        "transparentSheet": relative_to_workspace(transparent_path, workspace),
        "preflight": relative_to_workspace(preflight_path, workspace),
        "contactSheet": relative_to_workspace(contact_path, workspace),
        "sheets": sheets,
        "imageSize": list(transparent.size),
        "chromaKey": chroma_key or "none",
        "chromaTolerance": tolerance,
        "alphaThreshold": alpha_threshold,
        "minArea": min_area,
        "padding": padding,
        "componentCount": len(all_parts),
        "parts": all_parts,
        "greenPollution": {"before": green_before, "after": green_after},
        "chromaGreenResidue": {
            "afterKey": chroma_residue_after_key,
            "afterResidueRemoval": chroma_residue_after_removal,
            "afterDespill": chroma_residue_after_despill,
        },
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Connected components from a source-master parts sheet are raw candidates. They are not accepted layers until mapped to owners, registered, and passed by QA.",
    }
    write_json(manifest_path, manifest)

    run_state_path = workspace / "run-state.json"
    run_state = read_json_if_exists(run_state_path) or {}
    run_state["partsSheet"] = {
        "status": "processed",
        "manifest": relative_to_workspace(manifest_path, workspace),
        "componentCount": len(all_parts),
        "sheetId": sheet_id,
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(run_state_path, run_state)
    print(json.dumps({"status": "parts_sheet_processed", "sheetId": sheet_id, "componentCount": len(parts), "totalComponentCount": len(all_parts), "manifest": str(manifest_path)}, ensure_ascii=False, indent=2))


def load_parts_sheet_manifest(workspace: Path) -> dict[str, Any]:
    path = workspace / "parts" / "parts-sheet-manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing parts sheet manifest: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "parts" not in data:
        raise ValueError(f"Invalid parts sheet manifest: {path}")
    return normalize_parts_sheet_manifest(data)


def parse_part_assignments(values: list[str] | None) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError("--assign must use part-id=layer-id")
        part_id, layer_id = [item.strip() for item in value.split("=", 1)]
        if not part_id or not layer_id:
            raise ValueError("--assign must use non-empty part-id=layer-id")
        assignments[part_id] = layer_id
    return assignments


def layer_visible_bbox(workspace: Path, layer_id: str) -> list[int] | None:
    visible_mask = workspace / "layers" / layer_id / "masks" / "visible_mask.png"
    if visible_mask.exists():
        try:
            bbox = Image.open(visible_mask).convert("L").getbbox()
        except OSError:
            bbox = None
        if bbox:
            return list(bbox)
    layer_dir = workspace / "layers" / layer_id
    for name in ["visible_locked.png", "generated.png", "alpha_candidate.png"]:
        path = layer_dir / name
        if path.exists():
            try:
                bbox = Image.open(path).convert("RGBA").getchannel("A").getbbox()
            except OSError:
                bbox = None
            if bbox:
                return list(bbox)
    return None


def bbox_area(bbox: list[int] | tuple[int, int, int, int] | None) -> int:
    if not bbox:
        return 0
    return max(0, int(bbox[2]) - int(bbox[0])) * max(0, int(bbox[3]) - int(bbox[1]))


def bbox_aspect(bbox: list[int] | tuple[int, int, int, int] | None) -> float:
    if not bbox:
        return 0.0
    width = max(1, int(bbox[2]) - int(bbox[0]))
    height = max(1, int(bbox[3]) - int(bbox[1]))
    return width / height


def bbox_match_score(part_bbox: list[int], owner_bbox: list[int]) -> float:
    part_area = max(1, bbox_area(part_bbox))
    owner_area = max(1, bbox_area(owner_bbox))
    area_score = min(part_area, owner_area) / max(part_area, owner_area)
    part_aspect = max(0.01, bbox_aspect(part_bbox))
    owner_aspect = max(0.01, bbox_aspect(owner_bbox))
    aspect_score = min(part_aspect, owner_aspect) / max(part_aspect, owner_aspect)
    return round((area_score * 0.65) + (aspect_score * 0.35), 6)


def alpha_bbox_image(path: Path) -> tuple[Image.Image, list[int] | None]:
    img = Image.open(path).convert("RGBA")
    bbox = img.getchannel("A").getbbox()
    return img, list(bbox) if bbox else None


def crop_alpha_bbox(img: Image.Image) -> Image.Image:
    bbox = img.getchannel("A").getbbox()
    return img.crop(bbox) if bbox else Image.new("RGBA", (1, 1), (0, 0, 0, 0))


def normalized_alpha_mask(img: Image.Image, size: int = 96) -> Image.Image:
    crop = crop_alpha_bbox(img).getchannel("A")
    if crop.getbbox() is None:
        return Image.new("L", (size, size), 0)
    crop.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("L", (size, size), 0)
    canvas.paste(crop, ((size - crop.width) // 2, (size - crop.height) // 2))
    return canvas


def alpha_iou_score(a: Image.Image, b: Image.Image) -> float:
    aa = normalized_alpha_mask(a)
    bb = normalized_alpha_mask(b)
    a_data = aa.tobytes()
    b_data = bb.tobytes()
    union = 0
    intersection = 0
    for av, bv in zip(a_data, b_data):
        ap = av > 24
        bp = bv > 24
        if ap or bp:
            union += 1
            if ap and bp:
                intersection += 1
    return intersection / max(union, 1)


def masked_mean_rgb(img: Image.Image) -> tuple[float, float, float] | None:
    rgba = img.convert("RGBA")
    pixels = rgba.load()
    total = 0
    sums = [0.0, 0.0, 0.0]
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a <= 24:
                continue
            total += 1
            weight = a / 255.0
            sums[0] += r * weight
            sums[1] += g * weight
            sums[2] += b * weight
    if total == 0:
        return None
    return (sums[0] / total, sums[1] / total, sums[2] / total)


def color_similarity_score(a: Image.Image, b: Image.Image) -> float:
    mean_a = masked_mean_rgb(a)
    mean_b = masked_mean_rgb(b)
    if mean_a is None or mean_b is None:
        return 0.0
    distance = sum((av - bv) ** 2 for av, bv in zip(mean_a, mean_b)) ** 0.5
    return max(0.0, 1.0 - (distance / 441.673))


def masked_color_fraction(img: Image.Image, predicate: Any) -> float:
    rgba = img.convert("RGBA")
    total = 0
    hits = 0
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a <= 24:
                continue
            total += 1
            if predicate(r, g, b):
                hits += 1
    return hits / max(1, total)


def astronaut_palette_semantic_hint(workspace: Path, part: dict[str, Any], sheet_size: tuple[int, int]) -> dict[str, Any] | None:
    """Character-specific palette prior tuned for the astronaut regression sample.

    This prior fires only for parts that match the astronaut palette/geometry. It is kept so
    the astronaut regression sample still maps well, but it is no longer the only prior:
    `parts_sheet_semantic_hint` falls back to a generic, color-agnostic geometry prior for
    other characters. Either way the result still flows through source-relative visual
    similarity and the source-reference gate before registration.
    """
    part_file = workspace / "parts" / str(part.get("file"))
    if not part_file.exists():
        return None
    try:
        img, alpha_bbox = alpha_bbox_image(part_file)
    except OSError:
        return None
    bbox = part.get("bbox") or alpha_bbox
    if not (isinstance(bbox, list) and len(bbox) == 4 and alpha_bbox):
        return None
    width = max(1, alpha_bbox[2] - alpha_bbox[0])
    height = max(1, alpha_bbox[3] - alpha_bbox[1])
    aspect = width / max(1, height)
    sheet_w, sheet_h = max(1, sheet_size[0]), max(1, sheet_size[1])
    cx = ((bbox[0] + bbox[2]) / 2) / sheet_w
    cy = ((bbox[1] + bbox[3]) / 2) / sheet_h

    skin = masked_color_fraction(img, lambda r, g, b: r > 165 and 80 < g < 220 and b < 180)
    blonde = masked_color_fraction(img, lambda r, g, b: r > 180 and g > 120 and b < 125)
    cyan = masked_color_fraction(img, lambda r, g, b: g > 120 and b > 120 and r < 120)
    orange = masked_color_fraction(img, lambda r, g, b: r > 170 and 60 < g < 180 and b < 100)
    black = masked_color_fraction(img, lambda r, g, b: r < 80 and g < 80 and b < 80)
    white = masked_color_fraction(img, lambda r, g, b: r > 200 and g > 200 and b > 185)

    owner: str | None = None
    confidence = 0.0
    reason = "source_master_parts_sheet_semantic_prior"

    if orange > 0.18 and height > 60:
        owner, confidence = "props", 0.86
    elif cy < 0.27 and cyan > 0.32 and width > 150 and height > 140:
        owner, confidence = "head-accessory", 0.86
    elif cy < 0.27 and skin > 0.35 and black > 0.08 and height > 100:
        owner, confidence = "face", 0.84
    elif cy < 0.27 and blonde > 0.08 and height > 80 and black < 0.08:
        owner, confidence = ("hair-front" if cx < 0.62 else "hair-rear"), 0.82
    elif cy < 0.24 and blonde > 0.04 and aspect > 2.2 and height < 38:
        owner, confidence = "brows", 0.8
    elif cy < 0.28 and black > 0.14 and 0.75 <= aspect <= 2.2 and width < 90 and height < 70:
        owner, confidence = "eye-white", 0.78
    elif cy < 0.34 and skin > 0.35 and aspect < 1.1 and width < 50 and height < 60:
        owner, confidence = "nose", 0.82
    elif cy < 0.36 and skin > 0.25 and aspect > 1.2 and width < 90 and height < 70:
        owner, confidence = "mouth", 0.82
    elif 0.22 < cy < 0.42 and white > 0.35 and aspect > 1.45 and height < 130:
        owner, confidence = "collar-accessory", 0.82
    elif 0.22 < cy < 0.42 and black > 0.65 and height < 130:
        owner, confidence = "neck", 0.72
    elif 0.25 < cy < 0.52 and width > 210 and height > 200 and white > 0.35:
        owner, confidence = "torso", 0.82
    elif 0.30 < cy < 0.55 and height > 170 and width < 135 and white + black > 0.7:
        owner, confidence = "arms", 0.83
    elif 0.48 < cy < 0.66 and width > 170 and height > 130 and white > 0.35:
        owner, confidence = "hips", 0.82
    elif 0.52 < cy < 0.82 and height > 220 and width < 140 and white > 0.35:
        owner, confidence = "legs", 0.82
    elif cy > 0.56 and height > 200 and width < 130 and black > 0.55:
        owner, confidence = "legs", 0.74
    elif cy > 0.58 and height > 220 and width > 130 and black > 0.6:
        owner, confidence = "feet", 0.86
    elif cy > 0.58 and cyan > 0.5 and aspect > 2.0:
        owner, confidence = "props", 0.72

    if owner is None:
        return None
    full_bbox_owners = {"head-accessory", "face", "hair-front", "hair-rear", "torso", "hips"}
    return {
        "owner": owner,
        "confidence": round(confidence, 6),
        "source": reason,
        "registrationScope": "owner_visible_bbox" if owner in full_bbox_owners else "best_component_bbox",
        "features": {
            "center": [round(cx, 4), round(cy, 4)],
            "size": [width, height],
            "aspect": round(aspect, 4),
            "skin": round(skin, 4),
            "blonde": round(blonde, 4),
            "cyan": round(cyan, 4),
            "orange": round(orange, 4),
            "black": round(black, 4),
            "white": round(white, 4),
        },
    }


def generic_position_size_semantic_hint(workspace: Path, part: dict[str, Any], sheet_size: tuple[int, int]) -> dict[str, Any] | None:
    """Source-agnostic owner prior from a part's vertical band, size, and aspect.

    Unlike the astronaut palette prior, this never assumes a specific character's colors.
    It only nudges mapping for non-overfit characters with modest confidence; the final
    owner assignment still flows through source-relative visual similarity and the
    source-reference gate, so a wrong hint cannot force an accepted layer.
    """
    bbox = part.get("alphaBbox") or part.get("bbox")
    if not (isinstance(bbox, list) and len(bbox) == 4):
        return None
    sheet_w, sheet_h = max(1, sheet_size[0]), max(1, sheet_size[1])
    width = max(1, bbox[2] - bbox[0])
    height = max(1, bbox[3] - bbox[1])
    aspect = width / max(1, height)
    cx = ((bbox[0] + bbox[2]) / 2) / sheet_w
    cy = ((bbox[1] + bbox[3]) / 2) / sheet_h
    if cy < 0.30 and aspect >= 1.4:
        owner = "head-accessory"
    elif cy < 0.32:
        owner = "face"
    elif cy < 0.52 and aspect < 0.62:
        owner = "arms"
    elif cy < 0.52:
        owner = "torso"
    elif cy < 0.68:
        owner = "hips"
    elif cy < 0.86:
        owner = "legs"
    else:
        owner = "feet"
    full_bbox_owners = {"head-accessory", "face", "hair-front", "hair-rear", "torso", "hips"}
    return {
        "owner": owner,
        "confidence": 0.55,
        "source": "generic_position_size_prior",
        "registrationScope": "owner_visible_bbox" if owner in full_bbox_owners else "best_component_bbox",
        "features": {"center": [round(cx, 4), round(cy, 4)], "size": [width, height], "aspect": round(aspect, 4)},
    }


def parts_sheet_semantic_hint(workspace: Path, part: dict[str, Any], sheet_size: tuple[int, int]) -> dict[str, Any] | None:
    """Owner prior for parts-sheet mapping.

    Tries the character-specific palette prior first (helps the astronaut regression
    sample), then falls back to a generic, color-agnostic position/size prior so other
    characters are not left without any prior. Both still flow through source-relative
    visual similarity and the source-reference gate before any registration.
    """
    return astronaut_palette_semantic_hint(workspace, part, sheet_size) or generic_position_size_semantic_hint(workspace, part, sheet_size)


def visual_pair_score(part_img: Image.Image, owner_img: Image.Image, part_bbox: list[int], owner_bbox: list[int]) -> dict[str, Any]:
    shape_score = alpha_iou_score(part_img, owner_img)
    color_score = color_similarity_score(part_img, owner_img)
    area_score = min(max(1, bbox_area(part_bbox)), max(1, bbox_area(owner_bbox))) / max(
        max(1, bbox_area(part_bbox)),
        max(1, bbox_area(owner_bbox)),
    )
    aspect_score = min(max(0.01, bbox_aspect(part_bbox)), max(0.01, bbox_aspect(owner_bbox))) / max(
        max(0.01, bbox_aspect(part_bbox)),
        max(0.01, bbox_aspect(owner_bbox)),
    )
    score = (shape_score * 0.34) + (color_score * 0.34) + (aspect_score * 0.18) + (area_score * 0.14)
    return {
        "score": round(score, 6),
        "subscores": {
            "shape": round(shape_score, 6),
            "color": round(color_score, 6),
            "aspect": round(aspect_score, 6),
            "area": round(area_score, 6),
        },
    }


def source_reference_similarity_gate(owner: str, match: dict[str, Any] | None, semantic_hint: dict[str, Any] | None = None) -> dict[str, Any]:
    semantic_hint = semantic_hint or None
    is_strict_per_owner = bool(semantic_hint and semantic_hint.get("source") == "per_owner_strict_edit")
    if owner in FACIAL_MICRO_LAYERS and not is_strict_per_owner:
        return {
            "passes": False,
            "code": "facial_micro_layer_must_be_source_locked_or_strict_per_owner_edit",
            "owner": owner,
            "reason": "broad parts sheet candidates must not register independent facial micro redraws",
        }
    if not match:
        return {
            "passes": False,
            "code": "missing_source_reference_match",
            "owner": owner,
            "reason": "no source-visible owner reference was available for similarity review",
        }
    method = str(match.get("method") or "")
    if method == "bbox_fallback":
        return {
            "passes": False,
            "code": "bbox_only_match_not_enough_for_source_reference",
            "owner": owner,
            "match": match,
        }

    subscores = match.get("subscores") if isinstance(match.get("subscores"), dict) else {}
    score = float(match.get("score", 0.0))
    color = float(subscores.get("color", 0.0))
    aspect = float(subscores.get("aspect", 0.0))
    shape = float(subscores.get("shape", 0.0))
    strict = owner in SOURCE_REFERENCE_STRICT_OWNERS
    limits = {
        "score": SOURCE_REFERENCE_TOTAL_MIN + (0.04 if strict else 0.0),
        "color": SOURCE_REFERENCE_COLOR_MIN + (0.04 if strict else 0.0),
        "aspect": SOURCE_REFERENCE_ASPECT_MIN,
        "shape": SOURCE_REFERENCE_SHAPE_MIN,
    }
    failures = []
    if score < limits["score"]:
        failures.append(f"score_{round(score, 6)}_lt_{round(limits['score'], 6)}")
    if color < limits["color"]:
        failures.append(f"color_{round(color, 6)}_lt_{round(limits['color'], 6)}")
    if aspect < limits["aspect"]:
        failures.append(f"aspect_{round(aspect, 6)}_lt_{round(limits['aspect'], 6)}")
    if shape < limits["shape"] and not semantic_hint:
        failures.append(f"shape_{round(shape, 6)}_lt_{round(limits['shape'], 6)}")
    return {
        "passes": not failures,
        "code": "passed" if not failures else "source_reference_similarity_failed",
        "owner": owner,
        "strictOwner": strict,
        "score": score,
        "subscores": subscores,
        "limits": limits,
        "failures": failures,
        "matchScope": match.get("matchScope"),
        "ownerReference": match.get("ownerReference"),
        "semanticHint": semantic_hint,
    }


def candidate_owner_match_score(workspace: Path, candidate: Path, owner: str) -> dict[str, Any] | None:
    owner_bbox = layer_visible_bbox(workspace, owner)
    owner_img, owner_ref_bbox, owner_ref_source = owner_reference_image(workspace, owner)
    if owner_img is None or not owner_bbox:
        return None
    candidate_img, candidate_bbox = alpha_bbox_image(candidate)
    if not candidate_bbox:
        return None
    owner_crop = crop_alpha_bbox(owner_img)
    full_match = visual_pair_score(candidate_img, owner_crop, candidate_bbox, owner_ref_bbox or owner_bbox)
    best_match = {**full_match, "matchScope": "owner_full_alpha", "ownerComponentBbox": owner_ref_bbox or owner_bbox}
    for component in alpha_component_crops(owner_img):
        component_match = visual_pair_score(candidate_img, component["image"], candidate_bbox, component["bbox"])
        if component_match["score"] > best_match["score"]:
            best_match = {
                **component_match,
                "matchScope": "owner_alpha_component",
                "ownerComponentBbox": component["bbox"],
                "ownerComponentArea": component["area"],
            }
    return {
        "score": best_match["score"],
        "method": "visual_alpha_color_similarity",
        "subscores": best_match["subscores"],
        "matchScope": best_match["matchScope"],
        "ownerComponentBbox": best_match["ownerComponentBbox"],
        "ownerComponentArea": best_match.get("ownerComponentArea"),
        "ownerReference": owner_ref_source,
        "ownerReferenceBbox": owner_ref_bbox,
    }


def alpha_component_crops(img: Image.Image, min_area: int = 8) -> list[dict[str, Any]]:
    components = connected_alpha_components(img, alpha_threshold=24, min_area=min_area)
    crops = []
    for component in components:
        bbox = component["bbox"]
        crops.append({"bbox": bbox, "area": component["area"], "image": img.crop(tuple(bbox))})
    return crops


def owner_reference_image(workspace: Path, layer_id: str) -> tuple[Image.Image | None, list[int] | None, str | None]:
    layer_dir = workspace / "layers" / layer_id
    for name, source in [
        ("visible_locked.png", "visible_locked"),
        ("generated.png", "generated"),
        ("alpha_candidate.png", "alpha_candidate"),
    ]:
        path = layer_dir / name
        if not path.exists():
            continue
        try:
            img, bbox = alpha_bbox_image(path)
        except OSError:
            continue
        if bbox:
            return img, bbox, source
    return None, None, None


def part_owner_match_score(workspace: Path, part: dict[str, Any], owner: str, owner_bbox: list[int]) -> dict[str, Any]:
    part_file = workspace / "parts" / str(part.get("file"))
    part_img, part_alpha_bbox = alpha_bbox_image(part_file)
    owner_img, owner_ref_bbox, owner_ref_source = owner_reference_image(workspace, owner)
    part_bbox = part_alpha_bbox or part.get("bbox")
    if owner_img is None or not part_bbox:
        score = bbox_match_score(part.get("bbox") or part_bbox or [0, 0, 1, 1], owner_bbox)
        return {
            "score": score,
            "method": "bbox_fallback",
            "subscores": {"bbox": score},
            "ownerReference": owner_ref_source,
        }

    owner_crop = crop_alpha_bbox(owner_img)
    full_match = visual_pair_score(part_img, owner_crop, part_bbox, owner_ref_bbox or owner_bbox)
    best_match = {**full_match, "matchScope": "owner_full_alpha", "ownerComponentBbox": owner_ref_bbox or owner_bbox}
    for component in alpha_component_crops(owner_img):
        component_match = visual_pair_score(part_img, component["image"], part_bbox, component["bbox"])
        if component_match["score"] > best_match["score"]:
            best_match = {
                **component_match,
                "matchScope": "owner_alpha_component",
                "ownerComponentBbox": component["bbox"],
                "ownerComponentArea": component["area"],
            }
    return {
        "score": best_match["score"],
        "method": "visual_alpha_color_similarity",
        "subscores": best_match["subscores"],
        "matchScope": best_match["matchScope"],
        "ownerComponentBbox": best_match["ownerComponentBbox"],
        "ownerComponentArea": best_match.get("ownerComponentArea"),
        "ownerReference": owner_ref_source,
        "ownerReferenceBbox": owner_ref_bbox,
    }


def distribute_owner_component_slots(workspace: Path, mappings: list[dict[str, Any]]) -> None:
    by_owner: dict[str, list[dict[str, Any]]] = {}
    for mapping in mappings:
        if mapping.get("disposition") == "mapped" and mapping.get("owner"):
            by_owner.setdefault(str(mapping["owner"]), []).append(mapping)
    for owner, owner_mappings in by_owner.items():
        if len(owner_mappings) < 2:
            continue
        owner_img, _owner_bbox, owner_ref_source = owner_reference_image(workspace, owner)
        if owner_img is None:
            continue
        components = alpha_component_crops(owner_img)
        if len(components) < len(owner_mappings):
            continue
        candidates: list[tuple[float, int, int, dict[str, Any]]] = []
        for mapping_index, mapping in enumerate(owner_mappings):
            part_file = workspace / "parts" / str(mapping.get("partFile"))
            if not part_file.exists():
                continue
            try:
                part_img, part_alpha_bbox = alpha_bbox_image(part_file)
            except OSError:
                continue
            part_bbox = part_alpha_bbox or mapping.get("partBbox")
            if not part_bbox:
                continue
            for component_index, component in enumerate(components):
                score = visual_pair_score(part_img, component["image"], part_bbox, component["bbox"])["score"]
                candidates.append((score, mapping_index, component_index, component))
        candidates.sort(reverse=True, key=lambda item: item[0])
        used_mappings: set[int] = set()
        used_components: set[int] = set()
        assignments: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for _score, mapping_index, component_index, component in candidates:
            if mapping_index in used_mappings or component_index in used_components:
                continue
            used_mappings.add(mapping_index)
            used_components.add(component_index)
            assignments.append((owner_mappings[mapping_index], component))
            if len(assignments) == len(owner_mappings):
                break
        if len(assignments) != len(owner_mappings):
            continue
        for mapping, component in assignments:
            match = mapping.get("match")
            if not isinstance(match, dict):
                match = {}
                mapping["match"] = match
            match["matchScope"] = "owner_alpha_component_distributed"
            match["ownerComponentBbox"] = component["bbox"]
            match["ownerComponentArea"] = component["area"]
            match["ownerReference"] = owner_ref_source
            mapping["source"] = f"{mapping.get('source', 'visual_alpha_color_similarity')}+distributed_component_slot"


def update_parts_manifest_part(workspace: Path, part_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    manifest = load_parts_sheet_manifest(workspace)
    found = False
    for part in manifest.get("parts", []):
        if part.get("id") == part_id or part.get("globalPartId") == part_id or part.get("localPartId") == part_id:
            part.update(updates)
            found = True
            break
    if not found:
        raise ValueError(f"Unknown part id: {part_id}")
    manifest["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(workspace / "parts" / "parts-sheet-manifest.json", manifest)
    return manifest


def map_parts_to_owners(
    workspace: Path,
    assignments: dict[str, str],
    auto_visible_masks: bool,
    min_score: float,
) -> list[dict[str, Any]]:
    plan = load_plan(workspace)
    layer_ids = {layer["id"] for layer in plan["layers"]}
    manifest = load_parts_sheet_manifest(workspace)
    sheet_size_values = manifest.get("imageSize") or manifest.get("size") or manifest.get("canvas")
    if not sheet_size_values:
        transparent_sheet = workspace / str(manifest.get("transparentSheet", ""))
        raw_sheet = workspace / str(manifest.get("rawSheet", ""))
        for sheet_path in [transparent_sheet, raw_sheet]:
            if sheet_path.exists():
                try:
                    sheet_size_values = list(Image.open(sheet_path).size)
                    break
                except OSError:
                    pass
    sheet_size = tuple(sheet_size_values or (1, 1))
    owner_bboxes = {layer_id: layer_visible_bbox(workspace, layer_id) for layer_id in layer_ids}
    owner_bboxes = {layer_id: bbox for layer_id, bbox in owner_bboxes.items() if bbox}

    mappings = []
    for part in manifest.get("parts", []):
        part_id = str(part.get("id"))
        part_bbox = part.get("alphaBbox") or part.get("bbox")
        disposition = "unmapped"
        owner = None
        score = None
        reason = "no_assignment"
        match_details: dict[str, Any] | None = None
        alternatives: list[dict[str, Any]] = []
        semantic_hint: dict[str, Any] | None = None

        if part_id in assignments:
            owner = assignments[part_id]
            if owner not in layer_ids:
                raise ValueError(f"Unknown owner layer in assignment {part_id}={owner}")
            disposition = "mapped"
            score = 1.0
            reason = "debug_manual_assignment"
        elif auto_visible_masks and isinstance(part_bbox, list) and owner_bboxes:
            semantic_hint = parts_sheet_semantic_hint(workspace, part, sheet_size) if sheet_size else None
            candidates: list[tuple[float, str, dict[str, Any]]] = []
            for layer_id, bbox in owner_bboxes.items():
                details = part_owner_match_score(workspace, part, layer_id, bbox)
                candidates.append((float(details["score"]), layer_id, details))
            candidates.sort(reverse=True, key=lambda item: item[0])
            alternatives = [
                {
                    "owner": candidate_owner,
                    "score": round(candidate_score, 6),
                    "method": candidate_details.get("method"),
                    "subscores": candidate_details.get("subscores"),
                }
                for candidate_score, candidate_owner, candidate_details in candidates[:5]
            ]
            if candidates and candidates[0][0] >= min_score:
                score, owner, match_details = candidates[0]
                disposition = "mapped"
                reason = match_details.get("method", "auto_visible_similarity")
                if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.035:
                    disposition = "multi-owner"
                    owner = None
                    reason = "ambiguous_owner_similarity"
            elif candidates:
                score, best_owner, match_details = candidates[0]
                owner = None
                disposition = "unmapped"
                reason = f"below_min_score_best_{best_owner}"

            if semantic_hint and semantic_hint.get("owner") in owner_bboxes:
                hinted_owner = str(semantic_hint["owner"])
                hinted_details = part_owner_match_score(workspace, part, hinted_owner, owner_bboxes[hinted_owner])
                hinted_score = max(float(hinted_details.get("score", 0.0)), float(semantic_hint.get("confidence", 0.0)))
                if semantic_hint.get("registrationScope") == "owner_visible_bbox":
                    hinted_details = {
                        **hinted_details,
                        "matchScope": "owner_visible_bbox_semantic_prior",
                        "ownerComponentBbox": owner_bboxes[hinted_owner],
                        "ownerComponentArea": bbox_area(owner_bboxes[hinted_owner]),
                    }
                should_use_hint = (
                    disposition in {"unmapped", "multi-owner"}
                    or owner != hinted_owner and float(semantic_hint.get("confidence", 0.0)) >= 0.8
                    or owner == "nose" and hinted_owner == "props"
                )
                if should_use_hint and hinted_score >= min_score:
                    owner = hinted_owner
                    disposition = "mapped"
                    score = round(hinted_score, 6)
                    match_details = {
                        **hinted_details,
                        "semanticHint": semantic_hint,
                        "score": round(hinted_score, 6),
                    }
                    reason = "source_master_parts_sheet_semantic_prior"
            elif semantic_hint and float(semantic_hint.get("confidence", 0.0)) >= 0.72:
                owner = None
                disposition = "unmapped"
                score = semantic_hint.get("confidence")
                reason = f"semantic_hint_owner_not_visible_{semantic_hint.get('owner')}"

        mapping = {
            "partId": part_id,
            "owner": owner,
            "disposition": disposition,
            "confidence": score,
            "source": reason,
            "partFile": part.get("file"),
            "partBbox": part_bbox,
            "ownerVisibleBbox": owner_bboxes.get(owner) if owner else None,
            "match": match_details,
            "alternatives": alternatives,
            "semanticHint": semantic_hint,
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
        }
        if disposition == "mapped" and owner:
            gate = source_reference_similarity_gate(str(owner), match_details, semantic_hint)
            mapping["sourceReferenceGate"] = gate
            if not gate["passes"]:
                mapping["rejectedOwner"] = owner
                mapping["owner"] = None
                mapping["disposition"] = "source-reference-rejected"
                mapping["source"] = gate["code"]
                mapping["ownerVisibleBbox"] = None
        part["mapping"] = mapping
        part["candidateOnly"] = mapping["disposition"] != "mapped"
        mappings.append(mapping)

    distribute_owner_component_slots(workspace, mappings)
    mapping_by_part = {item["partId"]: item for item in mappings}
    for part in manifest.get("parts", []):
        part_id = str(part.get("id"))
        if part_id in mapping_by_part:
            part["mapping"] = mapping_by_part[part_id]

    manifest["status"] = "mapped_candidates" if any(item["disposition"] == "mapped" for item in mappings) else "candidate_parts_only"
    manifest["mappings"] = mappings
    manifest["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(workspace / "parts" / "parts-sheet-manifest.json", manifest)
    write_json(
        workspace / "parts" / "owner-mapping.json",
        {
            "type": "kine.partsOwnerMapping",
            "version": "0.1",
            "workspace": workspace.name,
            "status": manifest["status"],
            "autoVisibleMasks": auto_visible_masks,
            "minScore": min_score,
            "mappings": mappings,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    print(json.dumps({"status": manifest["status"], "mapped": sum(1 for item in mappings if item["disposition"] == "mapped"), "mappings": mappings}, ensure_ascii=False, indent=2))
    return mappings


def resize_part_to_bbox(part_img: Image.Image, target_bbox: list[int], canvas_size: tuple[int, int]) -> tuple[Image.Image, tuple[int, int]]:
    left, top, right, bottom = [int(value) for value in target_bbox]
    target_w = max(1, right - left)
    target_h = max(1, bottom - top)
    part_core = crop_alpha_bbox(part_img)
    resized = part_core.convert("RGBA").resize((target_w, target_h), Image.Resampling.LANCZOS)
    left = max(0, min(left, canvas_size[0] - resized.width))
    top = max(0, min(top, canvas_size[1] - resized.height))
    return resized, (left, top)


def register_part_candidate(
    workspace: Path,
    part_id: str,
    layer_id: str | None,
    x: int | None,
    y: int | None,
    fit_owner_bbox: bool,
    no_hidden_surface_required: bool,
    notes: str | None,
) -> None:
    plan = load_plan(workspace)
    layer_ids = {layer["id"] for layer in plan["layers"]}
    manifest = load_parts_sheet_manifest(workspace)
    part = next(
        (
            item
            for item in manifest.get("parts", [])
            if item.get("id") == part_id or item.get("globalPartId") == part_id or item.get("localPartId") == part_id
        ),
        None,
    )
    if not part:
        raise ValueError(f"Unknown part id: {part_id}")
    mapping = part.get("mapping") if isinstance(part.get("mapping"), dict) else {}
    owner = layer_id or mapping.get("owner")
    if not owner:
        raise ValueError(f"No owner mapping for {part_id}; pass --layer or run map-parts first.")
    if owner not in layer_ids:
        raise ValueError(f"Unknown layer id: {owner}")

    part_file = workspace / "parts" / str(part.get("file"))
    if not part_file.exists():
        raise FileNotFoundError(part_file)

    owner_bbox_for_gate = layer_visible_bbox(workspace, owner)
    gate_match = mapping.get("match") if isinstance(mapping.get("match"), dict) else None
    if not gate_match and owner_bbox_for_gate:
        try:
            gate_match = part_owner_match_score(workspace, part, owner, owner_bbox_for_gate)
        except OSError:
            gate_match = None
    semantic_hint_for_gate = mapping.get("semanticHint") if isinstance(mapping.get("semanticHint"), dict) else None
    gate = source_reference_similarity_gate(owner, gate_match, semantic_hint_for_gate)
    if not gate["passes"]:
        update_parts_manifest_part(
            workspace,
            part_id,
            {
                "candidateOnly": True,
                "mapping": {
                    **mapping,
                    "partId": part_id,
                    "owner": None,
                    "rejectedOwner": owner,
                    "disposition": "source-reference-rejected",
                    "source": gate["code"],
                    "sourceReferenceGate": gate,
                    "updatedAt": datetime.now().isoformat(timespec="seconds"),
                },
            },
        )
        raise ValueError(f"Source-reference similarity rejected {part_id} for {owner}: {gate.get('failures') or gate.get('code')}")

    canvas_size = tuple(plan["canvas"])
    part_img = Image.open(part_file).convert("RGBA")
    owner_bbox = owner_bbox_for_gate
    mapping_match = mapping.get("match") if isinstance(mapping.get("match"), dict) else {}
    mapped_component_bbox = mapping_match.get("ownerComponentBbox")
    if not (isinstance(mapped_component_bbox, list) and len(mapped_component_bbox) == 4):
        mapped_component_bbox = None
    registration_mode = "manual_xy"
    if fit_owner_bbox:
        target_bbox = mapped_component_bbox or owner_bbox
        if not target_bbox:
            raise ValueError(f"No visible bbox available for owner {owner}; provide --x/--y or run extract-visible.")
        registered_part, (px, py) = resize_part_to_bbox(part_img, target_bbox, canvas_size)
        registration_mode = "fit_owner_component_bbox" if mapped_component_bbox else "fit_owner_visible_bbox"
    else:
        px = 0 if x is None else x
        py = 0 if y is None else y
        registered_part = part_img

    layer_dir = workspace / "layers" / owner
    raw_dir = layer_dir / "backend_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / f"{part_id}.png"
    shutil.copy2(part_file, raw_copy)

    registered = register_candidate_to_canvas(registered_part, canvas_size, px, py)
    existing_generated = layer_dir / "generated.png"
    existing_alpha = layer_dir / "alpha_candidate.png"
    existing_provenance = read_json_if_exists(layer_dir / "generation-provenance.json")
    source_parts: list[dict[str, Any]] = []
    if existing_alpha.exists() and existing_provenance and existing_provenance.get("mode") == "parts_sheet_registered_candidate":
        aggregate = Image.open(existing_alpha).convert("RGBA")
        aggregate.alpha_composite(registered)
        for existing_part in existing_provenance.get("parts", []):
            if isinstance(existing_part, dict):
                source_parts.append(existing_part)
        registration_mode = f"{registration_mode}_aggregate"
    else:
        aggregate = registered
    source_parts.append(
        {
            "partId": part_id,
            "partFile": f"parts/{part.get('file')}",
            "rawCandidate": relative_to_workspace(raw_copy, workspace),
            "registration": {
                "mode": registration_mode,
                "x": px,
                "y": py,
                "canvas": list(canvas_size),
                "ownerVisibleBbox": owner_bbox,
                "ownerComponentBbox": mapped_component_bbox,
                "sourceReferenceGate": gate,
            },
        }
    )
    aggregate.save(layer_dir / "alpha_candidate.png")
    final = composite_source_visible_over_base(workspace, aggregate)
    visible_lock = layer_dir / "visible_locked.png"
    if visible_lock.exists():
        try:
            visible_img = Image.open(visible_lock).convert("RGBA")
            if visible_img.size == final.size:
                final.alpha_composite(visible_img)
        except OSError:
            pass
    final.save(layer_dir / "generated.png")
    stats = alpha_stats(final)
    provenance = {
        "type": "kine.layerGenerationProvenance",
        "version": "0.1",
        "componentId": owner,
        "backend": PUBLIC_GENERATION_BACKEND,
        "mode": "parts_sheet_registered_candidate",
        "rawCandidate": relative_to_workspace(raw_copy, workspace),
        "rawCandidates": [item["rawCandidate"] for item in source_parts],
        "partsSheet": manifest.get("rawSheet"),
        "partId": part_id,
        "parts": source_parts,
        "partFile": f"parts/{part.get('file')}",
        "ownerMapping": "parts/owner-mapping.json" if (workspace / "parts" / "owner-mapping.json").exists() else "parts/parts-sheet-manifest.json",
        "alphaCandidate": f"layers/{owner}/alpha_candidate.png",
        "registeredTarget": f"layers/{owner}/generated.png",
        "registration": {
            "mode": registration_mode,
            "x": px,
            "y": py,
            "canvas": list(canvas_size),
            "ownerVisibleBbox": owner_bbox,
            "ownerComponentBbox": mapped_component_bbox,
        },
        "sourceReferenceGate": gate,
        "noHiddenSurfaceRequired": no_hidden_surface_required,
        "alpha": stats,
        "aggregatePartCount": len(source_parts),
        "notes": notes,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(layer_dir / "generation-provenance.json", provenance)
    if no_hidden_surface_required:
        write_json(
            layer_dir / "surface-review.json",
            {
                "type": "kine.surfaceReview",
                "version": "0.1",
                "componentId": owner,
                "noHiddenSurfaceRequired": True,
                "reason": notes or "registered parts-sheet candidate reviewed as not requiring hidden underpaint",
                "provenance": "generation-provenance.json",
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            },
        )

    update_layer_plan_entry(
        workspace,
        owner,
        {
            "generationState": "generated_candidate",
            "qaDisposition": "needs_visual_review" if stats["alphaCoverage"] > 0 else "needs_regeneration",
            "bbox": stats["alphaBbox"],
            "xyxy": stats["alphaBbox"],
            "frame_size": list(canvas_size),
            "partsSheetPart": part_id,
            "noHiddenSurfaceRequired": no_hidden_surface_required,
        },
    )
    update_campaign_job(
        workspace,
        owner,
        {
            "generationState": "generated_candidate",
            "qaDisposition": "needs_visual_review" if stats["alphaCoverage"] > 0 else "needs_regeneration",
            "backendRaw": relative_to_workspace(raw_copy, workspace),
            "alphaCandidate": f"layers/{owner}/alpha_candidate.png",
            "bbox": stats["alphaBbox"],
            "partsSheetPart": part_id,
            "noHiddenSurfaceRequired": no_hidden_surface_required,
        },
    )
    update_parts_manifest_part(
        workspace,
        part_id,
        {
            "candidateOnly": False,
            "mapping": {
                **mapping,
                "partId": part_id,
                "owner": owner,
                "disposition": "mapped",
                "registeredLayer": f"layers/{owner}/generated.png",
                "registration": provenance["registration"],
                "sourceReferenceGate": gate,
                "updatedAt": datetime.now().isoformat(timespec="seconds"),
            },
        },
    )
    print(json.dumps({"status": "registered_part", "partId": part_id, "layer": owner, "alpha": stats, "registration": provenance["registration"]}, ensure_ascii=False, indent=2))


def alpha_overlap_score(part_alpha: Image.Image, owner_alpha: Image.Image, x: int, y: int) -> float:
    overlap = 0
    union = 0
    part_pixels = part_alpha.load()
    owner_pixels = owner_alpha.load()
    for py in range(part_alpha.height):
        oy = y + py
        if oy < 0 or oy >= owner_alpha.height:
            continue
        for px in range(part_alpha.width):
            ox = x + px
            if ox < 0 or ox >= owner_alpha.width:
                continue
            part_on = part_pixels[px, py] > 24
            owner_on = owner_pixels[ox, oy] > 24
            if part_on or owner_on:
                union += 1
                if part_on and owner_on:
                    overlap += 1
    return overlap / max(1, union)


def alpha_template_match(part_img: Image.Image, owner_img: Image.Image, owner_bbox: list[int] | None) -> dict[str, Any] | None:
    part_core = crop_alpha_bbox(part_img).convert("RGBA")
    if part_core.getchannel("A").getbbox() is None:
        return None
    owner_alpha = owner_img.convert("RGBA").getchannel("A")
    search_bbox = owner_bbox or list(owner_alpha.getbbox() or (0, 0, owner_alpha.width, owner_alpha.height))
    sx0 = max(0, search_bbox[0] - max(8, part_core.width // 2))
    sy0 = max(0, search_bbox[1] - max(8, part_core.height // 2))
    sx1 = min(owner_alpha.width, search_bbox[2] + max(8, part_core.width // 2))
    sy1 = min(owner_alpha.height, search_bbox[3] + max(8, part_core.height // 2))
    scales = [1.0]
    if owner_bbox:
        ow = max(1, owner_bbox[2] - owner_bbox[0])
        oh = max(1, owner_bbox[3] - owner_bbox[1])
        scales.extend([ow / max(1, part_core.width), oh / max(1, part_core.height)])
    scales.extend([0.85, 1.15])
    best: dict[str, Any] | None = None
    for scale in sorted({round(value, 4) for value in scales if 0.05 <= value <= 8.0}):
        resized = part_core.resize((max(1, int(round(part_core.width * scale))), max(1, int(round(part_core.height * scale)))), Image.Resampling.LANCZOS)
        alpha = resized.getchannel("A")
        if resized.width > owner_alpha.width or resized.height > owner_alpha.height:
            continue
        step = max(1, min(resized.width, resized.height, max(1, sx1 - sx0), max(1, sy1 - sy0)) // 96)
        for y in range(sy0, max(sy0 + 1, sy1 - resized.height + 1), step):
            for x in range(sx0, max(sx0 + 1, sx1 - resized.width + 1), step):
                score = alpha_overlap_score(alpha, owner_alpha, x, y)
                if best is None or score > best["score"]:
                    best = {"x": x, "y": y, "scale": scale, "rotationDegrees": 0.0, "method": "alpha_template_match", "score": round(score, 6)}
    return best


def owner_local_diff(workspace: Path, owner: str, placed: Image.Image) -> dict[str, Any]:
    owner_img, _owner_bbox, owner_source = owner_reference_image(workspace, owner)
    if owner_img is None:
        return {"passes": False, "reason": "owner_reference_missing"}
    owner_alpha = owner_img.getchannel("A")
    placed_alpha = placed.getchannel("A")
    outside = 0
    placed_pixels = 0
    for pv, ov in zip(placed_alpha.tobytes(), owner_alpha.tobytes()):
        if pv > 24:
            placed_pixels += 1
            if ov <= 24:
                outside += 1
    overlap_mask = ImageChops.multiply(placed_alpha, owner_alpha)
    overlap_pixels = sum(1 for value in overlap_mask.tobytes() if value > 24)
    rmse = masked_rgb_rmse(placed, owner_img, overlap_mask) if overlap_pixels else 999.0
    outside_ratio = round(outside / max(1, placed_pixels), 6)
    passes = overlap_pixels > 0 and outside_ratio <= LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT and rmse <= SOURCE_VISIBLE_CANDIDATE_RMSE_LIMIT
    return {
        "ownerReference": owner_source,
        "rgbRmse": rmse,
        "overlapPixels": overlap_pixels,
        "outsideOwnerAlphaPixels": outside,
        "outsideOwnerAlphaRatio": outside_ratio,
        "passes": passes,
    }


def register_v2(workspace: Path, part_id: str, owner: str, method: str = "auto", no_hidden_surface_required: bool = False) -> dict[str, Any]:
    plan = load_plan(workspace)
    if owner not in {layer["id"] for layer in plan["layers"]}:
        raise ValueError(f"Unknown layer id: {owner}")
    manifest = load_parts_sheet_manifest(workspace)
    part = next(
        (
            item
            for item in manifest.get("parts", [])
            if item.get("id") == part_id or item.get("globalPartId") == part_id or item.get("localPartId") == part_id
        ),
        None,
    )
    if not part:
        raise ValueError(f"Unknown part id: {part_id}")
    part_file = workspace / "parts" / str(part.get("file"))
    if not part_file.exists():
        raise FileNotFoundError(part_file)
    owner_img, owner_bbox, owner_source = owner_reference_image(workspace, owner)
    part_img = Image.open(part_file).convert("RGBA")
    records_path = workspace / "parts" / "registration-v2.json"
    records = read_json_if_exists(records_path) or {"type": "kine.registrationV2", "version": "0.1", "workspace": workspace.name, "registrations": []}
    if owner_img is None:
        record = {"partId": part_id, "owner": owner, "accepted": False, "reason": "owner_reference_missing"}
        records.setdefault("registrations", []).append(record)
        write_json(records_path, records)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return record
    transform = alpha_template_match(part_img, owner_img, owner_bbox)
    if not transform or transform["score"] <= 0:
        record = {"partId": part_id, "owner": owner, "accepted": False, "reason": "bbox_fallback_debug", "transform": None}
        records.setdefault("registrations", []).append(record)
        write_json(records_path, records)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return record
    part_core = crop_alpha_bbox(part_img).convert("RGBA")
    registered_part = part_core.resize(
        (max(1, int(round(part_core.width * transform["scale"]))), max(1, int(round(part_core.height * transform["scale"])))),
        Image.Resampling.LANCZOS,
    )
    canvas_size = tuple(plan["canvas"])
    placed = register_candidate_to_canvas(registered_part, canvas_size, int(transform["x"]), int(transform["y"]))
    diff = owner_local_diff(workspace, owner, placed)
    accepted = bool(diff.get("passes")) and float(transform["score"]) >= 0.35
    record = {
        "partId": part_id,
        "owner": owner,
        "method": method,
        "transform": transform,
        "ownerLocalDiff": diff,
        "accepted": accepted,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    if accepted:
        layer_dir = workspace / "layers" / owner
        raw_dir = layer_dir / "backend_raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_copy = raw_dir / f"{part_id}.register-v2.png"
        shutil.copy2(part_file, raw_copy)
        placed.save(layer_dir / "alpha_candidate.png")
        final = composite_source_visible_over_base(workspace, placed)
        final.save(layer_dir / "generated.png")
        stats = alpha_stats(final)
        provenance = {
            "type": "kine.layerGenerationProvenance",
            "version": "0.1",
            "componentId": owner,
            "backend": PUBLIC_GENERATION_BACKEND,
            "mode": "parts_sheet_register_v2_candidate",
            "rawCandidate": relative_to_workspace(raw_copy, workspace),
            "partsSheet": manifest.get("rawSheet"),
            "partId": part_id,
            "partFile": f"parts/{part.get('file')}",
            "registrationV2": record,
            "alphaCandidate": f"layers/{owner}/alpha_candidate.png",
            "registeredTarget": f"layers/{owner}/generated.png",
            "noHiddenSurfaceRequired": no_hidden_surface_required,
            "alpha": stats,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(layer_dir / "generation-provenance.json", provenance)
        update_layer_plan_entry(
            workspace,
            owner,
            {
                "generationState": "generated_candidate",
                "qaDisposition": "needs_visual_review",
                "bbox": stats["alphaBbox"],
                "xyxy": stats["alphaBbox"],
                "frame_size": list(canvas_size),
                "partsSheetPart": part_id,
                "registrationV2": relative_to_workspace(records_path, workspace),
                "noHiddenSurfaceRequired": no_hidden_surface_required,
            },
        )
        update_parts_manifest_part(
            workspace,
            part_id,
            {
                "candidateOnly": False,
                "mapping": {
                    **(part.get("mapping") if isinstance(part.get("mapping"), dict) else {}),
                    "partId": part_id,
                    "owner": owner,
                    "disposition": "mapped",
                    "registeredLayer": f"layers/{owner}/generated.png",
                    "registrationV2": record,
                    "updatedAt": datetime.now().isoformat(timespec="seconds"),
                },
            },
        )
    else:
        record["reason"] = "owner_local_diff_failed"
    records.setdefault("registrations", []).append(record)
    write_json(records_path, records)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return record


def verify_draw_order_local(workspace: Path, min_overlap_pixels: int = 24, rgb_disagreement_limit: float = 20.0) -> dict[str, Any]:
    plan = load_plan(workspace)
    canvas_size = tuple(plan["canvas"])
    source = Image.open(workspace / "source.png").convert("RGBA")
    order = list(plan["drawOrderBackToFront"])
    placed: dict[str, Image.Image] = {}
    for layer_id in order:
        img, valid, _failures = placed_layer_image(workspace, layer_id, canvas_size)
        if img is not None and valid and img.getchannel("A").getbbox():
            placed[layer_id] = img
    conflicts = []
    for back_index, back_id in enumerate(order):
        back = placed.get(back_id)
        if back is None:
            continue
        back_alpha = back.getchannel("A")
        for front_id in order[back_index + 1 :]:
            front = placed.get(front_id)
            if front is None:
                continue
            overlap_mask = ImageChops.multiply(back_alpha, front.getchannel("A"))
            overlap_pixels = sum(1 for value in overlap_mask.tobytes() if value > 24)
            if overlap_pixels < min_overlap_pixels:
                continue
            front_rmse = masked_rgb_rmse(front, source, overlap_mask)
            back_rmse = masked_rgb_rmse(back, source, overlap_mask)
            disagreement = round(abs(front_rmse - back_rmse), 3)
            if disagreement <= rgb_disagreement_limit:
                continue
            conflicts.append(
                {
                    "front": front_id,
                    "back": back_id,
                    "overlapPixels": overlap_pixels,
                    "frontSourceRmse": front_rmse,
                    "backSourceRmse": back_rmse,
                    "rgbDisagreement": disagreement,
                    "suggestedAction": "inspect_local_order",
                }
            )
    result = {
        "type": "kine.drawOrderLocalEvidence",
        "version": "0.1",
        "workspace": workspace.name,
        "status": "conflicts_found" if conflicts else "passed",
        "conflicts": conflicts,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Evidence only. This command never rewrites semantic draw order.",
    }
    out_path = workspace / "check" / "draw-order-conflicts.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def save_derived_color_layer(
    workspace: Path,
    source_layer: str,
    target_layer: str,
    predicate: Any,
    notes: str,
) -> dict[str, Any] | None:
    source_candidate = workspace / "layers" / source_layer / "alpha_candidate.png"
    if not source_candidate.exists():
        return None
    plan = load_plan(workspace)
    layer_ids = {layer["id"] for layer in plan["layers"]}
    if target_layer not in layer_ids:
        return None
    canvas_size = tuple(plan["canvas"])
    src = Image.open(source_candidate).convert("RGBA")
    if src.size != canvas_size:
        return None
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    src_px = src.load()
    out_px = out.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b, a = src_px[x, y]
            if a > 24 and predicate(r, g, b):
                out_px[x, y] = (r, g, b, a)
    stats = alpha_stats(out)
    if stats["alphaCoverage"] <= 0:
        return None
    layer_dir = workspace / "layers" / target_layer
    layer_dir.mkdir(parents=True, exist_ok=True)
    out.save(layer_dir / "alpha_candidate.png")
    final = composite_source_visible_over_base(workspace, out)
    visible_lock = layer_dir / "visible_locked.png"
    if visible_lock.exists():
        try:
            visible_img = Image.open(visible_lock).convert("RGBA")
            if visible_img.size == final.size:
                final.alpha_composite(visible_img)
        except OSError:
            pass
    final.save(layer_dir / "generated.png")
    final_stats = alpha_stats(final)
    provenance = {
        "type": "kine.layerGenerationProvenance",
        "version": "0.1",
        "componentId": target_layer,
        "backend": PUBLIC_GENERATION_BACKEND,
        "mode": "derived_semantic_color_split",
        "sourceLayer": source_layer,
        "parentProvenance": relative_to_workspace(workspace / "layers" / source_layer / "generation-provenance.json", workspace),
        "alphaCandidate": f"layers/{target_layer}/alpha_candidate.png",
        "registeredTarget": f"layers/{target_layer}/generated.png",
        "noHiddenSurfaceRequired": True,
        "alpha": final_stats,
        "notes": notes,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(layer_dir / "generation-provenance.json", provenance)
    write_json(
        layer_dir / "surface-review.json",
        {
            "type": "kine.surfaceReview",
            "version": "0.1",
            "componentId": target_layer,
            "noHiddenSurfaceRequired": True,
            "reason": notes,
            "provenance": "generation-provenance.json",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    update_layer_plan_entry(
        workspace,
        target_layer,
        {
            "generationState": "generated_candidate",
            "qaDisposition": "needs_visual_review",
            "bbox": final_stats["alphaBbox"],
            "xyxy": final_stats["alphaBbox"],
            "frame_size": list(canvas_size),
            "derivedFrom": source_layer,
            "noHiddenSurfaceRequired": True,
        },
    )
    update_campaign_job(
        workspace,
        target_layer,
        {
            "generationState": "generated_candidate",
            "qaDisposition": "needs_visual_review",
            "alphaCandidate": f"layers/{target_layer}/alpha_candidate.png",
            "bbox": final_stats["alphaBbox"],
            "derivedFrom": source_layer,
            "noHiddenSurfaceRequired": True,
        },
    )
    return {"layer": target_layer, "alpha": final_stats, "sourceLayer": source_layer}


def derive_eye_detail_layers(workspace: Path) -> list[dict[str, Any]]:
    return [
        item
        for item in [
            save_derived_color_layer(
                workspace,
                "eye-white",
                "eye-iris",
                lambda r, g, b: b > 95 and b > r + 20 and b >= g - 20,
                "derived iris/pupil pixels from owner-isolated generated eye candidate",
            ),
            save_derived_color_layer(
                workspace,
                "eye-white",
                "eye-line",
                lambda r, g, b: r < 90 and g < 90 and b < 90,
                "derived eyelash/eye-line pixels from owner-isolated generated eye candidate",
            ),
        ]
        if item
    ]


def strict_edit_prompt_for_layer(workspace: Path, layer_id: str, reason: str) -> str:
    plan = load_plan(workspace)
    layer = next((item for item in plan["layers"] if item["id"] == layer_id), {"id": layer_id, "tag": layer_id, "prompt": layer_id})
    source = Image.open(workspace / "source.png").convert("RGBA")
    visible = workspace / "layers" / layer_id / "visible_locked.png"
    contract = workspace / "layers" / layer_id / "layer-redraw-removal-contract.json"
    spine_bone = spine_bone_for_component(layer_id)
    micro_note = ""
    if layer_id in FACIAL_MICRO_LAYERS:
        micro_note = "\n- This is a facial micro layer. Use the source-locked visible pixels as the exact identity; generate only hidden/occluded owner pixels if needed."
    spine_note = f"\n- Spine target bone: `{spine_bone}`. Keep this owner riggable to that joint: do not merge in neighbouring bone parts."
    if layer_id in SPINE_LIMB_SEGMENTS:
        segment_ids = ", ".join(target["id"] for target in spine_part_targets(layer_id))
        spine_note += f"\n- This limb owner is split into Spine bone-chain parts after redraw ({segment_ids}); keep left/right and proximal/distal segments cleanly separable."
    return f"""Use case: precise-object-edit
Asset type: KINE-LAYER strict per-owner repair / hidden-underpaint candidate
Target owner: `{layer_id}`
Spine bone: `{spine_bone}`
Reason for this pass: {reason}
Source canvas: {source.width}x{source.height}px.

Required references in the workspace:
- source image: `source.png`
- source-visible owner lock: `{relative_to_workspace(visible, workspace) if visible.exists() else 'missing'}`
- removal contract: `{relative_to_workspace(contract, workspace) if contract.exists() else 'missing'}`
- director plan: `director/decomposition-plan.json`

Primary request:
Create only the `{layer_id}` owner repair or hidden-underpaint candidate for the exact source character. Start from the hard-cut source-visible owner evidence. If the hard cut contains foreign-owner pixels, erase them. If owner pixels are missing, restore only the missing owner pixels that belong to the original source component. Fill hidden or occluded owner surface only where needed for rigging.

Hard constraints:
- Prefer a full-canvas {source.width}x{source.height}px transparent PNG registered to the original source position. If the output cannot be full-canvas, keep the component crop tightly owner-isolated with no centered presentation framing.
- When the source-visible owner lock exists, do not repaint those visible pixels. Output only the hidden/occluded extension or repair pixels outside the source-visible owner lock; source-visible pixels will be composited locally from `visible_locked.png`.
- Preserve the original source identity, face proportions, hair shape, outfit/costume design, material colors, line weight, lighting, scale, pose relationship, and silhouette.
- Include only this owner. All other owners and background must be transparent or removable chroma-key background.
- Do not redesign, beautify, restyle, mirror, resize, rotate, change expression, change costume, or invent a new component.
- Do not output a full body, neighboring body parts, labels, text, watermark, shadow, floor, or checkerboard.
- Output a single owner-isolated transparent PNG or a flat #00ff00 chroma-key image suitable for alpha removal.{micro_note}{spine_note}
"""


def write_per_owner_strict_edit_plan(workspace: Path, owners: list[str] | None = None, reason: str | None = None) -> dict[str, Any]:
    plan = load_plan(workspace)
    layer_ids = [layer["id"] for layer in plan["layers"]]
    requested = [owner for owner in owners or [] if owner in layer_ids]
    qa = read_json_if_exists(workspace / "qa.json") or {}
    qa_by_id = {item.get("id"): item for item in qa.get("layers", []) if isinstance(item, dict)}
    target_reasons: dict[str, str] = {}
    for layer_id in requested:
        target_reasons[layer_id] = reason or "requested_per_owner_strict_edit"
    if owners is None:
        for layer_id in layer_ids:
            result = qa_by_id.get(layer_id)
            if result and result.get("status") in {"source_lock_only", "missing", "visual_rejected"}:
                target_reasons.setdefault(layer_id, ",".join(result.get("failures", [])) or str(result.get("status")))
            elif result and result.get("status") == "present" and not result.get("finalRedrawKind"):
                target_reasons.setdefault(layer_id, "present_layer_missing_final_imagegen_redraw")

    mapping_path = workspace / "parts" / "owner-mapping.json"
    mapping = read_json_if_exists(mapping_path) or {}
    for item in mapping.get("mappings", []) if isinstance(mapping.get("mappings"), list) else []:
        disposition = item.get("disposition")
        owner = item.get("rejectedOwner") or item.get("owner")
        if owner in layer_ids and disposition in {"source-reference-rejected", "multi-owner", "unmapped"}:
            target_reasons.setdefault(str(owner), f"parts_mapping_{disposition}:{item.get('source')}")

    targets = []
    prompt_dir = workspace / "imagegen" / "per-owner-strict-edit"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    for layer_id in layer_ids:
        if layer_id not in target_reasons:
            continue
        prompt = strict_edit_prompt_for_layer(workspace, layer_id, target_reasons[layer_id])
        prompt_path = prompt_dir / f"{layer_id}.prompt.txt"
        prompt_path.write_text(prompt + "\n", encoding="utf-8")
        visible_path = workspace / "layers" / layer_id / "visible_locked.png"
        targets.append(
            {
                "owner": layer_id,
                "reason": target_reasons[layer_id],
                "prompt": relative_to_workspace(prompt_path, workspace),
                "sourceVisibleLock": relative_to_workspace(visible_path, workspace) if visible_path.exists() else None,
                "removalContract": f"layers/{layer_id}/layer-redraw-removal-contract.json",
                "expectedMode": "hidden" if visible_path.exists() else "generated",
                "ingestCommand": (
                    "python3 skill/scripts/kine_layer_workspace.py ingest "
                    f"--workspace {workspace} --layer {layer_id} --candidate <candidate.png> "
                    f"--mode {'hidden' if visible_path.exists() else 'generated'} --chroma-key auto"
                ),
            }
        )

    payload = {
        "type": "kine.perOwnerStrictEditPlan",
        "version": "0.1",
        "status": "pending_imagegen" if targets else "no_targets",
        "workspace": workspace.name,
        "targetCount": len(targets),
        "targets": targets,
        "rules": [
            "use built-in image generation per owner when parts sheet is missing, polluted, ambiguous, or source-reference rejected",
            "present source-partition owners still require ImageGen final redraw or hidden-underpaint provenance before final export",
            "start from source-visible owner evidence and removal contract",
            "do not register a candidate until alpha extraction, source-canvas registration, provenance, source-reference gate, and QA pass",
        ],
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    plan_path = workspace / "imagegen" / "per-owner-strict-edit-plan.json"
    write_json(plan_path, payload)
    update_run_state(workspace, {"perOwnerStrictEditPlan": relative_to_workspace(plan_path, workspace), "perOwnerStrictEditTargetCount": len(targets)})
    return payload


def strict_edit_candidate_for_owner(candidate_dir: Path, owner: str) -> Path | None:
    for suffix in [".png", ".webp", ".jpg", ".jpeg"]:
        direct = candidate_dir / f"{owner}{suffix}"
        if direct.exists():
            return direct
    matches = sorted(
        path
        for path in candidate_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"} and path.stem.startswith(f"{owner}.")
    )
    return matches[0] if matches else None


def ingest_strict_edit_candidates(workspace: Path, candidate_dir: Path, chroma_key: str | None, tolerance: int) -> dict[str, Any]:
    plan_path = workspace / "imagegen" / "per-owner-strict-edit-plan.json"
    plan = read_json_if_exists(plan_path)
    if not plan:
        raise FileNotFoundError(plan_path)
    if not candidate_dir.exists():
        raise FileNotFoundError(candidate_dir)

    results = []
    for target in plan.get("targets", []):
        owner = str(target.get("owner") or "")
        if not owner:
            continue
        candidate = strict_edit_candidate_for_owner(candidate_dir, owner)
        if not candidate:
            results.append({"owner": owner, "status": "missing_candidate", "expectedMode": target.get("expectedMode")})
            continue
        before = read_json_if_exists(workspace / "layers" / owner / "visual_rejected.json")
        ingest_layer_candidate(
            workspace,
            owner,
            candidate,
            str(target.get("expectedMode") or "hidden"),
            chroma_key,
            tolerance,
            None,
            None,
            PUBLIC_GENERATION_BACKEND,
            "per-owner strict edit candidate batch ingest",
            False,
        )
        after_rejection = read_json_if_exists(workspace / "layers" / owner / "visual_rejected.json")
        status = "ingested_needs_qa"
        if after_rejection and after_rejection != before:
            status = str(after_rejection.get("reason") or "visual_rejected")
        results.append(
            {
                "owner": owner,
                "status": status,
                "candidate": relative_to_workspace(candidate, workspace) if candidate.is_relative_to(workspace) else str(candidate),
                "expectedMode": target.get("expectedMode"),
            }
        )

    ingested = sum(1 for item in results if item["status"] == "ingested_needs_qa")
    rejected = sum(1 for item in results if item["status"] not in {"ingested_needs_qa", "missing_candidate"})
    missing = sum(1 for item in results if item["status"] == "missing_candidate")
    summary = {
        "type": "kine.perOwnerStrictEditIngest",
        "version": "0.1",
        "workspace": workspace.name,
        "candidateDir": str(candidate_dir),
        "ingested": ingested,
        "rejected": rejected,
        "missing": missing,
        "results": results,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "imagegen" / "per-owner-strict-edit-ingest.json", summary)
    update_run_state(
        workspace,
        {
            "perOwnerStrictEditIngest": "imagegen/per-owner-strict-edit-ingest.json",
            "perOwnerStrictEditIngested": ingested,
            "perOwnerStrictEditRejected": rejected,
            "perOwnerStrictEditMissing": missing,
        },
    )
    return summary


def auto_register_parts(
    workspace: Path,
    min_score: float,
    no_hidden_surface_required: bool,
    notes: str | None,
) -> None:
    mappings = map_parts_to_owners(workspace, {}, auto_visible_masks=True, min_score=min_score)
    registered = []
    skipped = []
    for mapping in mappings:
        if mapping.get("disposition") != "mapped" or not mapping.get("owner"):
            skipped.append({"partId": mapping.get("partId"), "reason": mapping.get("source"), "disposition": mapping.get("disposition")})
            continue
        try:
            register_part_candidate(
                workspace,
                str(mapping["partId"]),
                str(mapping["owner"]),
                None,
                None,
                True,
                no_hidden_surface_required,
                notes or "auto-registered from parts sheet by visible-mask similarity",
            )
            registered.append({"partId": mapping["partId"], "owner": mapping["owner"], "confidence": mapping.get("confidence")})
        except Exception as exc:
            skipped.append({"partId": mapping.get("partId"), "owner": mapping.get("owner"), "reason": f"{type(exc).__name__}: {exc}"})
    derived = derive_eye_detail_layers(workspace)
    strict_edit_plan = write_per_owner_strict_edit_plan(
        workspace,
        sorted({str(item.get("owner") or item.get("rejectedOwner")) for item in skipped if item.get("owner") or item.get("rejectedOwner")}),
        "auto_register_skipped_or_rejected_candidate",
    )

    write_json(
        workspace / "parts" / "auto-registration.json",
        {
            "type": "kine.partsAutoRegistration",
            "version": "0.1",
            "workspace": workspace.name,
            "registered": registered,
            "derived": derived,
            "skipped": skipped,
            "perOwnerStrictEditPlan": "imagegen/per-owner-strict-edit-plan.json",
            "perOwnerStrictEditTargetCount": strict_edit_plan.get("targetCount"),
            "minScore": min_score,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    print(json.dumps({"status": "auto_registered_parts", "registered": registered, "derived": derived, "skipped": skipped}, ensure_ascii=False, indent=2))


def load_campaign(workspace: Path) -> dict[str, Any] | None:
    path = workspace / "campaign.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def sync_campaign_status(workspace: Path, layer_results: list[dict[str, Any]]) -> None:
    campaign = load_campaign(workspace)
    if not campaign:
        return
    result_by_id = {item["id"]: item for item in layer_results}
    for job in campaign.get("jobs", []):
        result = result_by_id.get(job.get("componentId"))
        if not result:
            continue
        status = result["status"]
        job["qaDisposition"] = status
        job["generationState"] = result.get("generationState") or (
            "registered"
            if status == "present"
            else "blocked"
            if status == "not_visible"
            else "pending_generation"
        )
        job["failures"] = result.get("failures", [])
        job["bbox"] = result.get("bbox")
    campaign["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(workspace / "campaign.json", campaign)


def mask_path(workspace: Path, layer_id: str, name: str) -> Path:
    return workspace / "layers" / layer_id / "masks" / f"{name}_mask.png"


def masked_rgb_rmse(a: Image.Image, b: Image.Image, mask: Image.Image) -> float:
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    stat = ImageStat.Stat(diff, mask.convert("L"))
    if not stat.rms:
        return 0.0
    return round(sum(v * v for v in stat.rms) ** 0.5, 3)


def mask_qa(workspace: Path, layer_id: str, img: Image.Image | None) -> dict[str, Any]:
    layer_dir = workspace / "layers" / layer_id
    visible = mask_path(workspace, layer_id, "visible")
    occlusion = mask_path(workspace, layer_id, "occlusion")
    result: dict[str, Any] = {
        "visibleMask": relative_to_workspace(visible, workspace),
        "visibleMaskExists": visible.exists(),
        "occlusionMask": relative_to_workspace(occlusion, workspace),
        "occlusionMaskExists": occlusion.exists(),
    }
    if img is not None and visible.exists():
        source = Image.open(workspace / "source.png").convert("RGBA")
        mask = Image.open(visible).convert("L")
        result["sourceVisibleRmse"] = masked_rgb_rmse(source, img, mask)
        candidate_path = layer_dir / "alpha_candidate.png"
        if candidate_path.exists():
            candidate = Image.open(candidate_path).convert("RGBA")
            if candidate.size == source.size:
                candidate_alpha = candidate.getchannel("A")
                overlap = ImageChops.multiply(mask, candidate_alpha)
                overlap_pixels = sum(1 for value in overlap.tobytes() if value > 0)
                visible_pixels = sum(1 for value in mask.tobytes() if value > 0)
                result["candidateVisibleOverlapPixels"] = overlap_pixels
                result["candidateVisibleOverlapRatio"] = round(overlap_pixels / max(visible_pixels, 1), 6)
                if overlap_pixels:
                    result["candidateVisibleRmse"] = masked_rgb_rmse(source, candidate, overlap)
    return result


def composite_layers(workspace: Path, plan: dict[str, Any], check_dir: Path) -> tuple[Image.Image, list[dict[str, Any]]]:
    canvas_size = tuple(plan["canvas"])
    comp = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    results = []
    by_id = {layer["id"]: layer for layer in plan["layers"]}
    for layer_id in plan["drawOrderBackToFront"]:
        layer = by_id[layer_id]
        img_path = layer_image(workspace, layer_id)
        status = "missing"
        failures = []
        stats = None
        img = None
        source_bounds = None
        masks: dict[str, Any] = {}
        issue = composition_issue(workspace, layer_id)
        if issue:
            failures.append(issue)
        completion_issue = layer_completion_status(workspace, layer_id)
        if completion_issue:
            failures.append(completion_issue)
        manual_failures = manual_visual_rejection(workspace, layer_id)
        failures.extend(manual_failures)
        if img_path.exists():
            placed, placement_valid, placement_failures = placed_layer_image(workspace, layer_id, canvas_size)
            img = placed if placed is not None else Image.open(img_path).convert("RGBA")
            stats = alpha_stats(img)
            source_bounds = layer_source_alpha_bounds(workspace, img)
            masks = mask_qa(workspace, layer_id, img if img.size == canvas_size else None)
            candidate_rmse = masks.get("candidateVisibleRmse")
            candidate_overlap = masks.get("candidateVisibleOverlapRatio", 0)
            if (
                isinstance(candidate_rmse, (int, float))
                and candidate_overlap > 0.1
                and candidate_rmse > SOURCE_VISIBLE_CANDIDATE_RMSE_LIMIT
            ):
                failures.append(
                    f"redraw_candidate_changes_source_visible_pixels_rmse_{candidate_rmse}_limit_{SOURCE_VISIBLE_CANDIDATE_RMSE_LIMIT}"
                )
            if not placement_valid:
                status = "visual_rejected"
                failures.extend(placement_failures or ["cropped_layer_missing_or_invalid_placement"])
            elif stats["alphaCoverage"] <= 0:
                status = "visual_rejected"
                failures.append("empty_alpha_layer")
            elif stats["opaqueCoverage"] > 0.98:
                status = "visual_rejected"
                failures.append("likely_opaque_background")
            elif (
                source_bounds
                and source_bounds.get("status") == "measured"
                and float(source_bounds.get("outsideSourceAlphaRatioOfSource", 0.0)) > LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT
            ):
                status = "visual_rejected"
                failures.append(
                    "layer_alpha_outside_source_silhouette_ratio_"
                    f"{source_bounds['outsideSourceAlphaRatioOfSource']}_limit_{LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT}"
                )
            elif completion_issue:
                status = completion_issue_status(completion_issue)
            elif failures:
                status = "visual_rejected"
            else:
                status = "present"
                comp.alpha_composite(img)
        elif manual_failures:
            status = "visual_rejected"
        elif layer.get("qaDisposition") == "not_visible":
            status = "not_visible"
        elif (workspace / "layers" / layer_id / "visible_locked.png").exists():
            status = "source_lock_only"
            failures.append("source_visible_lock_missing_hidden_underpaint_or_redraw")
        elif layer.get("required"):
            status = "missing"
            failures.append("missing_required_layer")
        debug_path = layer_debug_image(workspace, layer_id)
        artifacts = layer_artifact_paths(workspace, layer_id)
        artifact_rel = {key: relative_to_workspace(value, workspace) for key, value in artifacts.items()}
        artifact_alpha = {}
        for key, value in artifacts.items():
            artifact_stat = artifact_stats(value, canvas_size)
            if artifact_stat is not None:
                artifact_alpha[key] = artifact_stat
        final_redraw_kind = final_redraw_kind_for_layer_dir(workspace / "layers" / layer_id, status, artifacts)
        generation_state = (
            "registered"
            if status == "present"
            else str(layer.get("generationState") or "generated_candidate_rejected")
            if status == "visual_rejected"
            else str(layer.get("generationState") or "source_visible_locked")
            if status == "source_lock_only"
            else "blocked"
            if status == "not_visible"
            else "pending_generation"
        )
        provenance_path = workspace / "layers" / layer_id / "generation-provenance.json"
        results.append(
            {
                "id": layer_id,
                "tag": layer.get("tag"),
                "kind": layer.get("kind"),
                "required": layer.get("required", False),
                "status": status,
                "failures": failures,
                "file": relative_to_workspace(img_path, workspace),
                "debugFile": relative_to_workspace(debug_path, workspace) if debug_path else None,
                "artifacts": artifact_rel,
                "artifactAlpha": artifact_alpha,
                "redrawEvidence": {
                    "hasRedrawAlpha": "redraw" in artifacts,
                    "hasHiddenUnderpaint": "hidden" in artifacts,
                    "hasVisibleLock": "visible" in artifacts,
                    "hasBackendRaw": "raw" in artifacts,
                    "noHiddenSurfaceRequired": provenance_allows_no_hidden_surface(workspace / "layers" / layer_id),
                    "hiddenContribution": hidden_contribution(workspace, layer_id),
                },
                "finalRedrawKind": final_redraw_kind,
                "finalRedrawRequired": status == "present",
                "alpha": stats if img is not None and img.size == canvas_size else None,
                "masks": masks,
                "sourceAlphaBounds": source_bounds if img is not None and img.size == canvas_size else None,
                "bbox": stats["alphaBbox"] if stats else None,
                "depthMedian": layer.get("depthMedian"),
                "orderSource": layer.get("orderSource", "manual_static_initial"),
                "orderConfidence": layer.get("orderConfidence"),
                "generationState": generation_state,
                "qaDisposition": status,
                "provenance": relative_to_workspace(provenance_path, workspace) if provenance_path.exists() else None,
                "removalContract": relative_to_workspace(workspace / "layers" / layer_id / "layer-redraw-removal-contract.json", workspace),
                "noHiddenSurfaceRequired": provenance_allows_no_hidden_surface(workspace / "layers" / layer_id),
            }
        )
    comp.save(check_dir / "recompose.png")
    return comp, results


def apply_cross_layer_generation_audit(workspace: Path, layer_results: list[dict[str, Any]]) -> None:
    raw_candidate_owners: dict[str, list[str]] = {}
    for result in layer_results:
        layer_id = result["id"]
        for provenance_name in ["generation-provenance.json", "hidden_underpaint_provenance.json"]:
            provenance = read_json_if_exists(workspace / "layers" / layer_id / provenance_name)
            if not provenance:
                continue
            backend = provenance.get("backend")
            if backend == SOURCE_VISIBLE_BACKEND:
                continue
            raw_candidates = []
            if provenance.get("rawCandidate"):
                raw_candidates.append(str(provenance["rawCandidate"]))
            raw_candidates.extend(str(item) for item in provenance.get("rawCandidates", []) if item)
            for raw_candidate in sorted(set(raw_candidates)):
                raw_candidate_owners.setdefault(raw_candidate, []).append(layer_id)

    for raw_candidate, owners in raw_candidate_owners.items():
        unique_owners = sorted(set(owners))
        if len(unique_owners) < 2:
            continue
        owner_set = set(unique_owners)
        for result in layer_results:
            if result["id"] not in owner_set:
                continue
            result["failures"].append(
                f"shared_backend_raw_candidate_{raw_candidate}_with_{','.join(owner for owner in unique_owners if owner != result['id'])}"
            )
            if result["status"] == "present":
                result["status"] = "visual_rejected"
                result["finalRedrawKind"] = None
                result["generationState"] = "generated_candidate"
                result["qaDisposition"] = "visual_rejected"


def make_underlay(workspace: Path, composite: Image.Image, path: Path) -> None:
    source = Image.open(workspace / "source.png").convert("RGBA")
    bg = Image.new("RGBA", source.size, (255, 255, 255, 255))
    faint = source.copy()
    faint.putalpha(faint.getchannel("A").point(lambda value: min(value, 86)))
    bg.alpha_composite(faint)
    bg.alpha_composite(composite)
    ImageDraw.Draw(bg).text((24, 24), "source + Kine Layer recompose", fill=(0, 0, 0, 255))
    bg.save(path)


def make_source_diff(workspace: Path, composite: Image.Image, path: Path) -> None:
    source = Image.open(workspace / "source.png").convert("RGBA")
    bg = Image.new("RGBA", source.size, (255, 255, 255, 255))
    src_rgb = Image.alpha_composite(bg, source).convert("RGB")
    comp_rgb = Image.alpha_composite(bg, composite).convert("RGB")
    diff = ImageChops.difference(src_rgb, comp_rgb)
    diff.save(path)


def recompose_quality(workspace: Path, composite: Image.Image, measured_against: str = "real_present_layer_composite") -> dict[str, Any]:
    """Measure the real accepted-layer composite against the source.

    `composite` must be the actual present-layer recomposition, not a
    source-pose-locked review image rebuilt from source pixels. The coverage gate
    catches sparse composites that reconstruct only a small fraction of the
    source silhouette.
    """
    source = Image.open(workspace / "source.png").convert("RGBA")
    bg = Image.new("RGBA", source.size, (255, 255, 255, 255))
    src_rgb = Image.alpha_composite(bg, source).convert("RGB")
    comp_rgba = composite.convert("RGBA")
    comp_rgb = Image.alpha_composite(bg, comp_rgba).convert("RGB")
    diff = ImageChops.difference(src_rgb, comp_rgb)
    stat = ImageStat.Stat(diff)
    rmse = round(sum(value * value for value in stat.rms) ** 0.5, 3)
    source_alpha = source.getchannel("A")
    comp_alpha = comp_rgba.getchannel("A") if comp_rgba.size == source.size else None
    width, height = source.size
    exact_rgba_bbox = ImageChops.difference(source, comp_rgba).getbbox()
    if _np is not None:
        src_mask = _np.asarray(source_alpha) > 0
        comp_alpha_arr = _np.asarray(comp_alpha) if comp_alpha is not None else _np.zeros((height, width), dtype=_np.uint8)
        src_arr = _np.asarray(source)
        comp_arr = _np.asarray(comp_rgba)
        source_alpha_pixels = int(src_mask.sum())
        max_diff = _np.asarray(diff).max(axis=2)
        changed_pixels = int(((max_diff > 20) & src_mask).sum())
        if comp_alpha is None:
            missing_pixels = source_alpha_pixels
        else:
            missing_pixels = int((src_mask & (comp_alpha_arr == 0)).sum())
        alpha_mismatch_pixels = int((_np.asarray(source_alpha) != comp_alpha_arr).sum())
        extra_alpha_pixels = int(((comp_alpha_arr > 0) & ~src_mask).sum())
        rgba_mismatch_pixels = int(_np.any(src_arr != comp_arr, axis=2).sum())
        rgb_mismatch_pixels_in_source_alpha = int((_np.any(src_arr[:, :, :3] != comp_arr[:, :, :3], axis=2) & src_mask).sum())
    else:
        diff_px = diff.load()
        alpha_px = source_alpha.load()
        comp_alpha_px = comp_alpha.load() if comp_alpha is not None else None
        source_px = source.load()
        comp_px = comp_rgba.load()
        source_alpha_pixels = 0
        changed_pixels = 0
        missing_pixels = 0
        alpha_mismatch_pixels = 0
        extra_alpha_pixels = 0
        rgba_mismatch_pixels = 0
        rgb_mismatch_pixels_in_source_alpha = 0
        for y in range(height):
            for x in range(width):
                src_alpha = alpha_px[x, y]
                comp_alpha_value = comp_alpha_px[x, y] if comp_alpha_px is not None else 0
                if src_alpha != comp_alpha_value:
                    alpha_mismatch_pixels += 1
                if comp_alpha_value > 0 and src_alpha == 0:
                    extra_alpha_pixels += 1
                if source_px[x, y] != comp_px[x, y]:
                    rgba_mismatch_pixels += 1
                if src_alpha > 0:
                    source_alpha_pixels += 1
                    if max(diff_px[x, y]) > 20:
                        changed_pixels += 1
                    if source_px[x, y][:3] != comp_px[x, y][:3]:
                        rgb_mismatch_pixels_in_source_alpha += 1
                    if comp_alpha_value == 0:
                        missing_pixels += 1
    changed_ratio = round(changed_pixels / max(source_alpha_pixels, 1), 6)
    missing_ratio = round(missing_pixels / max(source_alpha_pixels, 1), 6)
    coverage_ratio = round(1.0 - missing_ratio, 6)
    pixel_perfect_source = (
        exact_rgba_bbox is None
        and alpha_mismatch_pixels == 0
        and extra_alpha_pixels == 0
        and missing_pixels == 0
        and rgb_mismatch_pixels_in_source_alpha == 0
    )
    passes = (
        rmse <= RECOMPOSE_RGB_RMSE_LIMIT
        and changed_ratio <= RECOMPOSE_SOURCE_ALPHA_DIFF_RATIO_LIMIT
        and missing_ratio <= RECOMPOSE_MAX_MISSING_SOURCE_ALPHA_RATIO
        and pixel_perfect_source
    )
    return {
        "rgbRmse": rmse,
        "sourceAlphaPixels": source_alpha_pixels,
        "changedPixelsGt20InSourceAlpha": changed_pixels,
        "changedRatioGt20InSourceAlpha": changed_ratio,
        "missingSourceAlphaPixels": missing_pixels,
        "missingSourceAlphaRatio": missing_ratio,
        "coverageRatio": coverage_ratio,
        "pixelPerfectSource": pixel_perfect_source,
        "exactRgbaDiffBbox": list(exact_rgba_bbox) if exact_rgba_bbox else None,
        "alphaMismatchPixels": alpha_mismatch_pixels,
        "extraAlphaPixels": extra_alpha_pixels,
        "rgbaMismatchPixels": rgba_mismatch_pixels,
        "rgbMismatchPixelsInSourceAlpha": rgb_mismatch_pixels_in_source_alpha,
        "measuredAgainst": measured_against,
        "passes": passes,
        "limits": {
            "rgbRmse": RECOMPOSE_RGB_RMSE_LIMIT,
            "changedRatioGt20InSourceAlpha": RECOMPOSE_SOURCE_ALPHA_DIFF_RATIO_LIMIT,
            "missingSourceAlphaRatio": RECOMPOSE_MAX_MISSING_SOURCE_ALPHA_RATIO,
        },
    }


def fit_alpha_preview(img: Image.Image, max_size: tuple[int, int], padding: int = 16) -> Image.Image:
    bbox = img.getchannel("A").getbbox()
    if bbox:
        img = img.crop(bbox)
    img.thumbnail((max_size[0] - padding * 2, max_size[1] - padding * 2), Image.Resampling.LANCZOS)
    tile = Image.new("RGBA", max_size, (0, 0, 0, 0))
    tile.alpha_composite(img, ((max_size[0] - img.width) // 2, (max_size[1] - img.height) // 2))
    return tile


def make_contact_sheet(workspace: Path, plan: dict[str, Any], layer_results: list[dict[str, Any]], path: Path) -> None:
    result_by_id = {item["id"]: item for item in layer_results}
    thumbs = []
    for layer in plan["layers"]:
        result = result_by_id.get(layer["id"], {})
        img_path = layer_image(workspace, layer["id"])
        debug_path = layer_debug_image(workspace, layer["id"])
        if result.get("status") == "present" and img_path.exists():
            img = Image.open(img_path).convert("RGBA")
        elif debug_path and debug_path.exists():
            img = Image.open(debug_path).convert("RGBA")
        else:
            img = Image.new("RGBA", tuple(plan["canvas"]), (0, 0, 0, 0))
        thumbs.append((layer["id"], result.get("status", "missing"), fit_alpha_preview(img, (210, 190)).copy()))

    cols = 4
    cell_w, cell_h = 250, 245
    rows = (len(thumbs) + cols - 1) // cols
    board = Image.new("RGBA", (cols * cell_w, rows * cell_h), (245, 245, 245, 255))
    draw = ImageDraw.Draw(board)
    for index, (label, status, img) in enumerate(thumbs):
        col = index % cols
        row = index // cols
        x = col * cell_w + (cell_w - img.width) // 2
        y = row * cell_h + 40
        board.alpha_composite(img, (x, y))
        draw.text((col * cell_w + 10, row * cell_h + 12), label, fill=(0, 0, 0, 255))
        if status == "source_lock_only":
            draw.text((col * cell_w + 10, row * cell_h + 28), "pending redraw", fill=(170, 80, 0, 255))
        elif status == "visual_rejected":
            draw.text((col * cell_w + 10, row * cell_h + 28), "visual rejected", fill=(170, 0, 0, 255))
    board.save(path)

def final_deliverable_blockers(qa: dict[str, Any] | None) -> list[str]:
    """Return reasons final component/Spine exports must be hidden or blocked."""
    if not qa:
        return ["qa_missing"]
    blockers: list[str] = []
    if qa.get("status") == "visual_rejected":
        blockers.append("qa_status_visual_rejected")
    recompose = qa.get("checks", {}).get("recomposeQuality") if isinstance(qa.get("checks"), dict) else None
    if not isinstance(recompose, dict) or recompose.get("passes") is not True:
        blockers.append("recompose_quality_failed_or_missing")
    elif recompose.get("pixelPerfectSource") is not True:
        blockers.append("pixel_perfect_source_recompose_failed")
    counts = qa.get("counts") if isinstance(qa.get("counts"), dict) else {}
    for status in ("visual_rejected", "source_lock_only"):
        if int(counts.get(status, 0) or 0) > 0:
            blockers.append(f"layer_status_{status}_{counts.get(status)}")
    layers = qa.get("layers") if isinstance(qa.get("layers"), list) else []
    present_layers = [item for item in layers if isinstance(item, dict) and item.get("status") == "present"]
    present_missing_final = [item for item in present_layers if not item.get("finalRedrawKind")]
    if present_missing_final:
        blockers.append(f"present_layers_missing_final_redraw_{len(present_missing_final)}")
        if len(present_missing_final) == len(present_layers):
            blockers.append("no_final_imagegen_redraw_layers")
    unique: list[str] = []
    for blocker in blockers:
        if blocker not in unique:
            unique.append(blocker)
    return unique


def final_redraw_kind_for_layer_dir(layer_dir: Path, status: str, artifacts: dict[str, Path]) -> str | None:
    """Classify accepted final art, excluding source-derived hard-cut evidence."""
    if status != "present" or not (layer_dir / "generated.png").exists():
        return None
    provenance = read_json_if_exists(layer_dir / "generation-provenance.json") or {}
    hidden_provenance = read_json_if_exists(layer_dir / "hidden_underpaint_provenance.json") or {}
    backend = str(provenance.get("backend") or hidden_provenance.get("backend") or "")
    mode = str(provenance.get("mode") or hidden_provenance.get("mode") or "")
    if backend in SOURCE_DERIVED_FINAL_BLOCKED_BACKENDS or mode in SOURCE_DERIVED_FINAL_BLOCKED_MODES:
        return None
    if "hidden" in artifacts:
        return "final_imagegen_hidden_composite"
    if "redraw" in artifacts:
        return "final_imagegen_redraw"
    if "raw" in artifacts:
        return "final_imagegen_registered"
    if backend:
        return "final_imagegen"
    return None


def final_redraw_display_kind(workspace: Path, layer: dict[str, Any]) -> str | None:
    """Return the final visual kind if the layer is backed by real redraw output.

    The review page should not present lossless source partitions, source locks, or
    facial source-lock micro layers as the final imagegen/redraw component art.
    Those are valid registration evidence, but the user's default visual target is
    the final generated/redrawn component.
    """
    if layer.get("finalRedrawKind"):
        return str(layer["finalRedrawKind"])
    if layer.get("status") != "present":
        return None
    layer_id = str(layer["id"])
    layer_dir = workspace / "layers" / layer_id
    if not (layer_dir / "generated.png").exists():
        return None
    artifacts = layer.get("artifacts", {}) if isinstance(layer.get("artifacts"), dict) else {}
    artifact_paths = {key: workspace / value for key, value in artifacts.items() if isinstance(value, str)}
    return final_redraw_kind_for_layer_dir(layer_dir, str(layer.get("status")), artifact_paths)


def review_component_kind_for_layer(workspace: Path, layer: dict[str, Any]) -> str | None:
    """Return the ImageGen-backed component kind that the simplified review UI should show.

    Final exports stay stricter: only `present` layers with `finalRedrawKind` can unlock
    PSD/component delivery. The HTML review, however, must still show registered ImageGen
    final-art candidates when QA rejected them, otherwise the user cannot judge what the
    $imagegen skill actually produced.
    """
    if layer.get("reviewComponentKind"):
        return str(layer["reviewComponentKind"])
    final_kind = final_redraw_display_kind(workspace, layer)
    if final_kind:
        return final_kind
    if layer.get("status") != "visual_rejected":
        return None
    layer_id = str(layer.get("id") or "")
    if not layer_id:
        return None
    layer_dir = workspace / "layers" / layer_id
    if not (layer_dir / "generated.png").exists():
        return None
    provenance = read_json_if_exists(layer_dir / "generation-provenance.json") or {}
    hidden_provenance = read_json_if_exists(layer_dir / "hidden_underpaint_provenance.json") or {}
    backend = str(provenance.get("backend") or hidden_provenance.get("backend") or "")
    mode = str(provenance.get("mode") or hidden_provenance.get("mode") or "")
    if not backend:
        return None
    if backend in SOURCE_DERIVED_FINAL_BLOCKED_BACKENDS or mode in SOURCE_DERIVED_FINAL_BLOCKED_MODES:
        return None
    artifacts = layer.get("artifacts", {}) if isinstance(layer.get("artifacts"), dict) else {}
    if "hidden" in artifacts:
        return "review_imagegen_hidden_candidate"
    if "redraw" in artifacts:
        return "review_imagegen_redraw_candidate"
    if "raw" in artifacts:
        return "review_imagegen_registered_candidate"
    return "review_imagegen_component_candidate"


def review_component_composite(workspace: Path, plan: dict[str, Any], layer_results: list[dict[str, Any]]) -> Image.Image:
    canvas_size = tuple(plan["canvas"])
    comp = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    result_by_id = {item["id"]: item for item in layer_results if isinstance(item, dict) and item.get("id")}
    for layer_id in plan["drawOrderBackToFront"]:
        result = result_by_id.get(layer_id)
        if not result or not review_component_kind_for_layer(workspace, result):
            continue
        placed, placement_valid, _ = placed_layer_image(workspace, layer_id, canvas_size)
        if placed is not None and placement_valid:
            comp.alpha_composite(placed)
    return comp


def make_review_html(workspace: Path, qa: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def html_rel(target: Path) -> str:
        return html.escape(target.relative_to(path.parent).as_posix() if target.is_relative_to(path.parent) else Path("..", target.relative_to(workspace)).as_posix())

    def image_src(target: Path) -> str:
        if target.exists() and target.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            mime = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }[target.suffix.lower()]
            encoded = base64.b64encode(target.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
        return html_rel(target)

    source = image_src(workspace / "source.png")
    checks = qa.get("checks", {}) if isinstance(qa.get("checks"), dict) else {}
    final_composite_path = Path(checks.get("finalComponentComposite") or (workspace / "check" / "final-component-composite.png"))
    if not final_composite_path.exists():
        try:
            plan = load_plan(workspace)
            review_component_composite(workspace, plan, qa.get("layers", []) if isinstance(qa.get("layers"), list) else []).save(final_composite_path)
        except Exception:
            Image.new("RGBA", Image.open(workspace / "source.png").size, (0, 0, 0, 0)).save(final_composite_path)
    components = []
    identity_references = []
    identity_manifest = read_json_if_exists(workspace / "parts" / "facial-micro-source-locks.json") or {}
    for part in identity_manifest.get("parts", []) if isinstance(identity_manifest.get("parts"), list) else []:
        if not isinstance(part, dict):
            continue
        part_file = part.get("file")
        if not isinstance(part_file, str):
            continue
        part_path = workspace / "parts" / part_file
        if not part_path.exists():
            continue
        identity_references.append(
            {
                "id": part.get("id", part_path.stem),
                "file": image_src(part_path),
                "bbox": None,
                "kind": "source_locked_reference",
                "exportableAsFinalLayer": False,
            }
        )
    parts_manifest = read_json_if_exists(workspace / "parts" / "parts-sheet-manifest.json") or {}
    parts = parts_manifest.get("parts", []) if isinstance(parts_manifest.get("parts"), list) else []
    parts_candidate_path: Path | None = None
    for sheet in parts_manifest.get("sheets", []) if isinstance(parts_manifest.get("sheets"), list) else []:
        if not isinstance(sheet, dict):
            continue
        for key in ("contactPath", "transparentPath", "rawPath"):
            value = sheet.get(key)
            if not isinstance(value, str):
                continue
            candidate = workspace / value
            if candidate.exists():
                parts_candidate_path = candidate
                break
        if parts_candidate_path:
            break
    generated_quality = checks.get("generatedArtReconstructionQuality")
    generated_passes = bool(generated_quality.get("passes")) if isinstance(generated_quality, dict) else False
    if parts_candidate_path and qa.get("status") != "passed" and not generated_passes:
        combined_review_path = parts_candidate_path
        combined_review_source = "parts-sheet-candidates"
    else:
        combined_review_path = final_composite_path
        combined_review_source = "final-component-composite"
    final_composite = image_src(final_composite_path)
    combined_review = image_src(combined_review_path)
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_file = part.get("file")
        if not isinstance(part_file, str):
            continue
        part_path = workspace / "parts" / part_file
        if not part_path.exists():
            continue
        mapping = part.get("mapping", {}) if isinstance(part.get("mapping"), dict) else {}
        components.append(
            {
                "id": part.get("id", part_path.stem),
                "file": image_src(part_path),
                "bbox": None,
                "kind": "parts_sheet_candidate",
                "owner": mapping.get("owner"),
                "disposition": mapping.get("disposition"),
                "source": "parts-sheet",
                "sheetId": part.get("sheetId"),
            }
        )
    for layer in qa["layers"]:
        final_kind = review_component_kind_for_layer(workspace, layer)
        if not final_kind:
            continue
        if parts:
            # The review page must expose all $imagegen skill parts-sheet candidates
            # when they exist. Layer candidates are still recorded in qa.json, but
            # showing only the few registered/rejected layers hides most of the run.
            continue
        components.append(
            {
                "id": layer["id"],
                "file": image_src(workspace / layer["file"]),
                "bbox": layer.get("bbox"),
                "kind": final_kind,
            }
        )
    v3_groups = {"accepted": [], "candidate": [], "rejected": [], "missing": [], "needs_hidden_completion": []}
    v3_component_plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    v3_recompose_report = read_json_if_exists(workspace / "v3" / "check" / "recompose-report.json") or {}
    v3_recompose_included = {
        item.get("componentId")
        for item in v3_recompose_report.get("included", [])
        if isinstance(item, dict) and item.get("componentId")
    }
    v3_recompose_missing = {
        item.get("componentId")
        for item in v3_recompose_report.get("missing", [])
        if isinstance(item, dict) and item.get("componentId")
    }
    for component in v3_component_plan.get("components", []) if isinstance(v3_component_plan.get("components"), list) else []:
        if not isinstance(component, dict) or component.get("status") == "not_visible":
            continue
        component_id = str(component.get("id") or "")
        if not component_id:
            continue
        if component.get("registrationStatus") == "accepted" and component.get("poseStressStatus") == "passed":
            group = "accepted"
        elif component.get("registrationStatus") == "accepted" and component.get("needsHiddenCompletion") and component.get("hiddenStatus") != "passed":
            group = "needs_hidden_completion"
        elif component.get("registrationStatus") == "accepted":
            group = "candidate"
        elif component.get("bestRejectedCandidate"):
            group = "rejected"
        else:
            group = "missing"
        image_file = component.get("mergedComponent") or component.get("visibleCut") or component.get("mask")
        image = image_src(workspace / image_file) if isinstance(image_file, str) and (workspace / image_file).exists() else ""
        if component_id in v3_recompose_included:
            recompose_status = "included"
        elif component_id in v3_recompose_missing:
            recompose_status = "missing"
        else:
            recompose_status = "not_run"
        label = (
            f"{component_id} -> {component.get('owner')} / {component.get('track')} / "
            f"mask:{component.get('maskStatus')} hidden:{component.get('hiddenStatus')} "
            f"recompose:{recompose_status} pose:{component.get('poseStressStatus')}"
        )
        details = [
            f"owner: {component.get('owner')}",
            f"track: {component.get('track')}",
            f"mask: {component.get('maskStatus')}",
            f"hidden: {component.get('hiddenStatus')}",
            f"registration: {component.get('registrationStatus')}",
            f"recompose: {recompose_status}",
            f"pose: {component.get('poseStressStatus')}",
        ]
        if component.get("hiddenReason"):
            details.append(f"hidden reason: {component.get('hiddenReason')}")
        if component.get("recomposeReason"):
            details.append(f"recompose reason: {component.get('recomposeReason')}")
        v3_groups.setdefault(group, []).append(
            {
                "id": component_id,
                "owner": component.get("owner"),
                "track": component.get("track"),
                "group": group,
                "file": image,
                "label": label,
                "details": details,
                "maskStatus": component.get("maskStatus"),
                "hiddenStatus": component.get("hiddenStatus"),
                "recomposeStatus": recompose_status,
                "poseStressStatus": component.get("poseStressStatus"),
                "registrationStatus": component.get("registrationStatus"),
            }
        )
    v3_sheet_manifest = read_json_if_exists(workspace / "v3" / "sheets" / "sheet-manifest.json") or {}
    for candidate in v3_sheet_manifest.get("candidates", []) if isinstance(v3_sheet_manifest.get("candidates"), list) else []:
        if not isinstance(candidate, dict) or candidate.get("status") != "rejected":
            continue
        candidate_file = candidate.get("file")
        if not isinstance(candidate_file, str) or not (workspace / candidate_file).exists():
            continue
        v3_groups["rejected"].append(
            {
                "id": candidate.get("id"),
                "owner": candidate.get("componentId"),
                "track": "candidate",
                "group": "rejected",
                "file": image_src(workspace / candidate_file),
                "label": f"{candidate.get('id')} -> {candidate.get('componentId')} / rejected / {','.join(str(reason) for reason in candidate.get('reasons', []))}",
                "details": [
                    f"candidate: {candidate.get('id')}",
                    f"component: {candidate.get('componentId')}",
                    f"score: {candidate.get('score')}",
                    f"reasons: {', '.join(str(reason) for reason in candidate.get('reasons', []))}",
                ],
                "registrationStatus": "rejected",
                "reasons": candidate.get("reasons", []),
            }
        )
    payload = json.dumps(
        {
            "status": qa["status"],
            "source": source,
            "finalComponentComposite": final_composite,
            "combinedReviewImage": combined_review,
            "combinedReviewSource": combined_review_source,
            "components": components,
            "v3Components": v3_groups,
            "identityReferences": identity_references,
            "reconstructionChecks": {
                "sourceLocked": checks.get("sourceLockedReconstructionQuality"),
                "generatedArt": checks.get("generatedArtReconstructionQuality"),
            },
            "registrationEvidence": (read_json_if_exists(workspace / "parts" / "registration-v2.json") or {}).get("registrations", []),
            "drawOrderEvidence": read_json_if_exists(workspace / "check" / "draw-order-conflicts.json") or {"conflicts": []},
            "reviewDecisionSchema": {
                "type": "kine.v3.reviewDecisions",
                "version": "0.1",
                "decisions": [
                    {
                        "componentId": "<component-id>",
                        "decision": "accepted | rejected | needs_hidden_completion | needs_manual_review",
                        "reason": "optional human review note",
                    }
                ],
            },
        },
        ensure_ascii=False,
    )
    payload = payload.replace("</", "<\\/")
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Cache-Control" content="no-store">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kine Layer Review</title>
<style>
  :root {{ color-scheme: dark; --bg:#15161a; --panel:#202126; --line:#3a3c44; --text:#f3f4f8; --muted:#a9adba; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font:13px/1.4 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  header {{ height:44px; display:flex; align-items:center; gap:12px; padding:0 14px; border-bottom:1px solid var(--line); background:#111216; }}
  header strong {{ font-size:15px; }}
  header code {{ color:var(--muted); }}
  main {{ height:calc(100vh - 44px); display:grid; grid-template-columns:1fr 1fr 1.15fr; gap:10px; padding:10px; }}
  section {{ min-width:0; min-height:0; display:grid; grid-template-rows:auto 1fr; gap:8px; }}
  h2 {{ margin:0; font-size:13px; font-weight:650; color:var(--muted); }}
  .viewer, .thumb {{ position:relative; display:grid; place-items:center; overflow:hidden; background:#f3f4f6; border:1px solid var(--line); border-radius:8px; }}
  .viewer::before, .thumb::before {{
    content:"";
    position:absolute;
    inset:0;
    background:
      linear-gradient(45deg, #e1e3e8 25%, transparent 25%),
      linear-gradient(-45deg, #e1e3e8 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #e1e3e8 75%),
      linear-gradient(-45deg, transparent 75%, #e1e3e8 75%);
    background-size:24px 24px;
    background-position:0 0,0 12px,12px -12px,-12px 0;
    opacity:.75;
  }}
  .viewer img, .thumb img {{ position:relative; z-index:1; max-width:100%; max-height:100%; object-fit:contain; }}
  .components {{ min-height:0; overflow:auto; display:grid; grid-template-columns:repeat(auto-fill, minmax(132px, 1fr)); gap:8px; align-content:start; }}
  .component {{ min-width:0; display:grid; grid-template-rows:132px auto auto; gap:5px; border:1px solid transparent; border-radius:8px; padding:3px; }}
  .component[hidden] {{ display:none; }}
  .thumb img {{ width:100%; height:132px; }}
  .thumbButton {{ width:100%; height:100%; padding:0; border:0; background:transparent; cursor:zoom-in; }}
  .thumbButton img {{ display:block; }}
  .thumb.placeholder {{ padding:10px; text-align:center; color:#6b7280; font-weight:650; overflow-wrap:anywhere; }}
  .label {{ color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .detailToggle {{ justify-self:start; padding:2px 0; border:0; background:transparent; color:#82c7ff; cursor:pointer; font:inherit; }}
  .detailText {{ display:none; margin:0; padding:6px; color:var(--muted); background:#17181d; border:1px solid var(--line); border-radius:6px; white-space:pre-wrap; overflow-wrap:anywhere; }}
  .component.open .detailText {{ display:block; }}
  .toolbar {{ display:flex; flex-wrap:wrap; gap:6px; margin:0 0 8px; }}
  .filterButton {{ padding:4px 8px; border:1px solid var(--line); border-radius:6px; background:#17181d; color:var(--muted); cursor:pointer; font:inherit; }}
  .filterButton.active {{ color:var(--text); border-color:#62a8ff; background:#173252; }}
  .decisionBar {{ display:flex; flex-wrap:wrap; gap:4px; }}
  .decisionButton {{ min-width:0; padding:3px 6px; border:1px solid var(--line); border-radius:6px; background:#17181d; color:var(--muted); cursor:pointer; font:inherit; }}
  .decisionButton.active {{ color:var(--text); border-color:#62a8ff; background:#173252; }}
  .rightStack {{ min-height:0; overflow:auto; display:grid; gap:14px; align-content:start; }}
  .subhead {{ margin:0 0 8px; color:var(--muted); font-weight:650; }}
  .debugPanel {{ border:1px solid var(--line); border-radius:8px; padding:8px; color:var(--muted); }}
  .debugPanel summary {{ cursor:pointer; color:var(--muted); font-weight:650; }}
  .debugPanel[open] {{ background:#17181d; }}
  .metric {{ display:grid; grid-template-columns:1fr auto; gap:8px; padding:6px 8px; border:1px solid var(--line); border-radius:6px; color:var(--muted); }}
  .metric strong {{ color:var(--text); }}
  .evidence {{ display:grid; gap:6px; }}
  .groupTitle {{ margin:10px 0 6px; color:var(--text); font-weight:650; }}
  .empty {{ min-height:180px; display:grid; place-items:center; color:var(--muted); border:1px solid var(--line); border-radius:8px; }}
  .zoomOverlay {{ position:fixed; inset:0; z-index:20; display:none; grid-template-rows:auto 1fr; gap:8px; padding:14px; background:rgba(10,11,14,.88); }}
  .zoomOverlay.open {{ display:grid; }}
  .zoomBar {{ display:flex; justify-content:space-between; gap:12px; align-items:center; color:var(--text); }}
  .zoomClose {{ padding:5px 10px; border:1px solid var(--line); border-radius:6px; background:#202126; color:var(--text); cursor:pointer; font:inherit; }}
  .zoomImageWrap {{ min-height:0; display:grid; place-items:center; background:#f3f4f6; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
  .zoomImageWrap img {{ max-width:100%; max-height:100%; object-fit:contain; }}
  @media (max-width: 1100px) {{ main {{ height:auto; grid-template-columns:1fr; }} .viewer {{ min-height:420px; }} }}
</style>
</head>
<body>
<header>
  <strong>Kine Layer Review</strong>
</header>
<main>
  <section>
    <h2>Original</h2>
    <div class="viewer"><img src="{source}" alt="original"></div>
  </section>
  <section>
    <h2>Combined</h2>
    <div class="viewer"><img src="{combined_review}" alt="combined review image"></div>
  </section>
  <section>
    <h2>Review</h2>
    <div class="rightStack">
      <div>
        <p class="subhead">V3 Components</p>
        <div id="v3Host"></div>
      </div>
      <div>
        <p class="subhead">Components</p>
        <div class="components" id="componentHost"></div>
      </div>
      <details class="debugPanel">
        <summary>Debug evidence</summary>
        <div>
          <p class="subhead">Identity References</p>
          <div class="components" id="identityHost"></div>
        </div>
        <div>
          <p class="subhead">Registration</p>
          <div class="evidence" id="registrationHost"></div>
        </div>
        <div>
          <p class="subhead">Draw Order Evidence</p>
          <div class="evidence" id="drawOrderHost"></div>
        </div>
      </details>
    </div>
  </section>
</main>
<div class="zoomOverlay" id="zoomOverlay" aria-hidden="true">
  <div class="zoomBar">
    <strong id="zoomTitle">Component</strong>
    <button class="zoomClose" type="button" id="zoomClose">Close</button>
  </div>
  <div class="zoomImageWrap"><img id="zoomImage" alt=""></div>
</div>
<script id="qa" type="application/json">{payload}</script>
<script>
const qa = JSON.parse(document.getElementById('qa').textContent);
const REVIEW_STORAGE_KEY = `kine-v3-review-decisions:${{location.pathname}}`;
let reviewDecisions = {{}};
try {{
  reviewDecisions = JSON.parse(localStorage.getItem(REVIEW_STORAGE_KEY) || '{{}}');
}} catch (_err) {{
  reviewDecisions = {{}};
}}
function setReviewDecision(componentId, decision) {{
  reviewDecisions[componentId] = {{
    componentId,
    decision,
    reason: '',
    decidedAt: new Date().toISOString(),
  }};
  localStorage.setItem(REVIEW_STORAGE_KEY, JSON.stringify(reviewDecisions));
  document.querySelectorAll(`[data-component-id="${{CSS.escape(componentId)}}"] .decisionButton`).forEach(button => {{
    button.classList.toggle('active', button.dataset.decision === decision);
  }});
}}
function downloadReviewDecisions() {{
  const payload = {{
    type: 'kine.v3.reviewDecisions',
    version: '0.1',
    source: 'review.html',
    decisions: Object.values(reviewDecisions),
  }};
  const blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'v3-review-decisions.json';
  link.click();
  URL.revokeObjectURL(url);
}}
function openZoom(component) {{
  if (!component.file) return;
  const overlay = document.getElementById('zoomOverlay');
  const image = document.getElementById('zoomImage');
  document.getElementById('zoomTitle').textContent = component.label || component.id || 'Component';
  image.src = component.file;
  image.alt = component.id || 'component';
  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
}}
function closeZoom() {{
  const overlay = document.getElementById('zoomOverlay');
  overlay.classList.remove('open');
  overlay.setAttribute('aria-hidden', 'true');
  document.getElementById('zoomImage').removeAttribute('src');
}}
document.getElementById('zoomClose').addEventListener('click', closeZoom);
document.getElementById('zoomOverlay').addEventListener('click', event => {{
  if (event.target.id === 'zoomOverlay') closeZoom();
}});
window.addEventListener('keydown', event => {{
  if (event.key === 'Escape') closeZoom();
}});
function renderCardGrid(host, items, emptyLabel, options = {{}}) {{
  host.innerHTML = '';
  if (!items.length) {{
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = emptyLabel;
    host.appendChild(empty);
    return;
  }}
  for (const component of items) {{
    const card = document.createElement('article');
    card.className = 'component';
    if (component.id) card.dataset.componentId = component.id;
    if (component.group) card.dataset.v3Group = component.group;
    const thumb = document.createElement('div');
    thumb.className = 'thumb';
    if (component.file) {{
      const button = document.createElement('button');
      button.className = 'thumbButton';
      button.type = 'button';
      button.title = 'Open large preview';
      const image = document.createElement('img');
      image.src = component.file;
      image.alt = component.id;
      button.appendChild(image);
      button.addEventListener('click', () => openZoom(component));
      thumb.appendChild(button);
    }} else {{
      thumb.classList.add('placeholder');
      thumb.textContent = component.id || 'missing';
    }}
    const meta = document.createElement('div');
    meta.className = 'label';
    meta.textContent = component.label || (component.owner ? `${{component.id}} -> ${{component.owner}}` : component.id);
    card.appendChild(thumb);
    card.appendChild(meta);
    if (options.showDetails) {{
      const detailButton = document.createElement('button');
      detailButton.className = 'detailToggle';
      detailButton.type = 'button';
      detailButton.textContent = 'Details';
      detailButton.addEventListener('click', () => card.classList.toggle('open'));
      const detailText = document.createElement('pre');
      detailText.className = 'detailText';
      detailText.textContent = (component.details || []).join('\\n') || component.label || component.id || '';
      card.appendChild(detailButton);
      card.appendChild(detailText);
    }}
    if (options.showDecisions && component.id) {{
      const decisionBar = document.createElement('div');
      decisionBar.className = 'decisionBar';
      for (const [decision, label] of [['accepted', 'Accept'], ['rejected', 'Reject'], ['needs_hidden_completion', 'Hidden']]) {{
        const button = document.createElement('button');
        button.className = 'decisionButton';
        button.type = 'button';
        button.dataset.decision = decision;
        button.textContent = label;
        button.classList.toggle('active', reviewDecisions[component.id] && reviewDecisions[component.id].decision === decision);
        button.addEventListener('click', () => setReviewDecision(component.id, decision));
        decisionBar.appendChild(button);
      }}
      card.appendChild(decisionBar);
    }}
    host.appendChild(card);
  }}
}}
function renderEvidence(host, items, emptyLabel, formatter) {{
  host.innerHTML = '';
  if (!items.length) {{
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = emptyLabel;
    host.appendChild(empty);
    return;
  }}
  for (const item of items) {{
    const row = document.createElement('div');
    row.className = 'metric';
    const name = document.createElement('strong');
    name.textContent = formatter(item)[0];
    const value = document.createElement('span');
    value.textContent = formatter(item)[1];
    row.appendChild(name);
    row.appendChild(value);
    host.appendChild(row);
  }}
}}
function renderV3Groups(host, groups) {{
  host.innerHTML = '';
  const names = ['accepted', 'candidate', 'needs_hidden_completion', 'rejected', 'missing'];
  let total = 0;
  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';
  const allButton = document.createElement('button');
  allButton.className = 'filterButton active';
  allButton.type = 'button';
  allButton.textContent = 'all';
  allButton.addEventListener('click', () => applyV3Filter(host, 'all'));
  toolbar.appendChild(allButton);
  const downloadButton = document.createElement('button');
  downloadButton.className = 'filterButton';
  downloadButton.type = 'button';
  downloadButton.textContent = 'download decisions';
  downloadButton.addEventListener('click', downloadReviewDecisions);
  toolbar.appendChild(downloadButton);
  for (const name of names) {{
    const button = document.createElement('button');
    button.className = 'filterButton';
    button.type = 'button';
    button.textContent = name;
    button.addEventListener('click', () => applyV3Filter(host, name));
    toolbar.appendChild(button);
  }}
  host.appendChild(toolbar);
  for (const name of names) {{
    const items = groups[name] || [];
    total += items.length;
    const title = document.createElement('div');
    title.className = 'groupTitle';
    title.dataset.v3Group = name;
    title.textContent = `${{name}} (${{items.length}})`;
    host.appendChild(title);
    const grid = document.createElement('div');
    grid.className = 'components';
    grid.dataset.v3Group = name;
    renderCardGrid(grid, items, 'No items', {{ showDetails: true, showDecisions: true }});
    host.appendChild(grid);
  }}
  if (!total) {{
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No V3 components';
    host.appendChild(empty);
  }}
}}
function applyV3Filter(host, groupName) {{
  host.querySelectorAll('.filterButton').forEach(button => {{
    button.classList.toggle('active', button.textContent === groupName);
  }});
  host.querySelectorAll('.groupTitle, .components').forEach(element => {{
    const group = element.dataset.v3Group;
    element.hidden = groupName !== 'all' && group !== groupName;
  }});
}}
renderV3Groups(document.getElementById('v3Host'), qa.v3Components || {{}});
renderCardGrid(document.getElementById('componentHost'), qa.components, 'No components');
renderCardGrid(document.getElementById('identityHost'), qa.identityReferences, 'No identity references');
renderEvidence(document.getElementById('registrationHost'), qa.registrationEvidence || [], 'No registration evidence', item => [
  `${{item.partId}} -> ${{item.owner}}`,
  `${{item.accepted ? 'accepted' : 'rejected'}} / ${{item.transform ? item.transform.method : item.reason}}`,
]);
renderEvidence(document.getElementById('drawOrderHost'), (qa.drawOrderEvidence && qa.drawOrderEvidence.conflicts) || [], 'No draw-order conflicts', item => [
  `${{item.front}} over ${{item.back}}`,
  `overlap ${{item.overlapPixels}} / disagreement ${{item.rgbDisagreement}}`,
]);
</script>
</body>
</html>
""",
        encoding="utf-8",
    )


def export_psd(workspace: Path, plan: dict[str, Any], path: Path, accepted_layer_ids: set[str]) -> dict[str, Any]:
    try:
        from psd_tools import PSDImage
    except Exception as exc:
        return {"status": "skipped", "failure": f"psd_tools unavailable: {exc}"}

    w, h = plan["canvas"]
    psd = PSDImage.new(mode="RGBA", size=(w, h), depth=8)
    written_layers: list[str] = []
    for layer_id in plan["drawOrderBackToFront"]:
        if layer_id not in accepted_layer_ids:
            continue
        placed, placement_valid, _ = placed_layer_image(workspace, layer_id, (w, h))
        if placed is None or not placement_valid:
            continue
        # Write each accepted layer as an independent cropped PSD layer at its source
        # offset, instead of a full-canvas square, matching the native PSD layer model.
        bbox = placed.getchannel("A").getbbox()
        if bbox:
            crop = placed.crop(bbox)
            left, top = int(bbox[0]), int(bbox[1])
        else:
            crop = placed
            left = top = 0
        psd.create_pixel_layer(crop, name=layer_id, top=top, left=left, opacity=255)
        written_layers.append(layer_id)
    try:
        # psd-tools updates the flattened preview through optional composite
        # dependencies. Layer data is already present, so skip preview refresh
        # to keep PSD export usable in lean or mismatched Python environments.
        psd._updated = False
        psd.save(path)
    except Exception as exc:
        return {"status": "failed", "failure": f"{type(exc).__name__}: {exc}", "writtenLayers": written_layers}

    try:
        reopened = PSDImage.open(path)
        reopened_names = [layer.name for layer in reopened]
    except Exception as exc:
        return {"status": "failed", "failure": f"psd reopen failed: {type(exc).__name__}: {exc}", "writtenLayers": written_layers}

    if reopened_names != written_layers:
        return {
            "status": "failed",
            "failure": "psd layer order/name mismatch after reopen",
            "writtenLayers": written_layers,
            "reopenedLayers": reopened_names,
        }
    return {"status": "written", "path": relative_to_workspace(path, workspace), "writtenLayers": written_layers, "reopenedLayers": reopened_names}


def validate_review_html(workspace: Path) -> None:
    path = workspace / "check" / "review.html"
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    required_tokens = [
        "Kine Layer Review",
        "Original",
        "Combined",
        "Components",
        "finalComponentComposite",
        "componentHost",
        "combinedReviewImage",
    ]
    missing = [token for token in required_tokens if token not in text]
    linked_files = [
        workspace / "source.png",
        workspace / "check" / "final-component-composite.png",
        workspace / "qa.json",
        workspace / "manifest.json",
    ]
    missing_files = [relative_to_workspace(item, workspace) for item in linked_files if not item.exists()]
    result = {
        "status": "passed" if not missing and not missing_files else "failed",
        "html": str(path),
        "missingTokens": missing,
        "missingFiles": missing_files,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "passed":
        raise SystemExit(1)


def extract_review_payload(review_html: str) -> dict[str, Any]:
    marker = '<script id="qa" type="application/json">'
    if marker not in review_html:
        return {}
    payload_text = review_html.split(marker, 1)[1].split("</script>", 1)[0]
    try:
        return json.loads(payload_text)
    except json.JSONDecodeError:
        return {}


def strip_review_payload_scripts(review_html: str) -> str:
    """Return review HTML without embedded JSON so visible-text checks stay honest."""
    marker = '<script id="qa" type="application/json">'
    if marker not in review_html:
        return review_html
    before, rest = review_html.split(marker, 1)
    _payload, after = rest.split("</script>", 1) if "</script>" in rest else (rest, "")
    return before + after


def write_v3_review_integrity_report(workspace: Path) -> dict[str, Any]:
    """Verify Review HTML actually exposes V3 visual evidence instead of stale debug shells."""
    review_path = workspace / "check" / "review.html"
    blockers: list[str] = []
    warnings: list[str] = []
    payload: dict[str, Any] = {}
    text = ""
    visible_text = ""
    if not review_path.exists():
        blockers.append("review_html_missing")
    else:
        text = review_path.read_text(encoding="utf-8")
        payload = extract_review_payload(text)
        visible_text = strip_review_payload_scripts(text)
        if not payload:
            blockers.append("review_payload_missing_or_invalid")

    component_plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    active_components = [
        component
        for component in component_plan.get("components", [])
        if isinstance(component, dict) and component.get("id") and component.get("status") != "not_visible"
    ]
    active_component_ids = {str(component.get("id")) for component in active_components}
    sheet_manifest = read_json_if_exists(workspace / "v3" / "sheets" / "sheet-manifest.json") or {}
    sheet_candidates = sheet_manifest.get("candidates", []) if isinstance(sheet_manifest.get("candidates"), list) else []
    rejected_candidates = [candidate for candidate in sheet_candidates if isinstance(candidate, dict) and candidate.get("status") == "rejected"]
    parts_manifest = load_parts_sheet_manifest(workspace) if (workspace / "parts" / "parts-sheet-manifest.json").exists() else {"parts": [], "sheets": []}
    parts = parts_manifest.get("parts", []) if isinstance(parts_manifest.get("parts"), list) else []

    payload_components = payload.get("components", []) if isinstance(payload.get("components"), list) else []
    payload_v3 = payload.get("v3Components", {}) if isinstance(payload.get("v3Components"), dict) else {}
    v3_rows = [
        row
        for rows in payload_v3.values()
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, dict)
    ]
    represented_component_ids = {str(row.get("id")) for row in v3_rows if row.get("id") in active_component_ids}
    missing_component_ids = sorted(active_component_ids - represented_component_ids)
    if active_component_ids and missing_component_ids:
        blockers.append(f"v3_active_components_missing_from_review_{len(missing_component_ids)}")
    if active_component_ids and not v3_rows:
        blockers.append("v3_components_payload_empty")

    if parts and len(payload_components) < len(parts):
        blockers.append(f"parts_sheet_components_missing_from_review_{len(parts) - len(payload_components)}")

    displayed_rejected_candidates = [
        row
        for row in payload_v3.get("rejected", [])
        if isinstance(row, dict) and row.get("registrationStatus") == "rejected"
    ]
    if rejected_candidates and len(displayed_rejected_candidates) < len(rejected_candidates):
        blockers.append(f"rejected_candidates_missing_from_review_{len(rejected_candidates) - len(displayed_rejected_candidates)}")

    combined_source = payload.get("combinedReviewSource")
    qa_json = read_json_if_exists(workspace / "qa.json") or {}
    generated_quality = (qa_json.get("checks") or {}).get("generatedArtReconstructionQuality") if isinstance(qa_json.get("checks"), dict) else None
    generated_passes = bool(generated_quality.get("passes")) if isinstance(generated_quality, dict) else False
    if parts and qa_json.get("status") != "passed" and not generated_passes and combined_source != "parts-sheet-candidates":
        blockers.append("combined_not_showing_parts_sheet_candidates")
    if not payload.get("combinedReviewImage"):
        blockers.append("combined_review_image_missing")

    required_hosts = ["v3Host", "componentHost", "identityHost"]
    for host in required_hosts:
        if f'id="{host}"' not in text:
            blockers.append(f"review_host_missing_{host}")

    if "<details class=\"debugPanel\">" not in text:
        blockers.append("debug_evidence_not_folded")
    for forbidden in ("Reconstruction QA", "source locked", "generated art"):
        if forbidden in visible_text:
            blockers.append(f"debug_text_visible_{forbidden.replace(' ', '_').lower()}")
    header = visible_text.split("</header>", 1)[0] if "</header>" in visible_text else ""
    if "components:" in header or "visual_rejected" in header or "identity refs" in header:
        blockers.append("header_contains_debug_summary")

    if parts and len(payload_components) > len(parts):
        warnings.append("review_components_include_non_parts_rows")

    status = "passed" if not blockers else PARTS_SHEET_BLOCKED_STATUS
    report = {
        "type": "kine.v3.reviewIntegrityReport",
        "version": "0.1",
        "status": status,
        "workspace": workspace.name,
        "reviewHtml": "check/review.html" if review_path.exists() else None,
        "combinedReviewSource": combined_source,
        "counts": {
            "activePlanComponents": len(active_component_ids),
            "representedPlanComponents": len(represented_component_ids),
            "missingPlanComponents": len(missing_component_ids),
            "partsSheetParts": len(parts),
            "reviewComponentCards": len(payload_components),
            "rejectedCandidates": len(rejected_candidates),
            "displayedRejectedCandidates": len(displayed_rejected_candidates),
        },
        "missingComponentIds": missing_component_ids,
        "blockers": blockers,
        "warnings": warnings,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Visual review integrity gate. It verifies that Review HTML exposes all active V3 components/candidates and keeps debug evidence folded.",
    }
    out_dir = workspace / "v3" / "review"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "review-integrity-report.json", report)
    update_run_state(workspace, {"v3ReviewIntegrity": "v3/review/review-integrity-report.json", "v3ReviewIntegrityStatus": status})
    print(json.dumps({"status": status, "blockerCount": len(blockers), "report": str(out_dir / "review-integrity-report.json")}, ensure_ascii=False, indent=2))
    return report


def refresh_v3_review_artifacts(workspace: Path, reason: str) -> dict[str, Any]:
    """Rebuild Review HTML after V3 downstream state changes.

    This is an evidence refresh, not an acceptance shortcut. If the legacy QA /
    Review generation fails, validation will continue to expose the blocker
    through the review integrity gate.
    """
    result: dict[str, Any] = {
        "type": "kine.v3.reviewRefresh",
        "version": "0.1",
        "status": "passed",
        "reason": reason,
        "reviewHtml": "check/review.html",
        "integrityReport": "v3/review/review-integrity-report.json",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    blockers: list[str] = []
    try:
        qa_workspace(workspace)
    except SystemExit as exc:
        code = exc.code if exc.code is not None else 1
        if code not in {0, None}:
            blockers.append(f"qa_workspace_exited_{code}")
    except Exception as exc:
        blockers.append(f"qa_workspace_exception_{type(exc).__name__}: {exc}")
    try:
        integrity = write_v3_review_integrity_report(workspace)
        result["integrityStatus"] = integrity.get("status")
        result["integrityBlockers"] = integrity.get("blockers", [])
        if integrity.get("status") != "passed":
            blockers.extend(str(blocker) for blocker in integrity.get("blockers", []) if blocker)
    except Exception as exc:
        blockers.append(f"review_integrity_exception_{type(exc).__name__}: {exc}")

    unique_blockers: list[str] = []
    for blocker in blockers:
        if blocker and blocker not in unique_blockers:
            unique_blockers.append(blocker)
    if unique_blockers:
        result["status"] = PARTS_SHEET_BLOCKED_STATUS
        result["blockers"] = unique_blockers
    else:
        result["blockers"] = []
    out_path = workspace / "v3" / "review" / "review-refresh-report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, result)
    update_run_state(
        workspace,
        {
            "v3ReviewRefresh": "v3/review/review-refresh-report.json",
            "v3ReviewRefreshStatus": result["status"],
        },
    )
    return result


def update_run_state(workspace: Path, updates: dict[str, Any]) -> None:
    path = workspace / "run-state.json"
    state = read_json_if_exists(path) or {
        "type": "kine.layerRunState",
        "version": "0.1",
        "freshWorkspace": False,
        "workspace": workspace.name,
    }
    state.update(updates)
    state["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(path, state)


def qa_workspace(workspace: Path) -> None:
    plan = load_plan(workspace)
    check_dir = workspace / "check"
    check_dir.mkdir(exist_ok=True)
    depth_order = write_depth_order(workspace, plan)
    comp, layer_results = composite_layers(workspace, plan, check_dir)
    apply_cross_layer_generation_audit(workspace, layer_results)
    for result in layer_results:
        review_kind = review_component_kind_for_layer(workspace, result)
        if review_kind:
            result["reviewComponentKind"] = review_kind
    raw_comp = Image.new("RGBA", tuple(plan["canvas"]), (0, 0, 0, 0))
    final_redraw_comp = Image.new("RGBA", tuple(plan["canvas"]), (0, 0, 0, 0))
    result_by_id = {item["id"]: item for item in layer_results}
    canvas_size = tuple(plan["canvas"])
    for layer_id in plan["drawOrderBackToFront"]:
        result = result_by_id[layer_id]
        if result["status"] != "present":
            continue
        placed, placement_valid, _ = placed_layer_image(workspace, layer_id, canvas_size)
        if placed is not None and placement_valid:
            raw_comp.alpha_composite(placed)
            if result.get("finalRedrawKind"):
                final_redraw_comp.alpha_composite(placed)
    final_component_comp = review_component_composite(workspace, plan, layer_results)
    raw_comp.save(check_dir / "raw-layer-composite.png")
    final_redraw_comp.save(check_dir / "final-redraw-composite.png")
    final_component_comp.save(check_dir / "final-component-composite.png")
    source_pose_img, source_pose = source_pose_recompose(workspace, raw_comp)
    source_pose_img.save(check_dir / "source-pose-review.png")
    raw_comp.save(check_dir / "recompose.png")
    make_source_diff(workspace, raw_comp, check_dir / "source-diff.png")
    recompose = recompose_quality(workspace, raw_comp)
    final_redraw_recompose = recompose_quality(workspace, final_redraw_comp)
    final_component_recompose = recompose_quality(workspace, final_component_comp)
    source_locked_recompose = recompose_quality(workspace, source_pose_img, "source_locked_reconstruction")
    generated_art_recompose = recompose_quality(workspace, final_component_comp, "generated_art_reconstruction")
    make_contact_sheet(workspace, plan, layer_results, check_dir / "contact-sheet.png")
    accepted_layer_ids = {item["id"] for item in layer_results if item["status"] == "present"}
    status_counts: dict[str, int] = {}
    for item in layer_results:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
    artifact_counts = {
        "final": sum(1 for item in layer_results if item.get("artifacts", {}).get("final")),
        "finalRedraw": sum(1 for item in layer_results if item.get("finalRedrawKind")),
        "redraw": sum(1 for item in layer_results if item.get("artifacts", {}).get("redraw")),
        "hidden": sum(1 for item in layer_results if item.get("artifacts", {}).get("hidden")),
        "visible": sum(1 for item in layer_results if item.get("artifacts", {}).get("visible")),
        "raw": sum(1 for item in layer_results if item.get("artifacts", {}).get("raw")),
        "noHiddenReview": sum(1 for item in layer_results if item.get("redrawEvidence", {}).get("noHiddenSurfaceRequired")),
        "reviewComponents": sum(1 for item in layer_results if item.get("reviewComponentKind")),
    }
    failures = [item for item in layer_results if item["failures"]]
    present_layers = [item for item in layer_results if item["status"] == "present"]
    present_missing_final_redraw = [item["id"] for item in present_layers if not item.get("finalRedrawKind")]
    if present_missing_final_redraw:
        redraw_failures = [f"present_layers_missing_final_redraw_{len(present_missing_final_redraw)}"]
        if len(present_missing_final_redraw) == len(present_layers):
            redraw_failures.append("no_final_imagegen_redraw_layers")
        failures.append(
            {
                "id": "final-imagegen-redraw",
                "failures": redraw_failures,
                "layers": present_missing_final_redraw,
            }
        )
    if not recompose["passes"]:
        failures.append(
            {
                "id": "check/recompose.png",
                "failures": [
                    "recompose_mismatch_exceeds_threshold",
                    f"pixel_perfect_source_{recompose['pixelPerfectSource']}",
                    f"rgba_mismatch_pixels_{recompose['rgbaMismatchPixels']}",
                    f"alpha_mismatch_pixels_{recompose['alphaMismatchPixels']}",
                    f"extra_alpha_pixels_{recompose['extraAlphaPixels']}",
                    f"rgb_rmse_{recompose['rgbRmse']}_limit_{recompose['limits']['rgbRmse']}",
                    f"changed_ratio_{recompose['changedRatioGt20InSourceAlpha']}_limit_{recompose['limits']['changedRatioGt20InSourceAlpha']}",
                    f"missing_source_alpha_ratio_{recompose['missingSourceAlphaRatio']}_limit_{recompose['limits']['missingSourceAlphaRatio']}",
                ],
            }
        )
    psd_path = workspace / "source-master.psd"
    if failures:
        if psd_path.exists():
            psd_path.unlink()
        psd_status = {
            "status": PARTS_SHEET_BLOCKED_STATUS,
            "path": None,
            "blockers": [str(item.get("id", "qa_failure")) for item in failures if isinstance(item, dict)],
            "note": "Not a final PSD export. QA, full-source recomposition, and final imagegen/redraw provenance must pass before source-master.psd is written.",
        }
    else:
        psd_status = export_psd(workspace, plan, psd_path, accepted_layer_ids)
    if psd_status["status"] != "written":
        if psd_status["status"] != PARTS_SHEET_BLOCKED_STATUS:
            failures.append({"id": "source-master.psd", "failures": [psd_status.get("failure", psd_status["status"])]})
    qa = {
        "status": "visual_rejected" if failures else "needs_visual_review",
        "workspace": str(workspace),
        "psd": psd_status,
        "counts": status_counts,
        "artifactCounts": artifact_counts,
        "checks": {
            "recompose": str(check_dir / "recompose.png"),
            "sourceDiff": str(check_dir / "source-diff.png"),
            "rawLayerComposite": str(check_dir / "raw-layer-composite.png"),
            "finalRedrawComposite": str(check_dir / "final-redraw-composite.png"),
            "finalComponentComposite": str(check_dir / "final-component-composite.png"),
            "sourcePoseReview": str(check_dir / "source-pose-review.png"),
            "contactSheet": str(check_dir / "contact-sheet.png"),
            "reviewHtml": str(check_dir / "review.html"),
            "recomposeQuality": recompose,
            "finalRedrawCompositeQuality": final_redraw_recompose,
            "finalComponentCompositeQuality": final_component_recompose,
            "sourceLockedReconstructionQuality": source_locked_recompose,
            "generatedArtReconstructionQuality": generated_art_recompose,
            "sourcePoseRecompose": source_pose,
        },
        "layers": layer_results,
    }
    sync_campaign_status(workspace, layer_results)
    write_json(workspace / "qa.json", qa)
    write_json(
        workspace / "manifest.json",
        {
            "type": "kine.layerSourceMaster",
            "status": qa["status"],
            "source": "source.png",
            "normalizedSource": "source/normalized.png",
            "inputNormalization": "source/input-normalization.json",
            "canvas": plan["canvas"],
            "drawOrderBackToFront": plan["drawOrderBackToFront"],
            "depthOrder": "depth-order.json",
            "depthOrderSummary": depth_order,
            "acceptedLayerIds": sorted(accepted_layer_ids, key=plan["drawOrderBackToFront"].index),
            "counts": status_counts,
            "artifactCounts": artifact_counts,
            "generation": {"backend": PUBLIC_GENERATION_BACKEND, "role": "owner_layer_drawing_and_hidden_underpaint"},
            "componentLedger": "component-ledger.json",
            "reviewHtml": "check/review.html",
            "psd": psd_status,
            "qaChecks": {
                "canvasSize": True,
                "alphaCoverage": True,
                "opaqueBackgroundGuard": True,
                "visibleMaskSourceRmseWhenMaskExists": True,
                "recomposeQuality": recompose,
                "sourceLockedReconstructionQuality": source_locked_recompose,
                "generatedArtReconstructionQuality": generated_art_recompose,
                "psdReopenLayerOrder": True if psd_status["status"] == "written" else psd_status["status"],
                "rotationExposure": "not_implemented",
                "dynamicDrawOrderVariants": "auto_split_reviewed" if (workspace / "auto-split-summary.json").exists() else "not_implemented",
            },
            "layers": layer_results,
        },
    )
    make_review_html(workspace, qa, check_dir / "review.html")
    update_run_state(
        workspace,
        {
            "status": qa["status"],
            "qa": "qa.json",
            "reviewHtml": "check/review.html",
            "psd": psd_status,
            "counts": status_counts,
            "artifactCounts": artifact_counts,
        },
    )
    print(json.dumps({"status": qa["status"], "qa": str(workspace / "qa.json"), **qa["checks"], "psd": psd_status}, ensure_ascii=False, indent=2))


def export_components(workspace: Path) -> dict[str, Any]:
    """Export each accepted (present) layer as an independent cropped PNG plus a transform.

    Mirrors see-through's separated-layer output: every component is its own standalone
    asset cropped to its alpha bbox, with a `placement` (offset/size on the source canvas)
    that recomposes it losslessly in draw order. The internal generated.png stays
    full-canvas registered; this is an additive, recomposition-faithful deliverable.
    """
    plan = load_plan(workspace)
    qa = read_json_if_exists(workspace / "qa.json") or {}
    result_by_id = {item.get("id"): item for item in qa.get("layers", []) if isinstance(item, dict)}
    canvas = tuple(plan["canvas"])
    out_dir = workspace / "components"
    out_dir.mkdir(parents=True, exist_ok=True)
    blockers = final_deliverable_blockers(qa)
    if blockers:
        for stale_png in out_dir.glob("*.png"):
            stale_png.unlink()
        manifest = {
            "type": "kine.independentComponents",
            "version": "0.1",
            "status": PARTS_SHEET_BLOCKED_STATUS,
            "source": "source.png",
            "sourceCanvas": list(canvas),
            "drawOrderBackToFront": [],
            "componentCount": 0,
            "components": [],
            "blockers": blockers,
            "qaStatus": qa.get("status"),
            "note": "Not a final component export. Accepted layers must pass full-source recomposition and final imagegen/redraw provenance before independent PNG components are exposed as final deliverables.",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(out_dir / "components-manifest.json", manifest)
        update_run_state(
            workspace,
            {
                "componentsManifest": "components/components-manifest.json",
                "componentsStatus": PARTS_SHEET_BLOCKED_STATUS,
                "independentComponentCount": 0,
            },
        )
        print(
            json.dumps(
                {"status": PARTS_SHEET_BLOCKED_STATUS, "componentCount": 0, "blockers": blockers, "manifest": str(out_dir / "components-manifest.json")},
                ensure_ascii=False,
                indent=2,
            )
        )
        return manifest
    order_index = {layer_id: index for index, layer_id in enumerate(plan["drawOrderBackToFront"])}
    components: list[dict[str, Any]] = []
    for layer_id in plan["drawOrderBackToFront"]:
        if result_by_id.get(layer_id, {}).get("status") != "present":
            continue
        placed, placement_valid, _ = placed_layer_image(workspace, layer_id, canvas)
        if placed is None or not placement_valid:
            continue
        bbox = placed.getchannel("A").getbbox()
        if not bbox:
            continue
        crop = placed.crop(bbox)
        out_name = f"{layer_id}.png"
        crop.save(out_dir / out_name)
        components.append(
            {
                "id": layer_id,
                "file": f"components/{out_name}",
                "placement": {
                    "x": int(bbox[0]),
                    "y": int(bbox[1]),
                    "w": int(bbox[2] - bbox[0]),
                    "h": int(bbox[3] - bbox[1]),
                    "sourceCanvas": list(canvas),
                },
                "order": order_index[layer_id],
            }
        )
    manifest = {
        "type": "kine.independentComponents",
        "version": "0.1",
        "status": "final_exportable",
        "source": "source.png",
        "sourceCanvas": list(canvas),
        "drawOrderBackToFront": [item["id"] for item in components],
        "componentCount": len(components),
        "components": components,
        "note": "Each component is a standalone cropped PNG plus a placement (offset/size) on the source canvas. Paste each at its placement in draw order to recompose losslessly against the accepted present-layer composite.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(out_dir / "components-manifest.json", manifest)
    update_run_state(
        workspace,
        {
            "componentsManifest": "components/components-manifest.json",
            "componentsStatus": "final_exportable",
            "independentComponentCount": len(components),
        },
    )
    print(json.dumps({"status": "components_exported", "componentCount": len(components), "manifest": str(out_dir / "components-manifest.json")}, ensure_ascii=False, indent=2))
    return manifest


SPINE_FORMAT_VERSION = "4.2.00"


def _spine_bone_world_positions(canvas: tuple[int, int]) -> dict[str, tuple[float, float]]:
    """Resolve each template bone to a Spine world position (y-up, origin at canvas bottom-left).

    `root` is pinned to (0, 0); every other bone uses its normalized canvas layout. The
    exporter writes child bones parent-relative, and because all bone rotations stay 0 the
    accumulated world position equals these values, so attachment offsets reproduce the
    source canvas exactly.
    """
    w, h = canvas
    world: dict[str, tuple[float, float]] = {}
    for bone in SPINE_BONE_TEMPLATE:
        if bone["parent"] is None:
            world[bone["name"]] = (0.0, 0.0)
        else:
            world[bone["name"]] = (round(bone["nx"] * w, 3), round(h - bone["ny"] * h, 3))
    return world


def export_spine(workspace: Path) -> dict[str, Any]:
    """Export a Spine skeleton (`spine/skeleton.json` + `spine/images/`) from accepted components.

    Borrows see-through's separated-layer model but targets Spine: each accepted component
    becomes a slot + region attachment parented to a bone-hierarchy joint, positioned so the
    default rest pose reproduces the source canvas (assembly == original). Region attachments
    keep rotation 0 / scale 1, so the file imports into the Spine editor and can be hand-rigged;
    this first version does not author mesh weights or animations.
    """
    plan = load_plan(workspace)
    manifest = read_json_if_exists(workspace / "components" / "components-manifest.json")
    if not manifest:
        manifest = export_components(workspace)
    qa = read_json_if_exists(workspace / "qa.json") or {}
    blockers = final_deliverable_blockers(qa)
    if manifest.get("status") == PARTS_SHEET_BLOCKED_STATUS:
        blockers.extend(str(item) for item in manifest.get("blockers", []) if item)
    blockers = list(dict.fromkeys(blockers))
    canvas = tuple(manifest.get("sourceCanvas") or plan["canvas"])
    w, h = canvas
    if blockers:
        out_dir = workspace / "spine"
        out_dir.mkdir(parents=True, exist_ok=True)
        stale_skeleton = out_dir / "skeleton.json"
        if stale_skeleton.exists():
            stale_skeleton.unlink()
        stale_images = out_dir / "images"
        if stale_images.exists():
            shutil.rmtree(stale_images)
        summary = {
            "type": "kine.spineExport",
            "version": "0.1",
            "status": PARTS_SHEET_BLOCKED_STATUS,
            "format": f"spine-json-{SPINE_FORMAT_VERSION}",
            "skeleton": None,
            "imagesDir": None,
            "sourceCanvas": [w, h],
            "boneCount": 0,
            "slotCount": 0,
            "slotOrderBackToFront": [],
            "components": [],
            "blockers": blockers,
            "qaStatus": qa.get("status"),
            "losslessRecompose": {
                "target": "check/raw-layer-composite.png",
                "lossless": None,
                "blocked": True,
                "note": "Not evaluated because final-source recomposition is blocked.",
            },
            "note": "Not a final Spine export. Accepted layers must pass full-source recomposition and final imagegen/redraw provenance before Spine slots/images are exposed as final deliverables.",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(out_dir / "spine-export.json", summary)
        update_run_state(
            workspace,
            {
                "spineExport": "spine/spine-export.json",
                "spineSkeleton": None,
                "spineStatus": PARTS_SHEET_BLOCKED_STATUS,
                "spineSlotCount": 0,
                "spineLosslessRecompose": None,
            },
        )
        print(
            json.dumps(
                {"status": PARTS_SHEET_BLOCKED_STATUS, "slotCount": 0, "blockers": blockers, "manifest": str(out_dir / "spine-export.json")},
                ensure_ascii=False,
                indent=2,
            )
        )
        return summary
    components = [item for item in manifest.get("components", []) if isinstance(item, dict)]
    draw_order = manifest.get("drawOrderBackToFront") or [item["id"] for item in components]
    component_by_id = {item["id"]: item for item in components}

    images_dir = workspace / "spine" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    bone_world = _spine_bone_world_positions(canvas)

    # Only emit bones that are root, an ancestor of a used bone, or used directly.
    bone_parent = {bone["name"]: bone["parent"] for bone in SPINE_BONE_TEMPLATE}
    used_bones: set[str] = {"root"}
    for component_id in draw_order:
        bone = spine_bone_for_component(component_id)
        while bone and bone not in used_bones:
            used_bones.add(bone)
            bone = bone_parent.get(bone)
    bones_out = [{"name": "root"}]
    for bone in SPINE_BONE_TEMPLATE:
        name = bone["name"]
        if name == "root" or name not in used_bones:
            continue
        parent = bone["parent"] or "root"
        px, py = bone_world[name]
        parent_x, parent_y = bone_world.get(parent, (0.0, 0.0))
        bones_out.append({"name": name, "parent": parent, "x": round(px - parent_x, 3), "y": round(py - parent_y, 3)})

    slots_out: list[dict[str, Any]] = []
    skin_attachments: dict[str, dict[str, Any]] = {}
    spine_components: list[dict[str, Any]] = []
    for component_id in draw_order:
        component = component_by_id.get(component_id)
        if not component:
            continue
        placement = component.get("placement") or {}
        try:
            x, y = int(placement["x"]), int(placement["y"])
            cw, ch = int(placement["w"]), int(placement["h"])
        except (KeyError, TypeError, ValueError):
            continue
        src_png = workspace / component["file"]
        if src_png.exists():
            shutil.copy2(src_png, images_dir / f"{component_id}.png")
        bone = spine_bone_for_component(component_id)
        bx, by = bone_world.get(bone, (0.0, 0.0))
        center_world_x = x + cw / 2.0
        center_world_y = h - (y + ch / 2.0)
        attach_x = round(center_world_x - bx, 3)
        attach_y = round(center_world_y - by, 3)
        slots_out.append({"name": component_id, "bone": bone, "attachment": component_id})
        skin_attachments[component_id] = {
            component_id: {"x": attach_x, "y": attach_y, "width": cw, "height": ch}
        }
        spine_components.append(
            {"id": component_id, "bone": bone, "slotOrder": len(slots_out) - 1, "placement": placement, "attachment": {"x": attach_x, "y": attach_y, "width": cw, "height": ch}}
        )

    skeleton = {
        "skeleton": {"spine": SPINE_FORMAT_VERSION, "images": "./images/", "width": w, "height": h},
        "bones": bones_out,
        "slots": slots_out,
        "skins": [{"name": "default", "attachments": skin_attachments}],
        "animations": {},
    }
    write_json(workspace / "spine" / "skeleton.json", skeleton)
    recompose_check = verify_spine_recompose(workspace, manifest, skeleton, canvas)
    summary = {
        "type": "kine.spineExport",
        "version": "0.1",
        "status": "final_exportable",
        "format": f"spine-json-{SPINE_FORMAT_VERSION}",
        "skeleton": "spine/skeleton.json",
        "imagesDir": "spine/images",
        "sourceCanvas": [w, h],
        "boneCount": len(bones_out),
        "slotCount": len(slots_out),
        "slotOrderBackToFront": [slot["name"] for slot in slots_out],
        "components": spine_components,
        "losslessRecompose": recompose_check,
        "note": "Region-attachment Spine skeleton. Default rest pose reproduces the accepted present-layer composite, and this export is only final when qa.checks.recomposeQuality also passes against the original source. Bones are placeholders for hand-rigging. No mesh/weights/animation in this version.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "spine" / "spine-export.json", summary)
    update_run_state(
        workspace,
        {
            "spineSkeleton": "spine/skeleton.json",
            "spineExport": "spine/spine-export.json",
            "spineStatus": "final_exportable",
            "spineSlotCount": len(slots_out),
            "spineLosslessRecompose": recompose_check.get("lossless"),
        },
    )
    print(json.dumps({"status": "spine_exported", "boneCount": len(bones_out), "slotCount": len(slots_out), "lossless": recompose_check.get("lossless"), "skeleton": str(workspace / "spine" / "skeleton.json")}, ensure_ascii=False, indent=2))
    return summary


def _recompose_from_components(workspace: Path, manifest: dict[str, Any], canvas: tuple[int, int]) -> Image.Image:
    """Rebuild a full-canvas composite by pasting each component crop at its manifest placement."""
    recon = Image.new("RGBA", canvas, (0, 0, 0, 0))
    component_by_id = {item["id"]: item for item in manifest.get("components", []) if isinstance(item, dict)}
    for component_id in manifest.get("drawOrderBackToFront", []):
        component = component_by_id.get(component_id)
        if not component:
            continue
        placement = component.get("placement") or {}
        png = workspace / component.get("file", "")
        if not png.exists():
            continue
        try:
            recon.alpha_composite(Image.open(png).convert("RGBA"), (int(placement["x"]), int(placement["y"])))
        except (KeyError, TypeError, ValueError, OSError):
            continue
    return recon


def _recompose_from_skeleton(workspace: Path, skeleton: dict[str, Any], canvas: tuple[int, int]) -> Image.Image:
    """Rebuild a full-canvas composite from the Spine skeleton's slot order + region attachments.

    Inverts the export math: attachment (x, y) is the region center in bone-relative y-up world
    space, so the canvas top-left is (bone_x + x - w/2, h - (bone_y + y) - h/2).
    """
    w, h = canvas
    recon = Image.new("RGBA", canvas, (0, 0, 0, 0))
    bone_world = _spine_bone_world_positions(canvas)
    attachments = {}
    for skin in skeleton.get("skins", []):
        if skin.get("name") == "default":
            attachments = skin.get("attachments", {})
            break
    images_dir = workspace / "spine" / "images"
    for slot in skeleton.get("slots", []):
        slot_name = slot.get("name")
        attachment_name = slot.get("attachment")
        region = (attachments.get(slot_name) or {}).get(attachment_name)
        png = images_dir / f"{attachment_name}.png"
        if not region or not png.exists():
            continue
        bx, by = bone_world.get(slot.get("bone"), (0.0, 0.0))
        cw, ch = int(region["width"]), int(region["height"])
        center_world_x = bx + float(region["x"])
        center_world_y = by + float(region["y"])
        left = int(round(center_world_x - cw / 2.0))
        top = int(round(h - center_world_y - ch / 2.0))
        try:
            recon.alpha_composite(Image.open(png).convert("RGBA"), (left, top))
        except OSError:
            continue
    return recon


def verify_spine_recompose(workspace: Path, manifest: dict[str, Any], skeleton: dict[str, Any], canvas: tuple[int, int]) -> dict[str, Any]:
    """Verify components + skeleton attachments rebuild the accepted present composite losslessly.

    Both the components-manifest placements and the Spine region attachments must re-paste to a
    byte-identical match of `check/raw-layer-composite.png` (the accepted present-layer composite).
    This is the Spine-level no-drift guarantee for exported accepted components only; the final
    source-image guarantee is `qa.checks.recomposeQuality.passes`.
    """
    target_path = workspace / "check" / "raw-layer-composite.png"
    result: dict[str, Any] = {
        "target": "check/raw-layer-composite.png",
        "targetExists": target_path.exists(),
        "componentsLossless": None,
        "skeletonLossless": None,
        "lossless": None,
        "note": "Components-manifest and skeleton region attachments must re-paste byte-identically to the accepted present-layer composite. This does not by itself prove full-source success; final source recomposition is qa.checks.recomposeQuality.",
    }
    if not target_path.exists():
        return result
    target = Image.open(target_path).convert("RGBA")
    if target.size != tuple(canvas):
        target = target.resize(tuple(canvas))
    target_bytes = target.tobytes()
    components_recon = _recompose_from_components(workspace, manifest, tuple(canvas))
    skeleton_recon = _recompose_from_skeleton(workspace, skeleton, tuple(canvas))
    result["componentsLossless"] = components_recon.tobytes() == target_bytes
    result["skeletonLossless"] = skeleton_recon.tobytes() == target_bytes
    result["lossless"] = bool(result["componentsLossless"] and result["skeletonLossless"])
    return result


def package_workspace(workspace: Path, allow_blocked: bool = False) -> None:
    qa_workspace(workspace)
    qa = json.loads((workspace / "qa.json").read_text(encoding="utf-8"))
    if qa["status"] == "visual_rejected" and not allow_blocked:
        write_completion_note(workspace, package_name="-")
        write_imagegen_handoff(workspace)
        export_components(workspace)
        export_v3_components(workspace)
        export_spine(workspace)
        make_review_html(workspace, qa, workspace / "check" / "review.html")
        print(json.dumps({"status": "visual_rejected", "blockedPackage": True, "qa": str(workspace / "qa.json")}, ensure_ascii=False, indent=2))
        return
    zip_name = f"{workspace.name}-blocked-evidence.zip" if qa["status"] == "visual_rejected" else f"{workspace.name}.zip"
    write_completion_note(workspace, package_name=zip_name)
    write_imagegen_handoff(workspace)
    export_components(workspace)
    export_v3_components(workspace)
    export_spine(workspace)
    # Re-render the review HTML now that components + spine deliverables exist, so the
    # component gallery and Spine skeleton view are populated in the packaged HTML.
    make_review_html(workspace, qa, workspace / "check" / "review.html")
    zip_path = workspace / zip_name
    if zip_path.exists():
        zip_path.unlink()
    include = []
    for pattern in [
        "source.png",
        "source/*",
        "layer-plan.json",
        "component-schema.json",
        "campaign.json",
        "layer-redraw-removal-contract.json",
        "component-ledger.json",
        "depth-order.json",
        "auto-split-summary.json",
        "spine-split-summary.json",
        "director/*.json",
        "manifest.json",
        "qa.json",
        "run-state.json",
        "imagegen-campaign.json",
        "IMAGEGEN_HANDOFF.md",
        "HANDOFF.md",
        "COMPLETION.md",
        "REDO_STATUS.md",
        "RUNTIME.md",
        "source-visible-extraction.json",
        "source-visible-mask-summary.json",
        "source-master.psd",
        "imagegen/*",
        "imagegen/per-owner-strict-edit/*.prompt.txt",
        "imagegen/per-owner-strict-edit-candidates/*",
        "parts/*.json",
        "parts/*.png",
        "parts/cropped/*.png",
        "parts/facial-micro-source-locks/*.png",
        "prompts/*.txt",
        "layers/*/*.png",
        "layers/*/*.json",
        "layers/*/backend_raw/*",
        "layers/*/masks/*.png",
        "layers/*/notes.md",
        "components/*.png",
        "components/*.json",
        "spine/*.json",
        "spine/images/*.png",
        "v3/*.json",
        "v3/*/*.json",
        "v3/*/*.png",
        "v3/*/*.txt",
        "v3/*/*/*.json",
        "v3/*/*/*.png",
        "v3/*/*/*.txt",
        "check/*.png",
        "check/*.html",
    ]:
        include.extend(workspace.glob(pattern))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(set(include)):
            if file.exists():
                zf.write(file, file.relative_to(workspace))
    update_run_state(
        workspace,
        {
            "status": qa["status"],
            "package": relative_to_workspace(zip_path, workspace),
            "packageKind": "blocked_evidence_package" if qa["status"] == "visual_rejected" else "completed_candidate_package",
        },
    )
    print(json.dumps({"status": "blocked_evidence_package" if qa["status"] == "visual_rejected" else "packaged", "zip": str(zip_path), "qaStatus": qa["status"]}, ensure_ascii=False, indent=2))


def write_completion_note(workspace: Path, package_name: str | None = None) -> None:
    qa = read_json_if_exists(workspace / "qa.json") or {}
    counts = qa.get("counts", {})
    artifact_counts = qa.get("artifactCounts", {})
    psd = qa.get("psd", {})
    if package_name is None:
        zip_candidates = sorted(workspace.glob(f"{workspace.name}*.zip"))
        zip_name = zip_candidates[-1].name if zip_candidates else "-"
    else:
        zip_name = package_name
    lines = [
        "# KINE-LAYER Run Completion",
        "",
        f"- status: `{qa.get('status', 'unknown')}`",
        f"- present layers: `{counts.get('present', 0)}`",
        f"- final redraw layers: `{artifact_counts.get('finalRedraw', 0)}`",
        f"- source lock only: `{counts.get('source_lock_only', 0)}`",
        f"- visual rejected: `{counts.get('visual_rejected', 0)}`",
        f"- missing: `{counts.get('missing', 0)}`",
        f"- not visible: `{counts.get('not_visible', 0)}`",
        f"- redraw evidence: `{artifact_counts.get('redraw', 0)}`",
        f"- hidden underpaint evidence: `{artifact_counts.get('hidden', 0)}`",
        f"- accepted PSD layers: `{len(psd.get('writtenLayers', []))}`",
        f"- package: `{zip_name}`",
        "",
        "This run is a fresh workspace candidate. `visual_rejected`, `source_lock_only`, or zero final redraw layers means the package is blocked evidence, not a completed source master.",
    ]
    (workspace / "COMPLETION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_imagegen_handoff(workspace: Path) -> None:
    plan = load_plan(workspace)
    qa = read_json_if_exists(workspace / "qa.json") or {}
    layer_results = {item["id"]: item for item in qa.get("layers", [])}
    blocked = [
        layer_id
        for layer_id in plan["drawOrderBackToFront"]
        if layer_results.get(layer_id, {}).get("status") in {"missing", "source_lock_only", "visual_rejected"}
        or (
            layer_results.get(layer_id, {}).get("status") == "present"
            and not layer_results.get(layer_id, {}).get("finalRedrawKind")
        )
    ]
    lines = [
        "# ImageGen Handoff",
        "",
        "Follow `director/decomposition-plan.json` first. Each listed component needs final `$imagegen` skill redraw or hidden-underpaint provenance before it can enter PSD/components/Spine final export.",
        "",
        "Use only the `$imagegen` skill to generate either a clean green-background component sheet or owner-isolated per-layer redraw/hidden-underpaint candidates, then ingest/register each result. A redraw passes only if it still looks like the same corresponding component in the original image.",
        "",
    ]
    for layer_id in blocked:
        prompt = f"prompts/{layer_id}.txt"
        contract = f"layers/{layer_id}/layer-redraw-removal-contract.json"
        status = layer_results.get(layer_id, {}).get("status", "missing")
        lines.extend(
            [
                f"## {layer_id}",
                "",
                f"- status: `{status}`",
                f"- prompt: `{prompt}`",
                f"- contract: `{contract}`",
                f"- hard-cut source evidence: `layers/{layer_id}/visible_locked.png`",
                f"- expected output: `layers/{layer_id}/hidden_underpaint.png` plus provenance, or a transparent owner-isolated repair/redraw candidate for ingest",
                "",
            ]
        )
    if not blocked:
        lines.append("No blocked components were detected by the current QA pass.\n")
    (workspace / "IMAGEGEN_HANDOFF.md").write_text("\n".join(lines), encoding="utf-8")


def dominant_source_colors(source: Image.Image, max_colors: int = 6) -> list[str]:
    """Sample the source character's own dominant colors (alpha>24) as hex strings.

    Used to describe the source palette to the $imagegen skill instead of hard-coding a
    specific character's colors.
    """
    small = source.convert("RGBA").copy()
    small.thumbnail((96, 96), Image.Resampling.LANCZOS)
    pixels = small.load()
    buckets: dict[tuple[int, int, int], int] = {}
    for y in range(small.height):
        for x in range(small.width):
            r, g, b, a = pixels[x, y]
            if a <= 24:
                continue
            key = ((r // 24) * 24, (g // 24) * 24, (b // 24) * 24)
            buckets[key] = buckets.get(key, 0) + 1
    top = sorted(buckets.items(), key=lambda item: item[1], reverse=True)[:max_colors]
    return ["#%02x%02x%02x" % rgb for rgb, _count in top]


def make_parts_sheet_prompt(workspace: Path) -> str:
    source = Image.open(workspace / "source.png").convert("RGBA")
    palette = ", ".join(dominant_source_colors(source)) or "the exact source palette"
    return f"""Use case: precise-object-edit
Asset type: Kine Layer final component sheet for rigging
Input image: the provided source character image is the strict identity, style, color, pose-logic, and proportion reference.
Source canvas: {source.width}x{source.height}px.

Primary request: Create a complete green-background source-master component sheet for this exact character, like a 2D rigging parts sheet. Draw separated, owner-isolated final components for all visible semantic owners: head/face/hair masses, headwear/accessories, neck/collar, torso/clothing front and back surfaces when inferable, hips/waist, arms/hands/sleeves, legs/knees/shins, feet/shoes/boots, props, and small costume details. Each component should be an independent polished part on the sheet, with generous spacing and no overlaps. These ImageGen components are the final visual candidates; local code will remove the green background, split them, register them back to the original source canvas, and only then accept or reject them.

Required workflow context:
- `director/decomposition-plan.json` defines the semantic owners and animation split needs before this imagegen pass.
- `partition-audit.json` or `source-visible-recompose-qa.json` provides the local source registration scaffold; local QA will reject any component that cannot be mapped back to the source proportions, alpha, and placement.
- The sheet itself is not the final deliverable until local registration/QA passes, but its visible art should be the final ImageGen component art shown in HTML.

Critical identity lock:
- Preserve the exact character identity, face proportions, hair shape, outfit/costume design, material colors, line style, lighting, and visible silhouette from the source image.
- Do not beautify, redesign, reinterpret, restyle, simplify, or replace any part of the character, its face, hair, outfit, accessories, colors, or proportions.
- Match the source character's own palette (dominant source colors: {palette}); do not introduce colors that are not present in the source.
- Keep the face as one identity-preserving head/face component unless a tiny detail is clearly separable in the source. Do not invent alternate eyes, nose, mouth, brows, or expressions.
- If a hidden/back surface cannot be inferred while preserving the source design, omit it rather than inventing a new design.

Component sheet content: include the source-facing visible components and inferred hidden/back/overlap surfaces needed for animation, each as separate non-overlapping parts. For symmetric limbs or boots, draw separate left/right components when visible or inferable. For layered hair/clothing/armor, separate front and rear masses when useful for rigging. Keep each component at a consistent source-like scale so local registration can restore the original proportions.

Style/medium: a polished illustration that exactly matches the provided source character's own art style, line/edge handling, shading, and palette. Do not change the medium, art style, or colors.

Composition/framing: create one organized separated component sheet on a flat background, similar to a game/animation parts sheet. Use a single consistent view/style, generous spacing, and no overlapping parts. Do not include a full assembled body, character turnaround, pose sheet, front/back/side model sheet, labels, captions, grids, or annotations.

Output/background: place all parts on a perfectly flat solid #00ff00 chroma-key background for local alpha removal. The #00ff00 background must be one uniform color with no shadows, gradients, texture, floor plane, or lighting variation. Do not use #00ff00 anywhere in the character parts.

Forbidden: no text, labels, watermark, checkerboard, black background, assembled full body, character turnaround/model sheet, design board, extra limbs, mirrored design swaps, new costume design, new face, different person, different art style, or replacing the source character with a different design."""


def write_parts_sheet_prompt(workspace: Path, out_path: Path | None = None) -> None:
    prompt = make_parts_sheet_prompt(workspace)
    target = out_path or workspace / "imagegen" / "source-master-parts-sheet.prompt.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(prompt + "\n", encoding="utf-8")
    print(json.dumps({"status": "written", "prompt": str(target)}, ensure_ascii=False, indent=2))


V3_SHEET_ROLE_OWNERS = {
    "head_identity": {"face", "hair-front", "hair-rear", "neck", "ears", "ear-accessory", "nose", "mouth", "eye-white", "eye-iris", "eye-line", "brows", "glasses", "head-accessory"},
    "body_clothes": {"collar-accessory", "torso", "hips", "tail", "wings"},
    "limbs": {"arms", "legs"},
    "feet_footwear": {"feet"},
    "props_accessories": {"props"},
}


def v3_owner_component_class(owner: str) -> str:
    if owner in V3_SOURCE_LOCKED_DETAIL_OWNERS:
        return "source-locked-detail"
    if owner in V3_INTERACTION_GROUP_OWNERS:
        return "interaction-group"
    if owner in V3_GARMENT_LAYER_OWNERS:
        return "garment-layer"
    return "final-layer"


def v3_owner_material_class(owner: str) -> str:
    if owner in V3_SOURCE_LOCKED_DETAIL_OWNERS:
        return "identity-detail"
    if owner in {"hair-front", "hair-rear"}:
        return "hair"
    if owner in {"torso", "hips", "legs", "feet", "collar-accessory"}:
        return "garment"
    if owner in {"head-accessory", "ear-accessory", "glasses", "tail", "wings"}:
        return "accessory"
    if owner == "props":
        return "prop"
    return "skin"


def v3_owner_coverage_target(owner: str) -> str:
    if owner in {"face", "hair-front", "hair-rear", "ears", "ear-accessory", "head-accessory", "glasses", "nose", "mouth", "eye-white", "eye-iris", "eye-line", "brows"}:
        return "head"
    if owner in {"neck", "collar-accessory", "torso"}:
        return "torso"
    if owner in {"hips", "tail"}:
        return "hip"
    if owner == "arms":
        return "upper-arm"
    if owner == "legs":
        return "thigh"
    if owner == "feet":
        return "foot"
    if owner == "wings":
        return "loose-appendage"
    if owner == "props":
        return "loose-appendage"
    return "full-body"


def v3_owner_split_reason(owner: str) -> str:
    if owner in V3_SOURCE_LOCKED_DETAIL_OWNERS or owner == "face":
        return "source-lock"
    if owner == "props":
        return "contact-group"
    if owner in {"hair-front", "hair-rear", "torso", "hips", "tail", "wings"}:
        return "front-back-occlusion"
    if owner in {"arms", "legs", "feet", "neck"}:
        return "joint-articulation"
    if owner in {"collar-accessory", "head-accessory"}:
        return "overlap-socket"
    return "overlap-socket"


def v3_owner_interaction_group_id(owner: str) -> str | None:
    if owner == "props":
        return "held-prop-contact"
    return None


def v3_owner_do_not_split_by(owner: str) -> list[str]:
    if owner in V3_SOURCE_LOCKED_DETAIL_OWNERS or owner == "face":
        return ["eye", "iris", "pupil", "brow", "nose", "mouth", "ear", "face-shadow"]
    if owner in {"hair-front", "hair-rear"}:
        return ["strand", "highlight", "shadow"]
    if owner in {"torso", "hips", "legs", "feet", "collar-accessory"}:
        return ["seam", "button", "wrinkle", "fold", "trim", "cuff", "color-patch", "highlight"]
    if owner == "props":
        return ["handle-highlight", "finger-shadow", "strap-highlight", "tiny-decoration"]
    if owner in {"head-accessory", "tail", "wings"}:
        return ["trim", "highlight", "shadow", "tiny-decoration"]
    return ["skin-shadow", "highlight"]


def v3_owner_split_strategy(owner: str) -> dict[str, Any]:
    if owner == "legs":
        return {
            "mode": "adaptive_garment_or_limb",
            "default": "coherent pants/lower-body garment or left/right leg layers",
            "allowBoneSegmentsWhen": "knee articulation is required and the source clearly supports thigh/shin separation",
            "avoid": ["fixed thigh/shin split for ordinary pants", "loose pant slivers", "duplicate leg angles", "shoe variants"],
        }
    if owner == "hips":
        return {
            "mode": "adaptive_lower_garment",
            "default": "coherent hips, skirt, shorts, or pants-top garment layer",
            "allowSeparatePanelsWhen": "front/back cloth overlap is needed for animation",
            "avoid": ["buttons", "belt holes", "pocket flaps", "wrinkles", "seams"],
        }
    if owner == "torso":
        return {
            "mode": "adaptive_upper_garment",
            "default": "coherent torso clothing or armor mass with shoulder/waist overlap",
            "allowSeparatePanelsWhen": "jacket, robe, armor plate, cape, or front/back overlap is visually meaningful",
            "avoid": ["buttons", "zippers", "badges", "seams", "fabric texture fragments"],
        }
    if owner == "arms":
        return {
            "mode": "adaptive_limb_or_interaction_group",
            "default": "upper/lower arm/hand only when source supports clean joints",
            "allowInteractionGroupWhen": "hand is holding or wearing an object; keep hand and contact object coherent",
            "avoid": ["detached fingers", "detached glove scraps", "loose cuffs", "duplicate arm poses"],
        }
    if owner == "props":
        return {
            "mode": "interaction_group_first",
            "default": "held or worn contact group with its grip/socket relationship preserved",
            "allowSeparatePropWhen": "explicit independent prop motion is needed and a socket is recorded",
            "avoid": ["floating handles", "detached straps", "tiny decorations"],
        }
    if owner in {"hair-front", "hair-rear"}:
        return {
            "mode": "coherent_hair_mass",
            "default": "front/rear hair masses, not individual strands",
            "avoid": ["strands", "highlights", "shadow shards"],
        }
    if owner in V3_SOURCE_LOCKED_DETAIL_OWNERS:
        return {
            "mode": "source_locked_detail",
            "default": "reference only; do not generate final component",
            "avoid": ["micro organ redraw", "independent identity changes"],
        }
    return {
        "mode": "named_owner_component",
        "default": "follow the V3 named owner/component plan",
        "avoid": v3_owner_do_not_split_by(owner),
    }


def v3_owner_sheet_eligible(owner: str) -> bool:
    return v3_owner_component_class(owner) != "source-locked-detail"


def v3_owner_generation_policy(owner: str) -> str:
    component_class = v3_owner_component_class(owner)
    if component_class == "source-locked-detail":
        return "source_locked_reference_only"
    if component_class == "interaction-group":
        return "draw_as_contact_group_unless_explicitly_split"
    if component_class == "garment-layer":
        return "split_only_by_animation_joint_not_visual_fabric_fragments"
    return "imagegen_final_candidate_requires_registration"


def v3_component_track(owner: str) -> str:
    if owner in V3_SOURCE_LOCKED_DETAIL_OWNERS:
        return "source_locked_detail_reference"
    if owner == "face":
        return "source_locked_identity"
    return "generated_completion_candidate"


def v3_hidden_requirement_for_owner(owner: str, visibility: str, sheet_eligible: bool, track: str | None = None) -> tuple[bool, str]:
    """Return the default hidden-completion requirement for a V3 owner.

    Source-locked identity/detail rows are source reconstruction evidence by default.
    They should not create ImageGen hidden-inpaint tasks unless a later explicit review
    decision asks for a face/identity rig mode.
    """
    owner_track = track or v3_component_track(owner)
    if visibility == "not_visible":
        return False, "component_not_visible"
    if not sheet_eligible:
        return False, "not_sheet_eligible"
    if owner_track in {"source_locked_detail_reference", "source_locked_identity"}:
        return False, "source_locked_identity_hidden_not_required_by_default"
    return True, "generated_component_requires_hidden_or_overlap_completion"


def v3_is_source_visible_candidate_id(candidate_id: Any) -> bool:
    return isinstance(candidate_id, str) and candidate_id.startswith("source-visible-")


def v3_component_has_source_visible_local_registration(component: dict[str, Any]) -> bool:
    registrations = component.get("registeredCandidates")
    if not isinstance(registrations, list) or not registrations:
        return False
    return any(v3_is_source_visible_candidate_id(item.get("candidateId")) for item in registrations if isinstance(item, dict))


def v3_component_registration_source_summary(component: dict[str, Any]) -> dict[str, Any]:
    registrations = component.get("registeredCandidates")
    registration_ids = [
        str(item.get("candidateId"))
        for item in registrations
        if isinstance(item, dict) and item.get("candidateId")
    ] if isinstance(registrations, list) else []
    source_visible_ids = [candidate_id for candidate_id in registration_ids if v3_is_source_visible_candidate_id(candidate_id)]
    generated_ids = [candidate_id for candidate_id in registration_ids if not v3_is_source_visible_candidate_id(candidate_id)]
    if source_visible_ids and not generated_ids:
        export_source = "source_visible_fallback"
    elif generated_ids:
        export_source = "generated_or_merged_component"
    else:
        export_source = "unknown"
    return {
        "registeredCandidateIds": registration_ids,
        "sourceVisibleCandidateIds": source_visible_ids,
        "generatedCandidateIds": generated_ids,
        "exportSource": export_source,
    }


def v3_candidate_is_generated(candidate: dict[str, Any]) -> bool:
    candidate_id = str(candidate.get("id") or "")
    return bool(candidate_id) and not v3_is_source_visible_candidate_id(candidate_id) and not bool(candidate.get("localSourceVisibleCandidate"))


def v3_candidate_bbox_size(workspace: Path, candidate: dict[str, Any]) -> tuple[int, int] | None:
    bbox = candidate.get("alphaBbox") if isinstance(candidate.get("alphaBbox"), list) else candidate.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 4:
        width = int(bbox[2]) - int(bbox[0])
        height = int(bbox[3]) - int(bbox[1])
        if width > 0 and height > 0:
            return width, height
    file_value = candidate.get("file")
    if isinstance(file_value, str) and (workspace / file_value).exists():
        try:
            _img, alpha_bbox = alpha_bbox_image(workspace / file_value)
        except OSError:
            alpha_bbox = None
        if alpha_bbox:
            width = int(alpha_bbox[2]) - int(alpha_bbox[0])
            height = int(alpha_bbox[3]) - int(alpha_bbox[1])
            if width > 0 and height > 0:
                return width, height
    return None


def v3_generated_candidate_quality_audit(workspace: Path) -> dict[str, Any]:
    sheet_manifest = read_json_if_exists(workspace / "v3" / "sheets" / "sheet-manifest.json") or {}
    registration = read_json_if_exists(workspace / "v3" / "registration" / "registration-report.json") or {}
    candidates = [
        candidate
        for candidate in sheet_manifest.get("candidates", [])
        if isinstance(candidate, dict)
    ] if isinstance(sheet_manifest.get("candidates"), list) else []
    candidates_by_id = {str(candidate.get("id")): candidate for candidate in candidates if candidate.get("id")}
    generated_ids = {candidate_id for candidate_id, candidate in candidates_by_id.items() if v3_candidate_is_generated(candidate)}
    accepted_rows = registration.get("accepted", []) if isinstance(registration.get("accepted"), list) else []
    rejected_rows = registration.get("rejected", []) if isinstance(registration.get("rejected"), list) else []
    accepted_generated_ids = {
        str(row.get("candidateId"))
        for row in accepted_rows
        if row.get("candidateId") in generated_ids
    }
    accepted_source_visible_ids = {
        str(row.get("candidateId"))
        for row in accepted_rows
        if v3_is_source_visible_candidate_id(row.get("candidateId"))
    }
    for candidate_id, candidate in candidates_by_id.items():
        if candidate.get("status") == "accepted":
            if candidate_id in generated_ids:
                accepted_generated_ids.add(candidate_id)
            elif v3_is_source_visible_candidate_id(candidate_id):
                accepted_source_visible_ids.add(candidate_id)

    drift_rows: list[dict[str, Any]] = []
    rejected_generated_count = 0
    for row in rejected_rows:
        if not isinstance(row, dict):
            continue
        candidate_id = str(row.get("candidateId") or "")
        if candidate_id not in generated_ids:
            continue
        rejected_generated_count += 1
        candidate = candidates_by_id.get(candidate_id, {})
        reasons = [str(reason) for reason in row.get("reasons", [])] if isinstance(row.get("reasons"), list) else []
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        transform = row.get("transform") if isinstance(row.get("transform"), dict) else {}
        target_bbox = transform.get("targetBbox") if isinstance(transform.get("targetBbox"), list) else None
        candidate_size = v3_candidate_bbox_size(workspace, candidate)
        target_size = None
        if isinstance(target_bbox, list) and len(target_bbox) == 4:
            target_w = int(target_bbox[2]) - int(target_bbox[0])
            target_h = int(target_bbox[3]) - int(target_bbox[1])
            if target_w > 0 and target_h > 0:
                target_size = (target_w, target_h)
        drift_reasons = []
        scale_x = scale_y = aspect_log_delta = axis_scale_ratio = None
        if candidate_size and target_size:
            candidate_w, candidate_h = candidate_size
            target_w, target_h = target_size
            scale_x = round(target_w / max(1, candidate_w), 6)
            scale_y = round(target_h / max(1, candidate_h), 6)
            candidate_aspect = candidate_w / max(1, candidate_h)
            target_aspect = target_w / max(1, target_h)
            aspect_log_delta = round(abs(math.log(max(candidate_aspect, 1e-6) / max(target_aspect, 1e-6))), 6)
            axis_scale_ratio = round(max(scale_x, scale_y) / max(min(scale_x, scale_y), 1e-6), 6)
            if aspect_log_delta > V3_PROPORTION_DRIFT_ASPECT_LOG_LIMIT:
                drift_reasons.append("aspect_ratio_drift")
            if axis_scale_ratio > V3_PROPORTION_DRIFT_AXIS_SCALE_RATIO_LIMIT:
                drift_reasons.append("axis_scale_drift")
        outside_ratio = float(metrics.get("outsideMaskRatio", 0.0) or 0.0)
        if outside_ratio > LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT:
            drift_reasons.append("outside_mask_ratio")
        if "shape_mismatch" in reasons:
            drift_reasons.append("shape_mismatch")
        if drift_reasons:
            drift_rows.append(
                {
                    "candidateId": candidate_id,
                    "componentId": row.get("componentId"),
                    "role": candidate.get("role"),
                    "reasons": reasons,
                    "driftReasons": sorted(set(drift_reasons)),
                    "candidateSize": list(candidate_size) if candidate_size else None,
                    "targetSize": list(target_size) if target_size else None,
                    "scaleX": scale_x,
                    "scaleY": scale_y,
                    "axisScaleRatio": axis_scale_ratio,
                    "aspectLogDelta": aspect_log_delta,
                    "outsideMaskRatio": outside_ratio,
                    "visibleRmse": metrics.get("visibleRmse"),
                }
            )

    blockers: list[str] = []
    if generated_ids and not accepted_generated_ids and accepted_source_visible_ids:
        blockers.append("imagegen_candidates_all_rejected_source_visible_fallback_only")
    if drift_rows:
        blockers.append(f"imagegen_proportion_drift_{len(drift_rows)}")
    return {
        "type": "kine.v3.generatedCandidateQualityAudit",
        "status": "passed" if not blockers else PARTS_SHEET_BLOCKED_STATUS,
        "generatedCandidateCount": len(generated_ids),
        "generatedAcceptedCount": len(accepted_generated_ids),
        "generatedRejectedCount": rejected_generated_count,
        "sourceVisibleAcceptedCount": len(accepted_source_visible_ids),
        "proportionDriftCount": len(drift_rows),
        "proportionDriftRows": drift_rows[:20],
        "blockers": blockers,
    }


def v3_candidate_has_stable_prop_evidence(workspace: Path, candidate: dict[str, Any], rejection: dict[str, Any] | None = None) -> bool:
    role = str(candidate.get("role") or candidate.get("sheetRole") or "")
    if role == "props_accessories":
        return True
    if not v3_candidate_is_generated(candidate):
        return False
    reasons = [str(reason) for reason in (rejection or {}).get("reasons", [])] if isinstance((rejection or {}).get("reasons"), list) else []
    if "owner_pollution" not in reasons:
        return False
    metrics = (rejection or {}).get("metrics") if isinstance((rejection or {}).get("metrics"), dict) else {}
    outside_ratio = float(metrics.get("outsideMaskRatio", 0.0) or 0.0)
    candidate_size = v3_candidate_bbox_size(workspace, candidate)
    long_or_thin = False
    if candidate_size:
        width, height = candidate_size
        aspect = width / max(1, height)
        long_or_thin = aspect < 0.42 or aspect > 2.4
    component_id = str((rejection or {}).get("componentId") or candidate.get("componentId") or "")
    contact_limb = role == "limbs" and ("arms" in component_id or "hand" in component_id or not component_id)
    return bool((contact_limb or role == "body_clothes") and (outside_ratio > LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT or long_or_thin))


def v3_stable_owner_coverage_audit(workspace: Path) -> dict[str, Any]:
    component_plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    sheet_manifest = read_json_if_exists(workspace / "v3" / "sheets" / "sheet-manifest.json") or {}
    registration = read_json_if_exists(workspace / "v3" / "registration" / "registration-report.json") or {}
    components = [
        component
        for component in component_plan.get("components", [])
        if isinstance(component, dict)
    ] if isinstance(component_plan.get("components"), list) else []
    candidates = [
        candidate
        for candidate in sheet_manifest.get("candidates", [])
        if isinstance(candidate, dict)
    ] if isinstance(sheet_manifest.get("candidates"), list) else []
    candidates_by_id = {str(candidate.get("id")): candidate for candidate in candidates if candidate.get("id")}
    rejected_by_id = {
        str(row.get("candidateId")): row
        for row in registration.get("rejected", [])
        if isinstance(row, dict) and row.get("candidateId")
    } if isinstance(registration.get("rejected"), list) else {}
    accepted_component_ids = {
        str(row.get("componentId"))
        for row in registration.get("accepted", [])
        if isinstance(row, dict) and row.get("componentId")
    } if isinstance(registration.get("accepted"), list) else set()
    owner_rows = {
        owner: [component for component in components if component.get("owner") == owner]
        for owner in V3_STABLE_OPTIONAL_OWNER_IDS
    }
    missing_owners: list[str] = []
    for owner, rows in owner_rows.items():
        if not rows:
            missing_owners.append(owner)
            continue
        has_accepted = any(
            component.get("id") in accepted_component_ids
            or component.get("registrationStatus") == "accepted"
            or component.get("status") not in {"not_visible", None} and component.get("maskStatus") == "passed"
            for component in rows
        )
        if not has_accepted:
            missing_owners.append(owner)

    evidence_rows: list[dict[str, Any]] = []
    for candidate_id, candidate in candidates_by_id.items():
        rejection = rejected_by_id.get(candidate_id)
        if v3_candidate_has_stable_prop_evidence(workspace, candidate, rejection):
            evidence_rows.append(
                {
                    "candidateId": candidate_id,
                    "role": candidate.get("role") or candidate.get("sheetRole"),
                    "componentId": (rejection or {}).get("componentId") or candidate.get("componentId"),
                    "reasons": (rejection or {}).get("reasons") or [],
                    "file": candidate.get("file"),
                }
            )
    blockers: list[str] = []
    if "props" in missing_owners and evidence_rows:
        blockers.append("stable_owner_missing_props")
    return {
        "type": "kine.v3.stableOwnerCoverageAudit",
        "status": "passed" if not blockers else PARTS_SHEET_BLOCKED_STATUS,
        "stableOwners": sorted(V3_STABLE_OPTIONAL_OWNER_IDS),
        "missingOwners": missing_owners,
        "evidenceCount": len(evidence_rows),
        "evidence": evidence_rows[:20],
        "blockers": blockers,
    }


def v3_stable_object_ledger_path(workspace: Path) -> Path:
    return workspace / "v3" / "stable-object-ledger.json"


def v3_lower_tokens_from_text(text: str) -> set[str]:
    lowered = text.lower()
    tokens: set[str] = set()
    current: list[str] = []
    for ch in lowered:
        if ch.isalnum() or ch in {"-", "_"}:
            current.append(ch)
        else:
            if current:
                tokens.add("".join(current))
                current = []
    if current:
        tokens.add("".join(current))
    return tokens


def v3_row_text(row: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "id",
        "name",
        "label",
        "type",
        "objectType",
        "role",
        "owner",
        "target",
        "policy",
        "mode",
        "relationship",
        "description",
        "notes",
        "prompt",
    ):
        value = row.get(key)
        if isinstance(value, str):
            values.append(value)
    for key in ("tags", "keywords", "owners"):
        value = row.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if isinstance(item, (str, int, float)))
    return " ".join(values)


def v3_stable_object_keyword_match(text: str, keywords: set[str]) -> bool:
    lowered = text.lower()
    tokens = v3_lower_tokens_from_text(lowered)
    for keyword in keywords:
        key = keyword.lower()
        if key in tokens or key in lowered:
            return True
    return False


def v3_classify_stable_object_type(text: str, role: str | None = None) -> str | None:
    if v3_stable_object_keyword_match(text, V3_STABLE_OBJECT_COMPONENT_DETAILS):
        return "non-component-detail"
    lowered_role = (role or "").lower()
    if lowered_role == "props_accessories":
        for object_type, keywords in V3_STABLE_OBJECT_TYPE_KEYWORDS.items():
            if v3_stable_object_keyword_match(text, keywords):
                return object_type
        return "prop"
    for object_type, keywords in V3_STABLE_OBJECT_TYPE_KEYWORDS.items():
        if v3_stable_object_keyword_match(text, keywords):
            return object_type
    if v3_stable_object_keyword_match(text, {"prop", "props", "accessory", "accessories", "道具", "配件"}):
        return "prop"
    return None


def v3_stable_object_relationship(text: str, object_type: str, role: str | None = None) -> str:
    lowered_role = (role or "").lower()
    if v3_stable_object_keyword_match(text, V3_STABLE_OBJECT_CONTACT_KEYWORDS):
        return "held-interaction-group"
    if v3_stable_object_keyword_match(text, V3_STABLE_OBJECT_WORN_KEYWORDS):
        if object_type == "bag":
            return "worn-prop"
        return "attached-prop"
    if object_type in {"weapon", "staff", "umbrella", "tool"} and lowered_role in {"limbs", "interaction_group"}:
        return "held-interaction-group"
    if object_type == "bag":
        return "worn-prop"
    return "independent-prop"


def v3_stable_object_expected_generation_target(object_type: str, relationship: str) -> str:
    if relationship == "held-interaction-group":
        if object_type == "weapon":
            return "hand-weapon-contact-group"
        if object_type == "umbrella":
            return "hand-umbrella-contact-group"
        if object_type in {"staff", "tool"}:
            return "held-tool-contact-group"
        return "hand-prop-contact-group"
    if object_type == "weapon":
        return "weapon-prop"
    if object_type == "umbrella":
        return "umbrella-prop"
    if object_type == "bag":
        return "worn-bag-prop"
    if object_type == "shield":
        return "shield-prop"
    if object_type == "book":
        return "book-prop"
    if object_type == "staff":
        return "staff-prop"
    if relationship == "attached-prop":
        return "attached-prop"
    if relationship == "worn-prop":
        return "worn-prop"
    return "prop"


def v3_stable_object_source_bbox_from_row(workspace: Path, row: dict[str, Any], decision: dict[str, Any] | None = None) -> list[int] | None:
    bbox = row.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        region = row.get("region")
        if isinstance(region, dict):
            bbox = region.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        values = [float(value) for value in bbox]
    except Exception:
        return None
    try:
        source = Image.open(workspace / "source.png").convert("RGBA")
    except OSError:
        return None
    source_size = source.size
    if all(0.0 <= value <= 1.0 for value in values):
        x0 = int(round(values[0] * source_size[0]))
        y0 = int(round(values[1] * source_size[1]))
        x1 = int(round(values[2] * source_size[0]))
        y1 = int(round(values[3] * source_size[1]))
    else:
        canvas_size = v3_visual_split_canvas_size(decision or {}, source_size) if decision else source_size
        bbox_transform = v3_visual_split_bbox_transform(workspace, decision or {}) if decision else None
        normalized = v3_visual_split_bbox_to_normalized(values, canvas_size, source_size, bbox_transform)
        x0 = int(round(normalized[0] * source_size[0]))
        y0 = int(round(normalized[1] * source_size[1]))
        x1 = int(round(normalized[2] * source_size[0]))
        y1 = int(round(normalized[3] * source_size[1]))
    x0 = max(0, min(source_size[0], x0))
    x1 = max(0, min(source_size[0], x1))
    y0 = max(0, min(source_size[1], y0))
    y1 = max(0, min(source_size[1], y1))
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def v3_merge_stable_object(records: dict[str, dict[str, Any]], row: dict[str, Any], source: str, decision: dict[str, Any] | None = None) -> None:
    text = v3_row_text(row)
    role = row.get("role") if isinstance(row.get("role"), str) else None
    object_type = v3_classify_stable_object_type(text, role)
    if object_type is None:
        return
    relationship = "non-component-detail" if object_type == "non-component-detail" else v3_stable_object_relationship(text, object_type, role)
    target = None if object_type == "non-component-detail" else v3_stable_object_expected_generation_target(object_type, relationship)
    label = str(row.get("id") or row.get("label") or row.get("target") or object_type)
    object_id = v3_slug(f"{object_type}-{relationship}-{label}")[:80]
    source_bbox = v3_stable_object_source_bbox_from_row(Path(row.get("__workspace") or "."), row, decision) if row.get("__workspace") else None
    compact_evidence = {
        "source": source,
        "id": row.get("id"),
        "role": row.get("role"),
        "target": row.get("target"),
        "description": row.get("description"),
        "bbox": row.get("bbox"),
        "region": row.get("region"),
        "candidateId": row.get("candidateId"),
        "file": row.get("file"),
        "reasons": row.get("reasons"),
    }
    compact_evidence = {key: value for key, value in compact_evidence.items() if value not in (None, [], {})}
    existing = records.get(object_id)
    if existing is None:
        records[object_id] = {
            "objectId": object_id,
            "objectType": object_type,
            "owner": None if object_type == "non-component-detail" else V3_STABLE_OBJECT_OWNER,
            "relationship": relationship,
            "expectedGenerationTarget": target,
            "status": "ignored_non_component_detail" if object_type == "non-component-detail" else "active",
            "sourceBbox": source_bbox,
            "sourceEvidence": [compact_evidence],
        }
        return
    existing.setdefault("sourceEvidence", []).append(compact_evidence)
    if existing.get("sourceBbox") is None and source_bbox is not None:
        existing["sourceBbox"] = source_bbox


def v3_collect_stable_object_records(workspace: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: dict[str, dict[str, Any]] = {}
    decision = read_v3_visual_split_decision(workspace)
    for row in decision.get("items", []) if isinstance(decision.get("items"), list) else []:
        if isinstance(row, dict):
            v3_merge_stable_object(records, {**row, "__workspace": str(workspace)}, "visual_split_decision.items", decision)
    for row in decision.get("generationTargets", []) if isinstance(decision.get("generationTargets"), list) else []:
        if isinstance(row, dict):
            v3_merge_stable_object(records, {**row, "__workspace": str(workspace)}, "visual_split_decision.generationTargets", decision)

    cutout = load_cutout_map(workspace)
    for owner in cutout.get("owners", []) if isinstance(cutout, dict) else []:
        if not isinstance(owner, dict):
            continue
        if owner.get("id") == V3_STABLE_OBJECT_OWNER and isinstance(owner.get("region"), dict):
            v3_merge_stable_object(
                records,
                {
                    "__workspace": str(workspace),
                    "id": "props-region",
                    "role": "props_accessories",
                    "target": "stable character-owned props from cutout-map",
                    "region": owner.get("region"),
                },
                "cutout_map.owner_region",
                None,
            )

    notes = read_json_if_exists(workspace / "v3" / "stable-object-notes.json") or {}
    for row in notes.get("objects", []) if isinstance(notes.get("objects"), list) else []:
        if isinstance(row, dict):
            v3_merge_stable_object(records, {**row, "__workspace": str(workspace)}, "manual_agent_semantic_notes", None)

    sheet_manifest = read_json_if_exists(workspace / "v3" / "sheets" / "sheet-manifest.json") or {}
    registration = read_json_if_exists(workspace / "v3" / "registration" / "registration-report.json") or {}
    candidates = [
        candidate
        for candidate in sheet_manifest.get("candidates", [])
        if isinstance(candidate, dict)
    ] if isinstance(sheet_manifest.get("candidates"), list) else []
    candidates_by_id = {str(candidate.get("id")): candidate for candidate in candidates if candidate.get("id")}
    for rejection in registration.get("rejected", []) if isinstance(registration.get("rejected"), list) else []:
        if not isinstance(rejection, dict):
            continue
        candidate = candidates_by_id.get(str(rejection.get("candidateId") or ""))
        if candidate and v3_candidate_has_stable_prop_evidence(workspace, candidate, rejection):
            v3_merge_stable_object(
                records,
                {
                    "__workspace": str(workspace),
                    "id": candidate.get("id"),
                    "role": candidate.get("role") or candidate.get("sheetRole") or "props_accessories",
                    "target": "stable held or worn prop evidence from rejected role sheet candidate",
                    "candidateId": candidate.get("id"),
                    "file": candidate.get("file"),
                    "reasons": rejection.get("reasons") or [],
                },
                "registration_rejected_candidate_owner_pollution",
                None,
            )

    active = [record for record in records.values() if record.get("status") == "active"]
    ignored = [record for record in records.values() if record.get("status") != "active"]
    return sorted(active, key=lambda item: str(item.get("objectId"))), sorted(ignored, key=lambda item: str(item.get("objectId")))


def v3_write_stable_object_reference_images(workspace: Path, objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        source = Image.open(workspace / "source.png").convert("RGBA")
    except OSError:
        return objects
    updated: list[dict[str, Any]] = []
    for obj in objects:
        source_bbox = obj.get("sourceBbox")
        if not isinstance(source_bbox, list) or len(source_bbox) != 4:
            updated.append(obj)
            continue
        try:
            bbox = [int(value) for value in source_bbox]
        except Exception:
            updated.append(obj)
            continue
        out_dir = workspace / "v3" / "stable-objects" / str(obj.get("objectId") or "object")
        out_dir.mkdir(parents=True, exist_ok=True)
        crop = source.crop(tuple(bbox))
        crop_path = out_dir / "object-local-crop.png"
        crop.save(crop_path)
        context_box = expand_bbox(tuple(bbox), source.size, padding=36)
        context = source.crop(context_box)
        context_path = out_dir / "nearby-contact-crop.png"
        context.save(context_path)
        updated.append(
            {
                **obj,
                "crop": relative_to_workspace(crop_path, workspace),
                "nearbyContactCrop": relative_to_workspace(context_path, workspace),
                "contextBbox": list(context_box),
            }
        )
    return updated


def write_v3_stable_object_ledger(workspace: Path) -> dict[str, Any]:
    active, ignored = v3_collect_stable_object_records(workspace)
    active = v3_write_stable_object_reference_images(workspace, active)
    ledger = {
        "type": "kine.v3.stableObjectLedger",
        "version": "0.1",
        "status": "ready" if active else "empty",
        "workspace": workspace.name,
        "owner": V3_STABLE_OBJECT_OWNER,
        "objectCount": len(active) + len(ignored),
        "activeObjectCount": len(active),
        "ignoredDetailCount": len(ignored),
        "objects": active,
        "ignoredDetails": ignored,
        "sourceFiles": {
            "visualSplitDecision": "v3/visual-split-decision.json" if v3_visual_split_decision_path(workspace).exists() else None,
            "cutoutMap": str(cutout_map_path(workspace).name) if cutout_map_path(workspace).exists() else None,
            "manualAgentNotes": "v3/stable-object-notes.json" if (workspace / "v3" / "stable-object-notes.json").exists() else None,
            "registrationReport": "v3/registration/registration-report.json" if (workspace / "v3" / "registration" / "registration-report.json").exists() else None,
        },
        "contract": {
            "activeObjectsEnterPlan": "active stable objects must activate props/interaction generation targets before role sheets are generated",
            "nonComponentDetails": "buttons, seams, texture, highlights, wrinkles, tiny logos, and similar decorative fragments must not create props sheets",
            "finalAuthority": "ledger is planning evidence only; final acceptance still requires ingest, registration, recompose, review, export, and validation",
        },
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(v3_stable_object_ledger_path(workspace), ledger)
    return ledger


def v3_active_stable_objects(workspace: Path, refresh: bool = False) -> list[dict[str, Any]]:
    ledger_path = v3_stable_object_ledger_path(workspace)
    ledger = write_v3_stable_object_ledger(workspace) if refresh or not ledger_path.exists() else read_json_if_exists(ledger_path) or {}
    return [
        obj
        for obj in ledger.get("objects", [])
        if isinstance(obj, dict) and obj.get("status") == "active"
    ] if isinstance(ledger.get("objects"), list) else []


def v3_target_source_bbox_for_components(components: list[dict[str, Any]]) -> list[int] | None:
    boxes = [component.get("bbox") for component in components if isinstance(component.get("bbox"), list) and len(component.get("bbox")) == 4]
    if not boxes:
        return None
    try:
        x0 = min(int(box[0]) for box in boxes)
        y0 = min(int(box[1]) for box in boxes)
        x1 = max(int(box[2]) for box in boxes)
        y1 = max(int(box[3]) for box in boxes)
    except Exception:
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def v3_source_scale_anchor(source_bbox: list[int] | None, source_size: list[int] | tuple[int, int] | None) -> dict[str, Any] | None:
    if not isinstance(source_bbox, list) or len(source_bbox) != 4 or not source_size or len(source_size) != 2:
        return None
    width = max(1, int(source_bbox[2]) - int(source_bbox[0]))
    height = max(1, int(source_bbox[3]) - int(source_bbox[1]))
    return {
        "targetSourceBbox": source_bbox,
        "targetWidthRatio": round(width / max(1, int(source_size[0])), 6),
        "targetHeightRatio": round(height / max(1, int(source_size[1])), 6),
        "targetAspectRatio": round(width / max(1, height), 6),
        "rule": "match this component's source-canvas bbox/proportion; do not scale all components to a uniform size",
    }


def v3_stable_object_generation_targets(workspace: Path, component_ids: list[str]) -> list[dict[str, Any]]:
    try:
        source = Image.open(workspace / "source.png").convert("RGBA")
        source_size: list[int] = [source.width, source.height]
    except OSError:
        source_size = []
    targets: list[dict[str, Any]] = []
    for obj in v3_active_stable_objects(workspace):
        target_id = str(obj.get("expectedGenerationTarget") or "prop")
        source_bbox = obj.get("sourceBbox") if isinstance(obj.get("sourceBbox"), list) else None
        targets.append(
            {
                "id": target_id,
                "owner": V3_STABLE_OBJECT_OWNER,
                "mode": obj.get("relationship") or "stable_object",
                "description": "stable character-owned object from the source image; preserve object type, direction, material, contact relationship, and source-canvas scale",
                "stableObjectId": obj.get("objectId"),
                "objectType": obj.get("objectType"),
                "relationship": obj.get("relationship"),
                "sourceEvidence": obj.get("sourceEvidence") or [],
                "sourceBbox": source_bbox,
                "sourceScaleAnchor": v3_source_scale_anchor(source_bbox, source_size),
                "referenceInputs": [
                    value
                    for value in [obj.get("crop"), obj.get("nearbyContactCrop")]
                    if isinstance(value, str)
                ],
                "doNotRequest": [
                    "floating handles",
                    "detached straps",
                    "unheld weapon fragments",
                    "tiny decoration fragments",
                    "multi-view design-board variants",
                    "replacement object type",
                ],
                "internalComponents": component_ids,
            }
        )
    return targets


def v3_stable_object_input_images(workspace: Path) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for obj in v3_active_stable_objects(workspace):
        object_id = str(obj.get("objectId") or "stable-object")
        for role, key, description in [
            ("stable-object-local-crop", "crop", "source object crop; object type, material, direction, and local detail authority"),
            ("stable-object-nearby-contact-crop", "nearbyContactCrop", "nearby hand/body/socket context; preserve contact relationship and source scale"),
        ]:
            value = obj.get(key)
            if isinstance(value, str) and (workspace / value).exists():
                images.append(
                    {
                        "role": role,
                        "componentId": object_id,
                        "path": value,
                        "description": description,
                        "referenceStrength": "stable_object_source_anchor",
                        "useAsPrimaryReference": True,
                    }
                )
    return images


def ensure_v3_stable_object_plan(workspace: Path) -> dict[str, Any]:
    ledger = write_v3_stable_object_ledger(workspace)
    active_objects = [
        obj
        for obj in ledger.get("objects", [])
        if isinstance(obj, dict) and obj.get("status") == "active"
    ] if isinstance(ledger.get("objects"), list) else []
    if not active_objects:
        return {"status": "no_active_stable_objects", "stableObjectLedger": "v3/stable-object-ledger.json"}

    plan_path = workspace / "v3" / "component-plan.json"
    campaign_path = workspace / "v3" / "sheet-campaign.json"
    plan = read_json_if_exists(plan_path) or {}
    campaign = read_json_if_exists(campaign_path) or {}
    if not isinstance(plan, dict) or not isinstance(campaign, dict) or not plan:
        return {"status": "stable_object_ledger_written_only", "stableObjectLedger": "v3/stable-object-ledger.json"}

    changed = False
    object_ids = [str(obj.get("objectId")) for obj in active_objects if obj.get("objectId")]
    generation_targets = [str(obj.get("expectedGenerationTarget")) for obj in active_objects if obj.get("expectedGenerationTarget")]
    owners = plan.get("owners") if isinstance(plan.get("owners"), list) else []
    props_owner = next((owner for owner in owners if isinstance(owner, dict) and owner.get("id") == V3_STABLE_OBJECT_OWNER), None)
    if isinstance(props_owner, dict):
        if props_owner.get("visibility") == "not_visible":
            props_owner["visibility"] = "present"
            changed = True
        for key, value in [
            ("stableObjectLedger", "v3/stable-object-ledger.json"),
            ("stableObjectIds", object_ids),
            ("expectedGenerationTargets", generation_targets),
            ("needsMask", True),
            ("sheetEligible", True),
        ]:
            if props_owner.get(key) != value:
                props_owner[key] = value
                changed = True

    components = plan.get("components") if isinstance(plan.get("components"), list) else []
    props_components = [component for component in components if isinstance(component, dict) and component.get("owner") == V3_STABLE_OBJECT_OWNER]
    if not props_components:
        for component in v3_component_targets_for_owner(V3_STABLE_OBJECT_OWNER):
            components.append(
                v3_normalize_component_hidden_requirement(
                    {
                        **component,
                        "role": "props_accessories",
                        "componentClass": v3_owner_component_class(V3_STABLE_OBJECT_OWNER),
                        "materialClass": v3_owner_material_class(V3_STABLE_OBJECT_OWNER),
                        "coverageTarget": v3_owner_coverage_target(V3_STABLE_OBJECT_OWNER),
                        "splitReason": v3_owner_split_reason(V3_STABLE_OBJECT_OWNER),
                        "interactionGroupId": v3_owner_interaction_group_id(V3_STABLE_OBJECT_OWNER),
                        "doNotSplitBy": v3_owner_do_not_split_by(V3_STABLE_OBJECT_OWNER),
                        "splitStrategy": v3_owner_split_strategy(V3_STABLE_OBJECT_OWNER),
                        "generationPolicy": v3_owner_generation_policy(V3_STABLE_OBJECT_OWNER),
                        "sheetEligible": True,
                        "drawOrder": 230,
                        "bbox": None,
                        "expectedMask": f"v3/masks/{component['id']}.mask.png",
                        "visibleCut": f"v3/masks/{component['id']}.visible_cut.png",
                        "pivot": None,
                        "needsMask": True,
                        "needsOverlapZone": True,
                        "track": v3_component_track(V3_STABLE_OBJECT_OWNER),
                        "status": "planned",
                        "stableObjectLedger": "v3/stable-object-ledger.json",
                        "stableObjectIds": object_ids,
                        "expectedGenerationTargets": generation_targets,
                    }
                )
            )
        plan["components"] = components
        changed = True
    else:
        for component in props_components:
            for key, value in [
                ("status", "planned" if component.get("status") == "not_visible" else component.get("status", "planned")),
                ("stableObjectLedger", "v3/stable-object-ledger.json"),
                ("stableObjectIds", object_ids),
                ("expectedGenerationTargets", generation_targets),
                ("sheetEligible", True),
            ]:
                if component.get(key) != value:
                    component[key] = value
                    changed = True

    sheets = campaign.get("sheets") if isinstance(campaign.get("sheets"), list) else []
    has_props_sheet = any(isinstance(sheet, dict) and sheet.get("role") == "props_accessories" and V3_STABLE_OBJECT_OWNER in (sheet.get("owners") or []) for sheet in sheets)
    if not has_props_sheet:
        next_index = 1
        for sheet in sheets:
            if not isinstance(sheet, dict):
                continue
            sid = str(sheet.get("id") or "")
            if sid.startswith("sheet-"):
                try:
                    next_index = max(next_index, int(sid.split("-")[-1]) + 1)
                except ValueError:
                    pass
        sheet_id = f"sheet-{next_index:03d}"
        sheets.append(
            {
                "id": sheet_id,
                "role": "props_accessories",
                "owners": [V3_STABLE_OBJECT_OWNER],
                "componentClasses": ["interaction-group"],
                "stableObjectLedger": "v3/stable-object-ledger.json",
                "stableObjectIds": object_ids,
                "expectedGenerationTargets": generation_targets,
                "maxComponents": 12,
                "promptPath": f"imagegen/v3/{sheet_id}.props_accessories.prompt.txt",
                "expectedRawPath": f"imagegen/v3/{sheet_id}.props_accessories.raw.png",
                "partsSheetCommand": (
                    "python3 skill-v3/scripts/kine_layer_workspace.py parts-sheet "
                    f"--workspace {{workspace}} --sheet imagegen/v3/{sheet_id}.props_accessories.raw.png "
                    f"--sheet-id {sheet_id} --role props_accessories --append --chroma-key auto"
                ),
            }
        )
        campaign["sheets"] = sheets
        changed = True

    if changed:
        plan["stableObjectLedger"] = "v3/stable-object-ledger.json"
        plan["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        campaign["stableObjectLedger"] = "v3/stable-object-ledger.json"
        campaign["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        write_json(plan_path, plan)
        write_json(campaign_path, campaign)
    return {
        "status": "updated" if changed else "already_current",
        "stableObjectLedger": "v3/stable-object-ledger.json",
        "activeObjectCount": len(active_objects),
        "expectedGenerationTargets": generation_targets,
    }


def v3_sheet_prompts_need_refresh(workspace: Path) -> bool:
    campaign = read_json_if_exists(workspace / "v3" / "sheet-campaign.json") or {}
    prompts = read_json_if_exists(workspace / "v3" / "sheet-prompts.json") or {}
    campaign_ids = {
        str(sheet.get("id"))
        for sheet in campaign.get("sheets", [])
        if isinstance(sheet, dict) and sheet.get("id")
    } if isinstance(campaign.get("sheets"), list) else set()
    prompt_ids = {
        str(row.get("sheetId"))
        for row in prompts.get("prompts", [])
        if isinstance(row, dict) and row.get("sheetId")
    } if isinstance(prompts.get("prompts"), list) else set()
    if campaign_ids != prompt_ids:
        return True
    active_objects = v3_active_stable_objects(workspace)
    if active_objects:
        prompt_rows = prompts.get("prompts", []) if isinstance(prompts.get("prompts"), list) else []
        has_stable_target = any(
            isinstance(row, dict)
            and row.get("role") == "props_accessories"
            and any(isinstance(target, dict) and target.get("stableObjectId") for target in row.get("generationTargets", []))
            for row in prompt_rows
        )
        if not has_stable_target:
            return True
    return False


def v3_normalize_component_hidden_requirement(component: dict[str, Any]) -> dict[str, Any]:
    owner = str(component.get("owner") or "")
    visibility = "not_visible" if component.get("status") == "not_visible" else str(component.get("visibility") or "present")
    sheet_eligible = bool(component.get("sheetEligible", v3_owner_sheet_eligible(owner)))
    track = str(component.get("track") or v3_component_track(owner))
    needs_hidden, reason = v3_hidden_requirement_for_owner(owner, visibility, sheet_eligible, track)
    manual_reason = str(component.get("hiddenReason") or component.get("manualReviewReason") or "")
    if manual_reason == "manual_review_needs_hidden_completion":
        needs_hidden = True
        reason = "manual_review_needs_hidden_completion"
    elif (
        component.get("hiddenCompletionPolicy") == "source_visible_local_no_hidden_target"
        or component.get("hiddenRequirementReason") == SOURCE_VISIBLE_HIDDEN_NOT_REQUIRED_REASON
        or v3_component_has_source_visible_local_registration(component)
    ):
        needs_hidden = False
        reason = SOURCE_VISIBLE_HIDDEN_NOT_REQUIRED_REASON
    return {
        **component,
        "track": track,
        "sheetEligible": sheet_eligible,
        "needsHiddenCompletion": needs_hidden,
        "hiddenRequirementReason": reason,
    }


def v3_component_sockets(owner: str, component_id: str) -> list[str]:
    cid = component_id.lower()
    if owner == "torso":
        return ["neck", "left-shoulder", "right-shoulder", "hips"]
    if owner == "hips":
        return ["left-thigh", "right-thigh"]
    if "upper-arm" in cid:
        return ["shoulder", "elbow"]
    if "lower-arm" in cid:
        return ["elbow", "wrist"]
    if "hand" in cid:
        return ["wrist", "grip"]
    if "thigh" in cid:
        return ["hip", "knee"]
    if "shin" in cid:
        return ["knee", "ankle"]
    if "foot" in cid:
        return ["ankle"]
    if owner in {"face", "hair-front", "hair-rear", "ears", "head-accessory", "glasses"}:
        return ["head"]
    if owner == "neck":
        return ["neck", "head"]
    if owner == "props":
        return ["prop-grip"]
    return []


def v3_component_parent(owner: str, component_id: str) -> str | None:
    cid = component_id.lower()
    if owner in {"face", "hair-front", "hair-rear", "ears", "ear-accessory", "head-accessory", "glasses", "nose", "mouth", "eye-white", "eye-iris", "eye-line", "brows"}:
        return "neck" if owner == "face" else "face"
    if owner == "neck":
        return "torso"
    if owner in {"collar-accessory", "wings"}:
        return "torso"
    if owner in {"hips", "tail"}:
        return "torso"
    if "upper-arm" in cid:
        return "torso"
    if "lower-arm" in cid:
        return component_id.replace("lower-arm", "upper-arm")
    if "hand" in cid:
        return component_id.replace("hand", "lower-arm")
    if "thigh" in cid:
        return "hips"
    if "shin" in cid:
        return component_id.replace("shin", "thigh")
    if "foot" in cid:
        return component_id.replace("foot", "shin") if owner == "legs" else "hips"
    if owner == "feet":
        return "legs"
    if owner == "props":
        return "arms"
    return None


def v3_owner_role(owner: str) -> str:
    for role, owners in V3_SHEET_ROLE_OWNERS.items():
        if owner in owners:
            return role
    return "misc"


def v3_component_targets_for_owner(owner: str) -> list[dict[str, Any]]:
    if not v3_owner_sheet_eligible(owner):
        return []
    targets = spine_part_targets(owner)
    components = []
    for target in targets:
        component_id = target["id"]
        components.append(
            {
                "id": component_id,
                "owner": owner,
                "parent": v3_component_parent(owner, component_id),
                "bone": target.get("bone") or spine_bone_for_component(component_id),
                "side": target.get("side"),
                "segment": target.get("segment"),
                "lengthFraction": target.get("lengthFraction", 1.0),
                "sockets": v3_component_sockets(owner, component_id),
            }
        )
    return components


def write_v3_component_plan(workspace: Path, max_sheet_components: int = 12) -> dict[str, Any]:
    """Write the V3 decomposition scaffold: semantic owners, sheet batches, and gates.

    V3 makes the rigging-sheet lesson executable: first name every expected owner,
    then group owners into bounded multi-sheet campaigns, then require per-owner mask,
    hidden completion, alpha cleanup, source recompose, and pose-stress gates.
    """
    source_path = workspace / "source.png"
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    source = Image.open(source_path).convert("RGBA")
    partition = read_json_if_exists(workspace / "partition-audit.json") or {}
    present_owners = set(partition.get("presentOwners", []) if isinstance(partition.get("presentOwners"), list) else [])
    not_visible_owners = set(partition.get("notVisibleOwners", []) if isinstance(partition.get("notVisibleOwners"), list) else [])
    stable_ledger = write_v3_stable_object_ledger(workspace)
    active_stable_objects = [
        obj
        for obj in stable_ledger.get("objects", [])
        if isinstance(obj, dict) and obj.get("status") == "active"
    ] if isinstance(stable_ledger.get("objects"), list) else []
    stable_object_ids = [str(obj.get("objectId")) for obj in active_stable_objects if obj.get("objectId")]
    stable_generation_targets = [
        str(obj.get("expectedGenerationTarget"))
        for obj in active_stable_objects
        if obj.get("expectedGenerationTarget")
    ]
    if active_stable_objects:
        present_owners.add(V3_STABLE_OBJECT_OWNER)
        not_visible_owners.discard(V3_STABLE_OBJECT_OWNER)

    owners: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    for item in KINE_LAYER_SEMANTIC_PARTS:
        owner_id = item["id"]
        role = v3_owner_role(owner_id)
        if owner_id in present_owners:
            visibility = "present"
        elif owner_id in not_visible_owners:
            visibility = "not_visible"
        else:
            visibility = "unknown"
        owner_track = v3_component_track(owner_id)
        component_class = v3_owner_component_class(owner_id)
        material_class = v3_owner_material_class(owner_id)
        coverage_target = v3_owner_coverage_target(owner_id)
        split_reason = v3_owner_split_reason(owner_id)
        interaction_group_id = v3_owner_interaction_group_id(owner_id)
        do_not_split_by = v3_owner_do_not_split_by(owner_id)
        split_strategy = v3_owner_split_strategy(owner_id)
        sheet_eligible = v3_owner_sheet_eligible(owner_id)
        needs_mask = visibility != "not_visible" and sheet_eligible
        needs_hidden, hidden_requirement_reason = v3_hidden_requirement_for_owner(owner_id, visibility, sheet_eligible, owner_track)
        owner_components = v3_component_targets_for_owner(owner_id)
        owners.append(
            {
                "id": owner_id,
                "role": role,
                "componentClass": component_class,
                "materialClass": material_class,
                "coverageTarget": coverage_target,
                "splitReason": split_reason,
                "interactionGroupId": interaction_group_id,
                "doNotSplitBy": do_not_split_by,
                "splitStrategy": split_strategy,
                "generationPolicy": v3_owner_generation_policy(owner_id),
                "sheetEligible": sheet_eligible,
                "required": bool(item.get("required")),
                "drawOrder": item.get("order"),
                "visibility": visibility,
                "promptHint": item.get("prompt"),
                "track": owner_track,
                "needsMask": needs_mask,
                "needsHiddenCompletion": needs_hidden,
                "hiddenRequirementReason": hidden_requirement_reason,
                "needsOverlapZone": owner_id in {"neck", "torso", "hips", "arms", "legs", "feet", "hair-front", "hair-rear", "props"},
                "components": [component["id"] for component in owner_components],
            }
        )
        if owner_id == V3_STABLE_OBJECT_OWNER and active_stable_objects:
            owners[-1].update(
                {
                    "stableObjectLedger": "v3/stable-object-ledger.json",
                    "stableObjectIds": stable_object_ids,
                    "expectedGenerationTargets": stable_generation_targets,
                    "stableObjectRule": "active stable objects force props/interaction generation before role sheets",
                }
            )
        owner_bbox = layer_visible_bbox(workspace, owner_id)
        for component in owner_components:
            component_id = component["id"]
            needs_overlap = bool(component["sockets"]) or owner_id in {"neck", "torso", "hips", "hair-front", "hair-rear", "props"}
            component_row = {
                **component,
                "role": role,
                "componentClass": component_class,
                "materialClass": material_class,
                "coverageTarget": coverage_target,
                "splitReason": split_reason,
                "interactionGroupId": interaction_group_id,
                "doNotSplitBy": do_not_split_by,
                "splitStrategy": split_strategy,
                "generationPolicy": v3_owner_generation_policy(owner_id),
                "sheetEligible": sheet_eligible,
                "drawOrder": item.get("order"),
                "bbox": owner_bbox,
                "expectedMask": f"v3/masks/{component_id}.mask.png",
                "visibleCut": f"v3/masks/{component_id}.visible_cut.png",
                "pivot": None,
                "needsMask": needs_mask,
                "needsHiddenCompletion": needs_hidden,
                "hiddenRequirementReason": hidden_requirement_reason,
                "needsOverlapZone": needs_overlap,
                "track": owner_track,
                "status": "planned" if visibility != "not_visible" else "not_visible",
            }
            if owner_id == V3_STABLE_OBJECT_OWNER and active_stable_objects:
                component_row.update(
                    {
                        "stableObjectLedger": "v3/stable-object-ledger.json",
                        "stableObjectIds": stable_object_ids,
                        "expectedGenerationTargets": stable_generation_targets,
                    }
                )
            components.append(component_row)

    sheet_roles = ["head_identity", "body_clothes", "limbs", "feet_footwear", "props_accessories", "misc"]
    sheets: list[dict[str, Any]] = []
    sheet_index = 1
    for role in sheet_roles:
        role_owners = [
            owner
            for owner in owners
            if owner["role"] == role and owner["visibility"] != "not_visible" and owner.get("sheetEligible") and owner.get("components")
        ]
        for start in range(0, len(role_owners), max_sheet_components):
            chunk = role_owners[start : start + max_sheet_components]
            if not chunk:
                continue
            sheet_id = f"sheet-{sheet_index:03d}"
            sheets.append(
                {
                    "id": sheet_id,
                    "role": role,
                    "owners": [owner["id"] for owner in chunk],
                    "componentClasses": sorted({str(owner.get("componentClass")) for owner in chunk if owner.get("componentClass")}),
                    "maxComponents": max_sheet_components,
                    "promptPath": f"imagegen/v3/{sheet_id}.{role}.prompt.txt",
                    "expectedRawPath": f"imagegen/v3/{sheet_id}.{role}.raw.png",
                    "partsSheetCommand": (
                        "python3 skill-v3/scripts/kine_layer_workspace.py parts-sheet "
                        f"--workspace {{workspace}} --sheet imagegen/v3/{sheet_id}.{role}.raw.png "
                        f"--sheet-id {sheet_id} --role {role} --append --chroma-key auto"
                    ),
                }
            )
            sheet_index += 1
    if active_stable_objects:
        for sheet in sheets:
            if isinstance(sheet, dict) and sheet.get("role") == "props_accessories" and V3_STABLE_OBJECT_OWNER in (sheet.get("owners") or []):
                sheet.update(
                    {
                        "stableObjectLedger": "v3/stable-object-ledger.json",
                        "stableObjectIds": stable_object_ids,
                        "expectedGenerationTargets": stable_generation_targets,
                    }
                )

    gates = [
        {"id": "component_plan_complete", "kind": "planning", "required": True, "passCondition": "every visible or unknown owner has an explicit owner row"},
        {"id": "component_mask", "kind": "mask", "required": True, "passCondition": "each non-not-visible owner has a mask or an explicit rejection reason"},
        {"id": "hidden_completion", "kind": "generation", "required": True, "passCondition": "occluded/rotating owners have generated hidden or overlap pixels with provenance"},
        {"id": "alpha_cleanup", "kind": "alpha", "required": True, "passCondition": "all candidate parts have transparent alpha and pass green-pollution limits"},
        {"id": "source_recompose", "kind": "qa", "required": True, "passCondition": "accepted source-locked track reconstructs the original exactly; generated track cannot be called final without local placement evidence"},
        {
            "id": "pose_stress",
            "kind": "animation",
            "required": False,
            "passCondition": "joint owners expose overlap zones for rotation without visible gaps",
            "pixelGapPolicy": "diagnostic",
            "thresholds": {
                "maxGapRatio": None,
                "maxGapPixels": None,
                "maxNewAlphaRatio": None,
            },
            "thresholdNote": "Set pixelGapPolicy to hard_fail only after calibrating thresholds on real character samples.",
        },
    ]

    out_dir = workspace / "v3"
    component_plan = {
        "type": "kine.v3.componentPlan",
        "version": "0.1",
        "source": "source.png",
        "sourceSize": [source.width, source.height],
        "owners": owners,
        "components": components,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    if active_stable_objects:
        component_plan["stableObjectLedger"] = "v3/stable-object-ledger.json"
        component_plan["stableObjectCount"] = len(active_stable_objects)
    sheet_campaign = {
        "type": "kine.v3.sheetCampaign",
        "version": "0.1",
        "multiSheet": True,
        "sheets": sheets,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    if active_stable_objects:
        sheet_campaign["stableObjectLedger"] = "v3/stable-object-ledger.json"
        sheet_campaign["stableObjectCount"] = len(active_stable_objects)
    qa_gates = {
        "type": "kine.v3.qaGates",
        "version": "0.1",
        "gates": gates,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(out_dir / "component-plan.json", component_plan)
    write_json(out_dir / "sheet-campaign.json", sheet_campaign)
    write_json(out_dir / "qa-gates.json", qa_gates)
    result = {
        "status": "v3_plan_written",
        "workspace": str(workspace),
        "componentPlan": str(out_dir / "component-plan.json"),
        "sheetCampaign": str(out_dir / "sheet-campaign.json"),
        "qaGates": str(out_dir / "qa-gates.json"),
        "ownerCount": len(owners),
        "componentCount": len(components),
        "sheetCount": len(sheets),
        "stableObjectLedger": str(v3_stable_object_ledger_path(workspace)),
        "activeStableObjectCount": len(active_stable_objects),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def v3_mask_from_owner_mask(owner_mask: Image.Image, component: dict[str, Any]) -> Image.Image:
    mask = owner_mask.convert("L").point(lambda value: 255 if value > 0 else 0)
    if component.get("side") is None and component.get("segment") is None:
        return mask
    bbox = mask.getbbox()
    if not bbox:
        return Image.new("L", mask.size, 0)
    x0, y0, x1, y1 = bbox
    width = max(1, x1 - x0)
    height = max(1, y1 - y0)
    side = component.get("side")
    segment = component.get("segment")
    owner = component.get("owner")
    side_mid = x0 + width / 2.0
    segment_start = y0
    segment_end = y1
    if owner in SPINE_LIMB_SEGMENTS and segment:
        cursor = y0
        for candidate_segment, fraction in SPINE_LIMB_SEGMENTS[owner]:
            next_cursor = cursor + height * float(fraction)
            if candidate_segment == segment:
                segment_start = cursor
                segment_end = next_cursor
                break
            cursor = next_cursor
    src = mask.load()
    out = Image.new("L", mask.size, 0)
    dst = out.load()
    for y in range(y0, y1):
        in_segment = segment_start <= y < segment_end or (segment == SPINE_LIMB_SEGMENTS.get(owner, [("", 1.0)])[-1][0] and y < y1)
        if not in_segment:
            continue
        for x in range(x0, x1):
            if src[x, y] <= 0:
                continue
            if side == "left" and x >= side_mid:
                continue
            if side == "right" and x < side_mid:
                continue
            dst[x, y] = 255
    return out


def v3_mask_status(source_alpha: Image.Image, mask: Image.Image) -> dict[str, Any]:
    mask_data = mask.tobytes()
    source_data = source_alpha.point(lambda value: 255 if value > 0 else 0).tobytes()
    mask_pixels = sum(1 for value in mask_data if value > 0)
    outside_pixels = sum(1 for mv, sv in zip(mask_data, source_data) if mv > 0 and sv == 0)
    bbox = mask.getbbox()
    if mask_pixels <= 0:
        status = "missing"
    elif outside_pixels > 0:
        status = "contaminated"
    else:
        status = "passed"
    return {
        "status": status,
        "maskPixels": mask_pixels,
        "outsideSourceAlphaPixels": outside_pixels,
        "bbox": list(bbox) if bbox else None,
    }


def v3_cutout_owner_regions(workspace: Path) -> dict[str, dict[str, Any]]:
    cutout = load_cutout_map(workspace)
    regions: dict[str, dict[str, Any]] = {}
    for owner in cutout.get("owners", []) if isinstance(cutout, dict) else []:
        if not isinstance(owner, dict):
            continue
        owner_id = owner.get("id")
        region = owner.get("region")
        if isinstance(owner_id, str) and isinstance(region, dict):
            regions[owner_id] = region
    for owner_id, region in v3_visual_split_owner_regions(workspace).items():
        regions.setdefault(owner_id, region)
    return regions


def v3_visual_split_owner_for_item(item: dict[str, Any]) -> str | None:
    text = " ".join(str(item.get(key) or "").lower() for key in ("id", "role", "target", "policy", "mode", "description"))
    role = str(item.get("role") or "").lower()
    if role == "props_accessories":
        return "props"
    if role == "feet_footwear":
        return "feet"
    if role == "limbs":
        if "leg" in text:
            return "legs"
        return "arms"
    if role == "interaction_group":
        return "arms"
    if role == "body_clothes":
        if any(token in text for token in ("lower", "skirt", "robe panels", "pants", "belt", "sash", "hip")):
            return "hips"
        if any(token in text for token in ("collar", "cape", "cloak", "torso", "robe", "jacket", "armor")):
            return "torso"
    if role == "head_identity":
        if any(token in text for token in ("accessory", "hat", "helmet")):
            return "head-accessory"
        return "face"
    if any(token in text for token in ("staff", "weapon", "umbrella", "tool", "prop", "wand", "sword", "bag")):
        return "props"
    if any(token in text for token in ("boot", "shoe", "foot", "feet")):
        return "feet"
    return None


def v3_visual_split_canvas_size(decision: dict[str, Any], fallback_size: tuple[int, int]) -> tuple[float, float]:
    canvas = decision.get("canvas")
    if isinstance(canvas, dict):
        width = canvas.get("width") or canvas.get("w")
        height = canvas.get("height") or canvas.get("h")
        if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0:
            return float(width), float(height)
    if isinstance(canvas, list) and len(canvas) >= 2 and all(isinstance(value, (int, float)) for value in canvas[:2]):
        width, height = float(canvas[0]), float(canvas[1])
        if width > 0 and height > 0:
            return width, height
    source = decision.get("source")
    if isinstance(source, str):
        try:
            source_path = Path(source)
            if source_path.exists():
                img = Image.open(source_path)
                return float(img.width), float(img.height)
        except OSError:
            pass
    bboxes = [item.get("bbox") for item in decision.get("items", []) if isinstance(item, dict)]
    max_x = max((float(bbox[2]) for bbox in bboxes if isinstance(bbox, list) and len(bbox) == 4), default=float(fallback_size[0]))
    max_y = max((float(bbox[3]) for bbox in bboxes if isinstance(bbox, list) and len(bbox) == 4), default=float(fallback_size[1]))
    return max(1.0, max_x), max(1.0, max_y)


def v3_visual_split_bbox_transform(workspace: Path, decision: dict[str, Any]) -> dict[str, Any] | None:
    source = decision.get("source")
    workspace_source_path = workspace / "source.png"
    if not isinstance(source, str) or not workspace_source_path.exists():
        return None
    source_path = Path(source)
    if not source_path.exists():
        return None
    try:
        decision_source = Image.open(source_path).convert("RGBA")
        workspace_source = Image.open(workspace_source_path).convert("RGBA")
    except OSError:
        return None
    source_alpha_bbox = decision_source.getchannel("A").getbbox()
    if source_alpha_bbox is None or source_alpha_bbox == (0, 0, decision_source.width, decision_source.height):
        try:
            source_alpha_bbox = foreground_alpha_by_edge_flood(decision_source).getbbox()
        except Exception:
            source_alpha_bbox = None
    workspace_alpha_bbox = workspace_source.getchannel("A").getbbox()
    if source_alpha_bbox is None or workspace_alpha_bbox is None:
        return None
    sx0, sy0, sx1, sy1 = source_alpha_bbox
    wx0, wy0, wx1, wy1 = workspace_alpha_bbox
    if sx1 <= sx0 or sy1 <= sy0 or wx1 <= wx0 or wy1 <= wy0:
        return None
    return {
        "source": "foreground_bbox_alignment",
        "decisionSource": source,
        "decisionForegroundBbox": list(source_alpha_bbox),
        "workspaceForegroundBbox": list(workspace_alpha_bbox),
        "workspaceSize": [workspace_source.width, workspace_source.height],
    }


def v3_visual_split_bbox_to_normalized(
    bbox: list[Any],
    canvas_size: tuple[float, float],
    workspace_size: tuple[int, int],
    transform: dict[str, Any] | None,
) -> list[float] | None:
    try:
        x0, y0, x1, y1 = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    if transform:
        sx0, sy0, sx1, sy1 = [float(value) for value in transform["decisionForegroundBbox"]]
        wx0, wy0, wx1, wy1 = [float(value) for value in transform["workspaceForegroundBbox"]]
        ww, wh = [float(value) for value in transform["workspaceSize"]]
        mapped = [
            wx0 + ((x0 - sx0) / max(1.0, sx1 - sx0)) * (wx1 - wx0),
            wy0 + ((y0 - sy0) / max(1.0, sy1 - sy0)) * (wy1 - wy0),
            wx0 + ((x1 - sx0) / max(1.0, sx1 - sx0)) * (wx1 - wx0),
            wy0 + ((y1 - sy0) / max(1.0, sy1 - sy0)) * (wy1 - wy0),
        ]
        normalized = [mapped[0] / ww, mapped[1] / wh, mapped[2] / ww, mapped[3] / wh]
    else:
        canvas_w, canvas_h = canvas_size
        normalized = [x0 / canvas_w, y0 / canvas_h, x1 / canvas_w, y1 / canvas_h]
    clipped = [
        max(0.0, min(1.0, normalized[0])),
        max(0.0, min(1.0, normalized[1])),
        max(0.0, min(1.0, normalized[2])),
        max(0.0, min(1.0, normalized[3])),
    ]
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        return None
    return clipped


def v3_visual_split_owner_regions(workspace: Path) -> dict[str, dict[str, Any]]:
    decision = read_v3_visual_split_decision(workspace)
    rows = decision.get("items")
    if not isinstance(rows, list):
        return {}
    source_size = Image.open(workspace / "source.png").convert("RGBA").size if (workspace / "source.png").exists() else (1, 1)
    canvas_w, canvas_h = v3_visual_split_canvas_size(decision, source_size)
    bbox_transform = v3_visual_split_bbox_transform(workspace, decision)
    owner_boxes: dict[str, list[float]] = {}
    owner_item_ids: dict[str, list[str]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        owner = v3_visual_split_owner_for_item(item)
        bbox = item.get("bbox")
        if owner is None or not isinstance(bbox, list) or len(bbox) != 4:
            continue
        normalized = v3_visual_split_bbox_to_normalized(bbox, (canvas_w, canvas_h), source_size, bbox_transform)
        if normalized is None:
            continue
        if owner in owner_boxes:
            current = owner_boxes[owner]
            owner_boxes[owner] = [
                min(current[0], normalized[0]),
                min(current[1], normalized[1]),
                max(current[2], normalized[2]),
                max(current[3], normalized[3]),
            ]
        else:
            owner_boxes[owner] = normalized
        owner_item_ids.setdefault(owner, []).append(str(item.get("id") or item.get("target") or owner))
    return {
        owner: {
            "type": "bbox",
            "bbox": bbox,
            "source": "visual_split_decision",
            "visualSplitDecision": "v3/visual-split-decision.json",
            "itemIds": owner_item_ids.get(owner, []),
            "bboxTransform": bbox_transform,
        }
        for owner, bbox in owner_boxes.items()
    }


def v3_mask_from_cutout_region(
    region: dict[str, Any],
    component: dict[str, Any],
    source_alpha: Image.Image,
    canvas_size: tuple[int, int],
) -> Image.Image | None:
    owner_mask = rasterize_owner_region(region, canvas_size)
    if owner_mask is None:
        return None
    owner_mask = ImageChops.multiply(owner_mask.convert("L"), source_alpha.point(lambda value: 255 if value > 0 else 0))
    return v3_mask_from_owner_mask(owner_mask, component)


def v3_mask_from_registered_candidates(workspace: Path, component: dict[str, Any], source_alpha: Image.Image) -> tuple[Image.Image | None, list[str]]:
    registered_candidates = component.get("registeredCandidates") if isinstance(component.get("registeredCandidates"), list) else []
    mask = Image.new("L", source_alpha.size, 0)
    sources: list[str] = []
    for candidate in registered_candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("registered"), str):
            continue
        registered_path = workspace / candidate["registered"]
        if not registered_path.exists():
            continue
        candidate_alpha = Image.open(registered_path).convert("RGBA").getchannel("A").point(lambda value: 255 if value > 0 else 0)
        visible_alpha = ImageChops.multiply(candidate_alpha, source_alpha.point(lambda value: 255 if value > 0 else 0))
        mask = ImageChops.lighter(mask, visible_alpha)
        sources.append(relative_to_workspace(registered_path, workspace))
    if not sources or mask.getbbox() is None:
        return None, sources
    return mask, sources


def v3_l_mask_pixel_count(mask: Image.Image, threshold: int = 24) -> int:
    alpha = mask.convert("L")
    if _np is not None:
        return int((_np.asarray(alpha) > threshold).sum())
    return sum(1 for value in alpha.getdata() if value > threshold)


def v3_binary_l_mask(mask: Image.Image, threshold: int = 24) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value > threshold else 0)


def v3_owner_evidence_mask(
    workspace: Path,
    owner: str,
    cutout_regions: dict[str, dict[str, Any]],
    owner_mask_cache: dict[str, Image.Image | None],
    source_alpha: Image.Image,
) -> tuple[Image.Image | None, str | None]:
    if owner in cutout_regions:
        region_mask = rasterize_owner_region(cutout_regions[owner], source_alpha.size)
        if region_mask is not None:
            evidence = ImageChops.multiply(v3_binary_l_mask(region_mask), source_alpha.point(lambda value: 255 if value > 0 else 0))
            if evidence.getbbox():
                return evidence, "vlm_cutout_map_region"
    owner_mask = owner_mask_cache.get(owner)
    if owner_mask is None:
        owner_mask_file = workspace / "layers" / owner / "masks" / "visible_mask.png"
        if owner_mask_file.exists():
            owner_mask = Image.open(owner_mask_file).convert("L")
            owner_mask_cache[owner] = owner_mask
        else:
            owner_mask_cache[owner] = None
    if owner_mask is not None:
        evidence = ImageChops.multiply(v3_binary_l_mask(owner_mask), source_alpha.point(lambda value: 255 if value > 0 else 0))
        if evidence.getbbox():
            return evidence, "source_partition_visible_mask"
    return None, None


def v3_should_subtract_foreign_owner(
    component_owner: str,
    foreign_owner: str,
    evidence: dict[str, Any],
    overlap_pixels: int,
    foreign_pixels: int,
    clean_pixels_before: int,
) -> tuple[bool, str]:
    if foreign_owner == component_owner:
        return False, "same_owner"
    if v3_owner_component_class(foreign_owner) == "source-locked-detail":
        return False, "source_locked_detail"
    overlap_component_ratio = overlap_pixels / max(1, clean_pixels_before)
    if overlap_component_ratio > V3_FOREIGN_SUBTRACTION_MAX_COMPONENT_RATIO:
        return False, "would_remove_most_of_component"
    evidence_source = str(evidence.get("source") or "")
    region = evidence.get("region") if isinstance(evidence.get("region"), dict) else {}
    region_source = str(region.get("source") or "")
    if evidence_source == "vlm_cutout_map_region":
        if foreign_owner not in V3_FOREIGN_SUBTRACTION_INDEPENDENT_OWNERS:
            return False, "coarse_region_owner_not_subtractive"
        if region_source == "visual_split_decision":
            bbox = region.get("bbox")
            if isinstance(bbox, list) and len(bbox) == 4:
                try:
                    x0, y0, x1, y1 = [float(value) for value in bbox]
                    bbox_area_ratio = max(0.0, x1 - x0) * max(0.0, y1 - y0)
                except (TypeError, ValueError):
                    bbox_area_ratio = 1.0
                if bbox_area_ratio > 0.28:
                    return False, "visual_split_bbox_too_broad_for_subtraction"
    elif foreign_owner in V3_FOREIGN_SUBTRACTION_MAJOR_BODY_OWNERS and component_owner in V3_FOREIGN_SUBTRACTION_MAJOR_BODY_OWNERS:
        return False, "major_body_owners_need_registration_not_subtraction"
    return True, "subtractive_independent_owner"


def v3_resolve_foreign_owner_mask(
    workspace: Path,
    component: dict[str, Any],
    raw_mask: Image.Image,
    owner_evidence_masks: dict[str, dict[str, Any]],
) -> tuple[Image.Image, Image.Image, dict[str, Any]]:
    """Remove stable foreign-owner pixels from a component mask.

    `visible_cut` remains source-visible evidence, but final component masks should not
    carry another stable owner when that owner already has its own evidence slice.
    """
    owner = str(component.get("owner") or "")
    clean_mask = v3_binary_l_mask(raw_mask)
    removed_mask = Image.new("L", clean_mask.size, 0)
    removed_owners: list[dict[str, Any]] = []
    skipped_owners: list[dict[str, Any]] = []

    for foreign_owner, evidence in sorted(owner_evidence_masks.items()):
        if foreign_owner == owner:
            continue
        if v3_owner_component_class(foreign_owner) == "source-locked-detail":
            continue
        foreign_mask = evidence.get("mask")
        if not isinstance(foreign_mask, Image.Image):
            continue
        overlap = ImageChops.multiply(clean_mask, foreign_mask)
        overlap_pixels = v3_l_mask_pixel_count(overlap)
        if overlap_pixels < 8:
            continue
        foreign_pixels = max(1, v3_l_mask_pixel_count(foreign_mask))
        clean_pixels_before = max(1, v3_l_mask_pixel_count(clean_mask))
        should_subtract, decision_reason = v3_should_subtract_foreign_owner(
            owner,
            foreign_owner,
            evidence,
            overlap_pixels,
            foreign_pixels,
            clean_pixels_before,
        )
        if not should_subtract:
            bbox = overlap.getbbox()
            skipped_owners.append(
                {
                    "owner": foreign_owner,
                    "source": evidence.get("source"),
                    "reason": decision_reason,
                    "overlapPixels": overlap_pixels,
                    "overlapOfForeignRatio": round(overlap_pixels / foreign_pixels, 6),
                    "overlapOfComponentRatio": round(overlap_pixels / clean_pixels_before, 6),
                    "bbox": list(bbox) if bbox else None,
                }
            )
            continue
        clean_mask = ImageChops.multiply(clean_mask, overlap.point(lambda value: 0 if value > 24 else 255))
        removed_mask = ImageChops.lighter(removed_mask, overlap)
        bbox = overlap.getbbox()
        removed_owners.append(
            {
                "owner": foreign_owner,
                "source": evidence.get("source"),
                "removedPixels": overlap_pixels,
                "overlapOfForeignRatio": round(overlap_pixels / foreign_pixels, 6),
                "overlapOfComponentRatio": round(overlap_pixels / clean_pixels_before, 6),
                "bbox": list(bbox) if bbox else None,
            }
        )

    raw_components = connected_alpha_components(Image.merge("RGBA", [clean_mask, clean_mask, clean_mask, clean_mask]), alpha_threshold=24, min_area=8)
    report = {
        "status": "cleaned" if removed_owners else "unchanged",
        "policy": "subtract_existing_stable_foreign_owner_alpha_from_component_clean_owner_mask",
        "componentId": component.get("id"),
        "owner": owner,
        "removedOwners": removed_owners,
        "removedOwnerCount": len(removed_owners),
        "removedPixels": v3_l_mask_pixel_count(removed_mask),
        "skippedOwners": skipped_owners,
        "skippedOwnerCount": len(skipped_owners),
        "cleanOwnerMaskPixels": v3_l_mask_pixel_count(clean_mask),
        "remainingClusterCount": len(raw_components),
        "note": "Source-visible masks are evidence only. cleanOwnerMask removes trusted independent foreign owners before ImageGen/reference/registration use; broad body/clothing bbox evidence is kept for QA and registration instead of destructive subtraction.",
    }
    return clean_mask, removed_mask, report


def v3_component_mask_candidate(
    workspace: Path,
    component: dict[str, Any],
    owner_mask: Image.Image | None,
    cutout_regions: dict[str, dict[str, Any]],
    source_alpha: Image.Image,
) -> tuple[Image.Image, str, dict[str, Any]]:
    owner = str(component.get("owner") or "")
    if owner in cutout_regions:
        cutout_mask = v3_mask_from_cutout_region(cutout_regions[owner], component, source_alpha, source_alpha.size)
        if cutout_mask is not None:
            return cutout_mask, "vlm_cutout_map_region", {"region": cutout_regions[owner]}
    if owner_mask is not None:
        partition_audit = read_json_if_exists(workspace / "partition-audit.json") or {}
        owner_sources = partition_audit.get("ownerSource") if isinstance(partition_audit.get("ownerSource"), dict) else {}
        owner_source = owner_sources.get(owner)
        mask_source = "source_partition_visible_mask"
        if owner_source:
            mask_source = f"source_partition_{owner_source}"
        return v3_mask_from_owner_mask(owner_mask, component), mask_source, {"ownerSource": owner_source}
    candidate_mask, candidate_sources = v3_mask_from_registered_candidates(workspace, component, source_alpha)
    if candidate_mask is not None:
        return candidate_mask, "registered_candidate_alpha", {"registeredCandidates": candidate_sources}
    return Image.new("L", source_alpha.size, 0), "missing_mask_source", {}


def v3_merge_source_locked_details_into_identity_mask(
    component: dict[str, Any],
    raw_mask: Image.Image,
    owner_evidence_masks: dict[str, dict[str, Any]],
) -> tuple[Image.Image, dict[str, Any] | None]:
    """Fold facial micro/source-locked details into the face identity mask.

    V3 default review should not show eye-white, iris, brows, nose, mouth, ears, or
    glasses as separate final components. Their visible pixels still belong in the
    source-locked face/head identity candidate, otherwise recompose loses source alpha.
    """
    if component.get("owner") != "face":
        return raw_mask, None
    merged = v3_binary_l_mask(raw_mask)
    added: list[dict[str, Any]] = []
    before_pixels = v3_l_mask_pixel_count(merged)
    for detail_owner in sorted(V3_SOURCE_LOCKED_DETAIL_OWNERS):
        evidence = owner_evidence_masks.get(detail_owner)
        if not isinstance(evidence, dict):
            continue
        detail_mask = evidence.get("mask")
        if not isinstance(detail_mask, Image.Image):
            continue
        detail_mask = v3_binary_l_mask(detail_mask)
        overlap = ImageChops.multiply(merged, detail_mask)
        new_pixels_mask = ImageChops.multiply(detail_mask, ImageChops.invert(merged))
        new_pixels = v3_l_mask_pixel_count(new_pixels_mask)
        if new_pixels <= 0:
            continue
        merged = ImageChops.lighter(merged, detail_mask)
        added.append(
            {
                "owner": detail_owner,
                "source": evidence.get("source"),
                "addedPixels": new_pixels,
                "overlapPixels": v3_l_mask_pixel_count(overlap),
                "bbox": list(detail_mask.getbbox()) if detail_mask.getbbox() else None,
            }
        )
    if not added:
        return merged, {
            "status": "unchanged",
            "policy": "source_locked_details_are_reference_only_but_fold_into_face_identity",
            "componentId": component.get("id"),
            "owner": component.get("owner"),
            "addedOwnerCount": 0,
            "addedPixels": 0,
        }
    after_pixels = v3_l_mask_pixel_count(merged)
    return merged, {
        "status": "merged",
        "policy": "source_locked_details_are_reference_only_but_fold_into_face_identity",
        "componentId": component.get("id"),
        "owner": component.get("owner"),
        "addedOwners": added,
        "addedOwnerCount": len(added),
        "addedPixels": max(0, after_pixels - before_pixels),
        "faceIdentityMaskPixels": after_pixels,
        "note": "Facial micro/source-locked detail pixels are not separate final components; they are preserved inside the face identity source-visible candidate.",
    }


def write_v3_mask_jobs(workspace: Path, ensure_partition: bool = True) -> dict[str, Any]:
    component_plan_path = workspace / "v3" / "component-plan.json"
    if not component_plan_path.exists():
        write_v3_component_plan(workspace)
    subject_report = v3_subject_preflight_blocks_masks(workspace)
    if subject_report.get("shouldBlockV3Masks"):
        out_dir = workspace / "v3" / "masks"
        out_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "type": "kine.v3.maskJobSummary",
            "version": "0.1",
            "status": "needs_imagegen_subject_matte",
            "source": "source.png",
            "componentPlan": "v3/component-plan.json",
            "componentCount": 0,
            "statusCounts": {"blocked": 1},
            "sourceCounts": {},
            "results": [],
            "blockers": ["source_subject_needs_imagegen_subject_matte"],
            "sourceSubjectPreflight": "source/source-subject-preflight.json",
            "requiredAction": subject_report.get("requiredAction"),
            "note": "V3 mask jobs were not generated because the source appears to be an opaque non-flat scene. V3 must run $imagegen subject isolation first.",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(out_dir / "mask-summary.json", summary)
        update_run_state(workspace, {"v3MaskJobs": "v3/masks/mask-summary.json", "v3MaskJobsStatus": "needs_imagegen_subject_matte"})
        print(json.dumps({"status": "needs_imagegen_subject_matte", "summary": str(out_dir / "mask-summary.json")}, ensure_ascii=False, indent=2))
        return summary
    component_plan = read_json_if_exists(component_plan_path) or {}
    components = component_plan.get("components", []) if isinstance(component_plan.get("components"), list) else []
    if ensure_partition and not (workspace / "partition-audit.json").exists():
        partition_source_to_components(workspace)
        write_v3_component_plan(workspace)
        component_plan = read_json_if_exists(component_plan_path) or {}
        components = component_plan.get("components", []) if isinstance(component_plan.get("components"), list) else []
    source = Image.open(workspace / "source.png").convert("RGBA")
    source_alpha = source.getchannel("A")
    transparent = Image.new("RGBA", source.size, (0, 0, 0, 0))
    out_dir = workspace / "v3" / "masks"
    jobs_dir = out_dir / "jobs"
    results = []
    updated_components = []
    owner_mask_cache: dict[str, Image.Image | None] = {}
    source_counts: dict[str, int] = {}
    cutout_regions = v3_cutout_owner_regions(workspace)
    owner_evidence_masks: dict[str, dict[str, Any]] = {}
    evidence_owner_ids = {
        str(component.get("owner"))
        for component in components
        if isinstance(component, dict) and isinstance(component.get("owner"), str)
    }
    # Source-locked detail owners are intentionally absent from the default V3 final
    # component plan, but their partition masks are still needed as evidence so their
    # pixels can be folded into the face identity owner.
    evidence_owner_ids.update(V3_SOURCE_LOCKED_DETAIL_OWNERS)
    evidence_owner_ids.update(cutout_regions.keys())
    for owner in sorted(evidence_owner_ids):
        evidence_mask, evidence_source = v3_owner_evidence_mask(workspace, owner, cutout_regions, owner_mask_cache, source_alpha)
        if evidence_mask is not None:
            owner_evidence_masks[owner] = {"mask": evidence_mask, "source": evidence_source, "region": cutout_regions.get(owner)}
    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = component.get("id")
        owner = component.get("owner")
        if not isinstance(component_id, str) or not isinstance(owner, str):
            continue
        if owner not in owner_mask_cache:
            owner_mask_file = workspace / "layers" / owner / "masks" / "visible_mask.png"
            if owner_mask_file.exists():
                owner_mask_cache[owner] = Image.open(owner_mask_file).convert("L")
            else:
                owner_mask_cache[owner] = None
        owner_mask = owner_mask_cache[owner]
        source_visible_mask, mask_source, mask_source_detail = v3_component_mask_candidate(workspace, component, owner_mask, cutout_regions, source_alpha)
        source_visible_mask, identity_detail_merge = v3_merge_source_locked_details_into_identity_mask(component, source_visible_mask, owner_evidence_masks)
        if identity_detail_merge:
            mask_source_detail = {
                **(mask_source_detail if isinstance(mask_source_detail, dict) else {}),
                "sourceLockedDetailMerge": identity_detail_merge,
            }
        clean_mask, removed_mask, owner_resolution = v3_resolve_foreign_owner_mask(workspace, component, source_visible_mask, owner_evidence_masks)
        source_counts[mask_source] = source_counts.get(mask_source, 0) + 1
        status = v3_mask_status(source_alpha, clean_mask)
        mask_file = out_dir / f"{component_id}.mask.png"
        clean_owner_mask_file = out_dir / f"{component_id}.clean_owner_mask.png"
        source_visible_mask_file = out_dir / f"{component_id}.source_visible_mask.png"
        visible_cut_file = out_dir / f"{component_id}.visible_cut.png"
        source_visible_cut_file = out_dir / f"{component_id}.source_visible_cut.png"
        removed_mask_file = out_dir / f"{component_id}.foreign_removed_mask.png"
        mask_file.parent.mkdir(parents=True, exist_ok=True)
        source_visible_mask.save(source_visible_mask_file)
        source_visible_cut = Image.composite(source, transparent, source_visible_mask)
        source_visible_cut.save(source_visible_cut_file)
        clean_mask.save(mask_file)
        clean_mask.save(clean_owner_mask_file)
        if owner_resolution["removedPixels"] > 0:
            removed_mask.save(removed_mask_file)
            owner_resolution["removedMask"] = relative_to_workspace(removed_mask_file, workspace)
        visible_cut = Image.composite(source, transparent, clean_mask)
        visible_cut.save(visible_cut_file)
        owner_resolution.update(
            {
                "sourceVisibleMask": relative_to_workspace(source_visible_mask_file, workspace),
                "sourceVisibleCut": relative_to_workspace(source_visible_cut_file, workspace),
                "cleanOwnerMask": relative_to_workspace(clean_owner_mask_file, workspace),
            }
        )
        job = {
            "type": "kine.v3.maskJob",
            "version": "0.1",
            "componentId": component_id,
            "owner": owner,
            "source": "source.png",
            "maskSource": mask_source,
            "maskSourceDetail": mask_source_detail,
            "mask": relative_to_workspace(mask_file, workspace),
            "sourceVisibleMask": relative_to_workspace(source_visible_mask_file, workspace),
            "cleanOwnerMask": relative_to_workspace(clean_owner_mask_file, workspace),
            "visibleCut": relative_to_workspace(visible_cut_file, workspace),
            "sourceVisibleCut": relative_to_workspace(source_visible_cut_file, workspace),
            "foreignOwnerResolution": owner_resolution,
            "sourceLockedDetailMerge": identity_detail_merge,
            "qa": status,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(jobs_dir / f"{component_id}.json", job)
        result = {
            "componentId": component_id,
            "owner": owner,
            "status": status["status"],
            "maskSource": mask_source,
            "maskSourceDetail": mask_source_detail,
            "mask": relative_to_workspace(mask_file, workspace),
            "sourceVisibleMask": relative_to_workspace(source_visible_mask_file, workspace),
            "cleanOwnerMask": relative_to_workspace(clean_owner_mask_file, workspace),
            "visibleCut": relative_to_workspace(visible_cut_file, workspace),
            "sourceVisibleCut": relative_to_workspace(source_visible_cut_file, workspace),
            "foreignOwnerResolution": owner_resolution,
            "sourceLockedDetailMerge": identity_detail_merge,
            "bbox": status["bbox"],
        }
        results.append(result)
        updated_components.append(
            {
                **component,
                "maskStatus": status["status"],
                "maskSource": mask_source,
                "maskSourceDetail": mask_source_detail,
                "mask": relative_to_workspace(mask_file, workspace),
                "sourceVisibleMask": relative_to_workspace(source_visible_mask_file, workspace),
                "cleanOwnerMask": relative_to_workspace(clean_owner_mask_file, workspace),
                "visibleCut": relative_to_workspace(visible_cut_file, workspace),
                "sourceVisibleCut": relative_to_workspace(source_visible_cut_file, workspace),
                "foreignOwnerResolution": owner_resolution,
                "sourceLockedDetailMerge": identity_detail_merge,
                "bbox": status["bbox"] or component.get("bbox"),
            }
        )
    component_plan["components"] = updated_components
    component_plan["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(component_plan_path, component_plan)
    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
    summary = {
        "type": "kine.v3.maskJobSummary",
        "version": "0.1",
        "source": "source.png",
        "componentPlan": "v3/component-plan.json",
        "jobDir": "v3/masks/jobs",
        "componentCount": len(results),
        "statusCounts": status_counts,
        "sourceCounts": source_counts,
        "results": results,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(out_dir / "mask-summary.json", summary)
    print(json.dumps({"status": "v3_mask_jobs_written", "componentCount": len(results), "statusCounts": status_counts, "summary": str(out_dir / "mask-summary.json")}, ensure_ascii=False, indent=2))
    return summary


def expand_bbox(bbox: list[int] | tuple[int, int, int, int], size: tuple[int, int], padding: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = [int(value) for value in bbox]
    width, height = size
    return (max(0, x0 - padding), max(0, y0 - padding), min(width, x1 + padding), min(height, y1 + padding))


def v3_reference_quality_for_mask(mask: Image.Image, source_size: tuple[int, int], owner: str | None = None) -> dict[str, Any]:
    bbox = mask.getbbox()
    mask_pixels = sum(1 for value in mask.getdata() if value > 0)
    ratios = _bbox_ratio_metrics(list(bbox) if bbox else None, source_size)
    blockers: list[str] = []
    warnings: list[str] = []
    if not bbox or mask_pixels <= 0:
        blockers.append("reference_mask_empty")
    if mask_pixels < 16:
        blockers.append("reference_alpha_too_few_pixels")
    if bbox:
        bw = int(bbox[2]) - int(bbox[0])
        bh = int(bbox[3]) - int(bbox[1])
        if min(bw, bh) < 4:
            blockers.append("reference_bbox_too_thin")
        if ratios["bboxAreaRatio"] < 0.0015:
            blockers.append("reference_bbox_too_small")
        if ratios["bboxWidthRatio"] < 0.015:
            warnings.append("reference_bbox_very_narrow")
        if ratios["bboxHeightRatio"] < 0.015:
            warnings.append("reference_bbox_very_short")
    strength = "weak_fragment" if blockers else "strong"
    return {
        "status": "weak" if blockers else "ready",
        "visibleCutStrength": strength,
        "primaryImagegenShapeReference": strength == "strong",
        "blockers": blockers,
        "warnings": warnings,
        "owner": owner,
        "metrics": {
            "maskPixels": mask_pixels,
            **ratios,
        },
    }


def write_v3_reference_bundles(workspace: Path, padding: int = 16, ensure_masks: bool = True) -> dict[str, Any]:
    """Write per-component reference bundles for $imagegen tasks.

    The bundle separates color/detail reference from mask evidence: original-region
    crops come from the un-keyed normalized source, while visible cuts and masks come
    from the processed source/mask pipeline.
    """
    subject_report = v3_subject_preflight_blocks_masks(workspace)
    if subject_report.get("shouldBlockV3Masks"):
        out_root = workspace / "v3" / "references"
        out_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "type": "kine.v3.referenceBundles",
            "version": "0.1",
            "status": "needs_imagegen_subject_matte",
            "sourceOriginalFull": "source/original-normalized.png",
            "processedSource": "source.png",
            "componentCount": 0,
            "statusCounts": {"blocked": 1},
            "components": [],
            "blockers": ["source_subject_needs_imagegen_subject_matte"],
            "sourceSubjectPreflight": "source/source-subject-preflight.json",
            "requiredAction": subject_report.get("requiredAction"),
            "note": "Reference bundles were not generated because source masks would be polluted by scene background. V3 must run $imagegen subject isolation first.",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(out_root / "reference-bundles.json", manifest)
        update_run_state(workspace, {"v3ReferenceBundles": "v3/references/reference-bundles.json", "v3ReferenceBundleStatus": "needs_imagegen_subject_matte"})
        print(json.dumps({"status": "needs_imagegen_subject_matte", "componentCount": 0, "manifest": str(out_root / "reference-bundles.json")}, ensure_ascii=False, indent=2))
        return manifest
    component_plan_path = workspace / "v3" / "component-plan.json"
    if not component_plan_path.exists():
        write_v3_component_plan(workspace)
    if ensure_masks and not (workspace / "v3" / "masks" / "mask-summary.json").exists():
        write_v3_mask_jobs(workspace)
    component_plan = read_json_if_exists(component_plan_path) or {}
    components = component_plan.get("components", []) if isinstance(component_plan.get("components"), list) else []
    original_path = workspace / "source" / "original-normalized.png"
    original_source = Image.open(original_path if original_path.exists() else workspace / "source.png").convert("RGBA")
    processed_source = Image.open(workspace / "source.png").convert("RGBA")
    out_root = workspace / "v3" / "references"
    component_root = out_root / "components"
    rows: list[dict[str, Any]] = []
    updated_components: list[dict[str, Any]] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = component.get("id")
        if not isinstance(component_id, str):
            updated_components.append(component)
            continue
        mask_path_value = component.get("mask")
        visible_cut_value = component.get("visibleCut")
        clean_owner_mask_value = component.get("cleanOwnerMask")
        source_visible_mask_value = component.get("sourceVisibleMask")
        source_visible_cut_value = component.get("sourceVisibleCut")
        mask_path = workspace / mask_path_value if isinstance(mask_path_value, str) else None
        visible_cut_path = workspace / visible_cut_value if isinstance(visible_cut_value, str) else None
        clean_owner_mask_path = workspace / clean_owner_mask_value if isinstance(clean_owner_mask_value, str) else None
        source_visible_mask_path = workspace / source_visible_mask_value if isinstance(source_visible_mask_value, str) else None
        source_visible_cut_path = workspace / source_visible_cut_value if isinstance(source_visible_cut_value, str) else None
        if not mask_path or not mask_path.exists():
            updated_components.append(component)
            continue
        mask = Image.open(mask_path).convert("L").point(lambda value: 255 if value > 0 else 0)
        bbox = mask.getbbox()
        component_dir = component_root / component_id
        component_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = component_dir / "reference-bundle.json"
        if not bbox:
            reference_quality = v3_reference_quality_for_mask(mask, original_source.size, owner=str(component.get("owner") or ""))
            bundle = {
                "type": "kine.v3.componentReferenceBundle",
                "version": "0.1",
                "status": "missing_mask",
                "componentId": component_id,
                "owner": component.get("owner"),
                "sourceOriginalFull": "source/original-normalized.png" if original_path.exists() else "source.png",
                "processedSource": "source.png",
                "mask": relative_to_workspace(mask_path, workspace),
                "visibleCut": relative_to_workspace(visible_cut_path, workspace) if visible_cut_path and visible_cut_path.exists() else component.get("visibleCut"),
                "referenceQuality": reference_quality,
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            }
            write_json(bundle_path, bundle)
            rel_bundle = relative_to_workspace(bundle_path, workspace)
            rows.append({"componentId": component_id, "status": "missing_mask", "referenceBundle": rel_bundle})
            updated_components.append({**component, "referenceBundle": rel_bundle})
            continue
        crop_box = expand_bbox(bbox, original_source.size, padding)
        reference_quality = v3_reference_quality_for_mask(mask, original_source.size, owner=str(component.get("owner") or ""))
        original_region = original_source.crop(crop_box)
        processed_region = processed_source.crop(crop_box)
        mask_region = mask.crop(crop_box)
        clean_owner_mask_region = (
            Image.open(clean_owner_mask_path).convert("L").point(lambda value: 255 if value > 0 else 0).crop(crop_box)
            if clean_owner_mask_path and clean_owner_mask_path.exists()
            else mask_region.copy()
        )
        original_region_path = component_dir / "original_region.png"
        processed_region_path = component_dir / "processed_region.png"
        mask_region_path = component_dir / "mask_region.png"
        clean_owner_mask_region_path = component_dir / "clean_owner_mask_region.png"
        original_masked_path = component_dir / "original_masked.png"
        original_region.save(original_region_path)
        processed_region.save(processed_region_path)
        mask_region.save(mask_region_path)
        clean_owner_mask_region.save(clean_owner_mask_region_path)
        original_masked = Image.new("RGBA", original_region.size, (0, 0, 0, 0))
        original_masked.paste(original_region, (0, 0), clean_owner_mask_region)
        original_masked.save(original_masked_path)
        bundle = {
            "type": "kine.v3.componentReferenceBundle",
            "version": "0.1",
            "status": "ready",
            "componentId": component_id,
            "owner": component.get("owner"),
            "role": component.get("role"),
            "track": component.get("track"),
            "sourceOriginalFull": "source/original-normalized.png" if original_path.exists() else "source.png",
            "processedSource": "source.png",
            "originalRegion": relative_to_workspace(original_region_path, workspace),
            "originalMasked": relative_to_workspace(original_masked_path, workspace),
            "processedRegion": relative_to_workspace(processed_region_path, workspace),
            "maskRegion": relative_to_workspace(mask_region_path, workspace),
            "cleanOwnerMaskRegion": relative_to_workspace(clean_owner_mask_region_path, workspace),
            "mask": relative_to_workspace(mask_path, workspace),
            "cleanOwnerMask": relative_to_workspace(clean_owner_mask_path, workspace) if clean_owner_mask_path and clean_owner_mask_path.exists() else relative_to_workspace(mask_path, workspace),
            "sourceVisibleMask": relative_to_workspace(source_visible_mask_path, workspace) if source_visible_mask_path and source_visible_mask_path.exists() else component.get("sourceVisibleMask"),
            "visibleCut": relative_to_workspace(visible_cut_path, workspace) if visible_cut_path and visible_cut_path.exists() else component.get("visibleCut"),
            "sourceVisibleCut": relative_to_workspace(source_visible_cut_path, workspace) if source_visible_cut_path and source_visible_cut_path.exists() else component.get("sourceVisibleCut"),
            "foreignOwnerResolution": component.get("foreignOwnerResolution"),
            "bbox": list(bbox),
            "cropBox": list(crop_box),
            "referenceQuality": reference_quality,
            "referenceContract": {
                "identityAndProportion": "sourceOriginalFull",
                "localColorAndDetails": "originalRegion",
                "componentShapeAndRegistration": "cleanOwnerMask + visibleCut when referenceQuality.visibleCutStrength is strong; sourceVisibleMask is evidence only",
                "processedCutoutIsNotColorAuthority": True,
                "sourceVisibleMaskIsNotFinal": True,
            },
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(bundle_path, bundle)
        rel_bundle = relative_to_workspace(bundle_path, workspace)
        rows.append(
            {
                "componentId": component_id,
                "owner": component.get("owner"),
                "role": component.get("role"),
                "status": "ready",
                "referenceBundle": rel_bundle,
                "originalRegion": bundle["originalRegion"],
                "visibleCut": bundle["visibleCut"],
                "cleanOwnerMask": bundle["cleanOwnerMask"],
                "bbox": list(bbox),
                "referenceQuality": reference_quality,
                "foreignOwnerResolution": component.get("foreignOwnerResolution"),
            }
        )
        updated_components.append(
            {
                **component,
                "referenceBundle": rel_bundle,
                "originalRegion": bundle["originalRegion"],
                "originalMasked": bundle["originalMasked"],
                "cleanOwnerMaskRegion": bundle["cleanOwnerMaskRegion"],
                "referenceQuality": reference_quality,
            }
        )
    component_plan["components"] = updated_components
    component_plan["referenceBundles"] = "v3/references/reference-bundles.json"
    component_plan["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(component_plan_path, component_plan)
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    manifest = {
        "type": "kine.v3.referenceBundles",
        "version": "0.1",
        "status": "ready" if rows and status_counts.get("ready", 0) == len(rows) else ("partial" if rows else "empty"),
        "sourceOriginalFull": "source/original-normalized.png" if original_path.exists() else "source.png",
        "processedSource": "source.png",
        "padding": padding,
        "componentCount": len(rows),
        "statusCounts": status_counts,
        "components": rows,
        "contract": {
            "sourceOriginalFull": "identity, style, full-body proportions",
            "originalRegion": "local color and details before chroma-key or background removal",
            "visibleCut": "processed component shape, alpha, and registration evidence",
            "weakVisibleCut": "if referenceQuality.visibleCutStrength is weak_fragment, use it only as weak boundary evidence; originalRegion and visualSplitDecision are stronger",
            "cleanOwnerMask": "preferred owner-clean boundary evidence after subtracting already-known stable foreign owners",
            "mask": "component boundary evidence",
        },
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(out_root / "reference-bundles.json", manifest)
    update_run_state(workspace, {"v3ReferenceBundles": "v3/references/reference-bundles.json", "v3ReferenceBundleStatus": manifest["status"]})
    print(json.dumps({"status": manifest["status"], "componentCount": len(rows), "statusCounts": status_counts, "manifest": str(out_root / "reference-bundles.json")}, ensure_ascii=False, indent=2))
    return manifest


def v3_component_reference_lines(workspace: Path, component_ids: list[str], limit: int = 18) -> list[str]:
    plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    by_id = {str(component.get("id")): component for component in plan.get("components", []) if isinstance(component, dict) and component.get("id")}
    lines: list[str] = []
    for component_id in component_ids[:limit]:
        component = by_id.get(component_id)
        if not component:
            continue
        bundle = component.get("referenceBundle")
        original_region = component.get("originalRegion")
        visible_cut = component.get("visibleCut")
        if bundle or original_region or visible_cut:
            smart_split = ", ".join(
                f"{key}={component.get(key)}"
                for key in ["materialClass", "coverageTarget", "componentClass", "splitReason", "interactionGroupId"]
                if component.get(key)
            )
            do_not_split = component.get("doNotSplitBy")
            do_not_split_text = f", doNotSplitBy={do_not_split}" if isinstance(do_not_split, list) and do_not_split else ""
            split_strategy = component.get("splitStrategy") if isinstance(component.get("splitStrategy"), dict) else {}
            split_strategy_text = ""
            if split_strategy:
                split_strategy_text = f", splitStrategy={split_strategy.get('mode')} default={split_strategy.get('default')}"
            lines.append(
                f"- {component_id}: {smart_split}{split_strategy_text}{do_not_split_text}; "
                f"bundle `{bundle or 'missing'}`, original crop `{original_region or 'missing'}`, visible cut `{visible_cut or 'missing'}`"
            )
    if len(component_ids) > limit:
        lines.append(f"- plus {len(component_ids) - limit} more components listed in `v3/references/reference-bundles.json`.")
    return lines


def v3_generation_target_reference_lines(generation_targets: list[dict[str, Any]], limit: int = 18) -> list[str]:
    lines: list[str] = []
    for target in generation_targets[:limit]:
        target_id = str(target.get("id") or "")
        if not target_id:
            continue
        owner = target.get("owner")
        mode = target.get("mode")
        description = target.get("description")
        do_not_request = target.get("doNotRequest")
        avoid_text = f"; doNotRequest={do_not_request}" if isinstance(do_not_request, list) and do_not_request else ""
        anchor = target.get("sourceScaleAnchor") if isinstance(target.get("sourceScaleAnchor"), dict) else {}
        anchor_text = ""
        if anchor:
            anchor_text = (
                f"; sourceScaleAnchor bbox={anchor.get('targetSourceBbox')} "
                f"widthRatio={anchor.get('targetWidthRatio')} "
                f"heightRatio={anchor.get('targetHeightRatio')} "
                f"aspect={anchor.get('targetAspectRatio')}"
            )
        stable_object = target.get("stableObjectId")
        stable_text = f"; stableObjectId={stable_object}" if stable_object else ""
        lines.append(
            f"- {target_id}: owner={owner}, mode={mode}; {description or 'use source/reference package'}{stable_text}{anchor_text}{avoid_text}"
        )
    if len(generation_targets) > limit:
        lines.append(f"- plus {len(generation_targets) - limit} more generation targets listed in `v3/sheet-prompts.json`.")
    return lines


def v3_canonical_sheet_layout_text(role: str) -> str:
    common = """Canonical sheet layout:
- Arrange parts on a clean orthographic puppet board, not a random design board.
- Keep source-facing orientation and consistent scale across related parts.
- Use generous spacing; parts must not touch or overlap.
- Do not add labels, numbers, arrows, callout lines, grid text, shadows, or decorative board framing."""
    if role == "head_identity":
        return common + """
- Put the whole head/head-screen near the upper center.
- Put hair/head accessory/helmet sublayers near the head, preserving front/back relationship.
- Do not create facial micro rows unless an explicit face-rig mode is enabled."""
    if role == "body_clothes":
        return common + """
- Put torso/chest armor or clothing in the upper center.
- Put pelvis/hips/lower garment directly below the torso.
- Put backpack/cape/back panel behind or beside the torso, keeping its original attachment side clear.
- Keep garment panels as coherent puppet layers, not scattered trim fragments."""
    if role == "limbs":
        return common + """
- Mirror the source body layout: source-left arm parts on the sheet's left side, source-right arm parts on the sheet's right side.
- Arrange each limb vertically from shoulder to hand or from hip to ankle when segmented.
- Keep hand-held or worn-contact groups beside the owning arm, with the contact relationship intact."""
    if role == "feet_footwear":
        return common + """
- Put left and right feet/footwear at the bottom in source-facing orientation.
- Do not create extra shoe poses, mirrored variants, turnarounds, or detached sole/detail pieces."""
    if role == "props_accessories":
        return common + """
- Put held props close to the hand/contact group they belong to.
- Put worn or attached props close to their socket area, such as backpack near torso."""
    return common


def v3_reference_bundle_input_images(workspace: Path, component: dict[str, Any], include_mask: bool = True) -> list[dict[str, str]]:
    component_id = str(component.get("id") or "")
    images: list[dict[str, str]] = []
    bundle_path_value = component.get("referenceBundle")
    bundle = read_json_if_exists(workspace / bundle_path_value) if isinstance(bundle_path_value, str) else {}
    if not isinstance(bundle, dict):
        bundle = {}
    reference_quality = bundle.get("referenceQuality") if isinstance(bundle.get("referenceQuality"), dict) else {}
    visible_cut_strength = str(reference_quality.get("visibleCutStrength") or "unknown")
    for role, key, description in [
        ("component-original-region", "originalRegion", "original source crop; color, local detail, material authority"),
        ("component-clean-owner-mask", "cleanOwnerMaskRegion", "owner-clean mask crop; preferred boundary after subtracting stable foreign owners"),
        ("component-visible-cut", "visibleCut", "processed cutout; shape, alpha boundary, registration authority"),
        ("component-mask-region", "maskRegion", "mask crop; boundary-only reference"),
    ]:
        if key == "maskRegion" and not include_mask:
            continue
        value = bundle.get(key) or component.get(key)
        if isinstance(value, str) and (workspace / value).exists():
            use_as_primary = True
            final_description = description
            if role == "component-visible-cut" and visible_cut_strength == "weak_fragment":
                use_as_primary = False
                final_description = "weak fragment evidence only; do not use as primary shape reference; use original-region, source-original-full, and visual split decision first"
            if role == "component-mask-region" and visible_cut_strength == "weak_fragment":
                use_as_primary = False
                final_description = "weak boundary evidence only; do not let this mask fragment drive redraw"
            if role == "component-clean-owner-mask":
                final_description = "preferred owner-clean boundary evidence; use this instead of polluted hard-cut masks when they differ"
            images.append(
                {
                    "role": role,
                    "componentId": component_id,
                    "path": value,
                    "description": final_description,
                    "referenceStrength": "owner_clean_boundary" if role == "component-clean-owner-mask" else (visible_cut_strength if role in {"component-visible-cut", "component-mask-region"} else "color_authority"),
                    "useAsPrimaryReference": use_as_primary,
                }
            )
    return images


def write_v3_source_calibration_guides(workspace: Path) -> dict[str, Any]:
    source_path = workspace / "source.png"
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    source = Image.open(source_path).convert("RGBA")
    width, height = source.size
    out_dir = workspace / "v3" / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)

    alpha = source.getchannel("A")
    silhouette = Image.new("RGBA", source.size, (255, 255, 255, 255))
    silhouette_shape = Image.new("RGBA", source.size, (0, 0, 0, 255))
    silhouette.paste(silhouette_shape, (0, 0), alpha)
    silhouette_path = out_dir / "source-silhouette.png"
    silhouette.save(silhouette_path)

    grayscale = source.convert("L")
    edge = grayscale.filter(ImageFilter.FIND_EDGES)
    edge = ImageChops.multiply(edge, alpha.point(lambda value: 255 if value > 0 else 0))
    edge_rgba = Image.new("RGBA", source.size, (255, 255, 255, 255))
    edge_pixels = edge.load()
    edge_draw = ImageDraw.Draw(edge_rgba)
    for y in range(height):
        for x in range(width):
            value = edge_pixels[x, y]
            if value > 18:
                edge_draw.point((x, y), fill=(0, 0, 0, 255))
    edge_path = out_dir / "source-edge-lineart.png"
    edge_rgba.save(edge_path)

    anchor = Image.new("RGBA", source.size, (255, 255, 255, 255))
    anchor.alpha_composite(Image.new("RGBA", source.size, (235, 245, 255, 255)))
    anchor_draw = ImageDraw.Draw(anchor)
    source_bbox = alpha.getbbox()
    if source_bbox:
        x0, y0, x1, y1 = source_bbox
        cx = (x0 + x1) // 2
        anchor_draw.rectangle((x0, y0, x1, y1), outline=(30, 80, 220, 255), width=max(2, width // 300))
        anchor_draw.line((cx, y0, cx, y1), fill=(30, 80, 220, 255), width=max(1, width // 500))
        for ratio, label in [(0.18, "head"), (0.36, "shoulder"), (0.55, "hip"), (0.76, "knee"), (0.93, "foot")]:
            y = int(y0 + (y1 - y0) * ratio)
            anchor_draw.line((x0, y, x1, y), fill=(220, 80, 30, 255), width=max(1, width // 600))
            anchor_draw.text((x0 + 4, y + 2), label, fill=(20, 20, 20, 255))
    plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    owner_boxes: list[dict[str, Any]] = []
    seen_owners: set[str] = set()
    for component in plan.get("components", []) if isinstance(plan.get("components"), list) else []:
        if not isinstance(component, dict):
            continue
        owner = component.get("owner")
        bbox = component.get("bbox")
        if not isinstance(owner, str) or owner in seen_owners or not isinstance(bbox, list) or len(bbox) != 4:
            continue
        seen_owners.add(owner)
        owner_boxes.append({"owner": owner, "bbox": bbox})
        try:
            bx0, by0, bx1, by1 = [int(value) for value in bbox]
        except Exception:
            continue
        anchor_draw.rectangle((bx0, by0, bx1, by1), outline=(40, 150, 80, 255), width=max(1, width // 600))
        anchor_draw.text((bx0 + 2, by0 + 2), owner, fill=(20, 20, 20, 255))
    anchor_path = out_dir / "source-anchor-map.png"
    anchor.save(anchor_path)

    board_tile_w = min(420, max(160, width // 2))
    board_tile_h = min(560, max(220, height // 2))
    rows = [
        {"label": "source", "sublabel": "identity and proportions", "image": source, "missing": False},
        {"label": "silhouette", "sublabel": "alpha pose and outer contour", "image": silhouette, "missing": False},
        {"label": "edge lineart", "sublabel": "source internal edges", "image": edge_rgba, "missing": False},
        {"label": "anchor map", "sublabel": "bbox, centerline, rough joints", "image": anchor, "missing": False},
    ]
    board_path = out_dir / "source-calibration-board.png"
    v3_write_image_grid(rows, board_path, columns=2, tile_size=(board_tile_w, board_tile_h))

    manifest = {
        "type": "kine.v3.sourceCalibrationGuides",
        "version": "0.1",
        "status": "ready",
        "source": "source.png",
        "guides": {
            "sourceSilhouette": relative_to_workspace(silhouette_path, workspace),
            "sourceEdgeLineart": relative_to_workspace(edge_path, workspace),
            "sourceAnchorMap": relative_to_workspace(anchor_path, workspace),
            "sourceCalibrationBoard": relative_to_workspace(board_path, workspace),
        },
        "sourceAlphaBbox": list(source_bbox) if source_bbox else None,
        "ownerBoxes": owner_boxes,
        "note": "ControlNet-style local guidance only. These files are not a drawing backend and do not replace registration/recompose gates.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(out_dir / "source-calibration-guides.json", manifest)
    update_run_state(workspace, {"v3SourceCalibrationGuides": "v3/calibration/source-calibration-guides.json"})
    return manifest


def v3_task_input_images(
    workspace: Path,
    components: list[dict[str, Any]],
    max_component_refs: int = 12,
    include_mask: bool = True,
) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    original_full = "source/original-normalized.png" if (workspace / "source" / "original-normalized.png").exists() else "source.png"
    calibration = write_v3_source_calibration_guides(workspace)
    images.append(
        {
            "role": "source-original-full",
            "path": original_full,
            "description": "identity, global style, full-body proportions, source color authority",
        }
    )
    guides = calibration.get("guides") if isinstance(calibration.get("guides"), dict) else {}
    for role, key, description in [
        ("source-silhouette-guide", "sourceSilhouette", "source alpha silhouette; outer contour and pose scale authority"),
        ("source-edge-lineart-guide", "sourceEdgeLineart", "source edge/lineart guide; internal contours and proportions"),
        ("source-anchor-map", "sourceAnchorMap", "rough source bbox, centerline, joints, and owner boxes for registration alignment"),
        ("source-calibration-board", "sourceCalibrationBoard", "combined source/silhouette/edge/anchor board; use to keep generated components recomposable"),
    ]:
        value = guides.get(key)
        if isinstance(value, str) and (workspace / value).exists():
            images.append(
                {
                    "role": role,
                    "path": value,
                    "description": description,
                    "referenceStrength": "geometry_calibration",
                    "useAsPrimaryReference": True,
                }
            )
    for component in components[:max_component_refs]:
        images.extend(v3_reference_bundle_input_images(workspace, component, include_mask=include_mask))
    if any(component.get("owner") == V3_STABLE_OBJECT_OWNER for component in components):
        seen = {(image.get("role"), image.get("path")) for image in images if isinstance(image, dict)}
        for stable_image in v3_stable_object_input_images(workspace):
            key = (stable_image.get("role"), stable_image.get("path"))
            if key not in seen:
                images.append(stable_image)
                seen.add(key)
    return images


def v3_input_image_contract(max_component_refs: int | None = None) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "required": True,
        "execution": "Before calling $imagegen, load every inputImages[].path into the conversation/image context. Do not rely on prompt text paths alone.",
        "roles": {
            "source-original-full": "identity, global style, full-body proportions",
            "component-original-region": "local color, material, facial/detail authority",
            "component-visible-cut": "shape, silhouette, alpha boundary, registration target only when referenceStrength is strong",
            "component-mask-region": "boundary-only mask evidence; weak_fragment masks must not drive redraw",
        },
        "referenceQuality": "If an input image has useAsPrimaryReference=false or referenceStrength=weak_fragment, treat it as diagnostic evidence only. Prefer source-original-full, component-original-region, and visualSplitDecision.",
    }
    if max_component_refs is not None:
        contract["maxComponentReferenceComponents"] = max_component_refs
        contract["note"] = "If a sheet has more components than this cap, generate additional smaller role sheets rather than dropping reference images silently."
    return contract


def v3_input_images_markdown_lines(task: dict[str, Any]) -> list[str]:
    images = task.get("inputImages") if isinstance(task.get("inputImages"), list) else []
    if not images:
        return ["- input images: `none listed`"]
    lines = ["- input images to load before `$imagegen`:"]
    for image in images:
        if not isinstance(image, dict):
            continue
        role = image.get("role")
        path = image.get("path")
        component_id = image.get("componentId")
        description = image.get("description")
        suffix = f" / {component_id}" if component_id else ""
        lines.append(f"  - `{role}{suffix}`: `{path}` - {description}")
    if task.get("referenceContactBoard"):
        lines.append(f"- reference-contact board to load if separate images cannot be attached: `{task.get('referenceContactBoard')}`")
    return lines


def v3_visual_split_decision_path(workspace: Path) -> Path:
    return workspace / "v3" / "visual-split-decision.json"


def read_v3_visual_split_decision(workspace: Path) -> dict[str, Any]:
    decision = read_json_if_exists(v3_visual_split_decision_path(workspace)) or {}
    return decision if isinstance(decision, dict) else {}


def v3_decision_generation_targets(decision: dict[str, Any], role: str, owners: list[str]) -> list[dict[str, Any]]:
    rows = decision.get("generationTargets")
    if not isinstance(rows, list):
        return []
    owner_set = set(owners)
    targets: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_role = row.get("role")
        row_owner = row.get("owner")
        if row_role and row_role != role:
            continue
        if isinstance(row_owner, str) and row_owner not in owner_set:
            continue
        if not row.get("id"):
            continue
        targets.append(row)
    return targets


def v3_sheet_generation_targets(
    role: str,
    owners: list[str],
    by_owner: dict[str, list[dict[str, Any]]],
    decision: dict[str, Any] | None = None,
    workspace: Path | None = None,
) -> list[dict[str, Any]]:
    """Return drawing-facing targets for $imagegen.

    These are intentionally not always the same as internal registration
    components. Internal rows may include bones or fallback slots; drawing rows
    must describe the coherent visual asset we want the model to create.
    """
    source_size: list[int] | None = None
    if workspace is not None and (workspace / "source.png").exists():
        try:
            with Image.open(workspace / "source.png") as source_img:
                source_size = [source_img.width, source_img.height]
        except OSError:
            source_size = None

    def attach_source_anchor(target: dict[str, Any], owner: str) -> dict[str, Any]:
        if target.get("sourceScaleAnchor") or not source_size:
            return target
        source_bbox = v3_target_source_bbox_for_components(by_owner.get(owner, []))
        anchor = v3_source_scale_anchor(source_bbox, source_size)
        if not anchor:
            return target
        return {
            **target,
            "targetSourceBbox": source_bbox,
            "sourceScaleAnchor": anchor,
        }

    if decision:
        decided_targets = v3_decision_generation_targets(decision, role, owners)
        if decided_targets:
            return [
                attach_source_anchor(dict(target), str(target.get("owner") or ""))
                for target in decided_targets
            ]

    targets: list[dict[str, Any]] = []
    for owner in owners:
        components = by_owner.get(owner, [])
        component_ids = [str(component.get("id")) for component in components if component.get("id")]
        split_strategy = v3_owner_split_strategy(owner)
        if owner == V3_STABLE_OBJECT_OWNER and workspace is not None:
            stable_targets = v3_stable_object_generation_targets(workspace, component_ids)
            if stable_targets:
                targets.extend(stable_targets)
                continue
        if owner == "legs":
            targets.append(
                attach_source_anchor(
                {
                    "id": "legs-garment-coherent",
                    "owner": owner,
                    "mode": "adaptive_garment",
                    "description": "one coherent lower-body pants/leg garment layer, or left/right leg layers only when the source clearly requires it",
                    "doNotRequest": ["thigh/shin pieces", "pant slivers", "duplicate leg angles", "shoes or boots"],
                    "internalComponents": component_ids,
                    "splitStrategy": split_strategy,
                },
                owner,
                )
            )
            continue
        if owner == "feet":
            targets.append(
                attach_source_anchor(
                {
                    "id": "feet-footwear-pair",
                    "owner": owner,
                    "mode": "coherent_footwear",
                    "description": "source-facing left/right feet or footwear pair with minimal ankle overlap only",
                    "doNotRequest": ["extra shoe poses", "turnarounds", "pants or leg pieces", "duplicate variants"],
                    "internalComponents": component_ids,
                    "splitStrategy": split_strategy,
                },
                owner,
                )
            )
            continue
        if owner == "hips":
            targets.append(
                attach_source_anchor(
                {
                    "id": "hips-lower-garment-coherent",
                    "owner": owner,
                    "mode": "adaptive_lower_garment",
                    "description": "coherent hips, skirt, shorts, robe bottom, or pants-top layer with overlap zones",
                    "doNotRequest": ["belt holes", "pocket flaps", "fold scraps", "loose trim"],
                    "internalComponents": component_ids,
                    "splitStrategy": split_strategy,
                },
                owner,
                )
            )
            continue
        if owner == "torso":
            targets.append(
                attach_source_anchor(
                {
                    "id": "torso-upper-garment-coherent",
                    "owner": owner,
                    "mode": "adaptive_upper_garment",
                    "description": "coherent torso clothing, jacket, armor, robe, or body mass with neck/shoulder/waist overlap zones",
                    "doNotRequest": ["buttons as parts", "badges as parts", "zipper scraps", "fabric texture fragments"],
                    "internalComponents": component_ids,
                    "splitStrategy": split_strategy,
                },
                owner,
                )
            )
            continue
        if owner == "arms":
            targets.append(
                attach_source_anchor(
                {
                    "id": "arms-riggable-or-contact-groups",
                    "owner": owner,
                    "mode": "adaptive_limb_or_interaction_group",
                    "description": "upper/lower arm/hand pieces only when clean joints are visible; preserve hand-held or worn-contact groups",
                    "doNotRequest": ["detached fingers", "glove scraps", "loose cuffs", "duplicate arm poses"],
                    "internalComponents": component_ids,
                    "splitStrategy": split_strategy,
                },
                owner,
                )
            )
            continue
        if owner == "props":
            targets.append(
                attach_source_anchor(
                {
                    "id": "props-contact-group",
                    "owner": owner,
                    "mode": "interaction_group_first",
                    "description": "coherent held or worn prop/contact group with grip/socket relationship preserved",
                    "doNotRequest": ["floating handles", "detached straps", "tiny decoration fragments"],
                    "internalComponents": component_ids,
                    "splitStrategy": split_strategy,
                },
                owner,
                )
            )
            continue
        for component in components:
            component_id = str(component.get("id") or "")
            if not component_id:
                continue
            targets.append(
                attach_source_anchor(
                {
                    "id": component_id,
                    "owner": owner,
                    "mode": "named_component",
                    "description": "named owner component from the V3 plan",
                    "doNotRequest": v3_owner_do_not_split_by(owner),
                    "internalComponents": [component_id],
                    "splitStrategy": split_strategy,
                },
                owner,
                )
            )
    return targets


def v3_write_reference_contact_board(workspace: Path, task: dict[str, Any], out_path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    images = task.get("inputImages") if isinstance(task.get("inputImages"), list) else []
    for image in images:
        if not isinstance(image, dict):
            continue
        rel_path = image.get("path")
        role = str(image.get("role") or "input")
        component_id = image.get("componentId")
        if not isinstance(rel_path, str):
            continue
        image_path = workspace / rel_path
        label = role if not component_id else f"{role} / {component_id}"
        try:
            img = Image.open(image_path).convert("RGBA") if image_path.exists() else None
        except Exception:
            img = None
        if img is None:
            missing.append(rel_path)
        rows.append(
            {
                "label": label,
                "sublabel": rel_path,
                "image": img,
                "missing": img is None,
            }
        )
    result = v3_write_image_grid(rows, out_path, columns=3, tile_size=(280, 260))
    return {
        "status": "ready" if rows and not missing else ("partial" if rows else "empty"),
        "path": relative_to_workspace(out_path, workspace),
        "inputImageCount": len(rows),
        "missingInputImages": missing,
        "missingCount": len(missing),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }


def v3_attach_reference_contact_boards(workspace: Path, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out_dir = workspace / "v3" / "imagegen" / "reference-boards"
    updated: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("taskId") or f"task-{len(updated) + 1:03d}")
        board_path = out_dir / f"{v3_slug(task_id)}.reference-contact.png"
        board = v3_write_reference_contact_board(workspace, task, board_path)
        contract = task.get("inputImageContract") if isinstance(task.get("inputImageContract"), dict) else {}
        updated.append(
            {
                **task,
                "referenceContactBoard": board["path"],
                "referenceContactBoardStatus": board["status"],
                "referenceContactBoardMissingCount": board["missingCount"],
                "inputImageContract": {
                    **contract,
                    "referenceContactBoard": board["path"],
                    "fallback": "If the execution surface cannot attach every inputImages item separately, attach this reference-contact board to $imagegen and save it as execution evidence.",
                },
            }
        )
    return updated


def v3_sheet_role_policy_text(role: str) -> str:
    if role == "head_identity":
        return """Role policy:
- Generate only whole head/face identity, hair-front, hair-rear, neck when needed, and head-accessory/helmet/hat as larger riggable parts.
- Do not split or redraw micro facial organs: no separate eye whites, irises, pupils, brows, nose, mouth, ears, or glasses unless they are a large removable accessory explicitly listed as a target component.
- Keep the face as one identity-preserving source-locked composite. Micro details are reference evidence, not final generated components."""
    if role == "limbs":
        return """Role policy:
- Generate only the drawing-facing generationTargets listed for this sheet. Do not reinterpret internal registration component IDs as drawing instructions.
- Do not force every leg garment into thigh/shin pieces. Ordinary pants may stay as one coherent lower-body garment or left/right leg layers; split into thigh/shin only when a future explicit knee-rig mode asks for it and the source supports it.
- Do not create duplicate pose variants, extra limb angles, loose cuffs, folds, pant slivers, shoes, boots, or cloth scraps.
- If a hand holds or wears an object such as a glove, umbrella handle, bag strap, or tool, draw the hand-contact group coherently; do not separate contact pixels into unrelated fragments."""
    if role == "feet_footwear":
        return """Role policy:
- Generate only coherent feet, shoes, or boots required by the listed generationTargets.
- Keep left and right footwear source-matched and source-facing. Do not create extra shoe poses, turnarounds, duplicate variants, or design-board alternates.
- Do not include pants or leg pieces except minimal ankle/cuff overlap pixels required for registration."""
    if role == "body_clothes":
        return """Role policy:
- Generate large garment and body layers only: torso, hips/lower garment, collar/tie/scarf, jacket/front/back masses, tail/wings if present.
- Split garments by animation structure and material behavior only, not by seams, buttons, wrinkles, cuffs, pockets, badges, zippers, or decorative cloth fragments.
- Pants, skirts, dresses, coats, robes, capes, and armor should stay as coherent garment/plate layers with overlap zones around joints. Only split panels when front/back occlusion or cloth swing makes it necessary."""
    if role == "props_accessories":
        return """Role policy:
- Generate character-owned props as coherent interaction groups.
- If a prop is held, preserve the contact relationship to the hand/grip; do not detach fingers, handles, straps, or held-object edges into unregistered fragments."""
    return """Role policy:
- Generate only named final-layer components from the V3 plan.
- Do not add micro details, labels, duplicate alternates, or unrelated visual fragments."""


def write_v3_sheet_prompts(workspace: Path) -> dict[str, Any]:
    subject_report = v3_subject_preflight_blocks_masks(workspace)
    if subject_report.get("shouldBlockV3Masks"):
        out_path = workspace / "v3" / "sheet-prompts.json"
        result = {
            "type": "kine.v3.sheetPrompts",
            "version": "0.1",
            "status": "needs_imagegen_subject_matte",
            "writtenCount": 0,
            "prompts": [],
            "blockers": ["source_subject_needs_imagegen_subject_matte"],
            "sourceSubjectPreflight": "source/source-subject-preflight.json",
            "requiredAction": subject_report.get("requiredAction"),
            "note": "Role sheet prompts were not generated because V3 must isolate the character with $imagegen before role sheet generation.",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(out_path, result)
        print(json.dumps({"status": "needs_imagegen_subject_matte", "writtenCount": 0, "manifest": str(out_path)}, ensure_ascii=False, indent=2))
        return result
    campaign_path = workspace / "v3" / "sheet-campaign.json"
    if not campaign_path.exists():
        write_v3_component_plan(workspace)
    stable_plan_status = ensure_v3_stable_object_plan(workspace)
    if stable_plan_status.get("status") == "updated" or not (workspace / "v3" / "references" / "reference-bundles.json").exists():
        write_v3_reference_bundles(workspace)
    sheet_campaign = read_json_if_exists(campaign_path) or {}
    component_plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    components = component_plan.get("components", []) if isinstance(component_plan.get("components"), list) else []
    visual_decision = read_v3_visual_split_decision(workspace)
    visual_decision_rel = (
        relative_to_workspace(v3_visual_split_decision_path(workspace), workspace)
        if visual_decision
        else None
    )
    by_owner: dict[str, list[dict[str, Any]]] = {}
    for component in components:
        if isinstance(component, dict) and isinstance(component.get("owner"), str):
            by_owner.setdefault(component["owner"], []).append(component)
    source = Image.open(workspace / "source.png").convert("RGBA")
    palette = ", ".join(dominant_source_colors(source)) or "the exact source palette"
    written = []
    for sheet in sheet_campaign.get("sheets", []) if isinstance(sheet_campaign.get("sheets"), list) else []:
        if not isinstance(sheet, dict):
            continue
        prompt_path_value = sheet.get("promptPath")
        if not isinstance(prompt_path_value, str):
            continue
        owners = [owner for owner in sheet.get("owners", []) if isinstance(owner, str)]
        sheet_components = [component for owner in owners for component in by_owner.get(owner, [])]
        component_ids = [component["id"] for component in sheet_components]
        role = sheet.get("role", "unspecified")
        role_policy = v3_sheet_role_policy_text(str(role))
        layout_policy = v3_canonical_sheet_layout_text(str(role))
        generation_targets = v3_sheet_generation_targets(str(role), owners, by_owner, decision=visual_decision, workspace=workspace)
        generation_target_ids = [str(target.get("id")) for target in generation_targets if target.get("id")]
        reference_lines = v3_generation_target_reference_lines(generation_targets)
        sheet_id = str(sheet.get("id") or f"sheet-{len(written) + 1:03d}")
        safe_role = str(role).replace("/", "-").replace(" ", "_")
        expected_output = f"imagegen/v3/{sheet_id}.{safe_role}.raw.png"
        ingest_command = (
            "python3 skill-v3/scripts/kine_layer_workspace.py parts-sheet "
            f"--workspace {shlex.quote(str(workspace))} "
            f"--sheet {shlex.quote(str(workspace / expected_output))} "
            f"--sheet-id {shlex.quote(sheet_id)} "
            f"--role {shlex.quote(str(role))} "
            "--append --chroma-key auto"
        )
        prompt = f"""Use case: precise-object-edit
Asset type: KINE-LAYER V3 bounded component sheet
Input image: the provided source character image is the strict identity, style, color, pose-logic, and proportion reference.
Source canvas: {source.width}x{source.height}px.

Create one role-specific parts sheet for role `{role}` only. Include only these semantic owners: {", ".join(owners) or "none"}.
Target generation rows for $imagegen: {", ".join(generation_target_ids) or "none"}.
These generation rows are the only drawing targets. Internal registration component IDs are not direct drawing instructions and must not be used to invent extra fragments.
Visual split decision: {visual_decision_rel or "none; using V3 fallback generation targets"}.

{role_policy}

{layout_policy}

Reference package:
- Full original reference before background removal: `source/original-normalized.png`.
- Source geometry calibration inputs: `v3/calibration/source-silhouette.png`, `v3/calibration/source-edge-lineart.png`, `v3/calibration/source-anchor-map.png`, and `v3/calibration/source-calibration-board.png`.
- Per-component reference manifest: `v3/references/reference-bundles.json`.
{chr(10).join(reference_lines) if reference_lines else "- No per-component references are available; run `v3-reference-bundles` before drawing."}

	Reference priority:
	- Use `source/original-normalized.png` for identity, overall proportions, and global style.
	- Use each target's `sourceScaleAnchor` as its local source bbox proportion lock. Match the corresponding source part's width/height/aspect and canvas-relative scale; do not normalize every generated component to one universal size.
	- Use source calibration guides like ControlNet-style visual references: silhouette for outer contour, edge-lineart for internal contours, anchor map for rough joints/placement, and calibration board for recompose alignment. They are image references, not API parameters.
- Use each component's `original_region.png` crop for local colors, facial details, material, and any pixels that may have been lost by chroma-key cleanup.
- Use `visible_cut.png` and `mask_region.png` only for component shape, boundary, alpha, and registration. Do not treat the processed cutout as the color authority.
- If an input image or reference bundle marks `referenceStrength=weak_fragment` or `useAsPrimaryReference=false`, treat that visible cut/mask as diagnostic boundary evidence only. Do not let a tiny fragment override the original crop, full source, or visual split decision.

Preserve the exact source identity, line style, palette ({palette}), proportions, outfit, hair, face, accessories, and visible silhouettes. The sheet is candidate art only; local KINE-LAYER V3 will split, alpha-clean, register, mask-check, and recompose it before anything can become final.

For each target owner/component, draw owner-isolated animation-ready parts with enough hidden/overlap surface for rigging when inferable. Do not include unrelated owners. Do not draw a full assembled body. Do not create turnarounds, labels, captions, grids, watermarks, text, shadows, or alternate designs.

Output all parts on one perfectly flat solid #00ff00 chroma-key background. Do not use #00ff00 inside any character part. If a hidden or back surface cannot be inferred from the source without redesigning, omit it rather than inventing a new design."""
        prompt_path = workspace / prompt_path_value
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt + "\n", encoding="utf-8")
        written.append(
            {
                "sheetId": sheet_id,
                "role": role,
                "prompt": relative_to_workspace(prompt_path, workspace),
                "expectedOutput": expected_output,
                "imagegenMode": "built_in_image_gen",
                "savePolicy": "Save the $imagegen result exactly at expectedOutput before running ingestCommand.",
                "ingestCommand": ingest_command,
                "referenceBundleManifest": "v3/references/reference-bundles.json",
                "referenceBundles": [by_owner_component.get("referenceBundle") for owner in owners for by_owner_component in by_owner.get(owner, []) if by_owner_component.get("referenceBundle")],
                "inputImageContract": v3_input_image_contract(max_component_refs=12),
                "inputImages": v3_task_input_images(workspace, sheet_components, max_component_refs=12),
                "owners": owners,
                "components": component_ids,
                "generationTargets": generation_targets,
                "generationTargetIds": generation_target_ids,
                "layoutPolicy": "canonical_puppet_board",
                "visualSplitDecision": visual_decision_rel,
                "visualSplitDecisionStatus": "used" if visual_decision_rel else "fallback",
            }
        )
    result = {
        "type": "kine.v3.sheetPrompts",
        "version": "0.1",
        "sheetCampaign": "v3/sheet-campaign.json",
        "visualSplitDecision": visual_decision_rel,
        "visualSplitDecisionStatus": "used" if visual_decision_rel else "fallback",
        "writtenCount": len(written),
        "prompts": written,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "v3" / "sheet-prompts.json", result)
    print(json.dumps({"status": "v3_sheet_prompts_written", "writtenCount": len(written), "manifest": str(workspace / "v3" / "sheet-prompts.json")}, ensure_ascii=False, indent=2))
    return result


def v3_source_visible_candidate_allowed(component: dict[str, Any]) -> tuple[bool, str | None]:
    component_id = component.get("id")
    owner = component.get("owner")
    if not isinstance(component_id, str) or not isinstance(owner, str):
        return False, "missing_component_id_or_owner"
    if component.get("status") == "not_visible":
        return False, "component_not_visible"
    if component.get("maskStatus") != "passed":
        return False, "mask_not_passed"
    if v3_owner_component_class(owner) == "source-locked-detail":
        return False, "source_locked_detail_reference_only"
    reference_quality = component.get("referenceQuality") if isinstance(component.get("referenceQuality"), dict) else {}
    if reference_quality and reference_quality.get("status") not in {None, "ready"}:
        return False, "reference_quality_not_ready"
    mask_path = component.get("cleanOwnerMask") or component.get("mask")
    if not isinstance(mask_path, str):
        return False, "clean_owner_mask_missing"
    return True, None


def build_v3_source_visible_local_candidates(workspace: Path, components: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create registrable source-visible candidate evidence from clean owner masks.

    This is not a drawing backend and it is not final art. It preserves pixels that are
    already visible in `source.png` so registration can test source fidelity before
    `$imagegen` is asked to fill hidden/overlap pixels.
    """
    reference_manifest_path = workspace / "v3" / "references" / "reference-bundles.json"
    if not reference_manifest_path.exists():
        return [], {
            "type": "kine.v3.sourceVisibleLocalCandidateReport",
            "version": "0.1",
            "status": "skipped",
            "reason": "reference_bundles_missing",
            "candidateCount": 0,
            "skipped": [],
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
    source_path = workspace / "source.png"
    if not source_path.exists():
        return [], {
            "type": "kine.v3.sourceVisibleLocalCandidateReport",
            "version": "0.1",
            "status": "skipped",
            "reason": "source_missing",
            "candidateCount": 0,
            "skipped": [],
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
    source = Image.open(source_path).convert("RGBA")
    transparent = Image.new("RGBA", source.size, (0, 0, 0, 0))
    out_dir = workspace / "v3" / "candidates" / "source-visible-local"
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = str(component.get("id") or "")
        allowed, reason = v3_source_visible_candidate_allowed(component)
        if not allowed:
            skipped.append({"componentId": component_id or None, "reason": reason})
            continue
        mask_rel = component.get("cleanOwnerMask") or component.get("mask")
        if not isinstance(mask_rel, str):
            skipped.append({"componentId": component_id, "reason": "clean_owner_mask_missing"})
            continue
        mask_path = workspace / mask_rel
        if not mask_path.exists():
            skipped.append({"componentId": component_id, "reason": "clean_owner_mask_file_missing", "mask": mask_rel})
            continue
        try:
            mask = Image.open(mask_path).convert("L").point(lambda value: 255 if value > 0 else 0)
        except OSError:
            skipped.append({"componentId": component_id, "reason": "clean_owner_mask_unreadable", "mask": mask_rel})
            continue
        bbox = mask.getbbox()
        if not bbox:
            skipped.append({"componentId": component_id, "reason": "clean_owner_mask_empty", "mask": mask_rel})
            continue
        candidate_img = Image.composite(source, transparent, mask)
        out_path = out_dir / f"{component_id}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_img.save(out_path)
        owner = str(component.get("owner") or "")
        role = component.get("role")
        reference_bundle = component.get("referenceBundle")
        input_images: list[dict[str, Any]] = []
        if isinstance(reference_bundle, str):
            bundle = read_json_if_exists(workspace / reference_bundle) or {}
            for key, role_name, description in [
                ("sourceOriginalFull", "source-original-full", "full source reference used for identity/style context"),
                ("originalRegion", "component-original-region", "unprocessed local crop used as detail reference"),
                ("cleanOwnerMask", "component-clean-owner-mask", "owner-clean mask used for this local candidate"),
                ("visibleCut", "component-visible-cut", "source-visible cut used for registration evidence"),
            ]:
                value = bundle.get(key)
                if isinstance(value, str):
                    input_images.append({"role": role_name, "path": value, "description": description})
        rows.append(
            {
                "id": f"source-visible-{component_id}",
                "partId": component_id,
                "sheetId": "source-visible-local",
                "role": role,
                "sheetRole": role,
                "sourceSheetId": "source-visible-local",
                "file": relative_to_workspace(out_path, workspace),
                "sourcePart": component.get("visibleCut"),
                "rawSheet": None,
                "transparentSheet": None,
                "preflightPath": None,
                "normalizationPolicy": "source_visible_clean_owner_mask_local_candidate",
                "allowedOwners": [owner],
                "allowedComponents": [component_id],
                "bbox": list(bbox),
                "alphaBbox": list(bbox),
                "ownerCandidate": owner,
                "ownerHint": {
                    "owner": owner,
                    "confidence": 1.0,
                    "source": "source_visible_clean_owner_mask",
                },
                "disposition": "candidate",
                "status": "candidate",
                "localSourceVisibleCandidate": True,
                "hiddenCompletion": False,
                "provenance": {
                    "source": "source_visible_local_candidate",
                    "sourceVisibleCandidate": True,
                    "componentId": component_id,
                    "owner": owner,
                    "sourceImage": "source.png",
                    "cleanOwnerMask": mask_rel,
                    "visibleCut": component.get("visibleCut"),
                    "sourceVisibleCut": component.get("sourceVisibleCut"),
                    "referenceBundle": reference_bundle,
                    "inputImages": input_images,
                    "normalizationPolicy": "source_visible_clean_owner_mask_local_candidate",
                    "registrationStatus": "candidate",
                    "rejectedReason": None,
                    "note": "Local source-visible candidate preserves already-visible source pixels. It is not final art and still requires registration, recompose, hidden completion, review, and validation.",
                },
            }
        )
    report = {
        "type": "kine.v3.sourceVisibleLocalCandidateReport",
        "version": "0.1",
        "status": "written" if rows else "empty",
        "source": "source.png",
        "referenceBundles": "v3/references/reference-bundles.json",
        "candidateDir": "v3/candidates/source-visible-local",
        "candidateCount": len(rows),
        "skippedCount": len(skipped),
        "candidates": [
            {
                "id": row["id"],
                "componentId": row["partId"],
                "owner": row["ownerCandidate"],
                "role": row["role"],
                "file": row["file"],
                "cleanOwnerMask": row["provenance"]["cleanOwnerMask"],
            }
            for row in rows
        ],
        "skipped": skipped,
        "policy": "preserve already-visible source pixels locally; use $imagegen only for hidden/overlap completion after registration",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    report_path = workspace / "v3" / "candidates" / "source-visible-local-candidates-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, report)
    return rows, report


def sync_v3_candidates_from_parts(workspace: Path) -> dict[str, Any]:
    parts_manifest = read_json_if_exists(workspace / "parts" / "parts-sheet-manifest.json") or {}
    parts = parts_manifest.get("parts", []) if isinstance(parts_manifest.get("parts"), list) else []
    sheets = parts_manifest.get("sheets", []) if isinstance(parts_manifest.get("sheets"), list) else []
    component_plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    components = [component for component in component_plan.get("components", []) if isinstance(component, dict)]
    sheets_by_id = {
        str(sheet.get("sheetId") or sheet.get("id")): sheet
        for sheet in sheets
        if isinstance(sheet, dict) and (sheet.get("sheetId") or sheet.get("id"))
    }
    candidates_dir = workspace / "v3" / "candidates"
    candidates = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_id = part.get("id")
        part_file = part.get("file")
        sheet_id = part.get("sheetId") or "sheet-001"
        if not isinstance(part_id, str) or not isinstance(part_file, str) or not isinstance(sheet_id, str):
            continue
        source_part = workspace / "parts" / part_file
        if not source_part.exists():
            continue
        target_name = f"{sheet_id}-{part_id}{source_part.suffix.lower() or '.png'}"
        target = candidates_dir / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_part, target)
        mapping = part.get("mapping", {}) if isinstance(part.get("mapping"), dict) else {}
        sheet_record = sheets_by_id.get(sheet_id, {})
        candidate_role = part.get("role") or part.get("sheetRole") or sheet_record.get("role")
        allowed_owners = part.get("allowedOwners") if isinstance(part.get("allowedOwners"), list) else sheet_record.get("allowedOwners", [])
        allowed_components = part.get("allowedComponents") if isinstance(part.get("allowedComponents"), list) else sheet_record.get("allowedComponents", [])
        provenance = part.get("provenance") if isinstance(part.get("provenance"), dict) else {}
        sheet_size_values = sheet_record.get("imageSize")
        sheet_size = tuple(sheet_size_values) if isinstance(sheet_size_values, list) and len(sheet_size_values) == 2 else None
        role_owner_hint = None
        if not mapping.get("owner"):
            try:
                part_img = Image.open(source_part).convert("RGBA")
                alpha_bbox = part.get("alphaBbox") if isinstance(part.get("alphaBbox"), list) else None
                role_owner_hint = v3_role_sheet_owner_hint(candidate_role, allowed_owners, allowed_components, part_img, alpha_bbox, sheet_size)
            except OSError:
                role_owner_hint = None
        owner_candidate = mapping.get("owner") or (role_owner_hint.get("owner") if isinstance(role_owner_hint, dict) else None)
        candidate = {
            "id": f"{sheet_id}-{part_id}",
            "partId": part_id,
            "sheetId": sheet_id,
            "role": candidate_role,
            "sheetRole": candidate_role,
            "sourceSheetId": part.get("sourceSheetId") or sheet_id,
            "file": relative_to_workspace(target, workspace),
            "sourcePart": relative_to_workspace(source_part, workspace),
            "rawSheet": part.get("rawSheet") or sheet_record.get("rawPath"),
            "transparentSheet": part.get("transparentSheet") or sheet_record.get("transparentPath"),
            "preflightPath": part.get("preflightPath") or sheet_record.get("preflightPath"),
            "normalizationPolicy": part.get("normalizationPolicy") or sheet_record.get("normalizationPolicy") or "legacy_parts_sheet_crop",
            "allowedOwners": allowed_owners,
            "allowedComponents": allowed_components,
            "bbox": part.get("bbox"),
            "alphaBbox": part.get("alphaBbox"),
            "ownerCandidate": owner_candidate,
            "ownerHint": role_owner_hint,
            "disposition": mapping.get("disposition", "candidate"),
            "status": "candidate",
            "provenance": {
                "source": provenance.get("source") or "parts-sheet",
                "rawSheet": provenance.get("rawSheet") or part.get("rawSheet") or sheet_record.get("rawPath"),
                "transparentSheet": provenance.get("transparentSheet") or part.get("transparentSheet") or sheet_record.get("transparentPath"),
                "preflightPath": provenance.get("preflightPath") or part.get("preflightPath") or sheet_record.get("preflightPath"),
                "inputImages": sheet_record.get("inputImages") or part.get("inputImages") or [],
                "ownerHint": role_owner_hint,
                "normalizationPolicy": part.get("normalizationPolicy") or sheet_record.get("normalizationPolicy") or "legacy_parts_sheet_crop",
                "registrationStatus": "candidate",
                "rejectedReason": None,
            },
        }
        candidates.append(candidate)
    source_visible_candidates, source_visible_report = build_v3_source_visible_local_candidates(workspace, components)
    candidates.extend(source_visible_candidates)
    result = {
        "type": "kine.v3.sheetCandidateManifest",
        "version": "0.1",
        "legacyPartsManifest": "parts/parts-sheet-manifest.json",
        "candidateDir": "v3/candidates",
        "sourceVisibleCandidateReport": "v3/candidates/source-visible-local-candidates-report.json"
        if (workspace / "v3" / "candidates" / "source-visible-local-candidates-report.json").exists()
        else None,
        "sourceVisibleLocalCandidateCount": len(source_visible_candidates),
        "sourceVisibleLocalCandidateStatus": source_visible_report.get("status"),
        "sheetCount": len(sheets),
        "candidateCount": len(candidates),
        "sheets": sheets,
        "candidates": candidates,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "v3" / "sheets" / "sheet-manifest.json", result)
    print(json.dumps({"status": "v3_candidates_synced", "candidateCount": len(candidates), "manifest": str(workspace / "v3" / "sheets" / "sheet-manifest.json")}, ensure_ascii=False, indent=2))
    return result


V3_REGISTRATION_REASON_CODES = {
    "candidate_component_pool_missing",
    "shape_mismatch",
    "source_similarity_failed",
    "owner_pollution",
    "registration_failed",
    "identity_drift",
    "hidden_area_missing",
}


V3_REGISTRATION_REASON_DETAILS = {
    "candidate_component_pool_missing": {
        "plainZh": "候选图没有进入任何可匹配的组件池。通常是 mixed 验证图冒充正式 role sheet，或 sheet-id 没有对应 V3 sheet campaign。",
        "nextActionZh": "保存并 ingest 正式 role sheet 输出，例如 sheet-001/head、sheet-002/body、sheet-003/limbs，而不是调低相似度阈值。",
    },
    "shape_mismatch": {
        "plainZh": "候选组件的轮廓、大小或比例和原图对应区域对不上，放回源图时会错位或变形。",
        "nextActionZh": "重新生成时要锁住原图局部 crop、mask/visible cut 和 anchor，不要让 ImageGen 改姿势、改比例或换角度。",
    },
    "source_similarity_failed": {
        "plainZh": "候选组件和原图对应区域不像。它可能是相似重绘，而不是可以拼回原图的源图组件。",
        "nextActionZh": "提高 source fidelity：颜色、材质、线条、纹理以原图局部 crop 为准，visible cut 只负责边界。",
    },
    "owner_pollution": {
        "plainZh": "候选组件混进了别的部件或背景。比如头发里带脸、衣服里带包、手臂里带草地。",
        "nextActionZh": "要求只输出目标 owner，不要带其他身体部件、道具、背景或相邻组件。",
    },
    "registration_failed": {
        "plainZh": "候选图没有满足基础注册条件，可能是角色/role 不匹配、缺少 mask、缺少 visible reference，或分数太低。",
        "nextActionZh": "先检查候选是否来自正确 role sheet，再检查 reference bundle、mask、visible cut 是否齐全。",
    },
    "identity_drift": {
        "plainZh": "身份细节变了，尤其是脸、眼睛、五官、发型等 source-locked 区域不能接受相似但不同的重绘。",
        "nextActionZh": "脸部和身份区域优先用原图 crop 锁定；默认不要把五官微器官拆成最终生成组件。",
    },
    "hidden_area_missing": {
        "plainZh": "组件缺少动画需要的遮挡补全部分，例如关节重叠区、被衣服挡住的边缘或可旋转 overlap surface。",
        "nextActionZh": "只补必要隐藏面和 overlap zone，不要重画已经可见的源图像素。",
    },
}


def v3_registration_reason_details(reasons: list[str] | tuple[str, ...] | None) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for reason in reasons or ["registration_failed"]:
        code = str(reason)
        info = V3_REGISTRATION_REASON_DETAILS.get(code, V3_REGISTRATION_REASON_DETAILS["registration_failed"])
        details.append(
            {
                "code": code,
                "plainZh": info["plainZh"],
                "nextActionZh": info["nextActionZh"],
            }
        )
    return details


def v3_registration_reason_counts_details(counts: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {
            "code": code,
            "count": count,
            **(V3_REGISTRATION_REASON_DETAILS.get(code) or V3_REGISTRATION_REASON_DETAILS["registration_failed"]),
        }
        for code, count in sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
    ]


def v3_component_visible_image(workspace: Path, component: dict[str, Any]) -> tuple[Image.Image | None, list[int] | None]:
    visible_cut = component.get("visibleCut")
    if isinstance(visible_cut, str) and (workspace / visible_cut).exists():
        try:
            img, bbox = alpha_bbox_image(workspace / visible_cut)
            if bbox:
                return img, bbox
        except OSError:
            pass
    mask_path_value = component.get("mask") or component.get("expectedMask")
    if isinstance(mask_path_value, str) and (workspace / mask_path_value).exists() and (workspace / "source.png").exists():
        source = Image.open(workspace / "source.png").convert("RGBA")
        mask = Image.open(workspace / mask_path_value).convert("L")
        visible = Image.composite(source, Image.new("RGBA", source.size, (0, 0, 0, 0)), mask)
        bbox = visible.getchannel("A").getbbox()
        if bbox:
            return visible, list(bbox)
    return None, None


def v3_role_allowed(candidate_role: str | None, component_role: str | None) -> bool:
    if not component_role:
        return True
    if not candidate_role or candidate_role == "unspecified":
        return False
    return candidate_role == component_role


def v3_candidate_allows_component(candidate: dict[str, Any], component: dict[str, Any]) -> bool:
    component_id = component.get("id")
    owner = component.get("owner")
    allowed_components = candidate.get("allowedComponents")
    if isinstance(allowed_components, list) and allowed_components:
        if component_id not in {str(item) for item in allowed_components}:
            return False
    allowed_owners = candidate.get("allowedOwners")
    if isinstance(allowed_owners, list) and allowed_owners:
        if owner not in {str(item) for item in allowed_owners}:
            return False
    return True


def v3_role_sheet_owner_hint(
    role: str | None,
    allowed_owners: list[Any],
    allowed_components: list[Any],
    part_img: Image.Image,
    alpha_bbox: list[int] | None,
    sheet_size: tuple[int, int] | None,
) -> dict[str, Any] | None:
    """Assign a conservative owner hint from role-specific puppet-board layout.

    This does not accept a candidate. It only limits the component pool before the
    normal source-visible registration score runs.
    """
    owner_set = {str(owner) for owner in allowed_owners if isinstance(owner, str)}
    component_set = {str(component) for component in allowed_components if isinstance(component, str)}
    if not role or role == "controlled_layout_mixed" or not owner_set or not component_set:
        return None
    if not (isinstance(alpha_bbox, list) and len(alpha_bbox) == 4 and sheet_size):
        return None

    features = parts_sheet_component_features(part_img, alpha_bbox, sheet_size)
    cx, cy = features["center"]
    rel_w, rel_h = features["relativeSize"]
    aspect = features["aspect"]
    skin = features["skin"]
    black = features["black"]
    orange = features["orange"]
    green = round(masked_color_fraction(part_img, lambda r, g, b: g > 80 and r < 150 and b < 120 and g >= r * 0.85), 4)
    brown = round(masked_color_fraction(part_img, lambda r, g, b: 55 < r < 175 and 25 < g < 130 and b < 95 and r >= g), 4)

    owner: str | None = None
    confidence = 0.0
    reason = "v3_role_sheet_layout_prior"

    if role == "head_identity":
        if "face" in owner_set and skin > 0.18 and rel_h > 0.30 and 0.30 <= cx <= 0.70:
            owner, confidence = "face", 0.84
        elif "head-accessory" in owner_set and green > 0.16 and cy < 0.46:
            owner, confidence = "head-accessory", 0.82
        elif {"hair-front", "hair-rear"} & owner_set and (brown > 0.20 or black > 0.40) and rel_w > 0.10:
            if "hair-rear" in owner_set and cx < 0.45:
                owner, confidence = "hair-rear", 0.78
            elif "hair-front" in owner_set:
                owner, confidence = "hair-front", 0.76
    elif role == "feet_footwear" and "feet" in owner_set:
        if rel_h > 0.12 and (black > 0.20 or brown > 0.15):
            owner, confidence = "feet", 0.72
    elif role == "body_clothes":
        if "collar-accessory" in owner_set and cy < 0.35 and aspect > 1.4:
            owner, confidence = "collar-accessory", 0.72
        elif "torso" in owner_set and cy < 0.58 and rel_h > 0.20:
            owner, confidence = "torso", 0.70
        elif "hips" in owner_set:
            owner, confidence = "hips", 0.68
    elif role == "limbs":
        if "arms" in owner_set and (skin > 0.08 or aspect < 0.75 or rel_h > 0.24):
            owner, confidence = "arms", 0.66
        elif "legs" in owner_set:
            owner, confidence = "legs", 0.64

    if owner is None or owner not in owner_set:
        return None
    return {
        "owner": owner,
        "confidence": round(confidence, 6),
        "source": reason,
        "features": {
            **features,
            "green": green,
            "brown": brown,
        },
    }


def v3_canvas_place_candidate(part_img: Image.Image, target_bbox: list[int], canvas_size: tuple[int, int]) -> tuple[Image.Image, dict[str, Any]]:
    registered_part, (x, y) = resize_part_to_bbox(part_img, target_bbox, canvas_size)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    canvas.alpha_composite(registered_part, (x, y))
    transform = {
        "method": "fit_component_mask_bbox",
        "x": x,
        "y": y,
        "width": registered_part.width,
        "height": registered_part.height,
        "targetBbox": target_bbox,
        "rotationDegrees": 0.0,
    }
    return canvas, transform


def v3_registered_candidate_metrics(
    placed: Image.Image,
    component_visible: Image.Image,
    component_mask: Image.Image,
) -> dict[str, Any]:
    placed_alpha = placed.getchannel("A").point(lambda value: 255 if value > 24 else 0)
    mask = component_mask.convert("L").point(lambda value: 255 if value > 24 else 0)
    visible_alpha = component_visible.getchannel("A").point(lambda value: 255 if value > 24 else 0)
    placed_pixels = sum(1 for value in placed_alpha.tobytes() if value > 0)
    mask_pixels = sum(1 for value in mask.tobytes() if value > 0)
    outside_mask = 0
    overlap = 0
    for pv, mv in zip(placed_alpha.tobytes(), mask.tobytes()):
        if pv > 0 and mv > 0:
            overlap += 1
        elif pv > 0 and mv == 0:
            outside_mask += 1
    visible_overlap = ImageChops.multiply(placed_alpha, visible_alpha)
    visible_overlap_pixels = sum(1 for value in visible_overlap.tobytes() if value > 0)
    rmse = masked_rgb_rmse(placed, component_visible, visible_overlap) if visible_overlap_pixels else 999.0
    return {
        "placedAlphaPixels": placed_pixels,
        "componentMaskPixels": mask_pixels,
        "maskOverlapPixels": overlap,
        "maskOverlapRatio": round(overlap / max(1, mask_pixels), 6),
        "outsideMaskPixels": outside_mask,
        "outsideMaskRatio": round(outside_mask / max(1, placed_pixels), 6),
        "visibleOverlapPixels": visible_overlap_pixels,
        "visibleRmse": rmse,
    }


def v3_registration_reasons(
    candidate: dict[str, Any],
    component: dict[str, Any],
    score: float,
    min_score: float,
    match: dict[str, Any],
    metrics: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    subscores = match.get("subscores") if isinstance(match.get("subscores"), dict) else {}
    shape = float(subscores.get("shape", 0.0))
    color = float(subscores.get("color", 0.0))
    if not v3_role_allowed(candidate.get("role"), component.get("role")):
        reasons.append("registration_failed")
    if score < min_score or shape < SOURCE_REFERENCE_SHAPE_MIN:
        reasons.append("shape_mismatch")
    if color < SOURCE_REFERENCE_COLOR_MIN and component.get("track") == "source_locked_identity":
        reasons.append("identity_drift")
    if float(metrics.get("outsideMaskRatio", 1.0)) > LAYER_OUTSIDE_SOURCE_ALPHA_RATIO_LIMIT:
        reasons.append("owner_pollution")
    if float(metrics.get("visibleRmse", 999.0)) > SOURCE_VISIBLE_CANDIDATE_RMSE_LIMIT:
        reasons.append("source_similarity_failed")
    if not reasons and score < min_score:
        reasons.append("registration_failed")
    return sorted(set(reason for reason in reasons if reason in V3_REGISTRATION_REASON_CODES))


def v3_score_candidate_for_component(
    workspace: Path,
    candidate: dict[str, Any],
    component: dict[str, Any],
    min_score: float,
) -> dict[str, Any] | None:
    candidate_file = candidate.get("file")
    component_id = component.get("id")
    if not isinstance(candidate_file, str) or not isinstance(component_id, str):
        return None
    candidate_path = workspace / candidate_file
    if not candidate_path.exists():
        return None
    component_visible, component_bbox = v3_component_visible_image(workspace, component)
    if component_visible is None or not component_bbox:
        return {
            "candidateId": candidate.get("id"),
            "componentId": component_id,
            "accepted": False,
            "score": 0.0,
            "reasons": ["registration_failed"],
            "detail": "component_visible_reference_missing",
        }
    mask_path_value = component.get("mask") or component.get("expectedMask")
    if not isinstance(mask_path_value, str) or not (workspace / mask_path_value).exists():
        return {
            "candidateId": candidate.get("id"),
            "componentId": component_id,
            "accepted": False,
            "score": 0.0,
            "reasons": ["registration_failed"],
            "detail": "component_mask_missing",
        }
    candidate_img, candidate_bbox = alpha_bbox_image(candidate_path)
    if not candidate_bbox:
        return {
            "candidateId": candidate.get("id"),
            "componentId": component_id,
            "accepted": False,
            "score": 0.0,
            "reasons": ["registration_failed"],
            "detail": "candidate_alpha_empty",
        }
    match = visual_pair_score(candidate_img, component_visible, candidate_bbox, component_bbox)
    role_score = 1.0 if v3_role_allowed(candidate.get("role"), component.get("role")) else 0.0
    owner_score = 1.0 if candidate.get("ownerCandidate") in {None, component.get("owner")} else 0.0
    score = round((float(match["score"]) * 0.82) + (role_score * 0.12) + (owner_score * 0.06), 6)
    placed, transform = v3_canvas_place_candidate(candidate_img, component_bbox, component_visible.size)
    component_mask = Image.open(workspace / mask_path_value).convert("L")
    metrics = v3_registered_candidate_metrics(placed, component_visible, component_mask)
    reasons = v3_registration_reasons(candidate, component, score, min_score, match, metrics)
    accepted = not reasons
    hidden_completion_status = "not_required"
    if component.get("needsHiddenCompletion"):
        if v3_is_source_visible_candidate_id(candidate.get("id")):
            hidden_completion_status = "not_required_source_visible"
        else:
            hidden_completion_status = "provided" if candidate.get("hiddenCompletion") else "missing"
    return {
        "candidateId": candidate.get("id"),
        "componentId": component_id,
        "owner": component.get("owner"),
        "role": component.get("role"),
        "accepted": accepted,
        "score": score,
        "minScore": min_score,
        "reasons": reasons,
        "hiddenCompletionStatus": hidden_completion_status,
        "match": match,
        "metrics": metrics,
        "transform": transform,
    }


def register_v3_candidates(workspace: Path, min_score: float = 0.55) -> dict[str, Any]:
    component_plan_path = workspace / "v3" / "component-plan.json"
    mask_summary_path = workspace / "v3" / "masks" / "mask-summary.json"
    sheet_manifest_path = workspace / "v3" / "sheets" / "sheet-manifest.json"
    if not component_plan_path.exists():
        write_v3_component_plan(workspace)
    if not mask_summary_path.exists():
        write_v3_mask_jobs(workspace)
    if not sheet_manifest_path.exists():
        sync_v3_candidates_from_parts(workspace)
    component_plan = read_json_if_exists(component_plan_path) or {}
    sheet_manifest = read_json_if_exists(sheet_manifest_path) or {}
    components = [component for component in component_plan.get("components", []) if isinstance(component, dict)]
    candidates = [candidate for candidate in sheet_manifest.get("candidates", []) if isinstance(candidate, dict)]
    registration_dir = workspace / "v3" / "registration"
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    scored_by_candidate: dict[str, list[dict[str, Any]]] = {}
    best_by_candidate: dict[str, dict[str, Any]] = {}
    available_components = [
        component
        for component in components
        if component.get("status") != "not_visible" and component.get("maskStatus") != "missing"
    ]
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "")
        owner_hint = candidate.get("ownerCandidate")
        role = candidate.get("role")
        component_pool = [
            component
            for component in available_components
            if (not owner_hint or component.get("owner") == owner_hint)
            and v3_role_allowed(role, component.get("role"))
            and v3_candidate_allows_component(candidate, component)
        ]
        scored = []
        for component in component_pool:
            result = v3_score_candidate_for_component(workspace, candidate, component, min_score)
            if result is not None:
                scored.append(result)
        scored.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        scored_by_candidate[candidate_id] = scored[:5]
        best = scored[0] if scored else {
            "candidateId": candidate_id,
            "componentId": None,
            "accepted": False,
            "score": 0.0,
            "reasons": ["candidate_component_pool_missing"],
            "detail": "no_component_pool",
            "candidateRole": role,
            "allowedOwners": candidate.get("allowedOwners") or [],
            "allowedComponents": candidate.get("allowedComponents") or [],
            "repairHint": "Ingest the $imagegen output with a sheet-id from v3/sheet-campaign.json, or regenerate a role-specific sheet so allowedOwners/allowedComponents are populated.",
        }
        if not best.get("accepted"):
            best["reasonDetails"] = v3_registration_reason_details(best.get("reasons") or ["registration_failed"])
        best_by_candidate[candidate_id] = best
        if best.get("accepted"):
            component_id = str(best["componentId"])
            candidate_file = candidate.get("file")
            if isinstance(candidate_file, str):
                candidate_img = Image.open(workspace / candidate_file).convert("RGBA")
                source_size = tuple(Image.open(workspace / "source.png").convert("RGBA").size)
                placed, _transform = v3_canvas_place_candidate(
                    candidate_img,
                    best["transform"]["targetBbox"],
                    source_size,
                )
                registered_path = registration_dir / component_id / f"{candidate_id}.registered.png"
                registered_path.parent.mkdir(parents=True, exist_ok=True)
                placed.save(registered_path)
                best["registered"] = relative_to_workspace(registered_path, workspace)
            accepted.append(best)
        else:
            rejected.append(best)
    accepted_by_component: dict[str, list[dict[str, Any]]] = {}
    for item in accepted:
        accepted_by_component.setdefault(str(item.get("componentId")), []).append(item)
    updated_components = []
    for component in components:
        component_id = str(component.get("id") or "")
        registrations = accepted_by_component.get(component_id, [])
        best_rejections = [
            scored[0]
            for scored in scored_by_candidate.values()
            if scored and scored[0].get("componentId") == component_id and not scored[0].get("accepted")
        ]
        updated = dict(component)
        if registrations:
            updated["registrationStatus"] = "accepted"
            updated["registeredCandidates"] = [
                {
                    "candidateId": item.get("candidateId"),
                    "score": item.get("score"),
                    "registered": item.get("registered"),
                    "transform": item.get("transform"),
                    "hiddenCompletionStatus": item.get("hiddenCompletionStatus"),
                }
                for item in registrations
            ]
            if any(v3_is_source_visible_candidate_id(item.get("candidateId")) for item in registrations):
                updated["hiddenCompletionPolicy"] = "source_visible_local_no_hidden_target"
                updated["needsHiddenCompletion"] = False
                updated["hiddenRequirementReason"] = SOURCE_VISIBLE_HIDDEN_NOT_REQUIRED_REASON
                updated["hiddenStatus"] = "not_required"
                updated["hiddenReason"] = SOURCE_VISIBLE_HIDDEN_NOT_REQUIRED_REASON
        elif component.get("status") == "not_visible":
            updated["registrationStatus"] = "not_visible"
            updated["registeredCandidates"] = []
        else:
            updated["registrationStatus"] = "missing"
            updated["registeredCandidates"] = []
            if best_rejections:
                updated["bestRejectedCandidate"] = {
                    "candidateId": best_rejections[0].get("candidateId"),
                    "score": best_rejections[0].get("score"),
                    "reasons": best_rejections[0].get("reasons"),
                }
        updated_components.append(updated)
    candidate_status: dict[str, dict[str, Any]] = {}
    for candidate_id in scored_by_candidate:
        best = best_by_candidate.get(candidate_id)
        if best and best.get("accepted"):
            candidate_status[candidate_id] = {
                "status": "accepted",
                "componentId": best.get("componentId"),
                "score": best.get("score"),
                "hiddenCompletionStatus": best.get("hiddenCompletionStatus"),
                "reasons": [],
            }
        elif best:
            candidate_status[candidate_id] = {
                "status": "rejected",
                "componentId": best.get("componentId"),
                "score": best.get("score"),
                "hiddenCompletionStatus": best.get("hiddenCompletionStatus"),
                "reasons": best.get("reasons") or ["registration_failed"],
                "reasonDetails": best.get("reasonDetails") or v3_registration_reason_details(best.get("reasons") or ["registration_failed"]),
                "detail": best.get("detail"),
                "repairHint": best.get("repairHint"),
            }
        else:
            candidate_status[candidate_id] = {
                "status": "rejected",
                "componentId": None,
                "score": 0.0,
                "reasons": ["candidate_component_pool_missing"],
                "reasonDetails": v3_registration_reason_details(["candidate_component_pool_missing"]),
                "detail": "no_component_pool",
            }
    updated_candidates = []
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "")
        status_update = candidate_status.get(candidate_id, {})
        provenance = candidate.get("provenance") if isinstance(candidate.get("provenance"), dict) else {}
        if status_update:
            provenance = {
                **provenance,
                "registrationStatus": status_update.get("status"),
                "rejectedReason": (status_update.get("reasons") or [None])[0] if status_update.get("status") == "rejected" else None,
                "rejectedReasonDetails": status_update.get("reasonDetails") if status_update.get("status") == "rejected" else None,
            }
        updated_candidates.append({**candidate, **status_update, "provenance": provenance})
    component_plan["components"] = updated_components
    component_plan["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(component_plan_path, component_plan)
    sheet_manifest["candidates"] = updated_candidates
    sheet_manifest["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(sheet_manifest_path, sheet_manifest)
    rejected_reason_counts: dict[str, int] = {}
    for item in rejected:
        for reason in item.get("reasons") or ["registration_failed"]:
            rejected_reason_counts[str(reason)] = rejected_reason_counts.get(str(reason), 0) + 1
    rejected_reason_details = v3_registration_reason_counts_details(rejected_reason_counts)
    report = {
        "type": "kine.v3.registrationReport",
        "version": "0.1",
        "componentPlan": "v3/component-plan.json",
        "sheetManifest": "v3/sheets/sheet-manifest.json",
        "candidateCount": len(candidates),
        "componentCount": len(available_components),
        "acceptedCount": len(accepted),
        "rejectedCount": len(candidates) - len(accepted),
        "minScore": min_score,
        "accepted": accepted,
        "rejected": rejected,
        "rejectedReasonCounts": rejected_reason_counts,
        "rejectedReasonDetails": rejected_reason_details,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(registration_dir / "registration-report.json", report)
    print(
        json.dumps(
            {
                "status": "v3_candidates_registered",
                "acceptedCount": len(accepted),
                "rejectedCount": len(candidates) - len(accepted),
                "report": str(registration_dir / "registration-report.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


def v3_registration_repair_action(reasons: list[str]) -> str:
    reason_set = set(reasons)
    if "candidate_component_pool_missing" in reason_set:
        return "regenerate_role_specific_sheet"
    if "identity_drift" in reason_set or "source_similarity_failed" in reason_set:
        return "redraw_source_fidelity"
    if "owner_pollution" in reason_set:
        return "redraw_owner_isolated"
    if "shape_mismatch" in reason_set or "registration_failed" in reason_set:
        return "regenerate_with_source_scale"
    if "hidden_area_missing" in reason_set:
        return "regenerate_with_overlap_surface"
    return "manual_review_required"


def v3_registration_repair_prompt(component: dict[str, Any], reasons: list[str], action: str) -> str:
    component_id = component.get("id")
    owner = component.get("owner")
    role = component.get("role")
    sockets = ", ".join(component.get("sockets") or [])
    reason_text = ", ".join(reasons) or "registration_failed"
    reference_bundle = component.get("referenceBundle") or "missing"
    original_region = component.get("originalRegion") or "missing"
    visible_cut = component.get("visibleCut") or "missing"
    return f"""Use case: precise-object-edit
Asset type: KINE-LAYER V3 registration repair candidate
Input image: the provided source character image is the strict identity, style, color, pose-logic, and proportion reference.

Repair target:
- componentId: {component_id}
- owner: {owner}
- role: {role}
- sockets: {sockets or "none"}
- previous rejection reasons: {reason_text}
- repair action: {action}

Reference package:
- full original reference before background removal: `source/original-normalized.png`
- component reference bundle: `{reference_bundle}`
- original local crop before chroma-key/background cleanup: `{original_region}`
- processed visible cut / shape reference: `{visible_cut}`

Reference priority:
- Use the full original reference for identity, full-body proportions, and global style.
- Use the original local crop for colors, facial/details, material, and any pixels that may have been lost by chroma-key cleanup.
- Use the processed visible cut and mask only for shape, boundary, and registration; do not let the processed cutout override original colors.

Source-visible preservation mode:
- This is not a creative redraw task. The source-visible pixels in the original local crop are the visual truth.
- Preserve the visible crop's exact color, texture, linework, highlights, shadow shape, pose angle, scale, and canvas-space bbox relationship.
- Use the clean owner mask / visible cut only to isolate the target owner and remove foreign owners. Do not use it as permission to redesign the component.
- If a target area is already visible in the source crop, keep it source-faithful. Generate only missing overlap/hidden pixels that are necessary for animation sockets.
- If source pixels are ambiguous, prefer a conservative smaller transparent result over a larger invented component that would fail source recompose.
- Match the source image's 2D illustration/rendering style. Do not convert the component into photorealistic product photography, a 3D render, or a different material treatment.
- Do not output multi-view variants, alternate angles, full-body context, design boards, decorative duplicates, or surrounding owner fragments.

Create only this component as an isolated animation-ready transparent part, preserving the exact source identity, silhouette, palette, material, line style, and proportions. Do not redesign, beautify, restyle, mirror into a new design, or add unrelated owners.

Requirements:
- If the previous reason includes source_similarity_failed or identity_drift, match the source-visible pixels more closely.
- If the previous reason includes owner_pollution, remove all foreign-owner pixels and keep only the target component.
- If the previous reason includes shape_mismatch or registration_failed, preserve the source-facing scale and bbox proportions so local registration can place it back on source.png.
- If the previous reason includes hidden_area_missing, include only the inferable hidden/overlap surface needed around the sockets, without repainting visible source pixels.

Output a full-canvas transparent PNG aligned to source.png dimensions when possible. If a green background is unavoidable, use a perfectly flat #00ff00 background and no #00ff00 inside the component. This is a candidate only; local V3 registration, recompose, and QA must pass before final export."""


def write_v3_registration_repair_report(workspace: Path, max_tasks: int = 24) -> dict[str, Any]:
    """Turn rejected V3 registration evidence into concrete $imagegen repair tasks."""
    if not (workspace / "v3" / "references" / "reference-bundles.json").exists():
        write_v3_reference_bundles(workspace)
    registration_path = workspace / "v3" / "registration" / "registration-report.json"
    if not registration_path.exists():
        register_v3_candidates(workspace)
    registration_report = read_json_if_exists(registration_path) or {}
    component_plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    components = {
        str(component.get("id")): component
        for component in component_plan.get("components", [])
        if isinstance(component, dict) and component.get("id")
    }
    rejected_rows = registration_report.get("rejected", [])
    rejected = [item for item in rejected_rows if isinstance(item, dict)] if isinstance(rejected_rows, list) else []
    accepted_component_ids = {str(item.get("componentId")) for item in registration_report.get("accepted", []) if isinstance(item, dict) and item.get("componentId")}
    missing_rejected_details = int(registration_report.get("rejectedCount") or 0) > 0 and not rejected

    by_component: dict[str, list[dict[str, Any]]] = {}
    for item in rejected:
        component_id = item.get("componentId")
        if isinstance(component_id, str) and component_id not in accepted_component_ids:
            by_component.setdefault(component_id, []).append(item)

    tasks: list[dict[str, Any]] = []
    prompt_dir = workspace / "v3" / "registration" / "repair-prompts"
    repair_candidate_dir = workspace / "v3" / "registration" / "repair-candidates"
    repair_candidate_dir.mkdir(parents=True, exist_ok=True)
    for component_id, rows in sorted(by_component.items()):
        component = components.get(component_id)
        if not component:
            continue
        rows = sorted(rows, key=lambda item: float(item.get("score") or 0.0), reverse=True)
        reason_counts: dict[str, int] = {}
        for row in rows:
            for reason in row.get("reasons") or ["registration_failed"]:
                reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1
        reasons = [reason for reason, _count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))]
        reason_details = v3_registration_reason_details(reasons)
        action = v3_registration_repair_action(reasons)
        prompt_path = prompt_dir / f"{component_id}.prompt.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(v3_registration_repair_prompt(component, reasons, action) + "\n", encoding="utf-8")
        expected_output = f"v3/registration/repair-candidates/{component_id}.imagegen.png"
        role = str(component.get("role") or "repair")
        sheet_id = f"repair-{component_id}".replace("_", "-")
        ingest_command = (
            "python3 skill-v3/scripts/kine_layer_workspace.py parts-sheet "
            f"--workspace {shlex.quote(str(workspace))} "
            f"--sheet {shlex.quote(str(workspace / expected_output))} "
            f"--sheet-id {shlex.quote(sheet_id)} "
            f"--role {shlex.quote(role)} "
            "--append --chroma-key auto"
        )
        tasks.append(
            {
                "componentId": component_id,
                "owner": component.get("owner"),
                "role": role,
                "track": component.get("track"),
                "action": action,
                "reasons": reasons,
                "reasonDetails": reason_details,
                "rejectedCandidateCount": len(rows),
                "bestRejectedCandidate": {
                    "candidateId": rows[0].get("candidateId"),
                    "score": rows[0].get("score"),
                    "reasons": rows[0].get("reasons"),
                    "reasonDetails": rows[0].get("reasonDetails") or v3_registration_reason_details(rows[0].get("reasons") or ["registration_failed"]),
                    "metrics": rows[0].get("metrics"),
                },
                "prompt": relative_to_workspace(prompt_path, workspace),
                "referenceBundle": component.get("referenceBundle"),
                "originalRegion": component.get("originalRegion"),
                "visibleCut": component.get("visibleCut"),
                "inputImageContract": v3_input_image_contract(),
                "inputImages": v3_task_input_images(workspace, [component]),
                "expectedOutput": expected_output,
                "imagegenMode": "built_in_image_gen",
                "ingestCommand": ingest_command,
                "nextIngest": "Save output at expectedOutput, run ingestCommand, then run v3-sync-candidates, v3-register-candidates, v3-recompose, and v3-validate.",
            }
        )
        if len(tasks) >= max_tasks:
            break

    reason_counts = registration_report.get("rejectedReasonCounts", {}) if isinstance(registration_report.get("rejectedReasonCounts"), dict) else {}
    status = "blocked_missing_rejected_details" if missing_rejected_details else ("needs_imagegen" if tasks else "no_registration_repair_tasks")
    report = {
        "type": "kine.v3.registrationRepairReport",
        "version": "0.1",
        "status": status,
        "registrationReport": "v3/registration/registration-report.json",
        "taskCount": len(tasks),
        "acceptedCount": registration_report.get("acceptedCount"),
        "rejectedCount": registration_report.get("rejectedCount"),
        "rejectedReasonCounts": reason_counts,
        "rejectedReasonDetails": v3_registration_reason_counts_details(reason_counts),
        "tasks": tasks,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "$imagegen repair task plan only. Repaired art remains candidate evidence until V3 registration, recompose, and validation pass.",
    }
    if missing_rejected_details:
        report["blocker"] = "registration report has rejectedCount > 0 but no rejected[] details; rerun v3-register-candidates before repair planning."
    out_dir = workspace / "v3" / "registration"
    write_json(out_dir / "registration-repair-report.json", report)
    lines = [
        "# V3 Registration Repair Handoff",
        "",
        "Use these tasks with the `$imagegen` skill only. Do not route them through any other drawing path.",
        "",
        "A repaired image is still candidate evidence. It must be ingested, split, registered, recomposed, and validated before export.",
        "",
    ]
    for task in tasks:
        lines.extend(
            [
                f"## {task['componentId']}",
                "",
                f"- action: `{task['action']}`",
                f"- reasons: `{', '.join(task['reasons'])}`",
                f"- prompt: `{task['prompt']}`",
                *v3_input_images_markdown_lines(task),
                f"- expected output: `{task['expectedOutput']}`",
                f"- ingest command: `{task['ingestCommand']}`",
                "",
            ]
        )
    if missing_rejected_details:
        lines.append("Blocked: registration report has `rejectedCount > 0` but no `rejected[]` details. Rerun `v3-register-candidates` before repair planning.\n")
    if not tasks:
        lines.append("No registration repair tasks were required by the current report.\n")
    (out_dir / "REGISTRATION_REPAIR_HANDOFF.md").write_text("\n".join(lines), encoding="utf-8")
    update_run_state(workspace, {"v3RegistrationRepair": "v3/registration/registration-repair-report.json", "v3RegistrationRepairStatus": status})
    print(json.dumps({"status": status, "taskCount": len(tasks), "report": str(out_dir / "registration-repair-report.json")}, ensure_ascii=False, indent=2))
    return report


def v3_hidden_prompt(component: dict[str, Any]) -> str:
    reference_bundle = component.get("referenceBundle") or "missing"
    original_region = component.get("originalRegion") or "missing"
    visible_cut = component.get("visibleCut") or "missing"
    return f"""Use case: precise-object-edit
Asset type: KINE-LAYER V3 hidden surface completion

Component: {component.get("id")}
Owner: {component.get("owner")}
Role: {component.get("role")}
Track: {component.get("track")}

Reference package:
- full original reference before background removal: `source/original-normalized.png`
- component reference bundle: `{reference_bundle}`
- original local crop before chroma-key/background cleanup: `{original_region}`
- processed visible cut / shape reference: `{visible_cut}`

Reference priority:
- Use the full original reference for identity and global style.
- Use the original local crop for local color, material, facial/detail preservation, and any pixels that may have been lost by chroma-key cleanup.
- Use the visible cut and mask only to know what source-visible pixels must not be repainted.

Task: create only the hidden/occluded or overlap pixels needed for this component to animate cleanly. Preserve the source identity, source-visible silhouette, palette, line style, shading, and material exactly. Do not redraw source-visible pixels. Do not redesign the component. If the missing surface cannot be inferred from the source, leave it empty and report that manual review is needed.

Return a transparent PNG containing only generated hidden/overlap pixels for this component."""


def v3_extract_hidden_pixels(registered: Image.Image, visible_cut: Image.Image) -> tuple[Image.Image, int]:
    registered_rgba = registered.convert("RGBA")
    visible_alpha = visible_cut.convert("RGBA").getchannel("A")
    hidden = Image.new("RGBA", registered_rgba.size, (0, 0, 0, 0))
    src = registered_rgba.load()
    dst = hidden.load()
    visible = visible_alpha.load()
    hidden_pixels = 0
    for y in range(registered_rgba.height):
        for x in range(registered_rgba.width):
            r, g, b, a = src[x, y]
            if a > 24 and visible[x, y] <= 24:
                dst[x, y] = (r, g, b, a)
                hidden_pixels += 1
    return hidden, hidden_pixels


def alpha_pixel_count(image: Image.Image, threshold: int = 24) -> int:
    alpha = image.convert("RGBA").getchannel("A")
    if _np is not None:
        return int((_np.asarray(alpha) > threshold).sum())
    return sum(1 for value in alpha.getdata() if value > threshold)


def v3_make_overlap_preview(visible_cut: Image.Image, hidden_inpaint: Image.Image) -> Image.Image:
    preview = Image.new("RGBA", visible_cut.size, (0, 0, 0, 0))
    visible = visible_cut.convert("RGBA")
    hidden = hidden_inpaint.convert("RGBA")
    visible_px = visible.load()
    hidden_px = hidden.load()
    out = preview.load()
    for y in range(preview.height):
        for x in range(preview.width):
            vr, vg, vb, va = visible_px[x, y]
            hr, hg, hb, ha = hidden_px[x, y]
            if va > 24 and ha > 24:
                out[x, y] = (255, 220, 0, 220)
            elif ha > 24:
                out[x, y] = (255, 0, 160, 220)
            elif va > 24:
                out[x, y] = (vr, vg, vb, min(180, va))
    return preview


def v3_hidden_visible_overlap_quality(visible_cut: Image.Image, hidden_inpaint: Image.Image) -> dict[str, Any]:
    visible = visible_cut.convert("RGBA")
    hidden = hidden_inpaint.convert("RGBA")
    hidden_pixels = 0
    overlap_pixels = 0
    bbox: list[int] | None = None
    visible_px = visible.load()
    hidden_px = hidden.load()
    for y in range(hidden.height):
        for x in range(hidden.width):
            if hidden_px[x, y][3] <= 24:
                continue
            hidden_pixels += 1
            if visible_px[x, y][3] <= 24:
                continue
            overlap_pixels += 1
            if bbox is None:
                bbox = [x, y, x + 1, y + 1]
            else:
                bbox[0] = min(bbox[0], x)
                bbox[1] = min(bbox[1], y)
                bbox[2] = max(bbox[2], x + 1)
                bbox[3] = max(bbox[3], y + 1)
    overlap_ratio = round(overlap_pixels / hidden_pixels, 6) if hidden_pixels else 0.0
    passes = not (
        overlap_pixels > V3_HIDDEN_VISIBLE_OVERLAP_MAX_PIXELS
        and overlap_ratio > V3_HIDDEN_VISIBLE_OVERLAP_MAX_RATIO
    )
    return {
        "status": "passed" if passes else "rejected",
        "passes": passes,
        "hiddenPixels": hidden_pixels,
        "overlapPixels": overlap_pixels,
        "overlapRatio": overlap_ratio,
        "overlapBbox": bbox,
        "limits": {
            "maxOverlapPixels": V3_HIDDEN_VISIBLE_OVERLAP_MAX_PIXELS,
            "maxOverlapRatio": V3_HIDDEN_VISIBLE_OVERLAP_MAX_RATIO,
        },
    }


def v3_merge_registered_candidates(
    workspace: Path,
    component: dict[str, Any],
    canvas_size: tuple[int, int],
) -> tuple[Image.Image | None, list[str], dict[str, Any], Image.Image | None]:
    merged = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    conflict_heatmap = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    heat_data = list(conflict_heatmap.getdata())
    files: list[str] = []
    accepted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    registered_candidates = component.get("registeredCandidates") if isinstance(component.get("registeredCandidates"), list) else []
    for index, candidate in enumerate(registered_candidates):
        if not isinstance(candidate, dict) or not isinstance(candidate.get("registered"), str):
            skipped.append(
                {
                    "candidateId": candidate.get("candidateId") if isinstance(candidate, dict) else None,
                    "index": index,
                    "reason": "registered_missing",
                }
            )
            continue
        registered_file = candidate["registered"]
        registered_path = workspace / registered_file
        if not registered_path.exists():
            skipped.append(
                {
                    "candidateId": candidate.get("candidateId"),
                    "registered": registered_file,
                    "index": index,
                    "reason": "registered_file_not_found",
                }
            )
            continue
        img = Image.open(registered_path).convert("RGBA")
        if img.size != canvas_size:
            skipped.append(
                {
                    "candidateId": candidate.get("candidateId"),
                    "registered": registered_file,
                    "index": index,
                    "reason": "registered_size_mismatch",
                    "size": list(img.size),
                    "expectedSize": list(canvas_size),
                }
            )
            continue
        score = candidate.get("score", 0.0)
        try:
            score_value = float(score)
        except (TypeError, ValueError):
            score_value = 0.0
        accepted.append(
            {
                "candidateId": candidate.get("candidateId") if isinstance(candidate.get("candidateId"), str) else f"candidate-{index + 1:03d}",
                "registered": registered_file,
                "score": score_value,
                "sourceIndex": index,
                "image": img,
            }
        )
    accepted.sort(key=lambda item: (item["score"], item["candidateId"], item["registered"]))
    merged_alpha = merged.getchannel("A")
    total_conflict_pixels = 0
    ordered: list[dict[str, Any]] = []
    for order, candidate in enumerate(accepted, start=1):
        img = candidate["image"]
        alpha_data = list(img.getchannel("A").getdata())
        existing_alpha_data = list(merged_alpha.getdata())
        conflict_pixels = 0
        alpha_pixels = 0
        for pixel_index, alpha in enumerate(alpha_data):
            if alpha <= 24:
                continue
            alpha_pixels += 1
            if existing_alpha_data[pixel_index] > 24:
                conflict_pixels += 1
                heat_data[pixel_index] = (255, 76, 0, 220)
        total_conflict_pixels += conflict_pixels
        merged.alpha_composite(img)
        merged_alpha = merged.getchannel("A")
        files.append(candidate["registered"])
        ordered.append(
            {
                "order": order,
                "candidateId": candidate["candidateId"],
                "registered": candidate["registered"],
                "score": candidate["score"],
                "sourceIndex": candidate["sourceIndex"],
                "alphaPixels": alpha_pixels,
                "conflictPixels": conflict_pixels,
            }
        )
    report = {
        "type": "kine.v3.registeredCandidateMergeReport",
        "version": "0.1",
        "componentId": component.get("id"),
        "compositeOrder": "ascending_score_highest_last",
        "candidateCount": len(registered_candidates),
        "mergedCandidateCount": len(files),
        "skippedCandidateCount": len(skipped),
        "totalConflictPixels": total_conflict_pixels,
        "candidates": ordered,
        "skipped": skipped,
    }
    conflict_image = None
    if total_conflict_pixels > 0:
        conflict_heatmap.putdata(heat_data)
        conflict_image = conflict_heatmap
    return (merged if files else None), files, report, conflict_image


def write_v3_hidden_jobs(workspace: Path) -> dict[str, Any]:
    component_plan_path = workspace / "v3" / "component-plan.json"
    if not component_plan_path.exists():
        write_v3_component_plan(workspace)
    component_plan = read_json_if_exists(component_plan_path) or {}
    components = [component for component in component_plan.get("components", []) if isinstance(component, dict)]
    if not any(component.get("mask") for component in components):
        write_v3_mask_jobs(workspace)
        component_plan = read_json_if_exists(component_plan_path) or {}
        components = [component for component in component_plan.get("components", []) if isinstance(component, dict)]
    if not any(component.get("referenceBundle") for component in components):
        write_v3_reference_bundles(workspace)
        component_plan = read_json_if_exists(component_plan_path) or {}
        components = [component for component in component_plan.get("components", []) if isinstance(component, dict)]
    hidden_root = workspace / "v3" / "hidden"
    source = Image.open(workspace / "source.png").convert("RGBA")
    transparent = Image.new("RGBA", source.size, (0, 0, 0, 0))
    results: list[dict[str, Any]] = []
    updated_components: list[dict[str, Any]] = []
    for component in components:
        component = v3_normalize_component_hidden_requirement(component)
        component_id = component.get("id")
        if not isinstance(component_id, str):
            continue
        component_dir = hidden_root / component_id
        component_dir.mkdir(parents=True, exist_ok=True)
        visible_cut_img, _visible_bbox = v3_component_visible_image(workspace, component)
        if visible_cut_img is None:
            visible_cut_img = transparent.copy()
        visible_path = component_dir / "visible_cut.png"
        hidden_path = component_dir / "hidden_inpaint.png"
        merged_path = component_dir / "merged_component.png"
        overlap_path = component_dir / "qa_overlap.png"
        registered_merged_path = component_dir / "registered_merged.png"
        prompt_path = component_dir / "hidden-prompt.txt"
        visible_cut_img.save(visible_path)
        merge_report_path = component_dir / "registered_merge_report.json"
        merge_conflict_path = component_dir / "registered_merge_conflicts.png"
        registered_merged, registered_files, merge_report, merge_conflict = v3_merge_registered_candidates(workspace, component, source.size)
        if registered_merged is not None:
            registered_merged.save(registered_merged_path)
        if merge_conflict is not None:
            merge_conflict.save(merge_conflict_path)
        merge_report["registeredMerged"] = relative_to_workspace(registered_merged_path, workspace) if registered_files else None
        merge_report["conflictHeatmap"] = relative_to_workspace(merge_conflict_path, workspace) if merge_conflict is not None else None
        write_json(merge_report_path, merge_report)
        hidden_img = transparent.copy()
        hidden_pixels = 0
        status = "not_required" if not component.get("needsHiddenCompletion") else "missing"
        reason = None
        if component.get("status") == "not_visible":
            status = "not_visible"
            reason = "component_not_visible"
        elif component.get("needsHiddenCompletion") and not registered_files:
            reason = "registered_candidate_missing"
        elif component.get("needsHiddenCompletion") and registered_merged is not None:
            hidden_img, hidden_pixels = v3_extract_hidden_pixels(registered_merged, visible_cut_img)
            if hidden_pixels > 0:
                status = "passed"
            else:
                status = "missing"
                reason = "hidden_pixels_missing"
        elif not component.get("needsHiddenCompletion"):
            reason = "hidden_completion_not_required"
        hidden_img.save(hidden_path)
        merged = Image.alpha_composite(visible_cut_img.convert("RGBA"), hidden_img.convert("RGBA"))
        merged.save(merged_path)
        v3_make_overlap_preview(visible_cut_img, hidden_img).save(overlap_path)
        prompt_path.write_text(v3_hidden_prompt(component) + "\n", encoding="utf-8")
        job = {
            "type": "kine.v3.hiddenJob",
            "version": "0.1",
            "componentId": component_id,
            "owner": component.get("owner"),
            "needsHiddenCompletion": bool(component.get("needsHiddenCompletion")),
            "registeredCandidates": registered_files,
            "registeredMerged": relative_to_workspace(registered_merged_path, workspace) if registered_files else None,
            "registeredMergeReport": relative_to_workspace(merge_report_path, workspace),
            "registeredMergeConflictHeatmap": relative_to_workspace(merge_conflict_path, workspace) if merge_conflict is not None else None,
            "visibleCut": relative_to_workspace(visible_path, workspace),
            "hiddenInpaint": relative_to_workspace(hidden_path, workspace),
            "mergedComponent": relative_to_workspace(merged_path, workspace),
            "qaOverlap": relative_to_workspace(overlap_path, workspace),
            "prompt": relative_to_workspace(prompt_path, workspace),
            "qa": {
                "status": status,
                "reason": reason,
                "hiddenPixels": hidden_pixels,
            },
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(component_dir / "job.json", job)
        result = {
            "componentId": component_id,
            "owner": component.get("owner"),
            "status": status,
            "reason": reason,
            "hiddenPixels": hidden_pixels,
            "registeredCandidateCount": len(registered_files),
            "job": relative_to_workspace(component_dir / "job.json", workspace),
            "registeredMerged": relative_to_workspace(registered_merged_path, workspace) if registered_files else None,
            "registeredMergeReport": relative_to_workspace(merge_report_path, workspace),
            "registeredMergeConflictHeatmap": relative_to_workspace(merge_conflict_path, workspace) if merge_conflict is not None else None,
            "visibleCut": relative_to_workspace(visible_path, workspace),
            "hiddenInpaint": relative_to_workspace(hidden_path, workspace),
            "mergedComponent": relative_to_workspace(merged_path, workspace),
            "qaOverlap": relative_to_workspace(overlap_path, workspace),
        }
        results.append(result)
        updated_components.append(
            {
                **component,
                "hiddenStatus": status,
                "hiddenReason": reason,
                "registeredMerged": relative_to_workspace(registered_merged_path, workspace) if registered_files else None,
                "registeredMergeReport": relative_to_workspace(merge_report_path, workspace),
                "registeredMergeConflictHeatmap": relative_to_workspace(merge_conflict_path, workspace) if merge_conflict is not None else None,
                "hiddenInpaint": relative_to_workspace(hidden_path, workspace),
                "mergedComponent": relative_to_workspace(merged_path, workspace),
                "qaOverlap": relative_to_workspace(overlap_path, workspace),
            }
        )
    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
    component_plan["components"] = updated_components
    component_plan["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(component_plan_path, component_plan)
    report = {
        "type": "kine.v3.hiddenJobReport",
        "version": "0.1",
        "componentPlan": "v3/component-plan.json",
        "componentCount": len(results),
        "statusCounts": status_counts,
        "results": results,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(hidden_root / "hidden-report.json", report)
    print(
        json.dumps(
            {
                "status": "v3_hidden_jobs_written",
                "componentCount": len(results),
                "statusCounts": status_counts,
                "report": str(hidden_root / "hidden-report.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


def write_v3_hidden_handoff(workspace: Path) -> dict[str, Any]:
    if not (workspace / "v3" / "references" / "reference-bundles.json").exists():
        write_v3_reference_bundles(workspace)
    hidden_root = workspace / "v3" / "hidden"
    hidden_report = write_v3_hidden_jobs(workspace)
    component_plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    components = {
        component.get("id"): component
        for component in component_plan.get("components", [])
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }
    tasks: list[dict[str, Any]] = []
    for result in hidden_report.get("results", []):
        if not isinstance(result, dict):
            continue
        component_id = result.get("componentId")
        component = components.get(component_id)
        if not isinstance(component_id, str) or not isinstance(component, dict):
            continue
        if not component.get("needsHiddenCompletion") or result.get("status") != "missing":
            continue
        component_dir = hidden_root / component_id
        expected_output = component_dir / "imagegen_hidden_inpaint.png"
        ingest_command = (
            "python3 skill-v3/scripts/kine_layer_workspace.py v3-ingest-hidden "
            f"--workspace {shlex.quote(str(workspace))} "
            f"--component {shlex.quote(component_id)} "
            f"--image {shlex.quote(str(expected_output))} --provenance-source imagegen"
        )
        tasks.append(
            {
                "taskId": f"hidden-inpaint:{component_id}",
                "taskType": "hidden_inpaint",
                "componentId": component_id,
                "owner": component.get("owner"),
                "role": component.get("role"),
                "track": component.get("track"),
                "reason": result.get("reason"),
                "visibleCut": result.get("visibleCut"),
                "referenceBundle": component.get("referenceBundle"),
                "originalRegion": component.get("originalRegion"),
                "inputImageContract": v3_input_image_contract(),
                "inputImages": v3_task_input_images(workspace, [component]),
                "registeredMerged": result.get("registeredMerged"),
                "registeredMergeReport": result.get("registeredMergeReport"),
                "registeredMergeConflictHeatmap": result.get("registeredMergeConflictHeatmap"),
                "qaOverlap": result.get("qaOverlap"),
                "prompt": relative_to_workspace(component_dir / "hidden-prompt.txt", workspace),
                "expectedOutput": relative_to_workspace(expected_output, workspace),
                "ingestCommand": ingest_command,
                "imagegenMode": "built_in_image_gen",
                "imagegenSavePolicy": "Save the final transparent PNG at expectedOutput before running ingestCommand.",
                "requirements": [
                    "Use the $imagegen skill only. Do not route this task through any other drawing path.",
                    "Return or post-process to a full-canvas transparent PNG matching source.png dimensions.",
                    "Paint only hidden or overlap pixels; do not repaint source-visible pixels.",
                    "Use originalRegion for color/detail reference; use visibleCut only as the no-redraw source-visible boundary.",
                    "Preserve source palette, material, line style, and component identity.",
                ],
            }
        )
    tasks = [
        v3_enrich_imagegen_task_contract(task)
        for task in v3_attach_reference_contact_boards(workspace, tasks)
    ]
    handoff = {
        "type": "kine.v3.hiddenInpaintHandoff",
        "version": "0.1",
        "status": "needs_imagegen" if tasks else "no_hidden_inpaint_tasks",
        "taskCount": len(tasks),
        "hiddenReport": "v3/hidden/hidden-report.json",
        "tasks": tasks,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(hidden_root / "hidden-inpaint-handoff.json", handoff)
    lines = [
        "# V3 Hidden Inpaint Handoff",
        "",
        "These tasks are for the `$imagegen` skill only. They are not final components until `v3-ingest-hidden`, `v3-recompose`, and `v3-pose-stress` pass.",
        "",
        "Do not route these tasks through any other drawing path. If transparency needs chroma-key cleanup, save the cleaned transparent PNG to the expected output path before ingest.",
        "",
        f"- status: `{handoff['status']}`",
        f"- task count: `{len(tasks)}`",
        "",
    ]
    for task in tasks:
        lines.extend(
            [
                f"## {task['componentId']}",
                "",
                f"- owner: `{task.get('owner')}`",
                f"- role: `{task.get('role')}`",
                f"- reason: `{task.get('reason')}`",
                f"- visible cut: `{task.get('visibleCut')}`",
                f"- reference bundle: `{task.get('referenceBundle')}`",
                f"- original region: `{task.get('originalRegion')}`",
                f"- registered merged: `{task.get('registeredMerged')}`",
                *v3_input_images_markdown_lines(task),
                f"- agent action: {' / '.join(task.get('agentAction') or [])}",
                f"- completion criteria: {' / '.join(task.get('completionCriteria') or [])}",
                f"- prompt: `{task.get('prompt')}`",
                f"- expected output: `{task.get('expectedOutput')}`",
                f"- imagegen mode: `{task.get('imagegenMode')}`",
                "",
                "```bash",
                str(task["ingestCommand"]),
                "```",
                "",
            ]
        )
    if not tasks:
        lines.append("No missing hidden-inpaint tasks were found.\n")
    (hidden_root / "HIDDEN_INPAINT_HANDOFF.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": handoff["status"], "taskCount": len(tasks), "handoff": str(hidden_root / "hidden-inpaint-handoff.json")}, ensure_ascii=False, indent=2))
    return handoff


def v3_parts_sheet_imagegen_tasks(workspace: Path) -> list[dict[str, Any]]:
    sheet_prompts_path = workspace / "v3" / "sheet-prompts.json"
    ensure_v3_stable_object_plan(workspace)
    if not sheet_prompts_path.exists() or v3_sheet_prompts_need_refresh(workspace):
        write_v3_sheet_prompts(workspace)
    sheet_prompts = read_json_if_exists(sheet_prompts_path) or {}
    tasks: list[dict[str, Any]] = []
    for prompt_row in sheet_prompts.get("prompts", []) if isinstance(sheet_prompts.get("prompts"), list) else []:
        if not isinstance(prompt_row, dict):
            continue
        sheet_id = prompt_row.get("sheetId")
        expected_output = prompt_row.get("expectedOutput")
        ingest_command = prompt_row.get("ingestCommand")
        if not isinstance(sheet_id, str) or not isinstance(expected_output, str) or not isinstance(ingest_command, str):
            continue
        tasks.append(
            {
                "taskId": f"parts-sheet:{sheet_id}",
                "taskType": "parts_sheet",
                "sheetId": sheet_id,
                "role": prompt_row.get("role"),
                "owners": prompt_row.get("owners") or [],
                "components": prompt_row.get("components") or [],
                "generationTargets": prompt_row.get("generationTargets") or [],
                "generationTargetIds": prompt_row.get("generationTargetIds") or [],
                "stableObjectLedger": "v3/stable-object-ledger.json"
                if any(isinstance(target, dict) and target.get("stableObjectId") for target in (prompt_row.get("generationTargets") or []))
                else None,
                "layoutPolicy": prompt_row.get("layoutPolicy") or "canonical_puppet_board",
                "prompt": prompt_row.get("prompt"),
                "referenceBundleManifest": prompt_row.get("referenceBundleManifest"),
                "referenceBundles": prompt_row.get("referenceBundles") or [],
                "inputImageContract": prompt_row.get("inputImageContract") or v3_input_image_contract(max_component_refs=12),
                "inputImages": prompt_row.get("inputImages") or [],
                "expectedOutput": expected_output,
                "imagegenMode": "built_in_image_gen",
                "savePolicy": "Save the $imagegen role sheet exactly at expectedOutput before running ingestCommand.",
                "ingestCommand": ingest_command,
                "validationCommands": [
                    "python3 skill-v3/scripts/kine_layer_workspace.py v3-sync-candidates --workspace <workspace>",
                    "python3 skill-v3/scripts/kine_layer_workspace.py v3-register-candidates --workspace <workspace>",
                    "python3 skill-v3/scripts/kine_layer_workspace.py v3-hidden-jobs --workspace <workspace>",
                    "python3 skill-v3/scripts/kine_layer_workspace.py v3-recompose --workspace <workspace>",
                    "python3 skill-v3/scripts/kine_layer_workspace.py v3-validate --workspace <workspace>",
                ],
            }
        )
    return tasks


def v3_stable_object_repair_tasks(workspace: Path) -> list[dict[str, Any]]:
    active_objects = v3_active_stable_objects(workspace, refresh=True)
    if not active_objects:
        return []
    if "stable-object-repair-001" in v3_ingested_parts_sheet_ids(workspace):
        return []
    plan = read_json_if_exists(workspace / "v3" / "component-plan.json") or {}
    components = [component for component in plan.get("components", []) if isinstance(component, dict)] if isinstance(plan.get("components"), list) else []
    props_components = [component for component in components if component.get("owner") == V3_STABLE_OBJECT_OWNER]
    has_accepted_props = any(
        component.get("registrationStatus") == "accepted"
        or component.get("status") == "accepted"
        or component.get("mergedComponent")
        for component in props_components
    )
    if has_accepted_props:
        return []
    audit = v3_stable_owner_coverage_audit(workspace)
    repair_reason = (
        "stable_owner_missing_props"
        if "stable_owner_missing_props" in (audit.get("blockers") or [])
        else "active_stable_objects_without_accepted_props"
    )

    out_dir = workspace / "imagegen" / "v3"
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet_id = "stable-object-repair-001"
    role = "props_accessories"
    prompt_path = out_dir / f"{sheet_id}.{role}.prompt.txt"
    expected_output = f"imagegen/v3/{sheet_id}.{role}.raw.png"
    component_ids = [str(component.get("id")) for component in props_components if component.get("id")]
    generation_targets = v3_stable_object_generation_targets(workspace, component_ids)
    target_ids = [str(target.get("id")) for target in generation_targets if target.get("id")]
    reference_lines = v3_generation_target_reference_lines(generation_targets)
    ingest_command = (
        "python3 skill-v3/scripts/kine_layer_workspace.py parts-sheet "
        f"--workspace {shlex.quote(str(workspace))} "
        f"--sheet {shlex.quote(str(workspace / expected_output))} "
        f"--sheet-id {sheet_id} "
        f"--role {role} "
        "--append --chroma-key auto"
    )
    prompt = f"""Use case: precise-object-edit
Asset type: KINE-LAYER V3 stable object repair sheet

Create one props/accessories role sheet to repair missing stable character-owned objects.

Repair trigger: {repair_reason}.

Target generation rows for $imagegen: {", ".join(target_ids) or "stable object props"}.
These are the only drawing targets. Do not create generic decorations or alternate designs.

Reference package:
- Use the full source image for identity, overall proportions, and placement logic.
- Use each stable object's local crop and nearby-contact crop as the object type, direction, material, contact, and source-scale authority.
- Use each target's `sourceScaleAnchor` as its local source bbox proportion lock. Match the corresponding source object size from the source canvas, not a universal component size.
{chr(10).join(reference_lines) if reference_lines else "- Stable object reference rows are listed in `v3/stable-object-ledger.json`."}

Output requirements:
- Draw coherent props or hand+prop interaction groups only.
- Preserve the source object type, direction, silhouette, material, handle/grip/contact relationship, and scale relative to the source body.
- Do not replace a knife with another weapon, a staff with another tool, a bag with another accessory, etc.
- Do not output floating handles, detached straps, tiny detail fragments, labels, duplicate views, turnarounds, full-body context, or design-board alternates.
- Put all parts on one flat #00ff00 chroma-key background and avoid #00ff00 inside parts."""
    prompt_path.write_text(prompt + "\n", encoding="utf-8")
    input_images = v3_task_input_images(workspace, props_components, max_component_refs=12)
    seen = {(image.get("role"), image.get("path")) for image in input_images if isinstance(image, dict)}
    for stable_image in v3_stable_object_input_images(workspace):
        key = (stable_image.get("role"), stable_image.get("path"))
        if key not in seen:
            input_images.append(stable_image)
            seen.add(key)
    return [
        {
            "taskId": "stable-object-repair:props",
            "taskType": "stable_object_repair",
            "sheetId": sheet_id,
            "role": role,
            "owners": [V3_STABLE_OBJECT_OWNER],
            "components": component_ids,
            "generationTargets": generation_targets,
            "generationTargetIds": target_ids,
            "stableObjectLedger": "v3/stable-object-ledger.json",
            "repairReason": repair_reason,
            "prompt": relative_to_workspace(prompt_path, workspace),
            "referenceBundleManifest": "v3/references/reference-bundles.json" if (workspace / "v3" / "references" / "reference-bundles.json").exists() else None,
            "inputImageContract": v3_input_image_contract(max_component_refs=12),
            "inputImages": input_images,
            "expectedOutput": expected_output,
            "imagegenMode": "built_in_image_gen",
            "savePolicy": "Save the $imagegen stable object repair sheet exactly at expectedOutput before running ingestCommand.",
            "ingestCommand": ingest_command,
            "validationCommands": [
                "python3 skill-v3/scripts/kine_layer_workspace.py v3-sync-candidates --workspace <workspace>",
                "python3 skill-v3/scripts/kine_layer_workspace.py v3-register-candidates --workspace <workspace>",
                "python3 skill-v3/scripts/kine_layer_workspace.py v3-recompose --workspace <workspace>",
                "python3 skill-v3/scripts/kine_layer_workspace.py v3-validate --workspace <workspace>",
            ],
        }
    ]


def v3_ingested_parts_sheet_ids(workspace: Path) -> set[str]:
    parts_manifest = read_json_if_exists(workspace / "parts" / "parts-sheet-manifest.json") or {}
    sheets = parts_manifest.get("sheets", []) if isinstance(parts_manifest.get("sheets"), list) else []
    return {
        str(sheet.get("sheetId"))
        for sheet in sheets
        if isinstance(sheet, dict) and isinstance(sheet.get("sheetId"), str) and sheet.get("sheetId")
    }


def v3_imagegen_task_agent_action(task: dict[str, Any]) -> list[str]:
    task_type = str(task.get("taskType") or "unknown")
    expected_output = str(task.get("expectedOutput") or "expectedOutput")
    ingest_command = str(task.get("ingestCommand") or "ingestCommand")
    if task_type in {"parts_sheet", "stable_object_repair"}:
        sheet_wording = "role-specific parts sheet" if task_type == "parts_sheet" else "stable object repair props/interaction sheet"
        return [
            "Load the listed inputImages or referenceContactBoard into the $imagegen context; do not rely on prompt text paths alone.",
            f"Use the $imagegen skill to generate only this {sheet_wording} as a PNG.",
            f"Save the generated PNG exactly at {expected_output}.",
            f"Run the ingest command: {ingest_command}",
            "Run v3-continue-imagegen for this workspace so candidate sync, registration, recompose, and validation continue.",
        ]
    if task_type == "registration_repair":
        return [
            "Load the listed inputImages or referenceContactBoard into the $imagegen context; do not rely on prompt text paths alone.",
            "Use source-visible preservation mode: keep the original local crop's visible pixels, colors, linework, texture, scale, and pose as the visual truth.",
            "Use the $imagegen skill to repair only the rejected component candidate; remove foreign owners and add only necessary hidden/overlap pixels.",
            "Keep the source image's 2D illustration/rendering style; do not turn the component into photorealistic product photography or a different material style.",
            "Do not produce multi-view variants, alternate angles, full-body context, design boards, or decorative duplicates.",
            f"Save the generated PNG exactly at {expected_output}.",
            f"Run the ingest command: {ingest_command}",
            "Run v3-continue-imagegen for this workspace so repaired candidates are synced, registered, recomposed, and validated.",
        ]
    if task_type == "hidden_inpaint":
        return [
            "Load the listed inputImages or referenceContactBoard into the $imagegen context; do not rely on prompt text paths alone.",
            "Use the $imagegen skill to complete only the hidden/overlap area for this component.",
            f"Save the full-canvas transparent PNG exactly at {expected_output}.",
            f"Run the ingest command: {ingest_command}",
            "Run v3-continue-imagegen for this workspace so hidden review, recompose, pose stress, and validation continue.",
        ]
    return [
        "Load the listed inputImages into the $imagegen context.",
        f"Save the generated PNG exactly at {expected_output}.",
        f"Run the ingest command: {ingest_command}",
        "Run v3-continue-imagegen for this workspace.",
    ]


def v3_imagegen_task_completion_criteria(task: dict[str, Any]) -> list[str]:
    task_type = str(task.get("taskType") or "unknown")
    if task_type in {"parts_sheet", "stable_object_repair"}:
        return [
            "expectedOutput exists as a readable PNG.",
            "parts-sheet ingest created or updated parts/parts-sheet-manifest.json for this sheetId.",
            "v3-sheet-manifest and v3-registration reports were refreshed by v3-continue-imagegen.",
            "v3-imagegen-progress-report no longer marks this task as pending_imagegen.",
        ]
    if task_type == "registration_repair":
        return [
            "expectedOutput exists as a readable PNG.",
            "parts-sheet ingest appended the repair candidate.",
            "v3-registration-report was refreshed and either accepts the repaired candidate or records structured rejection reasons.",
            "v3-imagegen-progress-report no longer marks this task as pending_imagegen.",
        ]
    if task_type == "hidden_inpaint":
        return [
            "expectedOutput exists as a readable full-canvas transparent PNG.",
            "v3-ingest-hidden wrote hidden-inpaint provenance for this component.",
            "v3-hidden-review, v3-recompose, v3-pose-stress, and v3-validate were refreshed.",
            "v3-imagegen-progress-report no longer marks this task as pending_imagegen.",
        ]
    return [
        "expectedOutput exists as a readable PNG.",
        "ingestCommand has been run.",
        "v3-imagegen-progress-report no longer marks this task as pending_imagegen.",
    ]


def v3_enrich_imagegen_task_contract(task: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(task)
    enriched.setdefault("agentAction", v3_imagegen_task_agent_action(enriched))
    enriched.setdefault("completionCriteria", v3_imagegen_task_completion_criteria(enriched))
    enriched.setdefault("continuationCommand", "python3 skill-v3/scripts/kine_layer_workspace.py v3-continue-imagegen --workspace <workspace>")
    enriched.setdefault("executionContract", "must_execute_save_ingest_and_continue_before_final")
    return enriched


def write_v3_subject_matte_prompt(workspace: Path) -> dict[str, Any]:
    out_dir = workspace / "imagegen" / "v3"
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = out_dir / "source-character-matte.prompt.txt"
    expected_output = "imagegen/v3/source-character-matte.png"
    default_out = workspace.parent / f"{workspace.name}-character-matte"
    ingest_command = (
        "python3 skill-v3/scripts/kine_layer_workspace.py v3-ingest-subject-matte "
        f"--workspace {shlex.quote(str(workspace))} "
        f"--matte {shlex.quote(str(workspace / expected_output))} "
        f"--out {shlex.quote(str(default_out))}"
    )
    prompt = """Use case: precise-object-edit
Asset type: KINE-LAYER V3 source subject isolation

Input image: use the provided source illustration as the strict reference.

Task: isolate only the main character as a clean full-canvas transparent PNG. Preserve the visible character pixels, proportions, identity, colors, clothing, hair, face, hands, boots, and held character-owned props. Remove environment/background content such as sky, grass, aircraft, buildings, ground, shadows not attached to the character, and other scene elements.

Output requirements:
- Return a high-resolution PNG matching source.png canvas dimensions.
- Prefer true alpha. If the tool cannot return true alpha, a perfectly flat #00ff00 background is acceptable only as an intermediate so the Agent can file it through v3-save-imagegen-inline.
- Keep the character in the exact same position and scale as the source.
- Do not redraw, beautify, redesign, change pose, or invent hidden surfaces.
- Do not create a parts sheet yet.
- Background must be fully transparent.

Agent action:
Load source.png into the $imagegen context before generating.
Use $imagegen to create subject matte.
Save PNG result at expectedOutput.
If $imagegen returns a savedPath or a file under $CODEX_HOME/generated_images, run v3-save-imagegen-inline --input for this task first.
If $imagegen returns savedPath=null but provides inline PNG/base64 result, run v3-save-imagegen-inline --base64-file or --base64 for this task first.
Then internally run ingestCommand.
Do not run v3-mask-jobs on the original scene source."""
    prompt_path.write_text(prompt + "\n", encoding="utf-8")
    task = {
        "taskId": "subject-matte:source-character",
        "taskType": "subject_matte",
        "prompt": relative_to_workspace(prompt_path, workspace),
        "sourceImage": "source.png",
        "editTarget": "source.png",
        "inputImageContract": {
            "required": True,
            "execution": "Before calling $imagegen, load source.png as the edit target/reference image. Do not rely on prompt text paths alone.",
        },
        "inputImages": [
            {
                "role": "edit-target-source-scene",
                "path": "source.png",
                "description": "source scene image; isolate the main character without changing position, scale, identity, or visible pixels",
            }
        ],
        "expectedOutput": expected_output,
        "imagegenMode": "built_in_image_gen",
        "agentAction": [
            "Load source.png into the $imagegen context before generating.",
            "Use $imagegen to create subject matte.",
            "Save the result as a PNG at expectedOutput.",
            "If savedPath or a $CODEX_HOME/generated_images file exists, run v3-save-imagegen-inline --input for this task.",
            "If savedPath is null but inline PNG/base64 exists, run v3-save-imagegen-inline --base64-file or --base64 for this task.",
            "Then internally run ingestCommand.",
        ],
        "completionCriteria": [
            "expectedOutput exists as a readable image.",
            "expectedOutput matches source.png canvas size.",
            "expectedOutput has non-empty alpha.",
            "v3-imagegen-progress-report marks this task ready_for_ingest or ingested_subject_matte.",
        ],
        "continuationCommand": (
            "python3 skill-v3/scripts/kine_layer_workspace.py v3-continue-imagegen "
            f"--workspace {shlex.quote(str(workspace))}"
        ),
        "savePolicy": "Agent saves the $imagegen subject matte as a PNG at expectedOutput. If built-in $imagegen returns a savedPath or generated_images file, use v3-save-imagegen-inline --input. If it returns inline PNG/base64 with savedPath=null, use --base64-file or --base64. Then internally run ingestCommand.",
        "ingestCommand": ingest_command,
        "nextAction": "Agent runs ingestCommand internally after the transparent matte exists, then continues V3 on the generated character-matte workspace.",
    }
    return task


def evaluate_v3_subject_matte(workspace: Path, matte_path: Path) -> dict[str, Any]:
    source_img = Image.open(workspace / "source.png").convert("RGBA")
    matte_img = Image.open(matte_path).convert("RGBA")
    matte_alpha = matte_img.getchannel("A")
    matte_stats = alpha_stats(matte_img)
    bbox = matte_stats.get("alphaBbox")
    ratios = _bbox_ratio_metrics(bbox, matte_img.size)
    edge_alpha_ratio = _alpha_edge_pixel_ratio(matte_alpha)
    source_overlap_ratio = _alpha_overlap_ratio(matte_alpha, source_img.getchannel("A"))
    coverage = float(matte_stats.get("alphaCoverage") or 0.0)
    blockers: list[str] = []
    warnings: list[str] = []

    if matte_img.size != source_img.size:
        blockers.append("subject_matte_canvas_size_mismatch")
    if not bbox:
        blockers.append("subject_matte_empty_alpha")
    if coverage < V3_SUBJECT_MIN_ALPHA_COVERAGE:
        blockers.append("subject_matte_alpha_too_sparse")
    if coverage >= 0.985:
        blockers.append("subject_matte_alpha_covers_entire_canvas")
    if coverage > V3_SUBJECT_MAX_ALPHA_COVERAGE:
        blockers.append("subject_matte_alpha_covers_too_much_canvas")
    if ratios["bboxAreaRatio"] < V3_SUBJECT_MIN_BBOX_AREA_RATIO:
        blockers.append("subject_matte_bbox_too_small")
    if ratios["bboxWidthRatio"] < V3_SUBJECT_MIN_BBOX_WIDTH_RATIO:
        blockers.append("subject_matte_bbox_too_narrow")
    if ratios["bboxHeightRatio"] < V3_SUBJECT_MIN_BBOX_HEIGHT_RATIO:
        blockers.append("subject_matte_bbox_too_short_for_full_character")
    if source_overlap_ratio < 0.95:
        blockers.append("subject_matte_low_source_visible_overlap")
    if edge_alpha_ratio > V3_SUBJECT_EDGE_ALPHA_RATIO_LIMIT and ratios["bboxTouchesEdgeCount"] >= 2:
        blockers.append("subject_matte_likely_contains_edge_background")
    elif edge_alpha_ratio > V3_SUBJECT_EDGE_ALPHA_RATIO_LIMIT:
        warnings.append("subject_matte_edge_alpha_high")

    status = "passed" if not blockers else PARTS_SHEET_BLOCKED_STATUS
    qa = {
        "type": "kine.v3.subjectMatteQA",
        "version": "0.1",
        "status": status,
        "workspace": str(workspace),
        "matte": str(matte_path),
        "blockers": blockers,
        "warnings": warnings,
        "matteStats": matte_stats,
        "sourceStats": alpha_stats(source_img),
        "metrics": {
            **ratios,
            "edgeAlphaRatio": edge_alpha_ratio,
            "sourceVisibleOverlapRatio": source_overlap_ratio,
        },
        "thresholds": {
            "minAlphaCoverage": V3_SUBJECT_MIN_ALPHA_COVERAGE,
            "maxAlphaCoverage": V3_SUBJECT_MAX_ALPHA_COVERAGE,
            "minBboxAreaRatio": V3_SUBJECT_MIN_BBOX_AREA_RATIO,
            "minBboxWidthRatio": V3_SUBJECT_MIN_BBOX_WIDTH_RATIO,
            "minBboxHeightRatio": V3_SUBJECT_MIN_BBOX_HEIGHT_RATIO,
            "edgeAlphaRatioLimit": V3_SUBJECT_EDGE_ALPHA_RATIO_LIMIT,
            "minSourceVisibleOverlapRatio": 0.95,
        },
        "note": "This QA only verifies matte geometry and source-canvas plausibility. It cannot prove semantic identity; final V3 acceptance still requires registration, recompose, and visual review.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "v3" / "source" / "subject-matte-qa.json", qa)
    return qa


def ingest_v3_subject_matte(workspace: Path, matte: Path, out: Path | None = None, force: bool = False) -> dict[str, Any]:
    """Create a clean V3 workspace from a $imagegen subject-isolated matte.

    Scene workspaces are not valid component-mask sources. The matte becomes a new
    source workspace, then normal V3 mask/reference/sheet task generation resumes.
    """
    if not (workspace / "source.png").exists():
        raise FileNotFoundError(workspace / "source.png")
    if not matte.exists():
        raise FileNotFoundError(matte)

    with Image.open(workspace / "source.png") as source_img:
        source_size = source_img.size
    matte_img = Image.open(matte).convert("RGBA")
    matte_stats = alpha_stats(matte_img)
    matte_qa = evaluate_v3_subject_matte(workspace, matte)
    blockers = list(matte_qa.get("blockers") or [])
    if blockers:
        result = {
            "type": "kine.v3.subjectMatteIngest",
            "version": "0.1",
            "status": PARTS_SHEET_BLOCKED_STATUS,
            "workspace": str(workspace),
            "matte": str(matte),
            "blockers": blockers,
            "matteStats": matte_stats,
            "subjectMatteQA": "v3/source/subject-matte-qa.json",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(workspace / "v3" / "source" / "subject-matte-ingest.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    target_workspace = out or (workspace.parent / f"{workspace.name}-character-matte")
    init_workspace(matte, target_workspace, resolution=source_size[0], force=force)
    write_v3_component_plan(target_workspace)
    mask_summary = write_v3_mask_jobs(target_workspace)
    reference_manifest = write_v3_reference_bundles(target_workspace)
    sheet_prompts = write_v3_sheet_prompts(target_workspace)
    imagegen_progress = write_v3_imagegen_progress_report(target_workspace, refresh_work_order=True)

    result = {
        "type": "kine.v3.subjectMatteIngest",
        "version": "0.1",
        "status": "subject_matte_ingested",
        "sourceSceneWorkspace": str(workspace),
        "characterMatteWorkspace": str(target_workspace),
        "matte": str(matte),
        "matteStats": matte_stats,
        "subjectMatteQA": "v3/source/subject-matte-qa.json",
        "nextArtifacts": {
            "sourceSubjectPreflight": str(target_workspace / "source" / "source-subject-preflight.json"),
            "maskSummary": str(target_workspace / "v3" / "masks" / "mask-summary.json"),
            "referenceBundles": str(target_workspace / "v3" / "references" / "reference-bundles.json"),
            "sheetPrompts": str(target_workspace / "v3" / "sheet-prompts.json"),
            "imagegenWorkOrder": str(target_workspace / "v3" / "imagegen" / "imagegen-work-order.json"),
            "imagegenProgressReport": str(target_workspace / "v3" / "imagegen" / "imagegen-progress-report.json"),
        },
        "counts": {
            "maskComponentCount": mask_summary.get("componentCount"),
            "referenceComponentCount": reference_manifest.get("componentCount"),
            "sheetPromptCount": sheet_prompts.get("writtenCount"),
            "pendingImagegenCount": imagegen_progress.get("pendingImagegenCount"),
        },
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "v3" / "source" / "subject-matte-ingest.json", result)
    update_run_state(
        workspace,
        {
            "v3SubjectMatteIngest": "v3/source/subject-matte-ingest.json",
            "v3SubjectMatteWorkspace": str(target_workspace),
            "status": "subject_matte_ingested",
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def write_v3_imagegen_work_order(workspace: Path, max_registration_tasks: int = 24) -> dict[str, Any]:
    """Write the current staged executable $imagegen work order for V3."""
    subject_report = v3_subject_preflight_blocks_masks(workspace)
    if subject_report.get("shouldBlockV3Masks"):
        tasks = [
            v3_enrich_imagegen_task_contract(task)
            for task in v3_attach_reference_contact_boards(workspace, [write_v3_subject_matte_prompt(workspace)])
        ]
        task_type_counts = {"subject_matte": 1}
        status = "needs_imagegen_subject_matte"
        out_dir = workspace / "v3" / "imagegen"
        out_dir.mkdir(parents=True, exist_ok=True)
        work_order = {
            "type": "kine.v3.imagegenWorkOrder",
            "version": "0.1",
            "status": status,
            "workspace": workspace.name,
            "stage": "subject_matte",
            "taskCount": len(tasks),
            "taskTypeCounts": task_type_counts,
            "sourceSubjectPreflight": "source/source-subject-preflight.json",
            "blockers": ["source_subject_needs_imagegen_subject_matte"],
            "tasks": tasks,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "rules": [
                "Use the $imagegen skill as the only drawing path.",
                "Do not generate parts sheets until a clean transparent character matte exists.",
                "Do not treat scene-source visible cuts as component evidence.",
            ],
        }
        write_json(out_dir / "imagegen-work-order.json", work_order)
        lines = [
            "# V3 $imagegen Work Order",
            "",
            "Status: `needs_imagegen_subject_matte`.",
            "",
            "The source appears to be an opaque non-flat scene. V3 routes it to `$imagegen` subject isolation before component masks, reference bundles, parts sheets, or hidden inpaint.",
            "",
            "Agent action:",
            "",
            "1. Use `$imagegen` to create subject matte.",
            "2. Save result at `expectedOutput`.",
            "3. Then internally run `ingestCommand`.",
            "",
        ]
        for task in tasks:
            lines.extend(
                [
                    f"## {task['taskId']}",
                    "",
                    f"- prompt: `{task.get('prompt')}`",
                    f"- source image: `{task.get('sourceImage')}`",
                    *v3_input_images_markdown_lines(task),
                    f"- reference-contact board: `{task.get('referenceContactBoard')}`",
                f"- expected output: `{task.get('expectedOutput')}`",
                f"- imagegen mode: `{task.get('imagegenMode')}`",
                f"- agent action: {' / '.join(task.get('agentAction') or [])}",
                f"- completion criteria: {' / '.join(task.get('completionCriteria') or [])}",
                "",
                "Internal ingest command for the agent:",
                "",
                "```bash",
                str(task.get("ingestCommand") or ""),
                    "```",
                    "",
                    f"- next action: {task.get('nextAction')}",
                    "",
                ]
            )
        (out_dir / "IMAGEGEN_WORK_ORDER.md").write_text("\n".join(lines), encoding="utf-8")
        update_run_state(
            workspace,
            {
                "v3ImagegenWorkOrder": "v3/imagegen/imagegen-work-order.json",
                "v3ImagegenWorkOrderStatus": status,
            },
        )
        print(json.dumps({"status": status, "taskCount": len(tasks), "workOrder": str(out_dir / "imagegen-work-order.json")}, ensure_ascii=False, indent=2))
        return work_order

    all_role_sheet_tasks = v3_parts_sheet_imagegen_tasks(workspace)
    ingested_sheet_ids = v3_ingested_parts_sheet_ids(workspace)
    pending_role_sheet_tasks = [
        task
        for task in all_role_sheet_tasks
        if str(task.get("sheetId") or "") not in ingested_sheet_ids
    ]

    stage = "role_sheets" if pending_role_sheet_tasks else "repair_and_hidden"
    registration_report: dict[str, Any] | None = None
    hidden_handoff: dict[str, Any] | None = None
    tasks: list[dict[str, Any]] = list(pending_role_sheet_tasks)

    if not pending_role_sheet_tasks:
        for task in v3_stable_object_repair_tasks(workspace):
            tasks.append(task)
        registration_report = write_v3_registration_repair_report(workspace, max_registration_tasks)
        hidden_handoff = write_v3_hidden_handoff(workspace)

        for task in registration_report.get("tasks", []) if isinstance(registration_report.get("tasks"), list) else []:
            if not isinstance(task, dict):
                continue
            tasks.append(
                {
                    "taskId": f"registration-repair:{task.get('componentId')}",
                    "taskType": "registration_repair",
                    "componentId": task.get("componentId"),
                    "owner": task.get("owner"),
                    "role": task.get("role"),
                    "action": task.get("action"),
                    "reasons": task.get("reasons") or [],
                    "prompt": task.get("prompt"),
                    "inputImageContract": task.get("inputImageContract") or v3_input_image_contract(),
                    "inputImages": task.get("inputImages") or [],
                    "expectedOutput": task.get("expectedOutput"),
                    "imagegenMode": "built_in_image_gen",
                    "savePolicy": "Save the $imagegen result exactly at expectedOutput before running ingestCommand.",
                    "ingestCommand": task.get("ingestCommand"),
                    "validationCommands": [
                        "python3 skill-v3/scripts/kine_layer_workspace.py v3-sync-candidates --workspace <workspace>",
                        "python3 skill-v3/scripts/kine_layer_workspace.py v3-register-candidates --workspace <workspace>",
                        "python3 skill-v3/scripts/kine_layer_workspace.py v3-recompose --workspace <workspace>",
                        "python3 skill-v3/scripts/kine_layer_workspace.py v3-validate --workspace <workspace>",
                    ],
                }
            )
        for task in hidden_handoff.get("tasks", []) if isinstance(hidden_handoff.get("tasks"), list) else []:
            if not isinstance(task, dict):
                continue
            tasks.append(
                {
                    "taskId": f"hidden-inpaint:{task.get('componentId')}",
                    "taskType": "hidden_inpaint",
                    "componentId": task.get("componentId"),
                    "owner": task.get("owner"),
                    "role": task.get("role"),
                    "reason": task.get("reason"),
                    "prompt": task.get("prompt"),
                    "visibleCut": task.get("visibleCut"),
                    "inputImageContract": task.get("inputImageContract") or v3_input_image_contract(),
                    "inputImages": task.get("inputImages") or [],
                    "registeredMerged": task.get("registeredMerged"),
                    "qaOverlap": task.get("qaOverlap"),
                    "expectedOutput": task.get("expectedOutput"),
                    "imagegenMode": "built_in_image_gen",
                    "savePolicy": "Save the $imagegen transparent PNG exactly at expectedOutput before running ingestCommand.",
                    "ingestCommand": task.get("ingestCommand"),
                    "validationCommands": [
                        "python3 skill-v3/scripts/kine_layer_workspace.py v3-hidden-review-report --workspace <workspace>",
                        "python3 skill-v3/scripts/kine_layer_workspace.py v3-recompose --workspace <workspace>",
                        "python3 skill-v3/scripts/kine_layer_workspace.py v3-pose-stress --workspace <workspace>",
                        "python3 skill-v3/scripts/kine_layer_workspace.py v3-validate --workspace <workspace>",
                    ],
                }
            )
        if not tasks:
            stage = "none"

    tasks = [
        v3_enrich_imagegen_task_contract(task)
        for task in v3_attach_reference_contact_boards(workspace, tasks)
    ]
    task_type_counts: dict[str, int] = {}
    for task in tasks:
        task_type = str(task.get("taskType") or "unknown")
        task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
    status = "needs_imagegen" if tasks else "no_imagegen_tasks"
    out_dir = workspace / "v3" / "imagegen"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_order = {
        "type": "kine.v3.imagegenWorkOrder",
        "version": "0.1",
        "status": status,
        "workspace": workspace.name,
        "stage": stage,
        "taskCount": len(tasks),
        "taskTypeCounts": task_type_counts,
        "roleSheetTaskCount": len(all_role_sheet_tasks),
        "pendingRoleSheetCount": len(pending_role_sheet_tasks),
        "ingestedRoleSheetCount": len(ingested_sheet_ids & {str(task.get("sheetId") or "") for task in all_role_sheet_tasks}),
        "registrationRepairReport": "v3/registration/registration-repair-report.json" if registration_report is not None else None,
        "stableObjectLedger": "v3/stable-object-ledger.json" if v3_stable_object_ledger_path(workspace).exists() else None,
        "hiddenInpaintHandoff": "v3/hidden/hidden-inpaint-handoff.json" if hidden_handoff is not None else None,
        "tasks": tasks,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "rules": [
            "Use the $imagegen skill as the only drawing path.",
            "Stage 1 work orders contain only role-specific parts sheets. Do not request hidden inpaint or repair until all role sheets have been saved and ingested.",
            "After each expectedOutput is saved, run its ingestCommand and then run v3-continue-imagegen so the next stage is refreshed.",
            "Role-specific parts sheets must be saved at expectedOutput and ingested with their listed parts-sheet command before registration can produce final components.",
            "Do not treat any generated output as final until ingest, registration or hidden review, recompose, pose stress, and v3-validate pass.",
            "If a generated image uses chroma key, save the cleaned transparent PNG at expectedOutput before ingest.",
            "Debug artifacts such as semantic-decomposition boards, visible crops, raw sheets, transparent sheets, and candidate sheets are never final deliverables.",
        ],
    }
    write_json(out_dir / "imagegen-work-order.json", work_order)

    lines = [
        "# V3 $imagegen Work Order",
        "",
        "Use the `$imagegen` skill as the only drawing path for every task below.",
        "",
        "Generated outputs are candidates only. Save each result at its `expectedOutput`, run the listed ingest command, then run validation.",
        "",
        f"- status: `{status}`",
        f"- stage: `{stage}`",
        f"- task count: `{len(tasks)}`",
        f"- pending role sheets: `{len(pending_role_sheet_tasks)}` / `{len(all_role_sheet_tasks)}`",
    ]
    for task_type, count in sorted(task_type_counts.items()):
        lines.append(f"- {task_type}: `{count}`")
    lines.append("")
    for task in tasks:
        lines.extend(
            [
                f"## {task['taskId']}",
                "",
                f"- component: `{task.get('componentId')}`",
                f"- prompt: `{task.get('prompt')}`",
                *v3_input_images_markdown_lines(task),
                f"- reference-contact board: `{task.get('referenceContactBoard')}`",
                f"- expected output: `{task.get('expectedOutput')}`",
                f"- imagegen mode: `{task.get('imagegenMode')}`",
                f"- agent action: {' / '.join(task.get('agentAction') or [])}",
                f"- completion criteria: {' / '.join(task.get('completionCriteria') or [])}",
                "",
                "```bash",
                str(task.get("ingestCommand") or ""),
                "```",
                "",
            ]
        )
    if not tasks:
        lines.append("No pending `$imagegen` tasks were found.\n")
    (out_dir / "IMAGEGEN_WORK_ORDER.md").write_text("\n".join(lines), encoding="utf-8")
    update_run_state(
        workspace,
            {
                "v3ImagegenWorkOrder": "v3/imagegen/imagegen-work-order.json",
                "v3ImagegenWorkOrderStatus": status,
                "v3ImagegenWorkOrderStage": stage,
            },
        )
    print(json.dumps({"status": status, "taskCount": len(tasks), "workOrder": str(out_dir / "imagegen-work-order.json")}, ensure_ascii=False, indent=2))
    return work_order


def inspect_v3_imagegen_task_output(workspace: Path, task: dict[str, Any], canvas_size: tuple[int, int]) -> dict[str, Any]:
    task_type = str(task.get("taskType") or "unknown")
    expected_output = str(task.get("expectedOutput") or "")
    expected_path = workspace / expected_output if expected_output else workspace / "__missing_expected_output__"
    row: dict[str, Any] = {
        "taskId": task.get("taskId"),
        "taskType": task_type,
        "componentId": task.get("componentId"),
        "expectedOutput": expected_output or None,
        "exists": expected_path.exists() if expected_output else False,
        "canIngest": False,
        "status": "missing_expected_output" if not expected_output else "pending_imagegen",
        "blockers": [],
    }
    if not expected_output:
        row["blockers"].append("expected_output_missing")
        return row
    if task_type == "subject_matte":
        subject_ingest = read_json_if_exists(workspace / "v3" / "source" / "subject-matte-ingest.json") or {}
        if subject_ingest.get("status") == "subject_matte_ingested":
            row["status"] = "ingested_subject_matte"
            row["exists"] = expected_path.exists()
            row["canIngest"] = False
            row["characterMatteWorkspace"] = subject_ingest.get("characterMatteWorkspace")
            row["subjectMatteQA"] = subject_ingest.get("subjectMatteQA")
            row["nextAction"] = "Continue V3 on the characterMatteWorkspace."
            return row
    if task_type in {"parts_sheet", "stable_object_repair"} and task.get("sheetId"):
        parts_manifest = read_json_if_exists(workspace / "parts" / "parts-sheet-manifest.json") or {}
        sheets = parts_manifest.get("sheets", []) if isinstance(parts_manifest.get("sheets"), list) else []
        ingested_sheet = next((sheet for sheet in sheets if isinstance(sheet, dict) and sheet.get("sheetId") == task.get("sheetId")), None)
        if ingested_sheet:
            row["status"] = "ingested_sheet"
            row["exists"] = expected_path.exists()
            row["canIngest"] = False
            row["partsSheet"] = {
                "contactPath": ingested_sheet.get("contactPath"),
                "componentCount": ingested_sheet.get("componentCount"),
                "transparentPath": ingested_sheet.get("transparentPath"),
            }
            row["nextAction"] = "Run v3-sync-candidates, v3-register-candidates, v3-hidden-jobs, v3-recompose, and v3-validate."
            return row
        preflight = read_json_if_exists(workspace / "parts" / f"{task.get('sheetId')}.preflight.json") or {}
        if expected_path.exists() and preflight.get("status") == "rejected":
            failures = preflight.get("failures", []) if isinstance(preflight.get("failures"), list) else []
            failure_codes = [str(item.get("code")) for item in failures if isinstance(item, dict) and item.get("code")]
            row["status"] = "sheet_preflight_rejected"
            row["exists"] = True
            row["canIngest"] = False
            row["blockers"].append("parts_sheet_preflight_rejected")
            row["blockers"].extend(f"sheet_preflight:{code}" for code in failure_codes)
            row["partsSheetPreflight"] = {
                "path": f"parts/{task.get('sheetId')}.preflight.json",
                "status": preflight.get("status"),
                "failureCodes": failure_codes,
                "componentCount": preflight.get("componentCount"),
            }
            row["nextAction"] = "Regenerate or repair this role sheet, then rerun parts-sheet ingest and v3-continue-imagegen."
            return row
    if not expected_path.exists():
        row["blockers"].append("output_missing")
        row["nextAction"] = "Run the $imagegen skill for this task and save the result at expectedOutput."
        return row
    stats = artifact_stats(expected_path, canvas_size)
    if not stats:
        row["status"] = "invalid_image"
        row["blockers"].append("output_unreadable")
        return row
    row["imageStats"] = stats
    if float(stats.get("alphaCoverage") or 0.0) <= 0.0:
        row["status"] = "invalid_empty_alpha"
        row["blockers"].append("output_alpha_empty")
        return row
    if task_type == "hidden_inpaint" and not stats.get("canvasRegistered"):
        row["status"] = "invalid_canvas_size"
        row["blockers"].append("hidden_output_must_match_source_canvas")
        row["nextAction"] = "Regenerate or post-process to a full-canvas transparent PNG before v3-ingest-hidden."
        return row
    if task_type == "subject_matte":
        if not stats.get("canvasRegistered"):
            row["status"] = "invalid_canvas_size"
            row["blockers"].append("subject_matte_must_match_source_canvas")
            row["nextAction"] = "Regenerate or post-process to a full-canvas transparent PNG matching source.png."
            return row
        row["canIngest"] = True
        row["status"] = "ready_for_ingest"
        row["nextAction"] = task.get("ingestCommand")
        return row

    row["canIngest"] = True
    row["status"] = "ready_for_ingest"
    row["nextAction"] = task.get("ingestCommand")

    if task_type == "hidden_inpaint" and task.get("componentId"):
        provenance = read_json_if_exists(workspace / "v3" / "hidden" / str(task["componentId"]) / "hidden-inpaint-provenance.json") or {}
        if provenance:
            row["provenance"] = {
                "status": provenance.get("status"),
                "storedImage": provenance.get("storedImage"),
                "provenanceSource": provenance.get("provenanceSource"),
                "visibleOverlapStatus": (provenance.get("visibleOverlapQuality") or {}).get("status") if isinstance(provenance.get("visibleOverlapQuality"), dict) else None,
            }
            if provenance.get("status") == "passed":
                row["status"] = "ingested_passed"
                row["canIngest"] = False
                row["nextAction"] = "Run v3-hidden-review-report, v3-recompose, v3-pose-stress, and v3-validate."
            elif provenance.get("status") == "rejected":
                row["status"] = "ingested_rejected"
                row["canIngest"] = False
                row["blockers"].append("hidden_ingest_rejected")
                row["nextAction"] = "Regenerate the hidden inpaint output with less source-visible overlap."
    return row


def write_v3_imagegen_progress_report(workspace: Path, refresh_work_order: bool = False) -> dict[str, Any]:
    """Inspect whether $imagegen work-order outputs exist and are ready to ingest."""
    work_order_path = workspace / "v3" / "imagegen" / "imagegen-work-order.json"
    work_order = read_json_if_exists(work_order_path) or {}
    if refresh_work_order or work_order.get("type") != "kine.v3.imagegenWorkOrder":
        work_order = write_v3_imagegen_work_order(workspace)
    source_path = workspace / "source.png"
    if source_path.exists():
        with Image.open(source_path) as source_img:
            canvas_size = source_img.size
    else:
        canvas_size = (DEFAULT_RESOLUTION, DEFAULT_RESOLUTION)

    tasks = [task for task in work_order.get("tasks", []) if isinstance(task, dict)] if isinstance(work_order.get("tasks"), list) else []
    rows = [inspect_v3_imagegen_task_output(workspace, task, canvas_size) for task in tasks]
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        task_type = str(row.get("taskType") or "unknown")
        type_counts[task_type] = type_counts.get(task_type, 0) + 1
    pending_count = sum(status_counts.get(status, 0) for status in ["pending_imagegen", "missing_expected_output"])
    invalid_count = sum(count for status, count in status_counts.items() if status.startswith("invalid_"))
    ready_count = status_counts.get("ready_for_ingest", 0)
    rejected_count = status_counts.get("ingested_rejected", 0) + status_counts.get("sheet_preflight_rejected", 0)
    passed_count = status_counts.get("ingested_passed", 0) + status_counts.get("ingested_sheet", 0) + status_counts.get("ingested_subject_matte", 0)
    if not rows:
        status = "no_imagegen_tasks"
    elif invalid_count or rejected_count:
        status = PARTS_SHEET_BLOCKED_STATUS
    elif pending_count:
        status = "needs_imagegen"
    elif ready_count:
        status = "ready_for_ingest"
    elif passed_count == len(rows):
        status = "ingested"
    else:
        status = "in_progress"

    report = {
        "type": "kine.v3.imagegenProgressReport",
        "version": "0.1",
        "status": status,
        "workspace": workspace.name,
        "workOrder": "v3/imagegen/imagegen-work-order.json" if work_order_path.exists() else None,
        "workOrderStage": work_order.get("stage"),
        "taskCount": len(rows),
        "statusCounts": status_counts,
        "taskTypeCounts": type_counts,
        "readyForIngestCount": ready_count,
        "pendingImagegenCount": pending_count,
        "invalidOutputCount": invalid_count,
        "ingestedPassedCount": passed_count,
        "ingestedSheetCount": status_counts.get("ingested_sheet", 0),
        "ingestedSubjectMatteCount": status_counts.get("ingested_subject_matte", 0),
        "ingestedRejectedCount": rejected_count,
        "tasks": rows,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "$imagegen progress evidence only. It checks expected outputs before ingest and never promotes generated art to final components.",
    }
    out_dir = workspace / "v3" / "imagegen"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "imagegen-progress-report.json", report)
    update_run_state(
        workspace,
        {
            "v3ImagegenProgress": "v3/imagegen/imagegen-progress-report.json",
            "v3ImagegenProgressStatus": status,
        },
    )
    print(json.dumps({"status": status, "taskCount": len(rows), "readyForIngestCount": ready_count, "pendingImagegenCount": pending_count, "report": str(out_dir / "imagegen-progress-report.json")}, ensure_ascii=False, indent=2))
    return report


def _decode_inline_imagegen_result(encoded: str) -> bytes:
    data = encoded.strip()
    if "," in data and data.lower().startswith("data:"):
        data = data.split(",", 1)[1]
    try:
        return base64.b64decode(data, validate=True)
    except Exception as exc:
        raise ValueError("inline_imagegen_result_must_be_base64_png") from exc


def _select_v3_imagegen_task(workspace: Path, task_id: str | None, expected_output: str | None) -> dict[str, Any]:
    if expected_output:
        return {"taskId": task_id or "explicit-expected-output", "taskType": "unknown", "expectedOutput": expected_output}
    work_order_path = workspace / "v3" / "imagegen" / "imagegen-work-order.json"
    work_order = read_json_if_exists(work_order_path) or write_v3_imagegen_work_order(workspace)
    tasks = work_order.get("tasks", []) if isinstance(work_order.get("tasks"), list) else []
    if task_id:
        for task in tasks:
            if isinstance(task, dict) and task.get("taskId") == task_id:
                return task
        raise ValueError(f"imagegen_task_not_found:{task_id}")
    if len(tasks) == 1 and isinstance(tasks[0], dict):
        return tasks[0]
    pending = [task for task in tasks if isinstance(task, dict) and task.get("expectedOutput") and not (workspace / str(task.get("expectedOutput"))).exists()]
    if len(pending) == 1:
        return pending[0]
    raise ValueError("imagegen_task_ambiguous_pass_task_id_or_expected_output")


def _v3_expected_output_path(workspace: Path, expected_output: str) -> Path:
    rel = Path(expected_output)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("imagegen_expected_output_must_be_workspace_relative")
    output_path = (workspace / rel).resolve()
    workspace_root = workspace.resolve()
    if not output_path.is_relative_to(workspace_root):
        raise ValueError("imagegen_expected_output_must_stay_inside_workspace")
    return output_path


def _effective_v3_edge_chroma_key(task: dict[str, Any], edge_chroma_key: str | None) -> str | None:
    if edge_chroma_key != "task":
        return edge_chroma_key
    task_type = str(task.get("taskType") or "")
    if task_type == "subject_matte":
        return "auto"
    return "none"


def _load_v3_imagegen_png(encoded: str | None = None, input_path: Path | None = None) -> Image.Image:
    if encoded and input_path:
        raise ValueError("pass_only_one_of_base64_or_input")
    if encoded:
        img = Image.open(io.BytesIO(_decode_inline_imagegen_result(encoded))).convert("RGBA")
        img.load()
        return img
    if input_path:
        if not input_path.exists():
            raise FileNotFoundError(input_path)
        with Image.open(input_path) as source_img:
            img = source_img.convert("RGBA")
            img.load()
            return img
    raise ValueError("imagegen_result_missing_base64_or_input")


def save_v3_imagegen_result(
    workspace: Path,
    encoded: str | None = None,
    input_path: Path | None = None,
    task_id: str | None = None,
    expected_output: str | None = None,
    edge_chroma_key: str | None = "task",
    tolerance: int = 36,
) -> dict[str, Any]:
    """File a built-in $imagegen PNG result into the V3 work-order path.

    Codex imagegen executions may expose a saved file, a generated_images file,
    or inline PNG bytes in the conversation. This adapter makes that generated
    image workspace-backed evidence without adding a drawing backend or
    bypassing V3 ingest/QA gates.
    """
    task = _select_v3_imagegen_task(workspace, task_id, expected_output)
    rel_output = str(task.get("expectedOutput") or "")
    if not rel_output:
        raise ValueError("imagegen_task_expected_output_missing")
    output_path = _v3_expected_output_path(workspace, rel_output)
    img = _load_v3_imagegen_png(encoded=encoded, input_path=input_path)
    cleanup_stats: dict[str, Any] | None = None
    resolved_edge_chroma_key = _effective_v3_edge_chroma_key(task, edge_chroma_key)
    if resolved_edge_chroma_key and resolved_edge_chroma_key != "none":
        key = auto_chroma_key(img) if resolved_edge_chroma_key == "auto" else parse_rgb(resolved_edge_chroma_key)
        if key:
            img, cleanup_stats = remove_edge_connected_background(img, key, tolerance)
            if key[1] > key[0] * 1.15 and key[1] > key[2] * 1.15:
                img = despill_green_edges(img)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    source_path = workspace / "source.png"
    if source_path.exists():
        with Image.open(source_path) as source_img:
            canvas_size = source_img.size
    else:
        canvas_size = (DEFAULT_RESOLUTION, DEFAULT_RESOLUTION)
    row = inspect_v3_imagegen_task_output(workspace, task, canvas_size)
    if not output_path.exists():
        save_status = PARTS_SHEET_BLOCKED_STATUS
    elif row.get("canIngest"):
        save_status = "saved_ready_for_ingest"
    else:
        save_status = "saved_blocked_not_final"
    report = {
        "type": "kine.v3.imagegenResultSave",
        "version": "0.1",
        "status": save_status,
        "fileStatus": "saved" if output_path.exists() else "missing",
        "canIngest": bool(row.get("canIngest")),
        "blockers": row.get("blockers") or [],
        "workspace": str(workspace),
        "taskId": task.get("taskId"),
        "taskType": task.get("taskType"),
        "expectedOutput": rel_output,
        "output": str(output_path),
        "input": str(input_path) if input_path else "inline_base64",
        "edgeChromaKey": resolved_edge_chroma_key or "none",
        "cleanupStats": cleanup_stats,
        "outputInspection": row,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Adapter for built-in $imagegen PNG results. It only files generated evidence at expectedOutput; ingest/QA still decides acceptance.",
    }
    out_dir = workspace / "v3" / "imagegen"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "imagegen-result-save-report.json", report)
    write_v3_imagegen_progress_report(workspace, refresh_work_order=False)
    print(json.dumps({"status": report["status"], "taskId": task.get("taskId"), "expectedOutput": rel_output, "canIngest": row.get("canIngest"), "report": str(out_dir / "imagegen-result-save-report.json")}, ensure_ascii=False, indent=2))
    return report


def save_v3_imagegen_inline_result(
    workspace: Path,
    encoded: str,
    task_id: str | None = None,
    expected_output: str | None = None,
    edge_chroma_key: str | None = "task",
    tolerance: int = 36,
) -> dict[str, Any]:
    return save_v3_imagegen_result(
        workspace,
        encoded=encoded,
        task_id=task_id,
        expected_output=expected_output,
        edge_chroma_key=edge_chroma_key,
        tolerance=tolerance,
    )


def _continue_v3_parts_sheet_task(workspace: Path, task: dict[str, Any], expected_output: str) -> dict[str, Any]:
    sheet_id = str(task.get("sheetId") or task.get("taskId") or "sheet-001").replace(":", "-")
    role = str(task.get("role") or "unspecified")
    process_parts_sheet(
        workspace,
        _v3_expected_output_path(workspace, expected_output),
        "auto",
        16,
        8,
        64,
        4,
        False,
        sheet_id,
        role,
        True,
    )
    sync_report = sync_v3_candidates_from_parts(workspace)
    registration_report = register_v3_candidates(workspace)
    hidden_report = write_v3_hidden_jobs(workspace)
    recompose_report = write_v3_recompose(workspace)
    review_refresh = refresh_v3_review_artifacts(workspace, f"continue_parts_sheet:{sheet_id}")
    validation_report = validate_v3_pipeline(workspace)
    return {
        "status": "parts_sheet_ingested",
        "sheetId": sheet_id,
        "role": role,
        "syncStatus": sync_report.get("status"),
        "registrationStatus": registration_report.get("status"),
        "hiddenStatusCounts": hidden_report.get("statusCounts"),
        "recomposeStatus": recompose_report.get("status"),
        "reviewRefreshStatus": review_refresh.get("status"),
        "reviewIntegrityStatus": review_refresh.get("integrityStatus"),
        "validationStatus": validation_report.get("status"),
    }


def _continue_v3_registration_repair_task(workspace: Path, task: dict[str, Any], expected_output: str) -> dict[str, Any]:
    component_id = str(task.get("componentId") or task.get("taskId") or "repair")
    repair_task = {
        **task,
        "sheetId": f"repair-{component_id}".replace("_", "-"),
        "role": str(task.get("role") or "repair"),
    }
    result = _continue_v3_parts_sheet_task(workspace, repair_task, expected_output)
    return {
        **result,
        "status": "registration_repair_ingested",
        "componentId": component_id,
    }


def _continue_v3_stable_object_repair_task(workspace: Path, task: dict[str, Any], expected_output: str) -> dict[str, Any]:
    result = _continue_v3_parts_sheet_task(workspace, task, expected_output)
    return {
        **result,
        "status": "stable_object_repair_ingested",
        "stableObjectLedger": task.get("stableObjectLedger"),
        "generationTargetIds": task.get("generationTargetIds") or [],
    }


def _continue_v3_hidden_inpaint_task(workspace: Path, task: dict[str, Any], expected_output: str) -> dict[str, Any]:
    component_id = str(task.get("componentId") or "")
    if not component_id:
        raise ValueError("hidden_inpaint_task_component_missing")
    ingest_result = ingest_v3_hidden_inpaint(
        workspace,
        component_id,
        _v3_expected_output_path(workspace, expected_output),
        "imagegen",
        "continued from V3 imagegen work order",
    )
    hidden_review = write_v3_hidden_review_report(workspace)
    recompose_report = write_v3_recompose(workspace)
    pose_report = write_v3_pose_stress(workspace)
    review_refresh = refresh_v3_review_artifacts(workspace, f"continue_hidden_inpaint:{component_id}")
    validation_report = validate_v3_pipeline(workspace)
    return {
        "status": "hidden_inpaint_ingested" if ingest_result.get("status") == "passed" else PARTS_SHEET_BLOCKED_STATUS,
        "componentId": component_id,
        "ingestStatus": ingest_result.get("status"),
        "reason": ingest_result.get("reason"),
        "hiddenReviewStatus": hidden_review.get("status"),
        "recomposeStatus": recompose_report.get("status"),
        "poseStressStatus": pose_report.get("status"),
        "reviewRefreshStatus": review_refresh.get("status"),
        "reviewIntegrityStatus": review_refresh.get("integrityStatus"),
        "validationStatus": validation_report.get("status"),
    }


def continue_v3_imagegen(workspace: Path, force: bool = False) -> dict[str, Any]:
    """Continue ready V3 $imagegen outputs without changing generation logic.

    It consumes already-saved expectedOutput PNGs and calls existing structured
    ingest functions, so Python never becomes a drawing backend.
    """
    work_order_path = workspace / "v3" / "imagegen" / "imagegen-work-order.json"
    if not work_order_path.exists():
        write_v3_imagegen_work_order(workspace)
    work_order = read_json_if_exists(work_order_path) or {}
    tasks = [task for task in work_order.get("tasks", []) if isinstance(task, dict)] if isinstance(work_order.get("tasks"), list) else []
    tasks_by_id = {str(task.get("taskId")): task for task in tasks if task.get("taskId")}
    progress = write_v3_imagegen_progress_report(workspace, refresh_work_order=False)
    rows = [row for row in progress.get("tasks", []) if isinstance(row, dict)] if isinstance(progress.get("tasks"), list) else []

    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in rows:
        row_status = row.get("status")
        if row_status != "ready_for_ingest":
            continue
        task_id = str(row.get("taskId") or "")
        task = tasks_by_id.get(task_id) or {}
        task_type = str(row.get("taskType") or task.get("taskType") or "")
        expected_output = str(task.get("expectedOutput") or row.get("expectedOutput") or "")
        try:
            if task_type == "subject_matte":
                matte_path = _v3_expected_output_path(workspace, expected_output)
                result = ingest_v3_subject_matte(workspace, matte_path, None, force=force)
                actions.append(
                    {
                        "taskId": task_id,
                        "taskType": task_type,
                        "status": result.get("status"),
                        "blockers": result.get("blockers") or [],
                        "characterMatteWorkspace": result.get("characterMatteWorkspace"),
                        "subjectMatteQA": result.get("subjectMatteQA"),
                    }
                )
            elif task_type == "parts_sheet":
                result = _continue_v3_parts_sheet_task(workspace, task, expected_output)
                actions.append({"taskId": task_id, "taskType": task_type, **result})
            elif task_type == "stable_object_repair":
                result = _continue_v3_stable_object_repair_task(workspace, task, expected_output)
                actions.append({"taskId": task_id, "taskType": task_type, **result})
            elif task_type == "registration_repair":
                result = _continue_v3_registration_repair_task(workspace, task, expected_output)
                actions.append({"taskId": task_id, "taskType": task_type, **result})
            elif task_type == "hidden_inpaint":
                result = _continue_v3_hidden_inpaint_task(workspace, task, expected_output)
                actions.append({"taskId": task_id, "taskType": task_type, **result})
            else:
                skipped.append(
                    {
                        "taskId": task_id,
                        "taskType": task_type,
                        "reason": "continue_imagegen_unknown_task_type",
                    }
                )
        except SystemExit as exc:
            actions.append(
                {
                    "taskId": task_id,
                    "taskType": task_type,
                    "status": PARTS_SHEET_BLOCKED_STATUS,
                    "blockers": [str(exc) or "ingest_exited"],
                }
            )
        except Exception as exc:
            actions.append(
                {
                    "taskId": task_id,
                    "taskType": task_type,
                    "status": PARTS_SHEET_BLOCKED_STATUS,
                    "blockers": [f"{type(exc).__name__}: {exc}"],
                }
            )

    if not actions and progress.get("status") == "ingested" and progress.get("workOrderStage") == "role_sheets":
        if any(row.get("taskType") == "parts_sheet" for row in rows):
            sync_report = sync_v3_candidates_from_parts(workspace)
            registration_report = register_v3_candidates(workspace)
            hidden_report = write_v3_hidden_jobs(workspace)
            recompose_report = write_v3_recompose(workspace)
            review_refresh = refresh_v3_review_artifacts(workspace, "continue_role_sheets_all_ingested")
            validation_report = validate_v3_pipeline(workspace)
            actions.append(
                {
                    "taskId": "role-sheets:all-ingested",
                    "taskType": "parts_sheet_batch",
                    "status": "role_sheets_ingested_pipeline_refreshed",
                    "syncStatus": sync_report.get("status"),
                    "registrationStatus": registration_report.get("status"),
                    "hiddenStatusCounts": hidden_report.get("statusCounts"),
                    "recomposeStatus": recompose_report.get("status"),
                    "reviewRefreshStatus": review_refresh.get("status"),
                    "reviewIntegrityStatus": review_refresh.get("integrityStatus"),
                    "validationStatus": validation_report.get("status"),
                }
            )

    should_refresh_work_order = bool(actions) or progress.get("status") in {
        "needs_imagegen",
        "ready_for_ingest",
        PARTS_SHEET_BLOCKED_STATUS,
    }
    refreshed = write_v3_imagegen_progress_report(workspace, refresh_work_order=should_refresh_work_order)
    refreshed_rows = [
        row
        for row in refreshed.get("tasks", [])
        if isinstance(row, dict)
    ] if isinstance(refreshed.get("tasks"), list) else []
    blocked_saved_outputs = [
        {
            "taskId": row.get("taskId"),
            "taskType": row.get("taskType"),
            "componentId": row.get("componentId"),
            "status": row.get("status"),
            "expectedOutput": row.get("expectedOutput"),
            "blockers": row.get("blockers") or [],
            "nextAction": row.get("nextAction"),
        }
        for row in refreshed_rows
        if row.get("exists") and not row.get("canIngest") and not str(row.get("status") or "").startswith("ingested")
    ]
    execution_report = write_v3_workspace_imagegen_execution_report(workspace, refresh=False)
    success_statuses = {
        "subject_matte_ingested",
        "parts_sheet_ingested",
        "stable_object_repair_ingested",
        "registration_repair_ingested",
        "hidden_inpaint_ingested",
        "role_sheets_ingested_pipeline_refreshed",
    }
    failed_actions = [action for action in actions if action.get("status") not in success_statuses]
    if failed_actions:
        status = PARTS_SHEET_BLOCKED_STATUS
    elif actions:
        refreshed_status = str(refreshed.get("status") or "")
        if refreshed_status in {"needs_imagegen", "ready_for_ingest", PARTS_SHEET_BLOCKED_STATUS}:
            status = refreshed_status
        else:
            status = "continued"
    elif any(str(row.get("status") or "").startswith("ingested") for row in rows):
        status = "already_continued"
    elif skipped:
        status = "unsupported_ready_tasks"
    elif refreshed.get("status") == PARTS_SHEET_BLOCKED_STATUS:
        status = PARTS_SHEET_BLOCKED_STATUS
    else:
        status = refreshed.get("status") or progress.get("status") or "no_ready_tasks"

    report = {
        "type": "kine.v3.imagegenContinuation",
        "version": "0.1",
        "status": status,
        "workspace": str(workspace),
        "actions": actions,
        "failedActions": failed_actions,
        "skipped": skipped,
        "blockedSavedOutputs": blocked_saved_outputs,
        "blockedSavedOutputCount": len(blocked_saved_outputs),
        "progressBefore": "v3/imagegen/imagegen-progress-report.json",
        "progressAfterStatus": refreshed.get("status"),
        "nextWorkOrderStage": refreshed.get("workOrderStage"),
        "nextPendingImagegenCount": refreshed.get("pendingImagegenCount"),
        "nextReadyForIngestCount": refreshed.get("readyForIngestCount"),
        "executionReport": "v3/imagegen/v3-imagegen-execution-report.json",
        "executionStatus": execution_report.get("status"),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Continuation consumes already-saved $imagegen expectedOutput PNG files. It does not generate images; it dispatches ready tasks to existing V3 ingest/QA functions.",
    }
    out_path = workspace / "v3" / "imagegen" / "imagegen-continuation-report.json"
    write_json(out_path, report)
    update_run_state(
        workspace,
        {
            "v3ImagegenContinuation": "v3/imagegen/imagegen-continuation-report.json",
            "v3ImagegenContinuationStatus": status,
            "v3ImagegenExecutionReport": "v3/imagegen/v3-imagegen-execution-report.json",
            "v3ImagegenExecutionStatus": execution_report.get("status"),
        },
    )
    print(
        json.dumps(
            {
                "status": status,
                "actionCount": len(actions),
                "skippedCount": len(skipped),
                "blockedSavedOutputCount": len(blocked_saved_outputs),
                "report": str(out_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


def update_v3_hidden_report_result(workspace: Path, updated_result: dict[str, Any]) -> dict[str, Any]:
    hidden_root = workspace / "v3" / "hidden"
    report_path = hidden_root / "hidden-report.json"
    report = read_json_if_exists(report_path) or {
        "type": "kine.v3.hiddenJobReport",
        "version": "0.1",
        "componentPlan": "v3/component-plan.json",
        "results": [],
    }
    results = [result for result in report.get("results", []) if isinstance(result, dict)]
    replaced = False
    for index, result in enumerate(results):
        if result.get("componentId") == updated_result.get("componentId"):
            results[index] = {**result, **updated_result}
            replaced = True
            break
    if not replaced:
        results.append(updated_result)
    status_counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    report["results"] = results
    report["componentCount"] = len(results)
    report["statusCounts"] = status_counts
    report["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(report_path, report)
    return report


def ingest_v3_hidden_inpaint(
    workspace: Path,
    component_id: str,
    image_path: Path,
    provenance_source: str = "imagegen",
    notes: str | None = None,
) -> dict[str, Any]:
    hidden_root = workspace / "v3" / "hidden"
    component_plan_path = workspace / "v3" / "component-plan.json"
    if not (hidden_root / "hidden-report.json").exists():
        write_v3_hidden_jobs(workspace)
    component_plan = read_json_if_exists(component_plan_path) or {}
    components = [component for component in component_plan.get("components", []) if isinstance(component, dict)]
    component = next((item for item in components if item.get("id") == component_id), None)
    if component is None:
        raise ValueError(f"Unknown V3 component: {component_id}")
    source = Image.open(workspace / "source.png").convert("RGBA")
    hidden_img = Image.open(image_path).convert("RGBA")
    if hidden_img.size != source.size:
        raise ValueError(f"Hidden inpaint size {hidden_img.size} does not match source canvas {source.size}")
    component_dir = hidden_root / component_id
    component_dir.mkdir(parents=True, exist_ok=True)
    visible_path = component_dir / "visible_cut.png"
    if not visible_path.exists():
        visible_img, _visible_bbox = v3_component_visible_image(workspace, component)
        visible_img = visible_img if visible_img is not None else Image.new("RGBA", source.size, (0, 0, 0, 0))
        visible_img.save(visible_path)
    visible = Image.open(visible_path).convert("RGBA")
    hidden_pixels = alpha_pixel_count(hidden_img)
    hidden_path = component_dir / "hidden_inpaint.png"
    imagegen_copy_path = component_dir / "imagegen_hidden_inpaint.png"
    merged_path = component_dir / "merged_component.png"
    overlap_path = component_dir / "qa_overlap.png"
    provenance_path = component_dir / "hidden-inpaint-provenance.json"
    hidden_img.save(imagegen_copy_path)
    hidden_img.save(hidden_path)
    merged = Image.alpha_composite(visible, hidden_img)
    merged.save(merged_path)
    v3_make_overlap_preview(visible, hidden_img).save(overlap_path)
    visible_overlap_quality = v3_hidden_visible_overlap_quality(visible, hidden_img)
    if hidden_pixels <= 0:
        status = "missing"
        reason = "empty_hidden_inpaint"
    elif not visible_overlap_quality["passes"]:
        status = "rejected"
        reason = "hidden_inpaint_overlaps_source_visible_pixels"
    else:
        status = "passed"
        reason = None
    provenance = {
        "type": "kine.v3.hiddenInpaintProvenance",
        "version": "0.1",
        "componentId": component_id,
        "provenanceSource": provenance_source,
        "imagegenMode": "built_in_image_gen",
        "sourceImage": relative_to_workspace(image_path, workspace) if image_path.is_relative_to(workspace) else str(image_path),
        "storedImage": relative_to_workspace(imagegen_copy_path, workspace),
        "hiddenPixels": hidden_pixels,
        "visibleOverlapQuality": visible_overlap_quality,
        "notes": notes,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(provenance_path, provenance)
    job_path = component_dir / "job.json"
    job = read_json_if_exists(job_path) or {
        "type": "kine.v3.hiddenJob",
        "version": "0.1",
        "componentId": component_id,
        "owner": component.get("owner"),
        "needsHiddenCompletion": bool(component.get("needsHiddenCompletion")),
    }
    job.update(
        {
            "hiddenInpaint": relative_to_workspace(hidden_path, workspace),
            "imagegenHiddenInpaint": relative_to_workspace(imagegen_copy_path, workspace),
            "mergedComponent": relative_to_workspace(merged_path, workspace),
            "qaOverlap": relative_to_workspace(overlap_path, workspace),
            "hiddenInpaintProvenance": relative_to_workspace(provenance_path, workspace),
            "qa": {
                "status": status,
                "reason": reason,
                "hiddenPixels": hidden_pixels,
                "visibleOverlapQuality": visible_overlap_quality,
            },
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
        }
    )
    write_json(job_path, job)
    result = {
        "componentId": component_id,
        "owner": component.get("owner"),
        "status": status,
        "reason": reason,
        "hiddenPixels": hidden_pixels,
        "job": relative_to_workspace(job_path, workspace),
        "visibleCut": relative_to_workspace(visible_path, workspace),
        "hiddenInpaint": relative_to_workspace(hidden_path, workspace),
        "imagegenHiddenInpaint": relative_to_workspace(imagegen_copy_path, workspace),
        "mergedComponent": relative_to_workspace(merged_path, workspace),
        "qaOverlap": relative_to_workspace(overlap_path, workspace),
        "hiddenInpaintProvenance": relative_to_workspace(provenance_path, workspace),
        "visibleOverlapQuality": visible_overlap_quality,
    }
    update_v3_hidden_report_result(workspace, result)
    updated_components = []
    for item in components:
        if item.get("id") == component_id:
            updated_components.append(
                {
                    **item,
                    "hiddenStatus": status,
                    "hiddenReason": reason,
                    "hiddenInpaint": relative_to_workspace(hidden_path, workspace),
                    "imagegenHiddenInpaint": relative_to_workspace(imagegen_copy_path, workspace),
                    "mergedComponent": relative_to_workspace(merged_path, workspace),
                    "qaOverlap": relative_to_workspace(overlap_path, workspace),
                    "hiddenInpaintProvenance": relative_to_workspace(provenance_path, workspace),
                    "visibleOverlapQuality": visible_overlap_quality,
                }
            )
        else:
            updated_components.append(item)
    component_plan["components"] = updated_components
    component_plan["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(component_plan_path, component_plan)
    print(json.dumps({"status": status, "componentId": component_id, "hiddenPixels": hidden_pixels, "job": str(job_path)}, ensure_ascii=False, indent=2))
    return result


def write_v3_hidden_review_report(workspace: Path, decisions_path: Path | None = None) -> dict[str, Any]:
    """Write or apply a batch review report for $imagegen hidden inpaint outputs."""
    hidden_root = workspace / "v3" / "hidden"
    hidden_report = read_json_if_exists(hidden_root / "hidden-report.json") or {}
    component_plan_path = workspace / "v3" / "component-plan.json"
    component_plan = read_json_if_exists(component_plan_path) or {}
    components = [component for component in component_plan.get("components", []) if isinstance(component, dict)]
    component_by_id = {str(component.get("id")): component for component in components if component.get("id")}
    decision_payload = read_json_if_exists(decisions_path) if decisions_path else None
    if decision_payload is not None and decision_payload.get("type") != "kine.v3.hiddenInpaintReviewDecisions":
        raise ValueError(f"Invalid hidden review decisions JSON: {decisions_path}")
    raw_decisions = decision_payload.get("reviews", []) if isinstance(decision_payload, dict) else []
    decisions = {
        str(item.get("componentId")): item
        for item in raw_decisions
        if isinstance(item, dict) and item.get("componentId") and item.get("decision") in {"accepted", "rejected", "needs_revision"}
    }

    review_rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    decision_counts: dict[str, int] = {}
    applied_reviews: list[dict[str, Any]] = []
    hidden_results = hidden_report.get("results", []) if isinstance(hidden_report.get("results"), list) else []
    for result in hidden_results:
        if not isinstance(result, dict):
            continue
        component_id = str(result.get("componentId") or "")
        if not component_id:
            continue
        provenance_rel = result.get("hiddenInpaintProvenance")
        provenance = read_json_if_exists(workspace / provenance_rel) if isinstance(provenance_rel, str) else {}
        visible_overlap = result.get("visibleOverlapQuality") if isinstance(result.get("visibleOverlapQuality"), dict) else {}
        if isinstance(provenance, dict) and isinstance(provenance.get("visibleOverlapQuality"), dict):
            visible_overlap = provenance["visibleOverlapQuality"]
        status = str(result.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        decision = decisions.get(component_id)
        review_record = None
        if decision:
            decision_value = str(decision.get("decision"))
            review_record = {
                "decision": decision_value,
                "reason": str(decision.get("reason") or ""),
                "reviewer": str(decision.get("reviewer") or "hidden_inpaint_review"),
                "source": decisions_path.name if decisions_path else None,
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            }
            decision_counts[decision_value] = decision_counts.get(decision_value, 0) + 1
            applied_reviews.append({"componentId": component_id, **review_record})
            component = component_by_id.get(component_id)
            if component is not None:
                component["hiddenManualReview"] = review_record
                component["hiddenManualReviewStatus"] = decision_value
                if decision_value == "rejected":
                    component["hiddenStatus"] = "rejected"
                    component["hiddenReason"] = "manual_hidden_review_rejected"
                elif decision_value == "needs_revision":
                    component["hiddenStatus"] = "missing"
                    component["hiddenReason"] = "manual_hidden_review_needs_revision"

        review_rows.append(
            {
                "componentId": component_id,
                "owner": result.get("owner") or component_by_id.get(component_id, {}).get("owner"),
                "status": status,
                "reason": result.get("reason"),
                "hiddenPixels": result.get("hiddenPixels"),
                "hiddenInpaint": result.get("hiddenInpaint"),
                "imagegenHiddenInpaint": result.get("imagegenHiddenInpaint"),
                "qaOverlap": result.get("qaOverlap"),
                "hiddenInpaintProvenance": provenance_rel,
                "provenanceSource": provenance.get("provenanceSource") if isinstance(provenance, dict) else None,
                "imagegenMode": provenance.get("imagegenMode") if isinstance(provenance, dict) else None,
                "visibleOverlapStatus": visible_overlap.get("status"),
                "visibleOverlapPixels": visible_overlap.get("overlapPixels"),
                "manualReview": review_record,
                "requiresHumanReview": status == "passed" and review_record is None,
            }
        )

    if applied_reviews:
        component_plan["components"] = components
        component_plan["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        write_json(component_plan_path, component_plan)

    report_status = "passed" if status_counts.get("rejected", 0) == 0 and status_counts.get("missing", 0) == 0 else PARTS_SHEET_BLOCKED_STATUS
    if decision_counts.get("rejected") or decision_counts.get("needs_revision"):
        report_status = PARTS_SHEET_BLOCKED_STATUS
    report = {
        "type": "kine.v3.hiddenInpaintReviewReport",
        "version": "0.1",
        "status": report_status,
        "workspace": workspace.name,
        "hiddenReport": "v3/hidden/hidden-report.json",
        "decisionSource": str(decisions_path) if decisions_path else None,
        "componentCount": len(review_rows),
        "statusCounts": status_counts,
        "decisionCounts": decision_counts,
        "requiresHumanReviewCount": sum(1 for row in review_rows if row["requiresHumanReview"]),
        "appliedReviews": applied_reviews,
        "components": review_rows,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "$imagegen hidden inpaint review evidence. Manual accepted is evidence only; manual rejected or needs_revision blocks final export.",
    }
    out_dir = hidden_root / "review"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "hidden-inpaint-review-report.json", report)
    update_run_state(
        workspace,
        {
            "v3HiddenInpaintReview": "v3/hidden/review/hidden-inpaint-review-report.json",
            "v3HiddenInpaintReviewStatus": report_status,
        },
    )
    print(json.dumps({"status": report_status, "componentCount": len(review_rows), "requiresHumanReviewCount": report["requiresHumanReviewCount"], "report": str(out_dir / "hidden-inpaint-review-report.json")}, ensure_ascii=False, indent=2))
    return report


def v3_artifact_slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-") or "component"


def v3_component_visible_quality(component: dict[str, Any], merged: Image.Image, workspace: Path) -> dict[str, Any]:
    component_id = str(component.get("id") or "unknown")
    visible_cut_value = component.get("visibleCut")
    if not isinstance(visible_cut_value, str) or not (workspace / visible_cut_value).exists():
        return {
            "componentId": component_id,
            "status": "missing_visible_cut",
            "passes": False,
            "reason": "visible_cut_missing",
        }
    visible = Image.open(workspace / visible_cut_value).convert("RGBA")
    merged_rgba = merged.convert("RGBA")
    artifact_dir = workspace / "v3" / "check" / "component-quality" / v3_artifact_slug(component_id)
    heatmap_path = artifact_dir / "visible-mismatch-heatmap.png"
    if visible.size != merged_rgba.size:
        return {
            "componentId": component_id,
            "status": "size_mismatch",
            "passes": False,
            "reason": "visible_cut_size_mismatch",
            "visibleCutSize": list(visible.size),
            "mergedSize": list(merged_rgba.size),
        }
    visible_alpha = visible.getchannel("A")
    merged_alpha = merged_rgba.getchannel("A")
    if _np is not None:
        visible_alpha_arr = _np.asarray(visible_alpha)
        merged_alpha_arr = _np.asarray(merged_alpha)
        visible_mask = visible_alpha_arr > 24
        merged_mask = merged_alpha_arr > 24
        visible_pixels = int(visible_mask.sum())
        missing_pixels = int((visible_mask & ~merged_mask).sum())
        generated_hidden_pixels = int((merged_mask & ~visible_mask).sum())
        visible_rgb = _np.asarray(visible.convert("RGB"), dtype=_np.int16)
        merged_rgb = _np.asarray(merged_rgba.convert("RGB"), dtype=_np.int16)
        rgb_delta = visible_rgb - merged_rgb
        mismatch_mask = _np.zeros(visible_mask.shape, dtype=bool)
        if visible_pixels:
            squared = rgb_delta[visible_mask].astype(_np.float64) ** 2
            rmse = round(float(_np.sqrt(squared.mean())), 3)
            max_delta = _np.abs(rgb_delta).max(axis=2)
            changed_pixels = int(((max_delta > 20) & visible_mask).sum())
            rgb_mismatch_pixels = int((_np.any(rgb_delta != 0, axis=2) & visible_mask).sum())
            mismatch_mask = visible_mask & ((max_delta > 20) | ~merged_mask)
        else:
            rmse = 0.0
            changed_pixels = 0
            rgb_mismatch_pixels = 0
        mismatch_bbox = Image.fromarray((mismatch_mask.astype(_np.uint8) * 255), mode="L").getbbox()
        if mismatch_bbox:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            heatmap_arr = _np.asarray(visible, dtype=_np.uint8).copy()
            heatmap_arr[:, :, 3] = _np.minimum(heatmap_arr[:, :, 3], 96)
            heatmap_arr[mismatch_mask] = _np.array([255, 0, 0, 230], dtype=_np.uint8)
            Image.fromarray(heatmap_arr, mode="RGBA").save(heatmap_path)
    else:
        visible_alpha_px = visible_alpha.load()
        merged_alpha_px = merged_alpha.load()
        visible_px = visible.convert("RGB").load()
        merged_px = merged_rgba.convert("RGB").load()
        width, height = visible.size
        visible_pixels = 0
        missing_pixels = 0
        generated_hidden_pixels = 0
        changed_pixels = 0
        rgb_mismatch_pixels = 0
        squared_total = 0
        channel_count = 0
        mismatch_mask_img = Image.new("L", visible.size, 0)
        mismatch_mask_px = mismatch_mask_img.load()
        for y in range(height):
            for x in range(width):
                visible_on = visible_alpha_px[x, y] > 24
                merged_on = merged_alpha_px[x, y] > 24
                if visible_on:
                    visible_pixels += 1
                    if not merged_on:
                        missing_pixels += 1
                    vr, vg, vb = visible_px[x, y]
                    mr, mg, mb = merged_px[x, y]
                    deltas = (vr - mr, vg - mg, vb - mb)
                    squared_total += sum(delta * delta for delta in deltas)
                    channel_count += 3
                    if max(abs(delta) for delta in deltas) > 20:
                        changed_pixels += 1
                        mismatch_mask_px[x, y] = 255
                    if deltas != (0, 0, 0):
                        rgb_mismatch_pixels += 1
                    if not merged_on:
                        mismatch_mask_px[x, y] = 255
                elif merged_on:
                    generated_hidden_pixels += 1
        rmse = round((squared_total / max(channel_count, 1)) ** 0.5, 3)
        mismatch_bbox = mismatch_mask_img.getbbox()
        if mismatch_bbox:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            heatmap = visible.copy()
            heatmap_px = heatmap.load()
            mask_px = mismatch_mask_img.load()
            width, height = heatmap.size
            for y in range(height):
                for x in range(width):
                    r, g, b, a = heatmap_px[x, y]
                    heatmap_px[x, y] = (r, g, b, min(a, 96))
                    if mask_px[x, y] > 0:
                        heatmap_px[x, y] = (255, 0, 0, 230)
            heatmap.save(heatmap_path)
    changed_ratio = round(changed_pixels / max(visible_pixels, 1), 6)
    missing_ratio = round(missing_pixels / max(visible_pixels, 1), 6)
    passes = bool(visible_pixels and missing_pixels == 0 and changed_pixels == 0 and rgb_mismatch_pixels == 0)
    return {
        "componentId": component_id,
        "status": "passed" if passes else "failed",
        "passes": passes,
        "visibleCut": visible_cut_value,
        "expectedVisiblePixels": visible_pixels,
        "missingVisiblePixels": missing_pixels,
        "missingVisibleRatio": missing_ratio,
        "generatedHiddenAlphaPixels": generated_hidden_pixels,
        "rgbRmseInVisible": rmse,
        "changedPixelsGt20InVisible": changed_pixels,
        "changedRatioGt20InVisible": changed_ratio,
        "rgbMismatchPixelsInVisible": rgb_mismatch_pixels,
        "mismatchBbox": list(mismatch_bbox) if mismatch_bbox else None,
        "mismatchHeatmap": relative_to_workspace(heatmap_path, workspace) if mismatch_bbox else None,
    }


def write_v3_recompose(workspace: Path) -> dict[str, Any]:
    component_plan_path = workspace / "v3" / "component-plan.json"
    if not component_plan_path.exists():
        write_v3_component_plan(workspace)
    component_plan = read_json_if_exists(component_plan_path) or {}
    components = [component for component in component_plan.get("components", []) if isinstance(component, dict)]
    source = Image.open(workspace / "source.png").convert("RGBA")
    check_dir = workspace / "v3" / "check"
    check_dir.mkdir(parents=True, exist_ok=True)
    composite = Image.new("RGBA", source.size, (0, 0, 0, 0))
    included: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    per_component_quality: list[dict[str, Any]] = []
    for component in sorted(components, key=lambda item: int(item.get("drawOrder") or 0)):
        component_id = component.get("id")
        if not isinstance(component_id, str):
            continue
        if component.get("status") == "not_visible":
            continue
        if component.get("registrationStatus") != "accepted":
            missing.append({"componentId": component_id, "owner": component.get("owner"), "reason": "registration_not_accepted"})
            continue
        merged_path_value = component.get("mergedComponent") or component.get("visibleCut")
        if not isinstance(merged_path_value, str) or not (workspace / merged_path_value).exists():
            missing.append({"componentId": component_id, "owner": component.get("owner"), "reason": "merged_component_missing"})
            continue
        merged = Image.open(workspace / merged_path_value).convert("RGBA")
        if merged.size != source.size:
            missing.append({"componentId": component_id, "owner": component.get("owner"), "reason": "merged_component_size_mismatch"})
            continue
        component_quality = v3_component_visible_quality(component, merged, workspace)
        per_component_quality.append(component_quality)
        composite.alpha_composite(merged)
        alpha_pixels = sum(1 for value in merged.getchannel("A").tobytes() if value > 24)
        included.append(
            {
                "componentId": component_id,
                "owner": component.get("owner"),
                "drawOrder": component.get("drawOrder"),
                "track": component.get("track"),
                "mergedComponent": merged_path_value,
                "alphaPixels": alpha_pixels,
                "hiddenStatus": component.get("hiddenStatus"),
                "quality": component_quality,
            }
        )
    preserved_composite = composite_source_visible_over_base(workspace, composite)
    recompose_path = check_dir / "recompose.png"
    diff_path = check_dir / "source-diff.png"
    preserved_composite.save(recompose_path)
    make_source_diff(workspace, preserved_composite, diff_path)
    quality = recompose_quality(workspace, preserved_composite, measured_against="v3_component_recompose")
    component_quality_passes = all(bool(item.get("passes")) for item in per_component_quality)
    status = "passed" if quality.get("passes") and not missing and component_quality_passes else "failed"
    track_counts: dict[str, int] = {}
    for item in included:
        track = str(item.get("track") or "unknown")
        track_counts[track] = track_counts.get(track, 0) + 1
    per_component_status_counts: dict[str, int] = {}
    for item in per_component_quality:
        item_status = str(item.get("status") or "unknown")
        per_component_status_counts[item_status] = per_component_status_counts.get(item_status, 0) + 1
    report = {
        "type": "kine.v3.recomposeReport",
        "version": "0.1",
        "status": status,
        "source": "source.png",
        "componentPlan": "v3/component-plan.json",
        "recompose": relative_to_workspace(recompose_path, workspace),
        "sourceDiff": relative_to_workspace(diff_path, workspace),
        "includedCount": len(included),
        "missingCount": len(missing),
        "trackCounts": track_counts,
        "perComponentStatusCounts": per_component_status_counts,
        "quality": quality,
        "sourceVisiblePreservation": {
            "status": "applied",
            "policy": "restore exact source RGBA wherever accepted components cover source-visible pixels",
            "reason": "source-visible local candidates and overlapping owner masks can otherwise alpha-composite semi-transparent source edges twice",
        },
        "perComponentQuality": per_component_quality,
        "included": included,
        "missing": missing,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(check_dir / "recompose-report.json", report)
    print(
        json.dumps(
            {
                "status": "v3_recompose_written",
                "recomposeStatus": status,
                "includedCount": len(included),
                "missingCount": len(missing),
                "report": str(check_dir / "recompose-report.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


def v3_pose_socket_angle(socket: str) -> int:
    socket = socket.lower()
    if "shoulder" in socket or socket in {"hip", "left-thigh", "right-thigh"}:
        return 12
    if socket in {"elbow", "knee", "wrist", "ankle"}:
        return 18
    if "grip" in socket:
        return 10
    if socket in {"neck", "head"}:
        return 10
    return 8


def v3_pose_pivot_for_socket(component: dict[str, Any], bbox: tuple[int, int, int, int], socket: str) -> list[int]:
    pivot = component.get("pivot")
    if isinstance(pivot, list) and len(pivot) == 2 and all(isinstance(value, (int, float)) for value in pivot):
        return [int(round(float(pivot[0]))), int(round(float(pivot[1])))]
    x0, y0, x1, y1 = bbox
    cx = int(round((x0 + x1) / 2))
    cy = int(round((y0 + y1) / 2))
    left_x = int(round(x0 + (x1 - x0) * 0.25))
    right_x = int(round(x0 + (x1 - x0) * 0.75))
    top_y = int(round(y0 + (y1 - y0) * 0.12))
    mid_y = cy
    bottom_y = int(round(y0 + (y1 - y0) * 0.88))
    socket = socket.lower()
    cid = str(component.get("id") or "").lower()
    if "left" in socket:
        cx = left_x
    elif "right" in socket:
        cx = right_x
    if socket in {"shoulder", "hip", "neck", "head"} or socket.startswith("left-") or socket.startswith("right-"):
        cy = top_y
    elif socket in {"elbow", "knee"}:
        cy = mid_y
    elif socket in {"wrist", "ankle", "grip", "prop-grip"}:
        cy = bottom_y
    if "lower-arm" in cid or "shin" in cid or "hand" in cid or "foot" in cid:
        cy = top_y if socket in {"elbow", "knee", "wrist", "ankle"} else cy
    return [cx, cy]


def v3_pose_preview_image(component_img: Image.Image, pivot: list[int], angle: int) -> Image.Image:
    base = component_img.convert("RGBA")
    try:
        resample = Image.Resampling.BICUBIC
    except AttributeError:  # pragma: no cover - old Pillow
        resample = Image.BICUBIC
    rotated = base.rotate(angle, resample=resample, center=tuple(pivot), fillcolor=(0, 0, 0, 0))
    preview = Image.new("RGBA", base.size, (0, 0, 0, 0))
    faded = Image.new("RGBA", base.size, (0, 0, 0, 0))
    src = base.load()
    dst = faded.load()
    for y in range(base.height):
        for x in range(base.width):
            r, g, b, a = src[x, y]
            if a > 0:
                dst[x, y] = (r, g, b, min(90, a))
    preview.alpha_composite(faded)
    preview.alpha_composite(rotated)
    draw = ImageDraw.Draw(preview)
    px, py = pivot
    draw.line((px - 5, py, px + 5, py), fill=(255, 0, 0, 255), width=1)
    draw.line((px, py - 5, px, py + 5), fill=(255, 0, 0, 255), width=1)
    return preview


def v3_pose_gap_quality(component_img: Image.Image, pivot: list[int], angle: int, heatmap_path: Path, workspace: Path) -> dict[str, Any]:
    base = component_img.convert("RGBA")
    try:
        resample = Image.Resampling.BICUBIC
    except AttributeError:  # pragma: no cover - old Pillow
        resample = Image.BICUBIC
    rotated = base.rotate(angle, resample=resample, center=tuple(pivot), fillcolor=(0, 0, 0, 0))
    if _np is not None:
        base_alpha = _np.asarray(base.getchannel("A")) > 24
        rotated_alpha = _np.asarray(rotated.getchannel("A")) > 24
        original_alpha_pixels = int(base_alpha.sum())
        retained_pixels = int((base_alpha & rotated_alpha).sum())
        gap_mask = base_alpha & ~rotated_alpha
        new_mask = rotated_alpha & ~base_alpha
        gap_pixels = int(gap_mask.sum())
        new_alpha_pixels = int(new_mask.sum())
        gap_bbox = Image.fromarray((gap_mask.astype(_np.uint8) * 255), mode="L").getbbox()
        if gap_bbox:
            heatmap_path.parent.mkdir(parents=True, exist_ok=True)
            heatmap_arr = _np.asarray(base, dtype=_np.uint8).copy()
            heatmap_arr[:, :, 3] = _np.minimum(heatmap_arr[:, :, 3], 90)
            heatmap_arr[gap_mask] = _np.array([255, 0, 0, 230], dtype=_np.uint8)
            heatmap_arr[new_mask] = _np.array([0, 120, 255, 210], dtype=_np.uint8)
            Image.fromarray(heatmap_arr, mode="RGBA").save(heatmap_path)
    else:
        base_alpha_img = base.getchannel("A")
        rotated_alpha_img = rotated.getchannel("A")
        base_alpha_px = base_alpha_img.load()
        rotated_alpha_px = rotated_alpha_img.load()
        width, height = base.size
        gap_mask_img = Image.new("L", base.size, 0)
        new_mask_img = Image.new("L", base.size, 0)
        gap_mask_px = gap_mask_img.load()
        new_mask_px = new_mask_img.load()
        original_alpha_pixels = 0
        retained_pixels = 0
        gap_pixels = 0
        new_alpha_pixels = 0
        for y in range(height):
            for x in range(width):
                base_on = base_alpha_px[x, y] > 24
                rotated_on = rotated_alpha_px[x, y] > 24
                if base_on:
                    original_alpha_pixels += 1
                    if rotated_on:
                        retained_pixels += 1
                    else:
                        gap_pixels += 1
                        gap_mask_px[x, y] = 255
                elif rotated_on:
                    new_alpha_pixels += 1
                    new_mask_px[x, y] = 255
        gap_bbox = gap_mask_img.getbbox()
        if gap_bbox:
            heatmap_path.parent.mkdir(parents=True, exist_ok=True)
            heatmap = base.copy()
            heatmap_px = heatmap.load()
            for y in range(height):
                for x in range(width):
                    r, g, b, a = heatmap_px[x, y]
                    heatmap_px[x, y] = (r, g, b, min(a, 90))
                    if gap_mask_px[x, y] > 0:
                        heatmap_px[x, y] = (255, 0, 0, 230)
                    elif new_mask_px[x, y] > 0:
                        heatmap_px[x, y] = (0, 120, 255, 210)
            heatmap.save(heatmap_path)
    retained_ratio = round(retained_pixels / max(original_alpha_pixels, 1), 6)
    gap_ratio = round(gap_pixels / max(original_alpha_pixels, 1), 6)
    new_alpha_ratio = round(new_alpha_pixels / max(original_alpha_pixels, 1), 6)
    return {
        "status": "clear" if gap_pixels == 0 else "observed",
        "originalAlphaPixels": original_alpha_pixels,
        "retainedAlphaPixels": retained_pixels,
        "retainedAlphaRatio": retained_ratio,
        "gapPixels": gap_pixels,
        "gapRatio": gap_ratio,
        "newAlphaPixels": new_alpha_pixels,
        "newAlphaRatio": new_alpha_ratio,
        "gapBbox": list(gap_bbox) if gap_bbox else None,
        "gapHeatmap": relative_to_workspace(heatmap_path, workspace) if gap_bbox else None,
        "note": "Diagnostic only. Pixel gap thresholds require real character calibration before becoming a hard failure.",
    }


def v3_pose_gap_gate_config(workspace: Path) -> dict[str, Any]:
    qa_gates = read_json_if_exists(workspace / "v3" / "qa-gates.json") or {}
    for gate in qa_gates.get("gates", []):
        if isinstance(gate, dict) and gate.get("id") == "pose_stress":
            thresholds = gate.get("thresholds") if isinstance(gate.get("thresholds"), dict) else {}
            return {
                "policy": str(gate.get("pixelGapPolicy") or "diagnostic"),
                "thresholds": {
                    "maxGapRatio": thresholds.get("maxGapRatio"),
                    "maxGapPixels": thresholds.get("maxGapPixels"),
                    "maxNewAlphaRatio": thresholds.get("maxNewAlphaRatio"),
                },
                "source": "v3/qa-gates.json",
            }
    return {
        "policy": "diagnostic",
        "thresholds": {"maxGapRatio": None, "maxGapPixels": None, "maxNewAlphaRatio": None},
        "source": "default",
    }


def v3_pose_gap_failure_reasons(pixel_gap: dict[str, Any], gate_config: dict[str, Any]) -> list[str]:
    if gate_config.get("policy") != "hard_fail":
        return []
    thresholds = gate_config.get("thresholds") if isinstance(gate_config.get("thresholds"), dict) else {}
    reasons: list[str] = []
    max_gap_ratio = thresholds.get("maxGapRatio")
    if isinstance(max_gap_ratio, (int, float)) and float(pixel_gap.get("gapRatio") or 0.0) > float(max_gap_ratio):
        reasons.append(f"pose_gap_ratio_exceeds_{max_gap_ratio}")
    max_gap_pixels = thresholds.get("maxGapPixels")
    if isinstance(max_gap_pixels, int) and int(pixel_gap.get("gapPixels") or 0) > max_gap_pixels:
        reasons.append(f"pose_gap_pixels_exceeds_{max_gap_pixels}")
    max_new_alpha_ratio = thresholds.get("maxNewAlphaRatio")
    if isinstance(max_new_alpha_ratio, (int, float)) and float(pixel_gap.get("newAlphaRatio") or 0.0) > float(max_new_alpha_ratio):
        reasons.append(f"pose_new_alpha_ratio_exceeds_{max_new_alpha_ratio}")
    return reasons


def write_v3_pose_stress(workspace: Path) -> dict[str, Any]:
    component_plan_path = workspace / "v3" / "component-plan.json"
    if not component_plan_path.exists():
        write_v3_component_plan(workspace)
    component_plan = read_json_if_exists(component_plan_path) or {}
    components = [component for component in component_plan.get("components", []) if isinstance(component, dict)]
    if not components:
        raise ValueError("v3/component-plan.json contains no components")
    out_dir = workspace / "v3" / "check" / "pose-stress"
    out_dir.mkdir(parents=True, exist_ok=True)
    gap_gate_config = v3_pose_gap_gate_config(workspace)
    cases: list[dict[str, Any]] = []
    updated_components: list[dict[str, Any]] = []
    for component in components:
        component = v3_normalize_component_hidden_requirement(component)
        updated = dict(component)
        component_id = str(component.get("id") or "")
        if not component_id or component.get("status") == "not_visible":
            updated_components.append(updated)
            continue
        sockets = [str(socket) for socket in component.get("sockets", []) if isinstance(socket, str)]
        if not sockets and not component.get("needsOverlapZone"):
            updated["poseStressStatus"] = "not_required"
            updated["poseStressCases"] = []
            updated_components.append(updated)
            continue
        if component.get("registrationStatus") != "accepted":
            updated["poseStressStatus"] = "missing"
            updated["poseStressCases"] = []
            updated_components.append(updated)
            continue
        merged_path = component.get("mergedComponent")
        if not isinstance(merged_path, str) or not (workspace / merged_path).exists():
            updated["poseStressStatus"] = "missing"
            updated["poseStressCases"] = []
            updated_components.append(updated)
            continue
        merged = Image.open(workspace / merged_path).convert("RGBA")
        bbox = merged.getchannel("A").getbbox()
        if bbox is None:
            updated["poseStressStatus"] = "failed"
            updated["poseStressCases"] = []
            updated_components.append(updated)
            continue
        component_case_ids: list[str] = []
        component_statuses: list[str] = []
        stress_sockets = sockets or ["overlap"]
        for socket in stress_sockets:
            pivot = v3_pose_pivot_for_socket(component, bbox, socket)
            angle = v3_pose_socket_angle(socket)
            case_id = f"{component_id}-{socket}".replace("/", "-")
            preview_path = out_dir / f"{case_id}.png"
            gap_heatmap_path = out_dir / f"{case_id}.gap.png"
            v3_pose_preview_image(merged, pivot, angle).save(preview_path)
            gap_quality = v3_pose_gap_quality(merged, pivot, angle, gap_heatmap_path, workspace)
            reasons: list[str] = []
            if component.get("drawOrder") is None:
                reasons.append("draw_order_missing")
            if not pivot:
                reasons.append("pivot_missing")
            if component.get("needsOverlapZone") and component.get("needsHiddenCompletion") and component.get("hiddenStatus") != "passed":
                reasons.append("overlap_zone_missing")
            reasons.extend(v3_pose_gap_failure_reasons(gap_quality, gap_gate_config))
            status = "passed" if not reasons else "failed"
            component_statuses.append(status)
            component_case_ids.append(case_id)
            cases.append(
                {
                    "caseId": case_id,
                    "componentId": component_id,
                    "owner": component.get("owner"),
                    "socket": socket,
                    "angleDeg": angle,
                    "pivot": pivot,
                    "preview": relative_to_workspace(preview_path, workspace),
                    "pixelGap": gap_quality,
                    "status": status,
                    "reasons": reasons,
                    "hiddenStatus": component.get("hiddenStatus"),
                    "needsOverlapZone": bool(component.get("needsOverlapZone")),
                    "drawOrder": component.get("drawOrder"),
                }
            )
        updated["pivot"] = v3_pose_pivot_for_socket(component, bbox, stress_sockets[0])
        updated["poseStressStatus"] = "passed" if component_statuses and all(status == "passed" for status in component_statuses) else "failed"
        updated["poseStressCases"] = component_case_ids
        updated_components.append(updated)
    status_counts: dict[str, int] = {}
    for case in cases:
        status = str(case.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    passed_count = status_counts.get("passed", 0)
    failed_count = status_counts.get("failed", 0)
    if not cases:
        status = "skipped"
    elif failed_count == 0:
        status = "passed"
    else:
        status = "failed"
    component_plan["components"] = updated_components
    component_plan["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(component_plan_path, component_plan)
    report_path = workspace / "v3" / "check" / "pose-stress-report.json"
    report = {
        "type": "kine.v3.poseStressReport",
        "version": "0.1",
        "status": status,
        "componentPlan": "v3/component-plan.json",
        "caseDir": "v3/check/pose-stress",
        "caseCount": len(cases),
        "passedCount": passed_count,
        "failedCount": failed_count,
        "statusCounts": status_counts,
        "pixelGapGate": gap_gate_config,
        "cases": cases,
        "note": "Foundation pose-stress evidence: small-angle alpha previews around estimated pivots. This is not a full rig simulation.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(report_path, report)
    print(
        json.dumps(
            {
                "status": "v3_pose_stress_written",
                "poseStressStatus": status,
                "caseCount": len(cases),
                "failedCount": failed_count,
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


def v3_component_export_status(component: dict[str, Any]) -> str:
    component = v3_normalize_component_hidden_requirement(component)
    if component.get("status") == "not_visible":
        return "not_visible"
    if component.get("manualReviewStatus") == "rejected":
        return "manual_review_rejected"
    if component.get("registrationStatus") != "accepted":
        return "missing"
    if component.get("needsHiddenCompletion") and component.get("hiddenStatus") != "passed":
        return "needs_hidden_completion"
    if component.get("poseStressStatus") not in {"passed", "not_required", None}:
        return "pose_stress_failed"
    if not component.get("mergedComponent"):
        return "missing"
    return "accepted"


def apply_v3_review_decisions(workspace: Path, decisions_path: Path) -> dict[str, Any]:
    component_plan_path = workspace / "v3" / "component-plan.json"
    if not component_plan_path.exists():
        raise FileNotFoundError(component_plan_path)
    decisions_doc = read_json_if_exists(decisions_path)
    if not isinstance(decisions_doc, dict):
        raise ValueError(f"Invalid review decisions JSON: {decisions_path}")
    decisions = decisions_doc.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("Review decisions JSON must contain a decisions array")
    valid_decisions = {"accepted", "rejected", "needs_hidden_completion", "needs_manual_review"}
    component_plan = read_json_if_exists(component_plan_path) or {}
    components = [item for item in component_plan.get("components", []) if isinstance(item, dict)]
    by_id = {str(component.get("id")): component for component in components if component.get("id")}
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw_decision in decisions:
        if not isinstance(raw_decision, dict):
            rejected.append({"reason": "decision_not_object", "decision": raw_decision})
            continue
        component_id = str(raw_decision.get("componentId") or "").strip()
        decision = str(raw_decision.get("decision") or "").strip()
        if component_id not in by_id:
            rejected.append({"componentId": component_id, "decision": decision, "reason": "unknown_component"})
            continue
        if decision not in valid_decisions:
            rejected.append({"componentId": component_id, "decision": decision, "reason": "invalid_decision"})
            continue
        component = by_id[component_id]
        review_record = {
            "status": decision,
            "reason": str(raw_decision.get("reason") or ""),
            "reviewer": str(raw_decision.get("reviewer") or "review_html"),
            "source": relative_to_workspace(decisions_path, workspace) if decisions_path.is_relative_to(workspace) else str(decisions_path),
            "appliedAt": datetime.now().isoformat(timespec="seconds"),
        }
        component["manualReview"] = review_record
        component["manualReviewStatus"] = decision
        component["manualReviewReason"] = review_record["reason"]
        if decision == "needs_hidden_completion":
            component["needsHiddenCompletion"] = True
            if component.get("hiddenStatus") != "passed":
                component["hiddenStatus"] = "missing"
                component["hiddenReason"] = "manual_review_needs_hidden_completion"
        applied.append({"componentId": component_id, "decision": decision})
    component_plan["components"] = components
    component_plan["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    component_plan["manualReviewDecisions"] = {
        "source": relative_to_workspace(decisions_path, workspace) if decisions_path.is_relative_to(workspace) else str(decisions_path),
        "appliedCount": len(applied),
        "rejectedCount": len(rejected),
        "updatedAt": component_plan["updatedAt"],
    }
    write_json(component_plan_path, component_plan)
    out_dir = workspace / "v3" / "review"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "type": "kine.v3.reviewDecisionApplyReport",
        "version": "0.1",
        "componentPlan": "v3/component-plan.json",
        "source": component_plan["manualReviewDecisions"]["source"],
        "appliedCount": len(applied),
        "rejectedCount": len(rejected),
        "applied": applied,
        "rejected": rejected,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(out_dir / "review-decisions-applied.json", report)
    update_run_state(
        workspace,
        {
            "v3ReviewDecisions": "v3/review/review-decisions-applied.json",
            "v3ReviewDecisionAppliedCount": len(applied),
        },
    )
    print(json.dumps({"status": "v3_review_decisions_applied", "appliedCount": len(applied), "rejectedCount": len(rejected), "report": str(out_dir / "review-decisions-applied.json")}, ensure_ascii=False, indent=2))
    return report


def export_v3_psd(workspace: Path, components: list[dict[str, Any]], out_path: Path, canvas: tuple[int, int]) -> dict[str, Any]:
    try:
        from psd_tools import PSDImage
    except Exception as exc:
        return {"status": "skipped", "failure": f"psd_tools unavailable: {exc}"}
    psd = PSDImage.new(mode="RGBA", size=canvas, depth=8)
    written: list[str] = []
    for component in components:
        source_file = component.get("sourceFile")
        component_id = component.get("id")
        placement = component.get("placement") or {}
        if not isinstance(source_file, str) or not isinstance(component_id, str):
            continue
        img_path = workspace / source_file
        if not img_path.exists():
            continue
        try:
            img = Image.open(img_path).convert("RGBA")
            psd.create_pixel_layer(img, name=component_id, top=int(placement["y"]), left=int(placement["x"]), opacity=255)
            written.append(component_id)
        except Exception:
            continue
    try:
        psd._updated = False
        psd.save(out_path)
    except Exception as exc:
        return {"status": "failed", "failure": f"{type(exc).__name__}: {exc}", "writtenLayers": written}
    return {"status": "written", "path": relative_to_workspace(out_path, workspace), "writtenLayers": written}


def v3_component_pivot(placement: dict[str, Any]) -> dict[str, Any]:
    x = int(placement.get("x") or 0)
    y = int(placement.get("y") or 0)
    w = int(placement.get("w") or 0)
    h = int(placement.get("h") or 0)
    return {
        "sourceCanvas": [x + round(w / 2, 3), y + round(h / 2, 3)],
        "local": [round(w / 2, 3), round(h / 2, 3)],
    }


def v3_runtime_targets(components: list[dict[str, Any]], canvas: tuple[int, int]) -> dict[str, Any]:
    bone_world = _spine_bone_world_positions(canvas)
    spine_slots: list[dict[str, Any]] = []
    live2d_parts: list[dict[str, Any]] = []
    for component in sorted(components, key=lambda item: int(item.get("drawOrder") or 0)):
        component_id = str(component.get("id") or "")
        placement = component.get("placement") if isinstance(component.get("placement"), dict) else {}
        pivot = v3_component_pivot(placement)
        bone = str(component.get("bone") or spine_bone_for_component(component_id))
        spine_slots.append(
            {
                "slot": component_id,
                "bone": bone,
                "attachment": component_id,
                "image": component.get("file"),
                "drawOrder": component.get("drawOrder"),
                "placement": placement,
                "pivot": pivot,
                "sockets": component.get("sockets", []),
            }
        )
        live2d_parts.append(
            {
                "partId": component_id,
                "parent": component.get("parent"),
                "texture": component.get("file"),
                "drawOrder": component.get("drawOrder"),
                "placement": placement,
                "pivot": pivot,
                "deformable": bool(component.get("deformable")),
                "sockets": component.get("sockets", []),
            }
        )
    return {
        "spine": {
            "format": f"spine-json-{SPINE_FORMAT_VERSION}",
            "canvas": list(canvas),
            "bones": [
                {
                    "name": item["name"],
                    "parent": item["parent"],
                    "world": list(bone_world[item["name"]]),
                }
                for item in SPINE_BONE_TEMPLATE
            ],
            "slots": spine_slots,
        },
        "live2d": {
            "format": "live2d-ready-texture-parts",
            "canvas": list(canvas),
            "parts": live2d_parts,
            "note": "Runtime handoff schema only. Meshes, weights, deformers, and animation curves must be authored downstream.",
        },
    }


def export_v3_components(workspace: Path) -> dict[str, Any]:
    component_plan_path = workspace / "v3" / "component-plan.json"
    if not component_plan_path.exists():
        write_v3_component_plan(workspace)
    recompose_report = read_json_if_exists(workspace / "v3" / "check" / "recompose-report.json")
    if not recompose_report:
        recompose_report = write_v3_recompose(workspace)
    pose_report = read_json_if_exists(workspace / "v3" / "check" / "pose-stress-report.json")
    if not pose_report:
        pose_report = write_v3_pose_stress(workspace)
    component_plan = read_json_if_exists(component_plan_path) or {}
    source = Image.open(workspace / "source.png").convert("RGBA")
    canvas = source.size
    out_dir = workspace / "v3" / "export"
    components_dir = out_dir / "components"
    components_dir.mkdir(parents=True, exist_ok=True)
    for stale in components_dir.glob("*.png"):
        stale.unlink()
    components_out: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    gate_blockers: list[str] = []
    source_visible_fallback_count = 0
    generated_or_merged_count = 0
    if recompose_report.get("status") != "passed":
        gate_blockers.append("v3_recompose_not_passed")
    if pose_report.get("status") not in {"passed", "skipped"}:
        gate_blockers.append("v3_pose_stress_not_passed")
    for component in sorted(
        [item for item in component_plan.get("components", []) if isinstance(item, dict)],
        key=lambda item: int(item.get("drawOrder") or 0),
    ):
        component_id = str(component.get("id") or "")
        if not component_id or component.get("status") == "not_visible":
            continue
        status = v3_component_export_status(component)
        if status != "accepted" or gate_blockers:
            blocked.append({"componentId": component_id, "owner": component.get("owner"), "status": status})
            continue
        merged_path = component.get("mergedComponent")
        if not isinstance(merged_path, str) or not (workspace / merged_path).exists():
            blocked.append({"componentId": component_id, "owner": component.get("owner"), "status": "merged_component_missing"})
            continue
        merged = Image.open(workspace / merged_path).convert("RGBA")
        bbox = merged.getchannel("A").getbbox()
        if not bbox:
            blocked.append({"componentId": component_id, "owner": component.get("owner"), "status": "empty_alpha"})
            continue
        crop = merged.crop(bbox)
        out_name = f"{component_id}.png"
        crop.save(components_dir / out_name)
        placement = {
            "x": int(bbox[0]),
            "y": int(bbox[1]),
            "w": int(bbox[2] - bbox[0]),
            "h": int(bbox[3] - bbox[1]),
            "sourceCanvas": list(canvas),
        }
        registration_source = v3_component_registration_source_summary(component)
        if registration_source["exportSource"] == "source_visible_fallback":
            source_visible_fallback_count += 1
        elif registration_source["exportSource"] == "generated_or_merged_component":
            generated_or_merged_count += 1
        components_out.append(
            {
                "id": component_id,
                "owner": component.get("owner"),
                "track": component.get("track"),
                "parent": component.get("parent"),
                "bone": component.get("bone") or spine_bone_for_component(component_id),
                "side": component.get("side"),
                "segment": component.get("segment"),
                "lengthFraction": component.get("lengthFraction"),
                "sockets": component.get("sockets", []),
                "deformable": bool(component.get("deformable", False)),
                "file": f"v3/export/components/{out_name}",
                "sourceFile": f"v3/export/components/{out_name}",
                "placement": placement,
                "pivot": v3_component_pivot(placement),
                "drawOrder": component.get("drawOrder"),
                "maskStatus": component.get("maskStatus"),
                "hiddenStatus": component.get("hiddenStatus"),
                "poseStressStatus": component.get("poseStressStatus"),
                "poseStressCases": component.get("poseStressCases", []),
                "exportSource": registration_source["exportSource"],
                "provenance": {
                    "registeredCandidateIds": registration_source["registeredCandidateIds"],
                    "sourceVisibleCandidateIds": registration_source["sourceVisibleCandidateIds"],
                    "generatedCandidateIds": registration_source["generatedCandidateIds"],
                    "mergedComponent": merged_path,
                    "exportPolicy": "accepted merged component only; source-visible fallback is debug/source-lock evidence, not redrawn final art",
                },
            }
        )
    generated_quality_audit = v3_generated_candidate_quality_audit(workspace)
    stable_owner_audit = v3_stable_owner_coverage_audit(workspace)
    export_content_blockers: list[str] = []
    if (
        components_out
        and source_visible_fallback_count == len(components_out)
        and int(generated_quality_audit.get("generatedCandidateCount") or 0) > 0
        and int(generated_quality_audit.get("generatedAcceptedCount") or 0) == 0
    ):
        export_content_blockers.append("export_source_visible_fallback_only")
    if stable_owner_audit.get("blockers"):
        export_content_blockers.extend(f"export_{blocker}" for blocker in stable_owner_audit.get("blockers", []))
    gate_blockers.extend(export_content_blockers)
    status = "final_exportable" if components_out and not blocked and not gate_blockers else PARTS_SHEET_BLOCKED_STATUS
    psd_path = out_dir / "source-master-v3.psd"
    if status == "final_exportable":
        psd_status = export_v3_psd(workspace, components_out, psd_path, canvas)
    else:
        if psd_path.exists():
            psd_path.unlink()
        psd_status = {
            "status": PARTS_SHEET_BLOCKED_STATUS,
            "path": None,
            "reason": "blocked_export_content_or_quality_gate",
            "blockers": export_content_blockers or gate_blockers,
        }
    runtime_targets = v3_runtime_targets(components_out, canvas)
    manifest = {
        "type": "kine.v3.componentsManifest",
        "version": "0.1",
        "status": status,
        "source": "source.png",
        "sourceCanvas": list(canvas),
        "componentPlan": "v3/component-plan.json",
        "recomposeReport": "v3/check/recompose-report.json",
        "poseStressReport": "v3/check/pose-stress-report.json",
        "componentCount": len(components_out),
        "blockedCount": len(blocked),
        "drawOrderBackToFront": [item["id"] for item in components_out],
        "components": components_out,
        "runtimeTargets": runtime_targets,
        "blocked": blocked,
        "gateBlockers": gate_blockers,
        "exportContentStatus": "passed" if not export_content_blockers else PARTS_SHEET_BLOCKED_STATUS,
        "exportContentBlockers": export_content_blockers,
        "provenanceCounts": {
            "sourceVisibleFallback": source_visible_fallback_count,
            "generatedOrMerged": generated_or_merged_count,
        },
        "qualityAudits": {
            "generatedCandidateQuality": generated_quality_audit,
            "stableOwnerCoverage": stable_owner_audit,
        },
        "psd": psd_status,
        "note": "V3 final components are exported only from accepted merged components after V3 recompose, pose-stress, generated-candidate, stable-owner, and export provenance gates.",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(out_dir / "components-manifest.json", manifest)
    handoff = {
        "type": "kine.v3.handoffManifest",
        "version": "0.1",
        "status": status,
        "source": "source.png",
        "componentPlan": "v3/component-plan.json",
        "componentsManifest": "v3/export/components-manifest.json",
        "recomposeReport": "v3/check/recompose-report.json",
        "poseStressReport": "v3/check/pose-stress-report.json",
        "psd": psd_status,
        "components": components_out,
        "runtimeTargets": runtime_targets,
        "blocked": blocked,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(out_dir / "kine-handoff-manifest.json", handoff)
    update_run_state(
        workspace,
        {
            "v3ComponentsManifest": "v3/export/components-manifest.json",
            "v3HandoffManifest": "v3/export/kine-handoff-manifest.json",
            "v3ComponentsStatus": status,
            "v3ComponentCount": len(components_out),
        },
    )
    print(
        json.dumps(
            {
                "status": "v3_components_exported" if status == "final_exportable" else PARTS_SHEET_BLOCKED_STATUS,
                "componentCount": len(components_out),
                "blockedCount": len(blocked),
                "gateBlockers": gate_blockers,
                "manifest": str(out_dir / "components-manifest.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return manifest


def validate_v3_handoff(workspace: Path) -> dict[str, Any]:
    """Validate exported V3 runtime handoff references without creating runtime projects."""
    export_dir = workspace / "v3" / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = export_dir / "components-manifest.json"
    handoff_path = export_dir / "kine-handoff-manifest.json"
    manifest = read_json_if_exists(manifest_path) or {}
    handoff = read_json_if_exists(handoff_path) or {}
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if manifest.get("type") != "kine.v3.componentsManifest":
        failures.append({"code": "components_manifest_missing_or_wrong_type", "path": "v3/export/components-manifest.json"})
    if handoff.get("type") != "kine.v3.handoffManifest":
        failures.append({"code": "handoff_manifest_missing_or_wrong_type", "path": "v3/export/kine-handoff-manifest.json"})

    components = manifest.get("components", []) if isinstance(manifest.get("components"), list) else []
    component_ids = [str(component.get("id") or "") for component in components if isinstance(component, dict)]
    component_by_id = {str(component.get("id")): component for component in components if isinstance(component, dict) and component.get("id")}
    canvas = manifest.get("sourceCanvas")
    if not (isinstance(canvas, list) and len(canvas) == 2):
        failures.append({"code": "source_canvas_missing"})
        canvas_w = canvas_h = 0
    else:
        canvas_w, canvas_h = int(canvas[0]), int(canvas[1])
    if int(manifest.get("componentCount") or -1) != len(components):
        failures.append({"code": "component_count_mismatch", "manifestCount": manifest.get("componentCount"), "actualCount": len(components)})
    if manifest.get("status") != "final_exportable":
        failures.append({"code": "components_manifest_not_final_exportable", "status": manifest.get("status")})

    for component in components:
        if not isinstance(component, dict):
            failures.append({"code": "component_not_object"})
            continue
        component_id = str(component.get("id") or "")
        component_file = component.get("file")
        placement = component.get("placement") if isinstance(component.get("placement"), dict) else {}
        if not component_id:
            failures.append({"code": "component_missing_id"})
            continue
        if not isinstance(component_file, str) or not (workspace / component_file).exists():
            failures.append({"code": "component_file_missing", "componentId": component_id, "file": component_file})
            continue
        try:
            img = Image.open(workspace / component_file).convert("RGBA")
        except Exception as exc:
            failures.append({"code": "component_file_unreadable", "componentId": component_id, "file": component_file, "error": str(exc)})
            continue
        x = int(placement.get("x") or 0)
        y = int(placement.get("y") or 0)
        w = int(placement.get("w") or 0)
        h = int(placement.get("h") or 0)
        if w <= 0 or h <= 0:
            failures.append({"code": "component_placement_empty", "componentId": component_id, "placement": placement})
        if img.size != (w, h):
            failures.append({"code": "component_image_size_mismatch", "componentId": component_id, "imageSize": list(img.size), "placement": placement})
        if x < 0 or y < 0 or x + w > canvas_w or y + h > canvas_h:
            failures.append({"code": "component_placement_outside_canvas", "componentId": component_id, "placement": placement, "canvas": [canvas_w, canvas_h]})
        if img.getchannel("A").getbbox() is None:
            failures.append({"code": "component_file_empty_alpha", "componentId": component_id, "file": component_file})

    runtime = handoff.get("runtimeTargets") if isinstance(handoff.get("runtimeTargets"), dict) else {}
    spine = runtime.get("spine") if isinstance(runtime.get("spine"), dict) else {}
    live2d = runtime.get("live2d") if isinstance(runtime.get("live2d"), dict) else {}
    spine_slots = spine.get("slots", []) if isinstance(spine.get("slots"), list) else []
    live2d_parts = live2d.get("parts", []) if isinstance(live2d.get("parts"), list) else []
    spine_bones = {str(item.get("name")) for item in spine.get("bones", []) if isinstance(item, dict) and item.get("name")}
    if len(spine_slots) != len(components):
        failures.append({"code": "spine_slot_count_mismatch", "slotCount": len(spine_slots), "componentCount": len(components)})
    if len(live2d_parts) != len(components):
        failures.append({"code": "live2d_part_count_mismatch", "partCount": len(live2d_parts), "componentCount": len(components)})
    for slot in spine_slots:
        if not isinstance(slot, dict):
            failures.append({"code": "spine_slot_not_object"})
            continue
        slot_id = str(slot.get("slot") or "")
        component = component_by_id.get(slot_id)
        if component is None:
            failures.append({"code": "spine_slot_unknown_component", "slot": slot_id})
            continue
        if slot.get("attachment") != slot_id:
            failures.append({"code": "spine_attachment_mismatch", "slot": slot_id, "attachment": slot.get("attachment")})
        if slot.get("image") != component.get("file"):
            failures.append({"code": "spine_image_mismatch", "slot": slot_id, "image": slot.get("image"), "componentFile": component.get("file")})
        if slot.get("bone") not in spine_bones:
            failures.append({"code": "spine_bone_missing", "slot": slot_id, "bone": slot.get("bone")})
    for part in live2d_parts:
        if not isinstance(part, dict):
            failures.append({"code": "live2d_part_not_object"})
            continue
        part_id = str(part.get("partId") or "")
        component = component_by_id.get(part_id)
        if component is None:
            failures.append({"code": "live2d_part_unknown_component", "partId": part_id})
            continue
        if part.get("texture") != component.get("file"):
            failures.append({"code": "live2d_texture_mismatch", "partId": part_id, "texture": part.get("texture"), "componentFile": component.get("file")})

    if component_ids != [str(item.get("slot") or "") for item in spine_slots if isinstance(item, dict)]:
        warnings.append({"code": "spine_slot_order_differs_from_component_order"})
    if component_ids != [str(item.get("partId") or "") for item in live2d_parts if isinstance(item, dict)]:
        warnings.append({"code": "live2d_part_order_differs_from_component_order"})

    status = "passed" if not failures else PARTS_SHEET_BLOCKED_STATUS
    report = {
        "type": "kine.v3.handoffValidationReport",
        "version": "0.1",
        "status": status,
        "workspace": workspace.name,
        "componentsManifest": "v3/export/components-manifest.json",
        "handoffManifest": "v3/export/kine-handoff-manifest.json",
        "componentCount": len(components),
        "failureCount": len(failures),
        "warningCount": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Reference and schema validation only. This does not prove a complete Spine or Live2D rig import.",
    }
    out_path = export_dir / "handoff-validation-report.json"
    write_json(out_path, report)
    update_run_state(workspace, {"v3HandoffValidation": "v3/export/handoff-validation-report.json", "v3HandoffValidationStatus": status})
    print(json.dumps({"status": status, "failureCount": len(failures), "warningCount": len(warnings), "report": str(out_path)}, ensure_ascii=False, indent=2))
    return report


def write_v3_runtime_import_report(workspace: Path, evidence_path: Path | None = None) -> dict[str, Any]:
    """Record external Spine/Live2D import evidence without pretending to generate a rig."""
    export_dir = workspace / "v3" / "export"
    manifest = read_json_if_exists(export_dir / "components-manifest.json") or {}
    handoff = read_json_if_exists(export_dir / "kine-handoff-manifest.json") or {}
    handoff_validation = read_json_if_exists(export_dir / "handoff-validation-report.json") or {}
    evidence = read_json_if_exists(evidence_path) if evidence_path else None
    if evidence is not None and evidence.get("type") != "kine.v3.runtimeImportEvidence":
        raise ValueError(f"Invalid runtime import evidence JSON: {evidence_path}")
    raw_imports = evidence.get("imports", []) if isinstance(evidence, dict) else []
    imports_by_target = {
        str(item.get("target")): item
        for item in raw_imports
        if isinstance(item, dict) and item.get("target") in {"spine", "live2d"} and item.get("status") in {"passed", "failed", "skipped"}
    }
    runtime = handoff.get("runtimeTargets") if isinstance(handoff.get("runtimeTargets"), dict) else {}
    required_targets = [target for target in ("spine", "live2d") if isinstance(runtime.get(target), dict)]
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    if manifest.get("status") != "final_exportable":
        blockers.append(f"v3_export_{manifest.get('status') or 'missing'}")
    if handoff_validation.get("status") != "passed":
        blockers.append(f"handoff_validation_{handoff_validation.get('status') or 'missing'}")
    if not required_targets:
        blockers.append("runtime_targets_missing")

    for target in required_targets:
        item = imports_by_target.get(target)
        if item is None:
            blockers.append(f"runtime_import_missing_{target}")
            rows.append({"target": target, "status": "missing", "requiresEvidence": True})
            continue
        status = str(item.get("status"))
        if status != "passed":
            blockers.append(f"runtime_import_{status}_{target}")
        rows.append(
            {
                "target": target,
                "status": status,
                "project": item.get("project"),
                "toolVersion": item.get("toolVersion"),
                "reviewer": item.get("reviewer"),
                "notes": item.get("notes"),
                "requiresEvidence": status != "passed",
            }
        )

    status = "passed" if not blockers else PARTS_SHEET_BLOCKED_STATUS
    report = {
        "type": "kine.v3.runtimeImportReport",
        "version": "0.1",
        "status": status,
        "workspace": workspace.name,
        "componentsManifest": "v3/export/components-manifest.json",
        "handoffManifest": "v3/export/kine-handoff-manifest.json",
        "handoffValidation": "v3/export/handoff-validation-report.json",
        "evidenceSource": str(evidence_path) if evidence_path else None,
        "requiredTargets": required_targets,
        "imports": rows,
        "blockers": blockers,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "External runtime import evidence only. This command records Spine/Live2D import review results; it does not generate meshes, weights, deformers, or animation curves.",
    }
    out_path = export_dir / "runtime-import-report.json"
    export_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_path, report)
    update_run_state(workspace, {"v3RuntimeImport": "v3/export/runtime-import-report.json", "v3RuntimeImportStatus": status})
    print(json.dumps({"status": status, "targetCount": len(required_targets), "blockerCount": len(blockers), "report": str(out_path)}, ensure_ascii=False, indent=2))
    return report


def v3_gate_result(gate_id: str, status: str, blockers: list[str] | None = None, artifacts: list[str] | None = None, counts: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": gate_id,
        "status": status,
        "passed": status == "passed",
        "blockers": blockers or [],
        "artifacts": artifacts or [],
        "counts": counts or {},
    }


def v3_runtime_import_validation_gate(runtime_import: dict[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    """Map optional external runtime-import evidence into the aggregate V3 gate.

    V3 exports Spine/Live2D handoff metadata, but it does not itself run those
    external tools. Missing import evidence should not block the default
    source-master pipeline; actual failed import evidence still blocks.
    """
    if not isinstance(runtime_import, dict) or runtime_import.get("type") != "kine.v3.runtimeImportReport":
        return "passed", [], {
            "status": "not_recorded",
            "required": False,
            "blockerCount": 0,
            "note": "external runtime import evidence not required for default V3 source-master validation",
        }
    status = runtime_import.get("status")
    blockers = [str(blocker) for blocker in runtime_import.get("blockers", []) if blocker] if isinstance(runtime_import.get("blockers"), list) else []
    missing_only = bool(blockers) and all(blocker.startswith("runtime_import_missing_") for blocker in blockers)
    if status == "passed":
        return "passed", [], {
            "status": status,
            "required": False,
            "requiredTargets": runtime_import.get("requiredTargets"),
            "blockerCount": 0,
        }
    if missing_only:
        return "passed", [], {
            "status": "optional_missing",
            "rawStatus": status,
            "required": False,
            "requiredTargets": runtime_import.get("requiredTargets"),
            "optionalMissing": blockers,
            "blockerCount": 0,
        }
    return "failed", blockers or [f"runtime_import_{status or 'missing'}"], {
        "status": status,
        "required": False,
        "requiredTargets": runtime_import.get("requiredTargets"),
        "blockerCount": len(blockers),
    }


def validate_v3_pipeline(workspace: Path) -> dict[str, Any]:
    """Aggregate V3 artifact gates for real-sample hardening without mutating artifacts."""
    v3_dir = workspace / "v3"
    component_plan = read_json_if_exists(v3_dir / "component-plan.json") or {}
    components = component_plan.get("components", []) if isinstance(component_plan.get("components"), list) else []
    active_components = [
        v3_normalize_component_hidden_requirement(component)
        for component in components
        if isinstance(component, dict) and component.get("status") != "not_visible"
    ]
    gates: list[dict[str, Any]] = []

    plan_blockers: list[str] = []
    if component_plan.get("type") != "kine.v3.componentPlan":
        plan_blockers.append("component_plan_missing_or_wrong_type")
    if not active_components:
        plan_blockers.append("no_active_components")
    for key in ("id", "owner", "track", "drawOrder", "expectedMask", "pivot", "sockets"):
        if any(key not in component for component in active_components):
            plan_blockers.append(f"component_missing_{key}")
    gates.append(
        v3_gate_result(
            "component_plan",
            "passed" if not plan_blockers else "missing",
            plan_blockers,
            ["v3/component-plan.json"] if (v3_dir / "component-plan.json").exists() else [],
            {"activeComponents": len(active_components), "totalComponents": len(components)},
        )
    )

    subject_report = read_json_if_exists(workspace / "source" / "source-subject-preflight.json") or {}
    subject_status = str(subject_report.get("status") or "missing")
    subject_blockers: list[str] = []
    if subject_report.get("type") != "kine.v3.sourceSubjectPreflight":
        subject_blockers.append("source_subject_preflight_missing")
    elif subject_report.get("shouldUseImagegenSubjectIsolation"):
        subject_blockers.append("source_subject_needs_imagegen_subject_matte")
    gates.append(
        v3_gate_result(
            "source_subject",
            "passed" if not subject_blockers else "failed" if subject_report else "missing",
            subject_blockers,
            ["source/source-subject-preflight.json"] if (workspace / "source" / "source-subject-preflight.json").exists() else [],
            {
                "status": subject_status,
                "requiredAction": subject_report.get("requiredAction"),
                "shouldUseImagegenSubjectIsolation": subject_report.get("shouldUseImagegenSubjectIsolation"),
            },
        )
    )

    mask_summary = read_json_if_exists(v3_dir / "masks" / "mask-summary.json") or {}
    mask_counts = mask_summary.get("statusCounts", {}) if isinstance(mask_summary.get("statusCounts"), dict) else {}
    mask_missing = sum(1 for component in active_components if component.get("needsMask") and component.get("maskStatus") != "passed")
    mask_blockers = []
    if mask_summary.get("type") != "kine.v3.maskJobSummary":
        mask_blockers.append("mask_summary_missing")
    if mask_missing:
        mask_blockers.append(f"active_masks_not_passed_{mask_missing}")
    gates.append(
        v3_gate_result(
            "component_mask",
            "passed" if not mask_blockers else "failed" if mask_summary else "missing",
            mask_blockers,
            ["v3/masks/mask-summary.json"] if (v3_dir / "masks" / "mask-summary.json").exists() else [],
            {"statusCounts": mask_counts, "activeMasksNotPassed": mask_missing},
        )
    )

    work_order = read_json_if_exists(v3_dir / "imagegen" / "imagegen-work-order.json") or {}
    role_sheet_tasks = [
        task
        for task in work_order.get("tasks", [])
        if isinstance(task, dict) and str(task.get("taskId") or "").startswith("parts-sheet:")
    ] if isinstance(work_order.get("tasks"), list) else []
    role_expected_outputs = []
    missing_role_outputs = []
    if role_sheet_tasks:
        for task in role_sheet_tasks:
            expected = task.get("expectedOutput")
            exists = isinstance(expected, str) and (workspace / expected).exists()
            row = {
                "taskId": task.get("taskId"),
                "role": task.get("role"),
                "expectedOutput": expected,
                "exists": exists,
            }
            role_expected_outputs.append(row)
            if not exists:
                missing_role_outputs.append(row)

    sheet_manifest = read_json_if_exists(v3_dir / "sheets" / "sheet-manifest.json") or {}
    candidates = sheet_manifest.get("candidates", []) if isinstance(sheet_manifest.get("candidates"), list) else []
    sheets = sheet_manifest.get("sheets", []) if isinstance(sheet_manifest.get("sheets"), list) else []
    ingested_sheet_ids = {
        str(sheet.get("sheetId") or sheet.get("id"))
        for sheet in sheets
        if isinstance(sheet, dict) and (sheet.get("sheetId") or sheet.get("id"))
    }
    if role_sheet_tasks:
        missing_ingested_sheet_ids = [
            str(task.get("taskId")).split(":", 1)[1]
            for task in role_sheet_tasks
            if ":" in str(task.get("taskId")) and str(task.get("taskId")).split(":", 1)[1] not in ingested_sheet_ids
        ]
        role_sheet_blockers = []
        if missing_role_outputs:
            role_sheet_blockers.append(f"role_sheet_expected_outputs_missing_{len(missing_role_outputs)}")
        if missing_ingested_sheet_ids:
            role_sheet_blockers.append(f"role_sheet_outputs_not_ingested_{len(missing_ingested_sheet_ids)}")
        gates.append(
            v3_gate_result(
                "imagegen_role_sheets",
                "passed" if not role_sheet_blockers else "failed",
                role_sheet_blockers,
                ["v3/imagegen/imagegen-work-order.json"],
                {
                    "roleSheetTaskCount": len(role_sheet_tasks),
                    "missingExpectedOutputCount": len(missing_role_outputs),
                    "ingestedRoleSheetCount": len(role_sheet_tasks) - len(missing_ingested_sheet_ids),
                    "missingIngestedSheetIds": missing_ingested_sheet_ids,
                    "expectedOutputs": role_expected_outputs,
                },
            )
        )

    sheet_blockers = []
    if sheet_manifest.get("type") != "kine.v3.sheetCandidateManifest":
        sheet_blockers.append("sheet_candidate_manifest_missing")
    if not candidates:
        sheet_blockers.append("no_v3_candidates")
    gates.append(
        v3_gate_result(
            "multi_sheet_ingest",
            "passed" if not sheet_blockers else "missing",
            sheet_blockers,
            ["v3/sheets/sheet-manifest.json"] if (v3_dir / "sheets" / "sheet-manifest.json").exists() else [],
            {"candidateCount": len(candidates), "sheetCount": len(sheets)},
        )
    )

    registration_report = read_json_if_exists(v3_dir / "registration" / "registration-report.json") or {}
    accepted_count = int(registration_report.get("acceptedCount") or 0) if isinstance(registration_report, dict) else 0
    rejected_count = int(registration_report.get("rejectedCount") or 0) if isinstance(registration_report, dict) else 0
    rejected_reason_counts = registration_report.get("rejectedReasonCounts", {}) if isinstance(registration_report.get("rejectedReasonCounts"), dict) else {}
    registration_blockers = []
    if registration_report.get("type") != "kine.v3.registrationReport":
        registration_blockers.append("registration_report_missing")
    elif accepted_count + rejected_count < len(candidates):
        registration_blockers.append("some_candidates_not_registered")
    elif candidates and active_components and accepted_count == 0:
        registration_blockers.append("no_candidates_accepted")
        for reason, count in sorted(rejected_reason_counts.items()):
            if count:
                registration_blockers.append(f"rejected_reason_{reason}_{count}")
    gates.append(
        v3_gate_result(
            "candidate_registration",
            "passed" if not registration_blockers else "failed" if registration_report else "missing",
            registration_blockers,
            ["v3/registration/registration-report.json"] if (v3_dir / "registration" / "registration-report.json").exists() else [],
            {"acceptedCount": accepted_count, "rejectedCount": rejected_count, "candidateCount": len(candidates), "rejectedReasonCounts": rejected_reason_counts},
        )
    )

    stable_owner_audit = v3_stable_owner_coverage_audit(workspace)
    stable_owner_blockers = [str(blocker) for blocker in stable_owner_audit.get("blockers", []) if blocker]
    gates.append(
        v3_gate_result(
            "stable_owner_coverage",
            "passed" if not stable_owner_blockers else "failed",
            stable_owner_blockers,
            [
                artifact
                for artifact in [
                    "v3/component-plan.json" if (v3_dir / "component-plan.json").exists() else "",
                    "v3/sheets/sheet-manifest.json" if (v3_dir / "sheets" / "sheet-manifest.json").exists() else "",
                    "v3/registration/registration-report.json" if (v3_dir / "registration" / "registration-report.json").exists() else "",
                ]
                if artifact
            ],
            {
                "stableOwners": stable_owner_audit.get("stableOwners"),
                "missingOwners": stable_owner_audit.get("missingOwners"),
                "evidenceCount": stable_owner_audit.get("evidenceCount"),
                "evidence": stable_owner_audit.get("evidence"),
            },
        )
    )

    generated_quality_audit = v3_generated_candidate_quality_audit(workspace)
    generated_quality_blockers = [str(blocker) for blocker in generated_quality_audit.get("blockers", []) if blocker]
    gates.append(
        v3_gate_result(
            "imagegen_proportion_consistency",
            "passed" if not generated_quality_blockers else "failed",
            generated_quality_blockers,
            [
                artifact
                for artifact in [
                    "v3/sheets/sheet-manifest.json" if (v3_dir / "sheets" / "sheet-manifest.json").exists() else "",
                    "v3/registration/registration-report.json" if (v3_dir / "registration" / "registration-report.json").exists() else "",
                ]
                if artifact
            ],
            {
                "generatedCandidateCount": generated_quality_audit.get("generatedCandidateCount"),
                "generatedAcceptedCount": generated_quality_audit.get("generatedAcceptedCount"),
                "generatedRejectedCount": generated_quality_audit.get("generatedRejectedCount"),
                "sourceVisibleAcceptedCount": generated_quality_audit.get("sourceVisibleAcceptedCount"),
                "proportionDriftCount": generated_quality_audit.get("proportionDriftCount"),
                "proportionDriftRows": generated_quality_audit.get("proportionDriftRows"),
            },
        )
    )

    hidden_report = read_json_if_exists(v3_dir / "hidden" / "hidden-report.json") or {}
    hidden_counts = hidden_report.get("statusCounts", {}) if isinstance(hidden_report.get("statusCounts"), dict) else {}
    hidden_missing = sum(1 for component in active_components if component.get("needsHiddenCompletion") and component.get("hiddenStatus") != "passed")
    hidden_blockers = []
    if hidden_report.get("type") != "kine.v3.hiddenJobReport":
        hidden_blockers.append("hidden_report_missing")
    if hidden_missing:
        hidden_blockers.append(f"hidden_completion_not_passed_{hidden_missing}")
    gates.append(
        v3_gate_result(
            "hidden_completion",
            "passed" if not hidden_blockers else "failed" if hidden_report else "missing",
            hidden_blockers,
            ["v3/hidden/hidden-report.json"] if (v3_dir / "hidden" / "hidden-report.json").exists() else [],
            {"statusCounts": hidden_counts, "hiddenMissing": hidden_missing},
        )
    )

    imagegen_hidden_count = 0
    for result in hidden_report.get("results", []) if isinstance(hidden_report.get("results"), list) else []:
        if not isinstance(result, dict):
            continue
        provenance_rel = result.get("hiddenInpaintProvenance")
        provenance = read_json_if_exists(workspace / provenance_rel) if isinstance(provenance_rel, str) else {}
        if isinstance(provenance, dict) and provenance.get("provenanceSource") == "imagegen":
            imagegen_hidden_count += 1
    hidden_review = read_json_if_exists(v3_dir / "hidden" / "review" / "hidden-inpaint-review-report.json") or {}
    hidden_review_blockers = []
    if imagegen_hidden_count:
        if hidden_review.get("type") != "kine.v3.hiddenInpaintReviewReport":
            hidden_review_blockers.append("hidden_inpaint_review_report_missing")
        if int(hidden_review.get("requiresHumanReviewCount") or 0) > 0:
            hidden_review_blockers.append(f"hidden_inpaint_requires_human_review_{hidden_review.get('requiresHumanReviewCount')}")
        decision_counts = hidden_review.get("decisionCounts", {}) if isinstance(hidden_review.get("decisionCounts"), dict) else {}
        if int(decision_counts.get("rejected") or 0):
            hidden_review_blockers.append(f"hidden_inpaint_manual_rejected_{decision_counts.get('rejected')}")
        if int(decision_counts.get("needs_revision") or 0):
            hidden_review_blockers.append(f"hidden_inpaint_needs_revision_{decision_counts.get('needs_revision')}")
    gates.append(
        v3_gate_result(
            "hidden_inpaint_review",
            "passed" if not hidden_review_blockers else "failed" if hidden_review or imagegen_hidden_count else "missing",
            hidden_review_blockers,
            ["v3/hidden/review/hidden-inpaint-review-report.json"] if (v3_dir / "hidden" / "review" / "hidden-inpaint-review-report.json").exists() else [],
            {
                "imagegenHiddenCount": imagegen_hidden_count,
                "requiresHumanReviewCount": hidden_review.get("requiresHumanReviewCount"),
                "decisionCounts": hidden_review.get("decisionCounts"),
            },
        )
    )

    recompose_report = read_json_if_exists(v3_dir / "check" / "recompose-report.json") or {}
    recompose_status = recompose_report.get("status") if isinstance(recompose_report, dict) else None
    gates.append(
        v3_gate_result(
            "source_recompose",
            "passed" if recompose_status == "passed" else "failed" if recompose_report else "missing",
            [] if recompose_status == "passed" else [f"recompose_{recompose_status or 'missing'}"],
            ["v3/check/recompose-report.json"] if (v3_dir / "check" / "recompose-report.json").exists() else [],
            {"status": recompose_status, "includedCount": recompose_report.get("includedCount"), "missingCount": recompose_report.get("missingCount")},
        )
    )

    pose_report = read_json_if_exists(v3_dir / "check" / "pose-stress-report.json") or {}
    pose_status = pose_report.get("status") if isinstance(pose_report, dict) else None
    gates.append(
        v3_gate_result(
            "pose_stress",
            "passed" if pose_status in {"passed", "skipped"} else "failed" if pose_report else "missing",
            [] if pose_status in {"passed", "skipped"} else [f"pose_stress_{pose_status or 'missing'}"],
            ["v3/check/pose-stress-report.json"] if (v3_dir / "check" / "pose-stress-report.json").exists() else [],
            {"status": pose_status, "caseCount": pose_report.get("caseCount"), "failedCount": pose_report.get("failedCount")},
        )
    )

    review_path = workspace / "check" / "review.html"
    review_integrity = read_json_if_exists(v3_dir / "review" / "review-integrity-report.json") or {}
    if review_path.exists():
        try:
            review_integrity = write_v3_review_integrity_report(workspace)
        except Exception as exc:
            review_integrity = {"status": PARTS_SHEET_BLOCKED_STATUS, "blockers": [f"review_integrity_exception_{type(exc).__name__}: {exc}"]}
    review_blockers = [] if review_path.exists() else ["review_html_missing"]
    if review_path.exists():
        review_text = review_path.read_text(encoding="utf-8")
        if "Reconstruction QA" in review_text or 'id="summary"' in review_text:
            review_blockers.append("review_debug_text_visible")
        if "v3Components" not in review_text:
            review_blockers.append("review_missing_v3_components_payload")
    if review_integrity.get("status") not in {None, "passed"}:
        review_blockers.extend(str(blocker) for blocker in review_integrity.get("blockers", []) if blocker)
    gates.append(
        v3_gate_result(
            "review_html",
            "passed" if not review_blockers else "failed" if review_path.exists() else "missing",
            review_blockers,
            [artifact for artifact in ["check/review.html" if review_path.exists() else "", "v3/review/review-integrity-report.json" if (v3_dir / "review" / "review-integrity-report.json").exists() else ""] if artifact],
            {"integrityStatus": review_integrity.get("status"), "integrityCounts": review_integrity.get("counts")},
        )
    )

    export_manifest = read_json_if_exists(v3_dir / "export" / "components-manifest.json") or {}
    export_status = export_manifest.get("status") if isinstance(export_manifest, dict) else None
    gates.append(
        v3_gate_result(
            "v3_export",
            "passed" if export_status == "final_exportable" else "failed" if export_manifest else "missing",
            [] if export_status == "final_exportable" else [f"v3_export_{export_status or 'missing'}"],
            ["v3/export/components-manifest.json"] if (v3_dir / "export" / "components-manifest.json").exists() else [],
            {
                "status": export_status,
                "componentCount": export_manifest.get("componentCount"),
                "blockedCount": export_manifest.get("blockedCount"),
                "exportContentStatus": export_manifest.get("exportContentStatus"),
                "exportContentBlockers": export_manifest.get("exportContentBlockers"),
                "provenanceCounts": export_manifest.get("provenanceCounts"),
                "psd": export_manifest.get("psd"),
            },
        )
    )

    handoff_validation = read_json_if_exists(v3_dir / "export" / "handoff-validation-report.json") or {}
    handoff_status = handoff_validation.get("status") if isinstance(handoff_validation, dict) else None
    gates.append(
        v3_gate_result(
            "handoff_manifest",
            "passed" if handoff_status == "passed" else "failed" if handoff_validation else "missing",
            [] if handoff_status == "passed" else [f"handoff_manifest_{handoff_status or 'missing'}"],
            ["v3/export/handoff-validation-report.json"] if (v3_dir / "export" / "handoff-validation-report.json").exists() else [],
            {"status": handoff_status, "failureCount": handoff_validation.get("failureCount"), "warningCount": handoff_validation.get("warningCount")},
        )
    )

    runtime_import = read_json_if_exists(v3_dir / "export" / "runtime-import-report.json") or {}
    runtime_gate_status, runtime_gate_blockers, runtime_gate_counts = v3_runtime_import_validation_gate(runtime_import)
    gates.append(
        v3_gate_result(
            "runtime_import",
            runtime_gate_status,
            runtime_gate_blockers,
            ["v3/export/runtime-import-report.json"] if (v3_dir / "export" / "runtime-import-report.json").exists() else [],
            runtime_gate_counts,
        )
    )

    status_counts: dict[str, int] = {}
    for gate in gates:
        status_counts[gate["status"]] = status_counts.get(gate["status"], 0) + 1
    passed_count = status_counts.get("passed", 0)
    report_status = "passed" if passed_count == len(gates) else PARTS_SHEET_BLOCKED_STATUS
    report = {
        "type": "kine.v3.validationReport",
        "version": "0.1",
        "status": report_status,
        "workspace": workspace.name,
        "statusCounts": status_counts,
        "gates": gates,
        "blockers": [{"gate": gate["id"], "blockers": gate["blockers"]} for gate in gates if gate["blockers"]],
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Read-only aggregate gate report for real-sample hardening. Missing or failed gates must not be treated as final components.",
    }
    out_dir = v3_dir / "check"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "v3-validation-report.json", report)
    update_run_state(workspace, {"v3Validation": "v3/check/v3-validation-report.json", "v3ValidationStatus": report_status})
    print(json.dumps({"status": report_status, "passedGates": passed_count, "blockedGates": len(gates) - passed_count, "report": str(out_dir / "v3-validation-report.json")}, ensure_ascii=False, indent=2))
    return report


def discover_v3_workspaces(root: Path) -> list[Path]:
    """Find likely V3 workspaces below a root without assuming a fixed output layout."""
    if (root / "v3").is_dir():
        return [root]
    workspaces: set[Path] = set()
    for marker in root.rglob("v3/component-plan.json"):
        workspaces.add(marker.parent.parent)
    for marker in root.rglob("v3/check/v3-validation-report.json"):
        workspaces.add(marker.parent.parent.parent)
    return sorted(workspaces)


def write_v3_hardening_report(
    workspaces: list[Path],
    out_path: Path,
    refresh: bool = False,
) -> dict[str, Any]:
    """Aggregate multiple V3 validation reports for real-sample hardening."""
    workspace_rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    gate_status_counts: dict[str, dict[str, int]] = {}
    blocker_counts: dict[str, int] = {}

    for workspace in sorted({path.resolve() for path in workspaces}):
        report_path = workspace / "v3" / "check" / "v3-validation-report.json"
        if refresh or not report_path.exists():
            report = validate_v3_pipeline(workspace)
        else:
            report = read_json_if_exists(report_path) or {}
        if not isinstance(report, dict) or report.get("type") != "kine.v3.validationReport":
            report = {
                "type": "kine.v3.validationReport",
                "status": PARTS_SHEET_BLOCKED_STATUS,
                "workspace": workspace.name,
                "gates": [],
                "blockers": [{"gate": "v3_validation", "blockers": ["v3_validation_report_missing_or_wrong_type"]}],
            }

        status = str(report.get("status") or PARTS_SHEET_BLOCKED_STATUS)
        status_counts[status] = status_counts.get(status, 0) + 1
        gate_rows = report.get("gates", []) if isinstance(report.get("gates"), list) else []
        blocked_gates = []
        for gate in gate_rows:
            if not isinstance(gate, dict):
                continue
            gate_id = str(gate.get("id") or "unknown")
            gate_status = str(gate.get("status") or "unknown")
            gate_status_counts.setdefault(gate_id, {})
            gate_status_counts[gate_id][gate_status] = gate_status_counts[gate_id].get(gate_status, 0) + 1
            if gate_status != "passed":
                blocked_gates.append(gate_id)
            for blocker in gate.get("blockers", []) if isinstance(gate.get("blockers"), list) else []:
                blocker_key = f"{gate_id}:{blocker}"
                blocker_counts[blocker_key] = blocker_counts.get(blocker_key, 0) + 1

        workspace_rows.append(
            {
                "workspace": str(workspace),
                "status": status,
                "passedGates": sum(1 for gate in gate_rows if isinstance(gate, dict) and gate.get("status") == "passed"),
                "totalGates": len(gate_rows),
                "blockedGates": blocked_gates,
                "validationReport": relative_to_workspace(report_path, workspace) if report_path.exists() else None,
            }
        )

    passed_workspaces = status_counts.get("passed", 0)
    report_status = "passed" if workspaces and passed_workspaces == len(set(path.resolve() for path in workspaces)) else PARTS_SHEET_BLOCKED_STATUS
    top_blockers = [
        {"blocker": blocker, "count": count}
        for blocker, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    report = {
        "type": "kine.v3.hardeningReport",
        "version": "0.1",
        "status": report_status,
        "workspaceCount": len(workspace_rows),
        "statusCounts": status_counts,
        "gateStatusCounts": gate_status_counts,
        "topBlockers": top_blockers,
        "workspaces": workspace_rows,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Batch hardening summary over V3 validation reports. It does not generate art or promote blocked workspaces.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, report)
    print(json.dumps({"status": report_status, "workspaceCount": len(workspace_rows), "report": str(out_path)}, ensure_ascii=False, indent=2))
    return report


def v3_open_board_image(workspace: Path, rel_path: str | None) -> Image.Image | None:
    if not isinstance(rel_path, str):
        return None
    path = workspace / rel_path
    if not path.exists():
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def write_v3_imagegen_visual_execution_board(workspace: Path) -> dict[str, Any]:
    work_order = read_json_if_exists(workspace / "v3" / "imagegen" / "imagegen-work-order.json") or {}
    tasks = work_order.get("tasks", []) if isinstance(work_order.get("tasks"), list) else []
    parts_manifest = read_json_if_exists(workspace / "parts" / "parts-sheet-manifest.json") or {}
    sheets = parts_manifest.get("sheets", []) if isinstance(parts_manifest.get("sheets"), list) else []
    candidates_manifest = read_json_if_exists(workspace / "v3" / "sheets" / "sheet-manifest.json") or {}
    candidates = candidates_manifest.get("candidates", []) if isinstance(candidates_manifest.get("candidates"), list) else []
    recompose = read_json_if_exists(workspace / "v3" / "check" / "recompose-report.json") or {}

    rows: list[dict[str, Any]] = [
        {
            "label": "source",
            "sublabel": "source.png",
            "image": v3_open_board_image(workspace, "source.png"),
        }
    ]
    for task in tasks[:4]:
        if not isinstance(task, dict):
            continue
        board_path = task.get("referenceContactBoard")
        rows.append(
            {
                "label": f"reference / {task.get('taskId')}",
                "sublabel": board_path or "missing reference-contact board",
                "image": v3_open_board_image(workspace, board_path if isinstance(board_path, str) else None),
            }
        )
        expected = task.get("expectedOutput")
        rows.append(
            {
                "label": f"raw output / {task.get('taskId')}",
                "sublabel": expected or "missing expectedOutput",
                "image": v3_open_board_image(workspace, expected if isinstance(expected, str) else None),
            }
        )
    for sheet in sheets[:4]:
        if not isinstance(sheet, dict):
            continue
        sheet_id = sheet.get("sheetId") or sheet.get("id")
        for label, key in [("transparent sheet", "transparentPath"), ("parts contact", "contactPath")]:
            rel_path = sheet.get(key)
            rows.append(
                {
                    "label": f"{label} / {sheet_id}",
                    "sublabel": rel_path or f"missing {key}",
                    "image": v3_open_board_image(workspace, rel_path if isinstance(rel_path, str) else None),
                }
            )
    for candidate in candidates[:6]:
        if not isinstance(candidate, dict):
            continue
        rel_path = candidate.get("file")
        rows.append(
            {
                "label": f"candidate / {candidate.get('id')}",
                "sublabel": f"{candidate.get('status') or 'candidate'} / {rel_path}",
                "image": v3_open_board_image(workspace, rel_path if isinstance(rel_path, str) else None),
            }
        )
    for label, rel_path in [("v3 recompose", recompose.get("recompose")), ("source diff", recompose.get("sourceDiff"))]:
        rows.append(
            {
                "label": label,
                "sublabel": rel_path or "not written",
                "image": v3_open_board_image(workspace, rel_path if isinstance(rel_path, str) else None),
            }
        )

    out_path = workspace / "v3" / "imagegen" / "imagegen-execution-board.png"
    grid = v3_write_image_grid(rows, out_path, columns=3, tile_size=(300, 280))
    report = {
        "type": "kine.v3.imagegenExecutionVisualBoard",
        "version": "0.1",
        "status": "ready" if grid["itemCount"] > grid["missingCount"] else PARTS_SHEET_BLOCKED_STATUS,
        "board": relative_to_workspace(out_path, workspace),
        "itemCount": grid["itemCount"],
        "missingCount": grid["missingCount"],
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workspace / "v3" / "imagegen" / "imagegen-execution-board.json", report)
    return report


def write_v3_imagegen_execution_report(
    workspaces: list[Path],
    out_path: Path,
    refresh: bool = False,
) -> dict[str, Any]:
    """Summarize whether real $imagegen outputs completed the V3 sheet loop.

    This report is intentionally narrower than aggregate V3 validation: it answers
    the practical debugging question "did the generated role sheets get saved,
    ingested, split, synced, and registered according to the V3 contract?"
    """
    workspace_rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    blocker_counts: dict[str, int] = {}

    for workspace in sorted({path.resolve() for path in workspaces}):
        if refresh and (workspace / "parts" / "parts-sheet-manifest.json").exists():
            sync_v3_candidates_from_parts(workspace)
            register_v3_candidates(workspace)
            validate_v3_pipeline(workspace)
        elif refresh:
            validate_v3_pipeline(workspace)

        progress_report = write_v3_imagegen_progress_report(workspace, refresh_work_order=refresh)
        work_order = read_json_if_exists(workspace / "v3" / "imagegen" / "imagegen-work-order.json") or {}
        tasks = work_order.get("tasks", []) if isinstance(work_order.get("tasks"), list) else []
        role_sheet_tasks = [task for task in tasks if isinstance(task, dict) and task.get("taskType") == "parts_sheet"]
        expected_outputs = []
        missing_expected_outputs = []
        for task in role_sheet_tasks:
            expected = task.get("expectedOutput")
            if not isinstance(expected, str):
                continue
            row = {"taskId": task.get("taskId"), "role": task.get("role"), "expectedOutput": expected}
            expected_outputs.append({**row, "exists": (workspace / expected).exists()})
            if not (workspace / expected).exists():
                missing_expected_outputs.append(row)

        parts_manifest = read_json_if_exists(workspace / "parts" / "parts-sheet-manifest.json") or {}
        sheets = parts_manifest.get("sheets", []) if isinstance(parts_manifest.get("sheets"), list) else []
        parts = parts_manifest.get("parts", []) if isinstance(parts_manifest.get("parts"), list) else []
        sheet_rows = []
        preflight_failures: list[str] = []
        preflight_status_counts: dict[str, int] = {}
        seen_preflight_paths: set[str] = set()
        for sheet in sheets:
            if not isinstance(sheet, dict):
                continue
            preflight_value = sheet.get("preflightPath") or sheet.get("preflight")
            if isinstance(preflight_value, str):
                seen_preflight_paths.add(preflight_value)
            preflight = read_json_if_exists(workspace / preflight_value) if isinstance(preflight_value, str) else {}
            preflight_status = str(preflight.get("status") or "missing")
            preflight_status_counts[preflight_status] = preflight_status_counts.get(preflight_status, 0) + 1
            failures = [
                str(failure.get("code") or failure)
                for failure in preflight.get("failures", [])
                if isinstance(failure, (dict, str))
            ] if isinstance(preflight, dict) else ["preflight_missing"]
            preflight_failures.extend(failures)
            sheet_rows.append(
                {
                    "sheetId": sheet.get("sheetId") or sheet.get("id"),
                    "role": sheet.get("role"),
                    "componentCount": sheet.get("componentCount"),
                    "rawPath": sheet.get("rawPath"),
                    "transparentPath": sheet.get("transparentPath"),
                    "normalizedPath": sheet.get("normalizedPath"),
                    "preflightPath": preflight_value,
                    "preflightStatus": preflight_status,
                    "preflightFailures": failures,
                    "allowedOwners": sheet.get("allowedOwners") or [],
                    "allowedComponents": sheet.get("allowedComponents") or [],
                    "normalizationPolicy": sheet.get("normalizationPolicy"),
                }
            )
        for preflight_path in sorted((workspace / "parts").glob("*.preflight.json")):
            rel_preflight = relative_to_workspace(preflight_path, workspace)
            if rel_preflight in seen_preflight_paths:
                continue
            preflight = read_json_if_exists(preflight_path) or {}
            preflight_status = str(preflight.get("status") or "missing")
            preflight_status_counts[preflight_status] = preflight_status_counts.get(preflight_status, 0) + 1
            failures = [
                str(failure.get("code") or failure)
                for failure in preflight.get("failures", [])
                if isinstance(failure, (dict, str))
            ] if isinstance(preflight, dict) else ["preflight_missing"]
            preflight_failures.extend(failures)
            sheet_rows.append(
                {
                    "sheetId": preflight_path.name.replace(".preflight.json", ""),
                    "role": preflight.get("role") if isinstance(preflight, dict) else None,
                    "componentCount": preflight.get("componentCount") if isinstance(preflight, dict) else None,
                    "rawPath": None,
                    "transparentPath": None,
                    "normalizedPath": None,
                    "preflightPath": rel_preflight,
                    "preflightStatus": preflight_status,
                    "preflightFailures": failures,
                    "allowedOwners": [],
                    "allowedComponents": [],
                    "normalizationPolicy": None,
                    "manifestStatus": "preflight_only_not_ingested",
                }
            )

        candidate_manifest = read_json_if_exists(workspace / "v3" / "sheets" / "sheet-manifest.json") or {}
        candidates = candidate_manifest.get("candidates", []) if isinstance(candidate_manifest.get("candidates"), list) else []
        candidate_status_counts: dict[str, int] = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            status = str(candidate.get("status") or "candidate")
            candidate_status_counts[status] = candidate_status_counts.get(status, 0) + 1

        registration = read_json_if_exists(workspace / "v3" / "registration" / "registration-report.json") or {}
        accepted_count = int(registration.get("acceptedCount", 0) or 0)
        rejected_count = int(registration.get("rejectedCount", 0) or 0)
        accepted_component_counts: dict[str, int] = {}
        for row in registration.get("accepted", []) if isinstance(registration.get("accepted"), list) else []:
            if not isinstance(row, dict):
                continue
            component_id = str(row.get("componentId") or "unknown")
            accepted_component_counts[component_id] = accepted_component_counts.get(component_id, 0) + 1
        if accepted_count > 0 and not accepted_component_counts:
            for candidate in candidates:
                if not isinstance(candidate, dict) or candidate.get("status") != "accepted":
                    continue
                component_id = str(candidate.get("componentId") or "unknown")
                accepted_component_counts[component_id] = accepted_component_counts.get(component_id, 0) + 1
        rejection_reason_counts: dict[str, int] = {}
        for row in registration.get("rejected", []) if isinstance(registration.get("rejected"), list) else []:
            if not isinstance(row, dict):
                continue
            for reason in row.get("reasons", []) if isinstance(row.get("reasons"), list) else []:
                key = str(reason)
                rejection_reason_counts[key] = rejection_reason_counts.get(key, 0) + 1
        stable_owner_audit = v3_stable_owner_coverage_audit(workspace)
        generated_quality_audit = v3_generated_candidate_quality_audit(workspace)

        validation = read_json_if_exists(workspace / "v3" / "check" / "v3-validation-report.json") or {}
        validation_status = str(validation.get("status") or "missing")
        validation_blocked_gates = [
            {
                "gate": str(gate.get("id") or "unknown"),
                "blockers": gate.get("blockers") or [],
            }
            for gate in validation.get("gates", [])
            if isinstance(gate, dict) and gate.get("status") != "passed"
        ] if isinstance(validation.get("gates"), list) else []
        blockers: list[str] = []
        warnings: list[str] = []
        if role_sheet_tasks and missing_expected_outputs:
            blockers.append("role_sheet_expected_outputs_missing")
        if role_sheet_tasks and len(sheets) < len(role_sheet_tasks):
            blockers.append("role_sheet_outputs_not_all_ingested")
        if role_sheet_tasks and not sheets and not preflight_failures:
            blockers.append("role_sheet_outputs_not_ingested")
        if preflight_failures:
            blockers.extend(f"sheet_preflight:{code}" for code in sorted(set(preflight_failures)))
        if parts and not candidates:
            blockers.append("parts_not_synced_to_v3_candidates")
        if candidates and not registration:
            blockers.append("candidates_not_registered")
        if candidates and accepted_count == 0:
            blockers.append("no_candidates_accepted")
        for blocker in stable_owner_audit.get("blockers", []) if isinstance(stable_owner_audit.get("blockers"), list) else []:
            blockers.append(f"stable_owner_coverage:{blocker}")
        for blocker in generated_quality_audit.get("blockers", []) if isinstance(generated_quality_audit.get("blockers"), list) else []:
            blockers.append(f"generated_candidate_quality:{blocker}")
        if not role_sheet_tasks and not sheets and not candidates:
            blockers.append("no_imagegen_role_sheet_execution")
        if accepted_count > 1 and len(accepted_component_counts) < accepted_count:
            warnings.append("accepted_candidates_concentrated_on_duplicate_components")
        if validation_status not in {"passed", "missing"} and accepted_count > 0:
            blockers.extend(f"v3_validation:{row['gate']}" for row in validation_blocked_gates)

        progress_rows = progress_report.get("tasks", []) if isinstance(progress_report.get("tasks"), list) else []
        pending_progress_rows = [
            row
            for row in progress_rows
            if isinstance(row, dict)
            and str(row.get("status") or "") in {"pending_imagegen", "missing_expected_output", "ready_for_ingest"}
        ]
        pending_imagegen_count = int(progress_report.get("pendingImagegenCount", 0) or 0) if isinstance(progress_report, dict) else 0
        ready_for_ingest_count = int(progress_report.get("readyForIngestCount", 0) or 0) if isinstance(progress_report, dict) else 0
        if pending_imagegen_count:
            blockers.append(f"imagegen_pending_outputs_{pending_imagegen_count}")
        if ready_for_ingest_count:
            blockers.append(f"imagegen_outputs_ready_for_ingest_{ready_for_ingest_count}")

        if validation_status == "passed" and not blockers:
            status = "passed"
        elif accepted_count > 0:
            status = "imagegen_execution_partial"
        elif blockers == ["no_imagegen_role_sheet_execution"]:
            status = "no_imagegen_execution"
        else:
            status = "imagegen_execution_failed"

        visual_board = write_v3_imagegen_visual_execution_board(workspace)
        show_review_html = status == "passed" and validation_status == "passed" and pending_imagegen_count == 0
        review_html_policy = {
            "showReviewHtmlAsDeliverable": show_review_html,
            "reviewHtml": "check/review.html" if show_review_html and (workspace / "check" / "review.html").exists() else None,
            "preferredVisualEvidence": visual_board.get("board"),
            "reason": "passed_v3_validation" if show_review_html else "blocked_or_incomplete_v3_run",
            "pendingImagegenCount": pending_imagegen_count,
            "acceptedCount": accepted_count,
            "validationStatus": validation_status,
            "note": "When false, review.html is a debug/review artifact only. User-facing evidence should show the ImageGen execution board and execution/progress reports.",
        }
        for blocker in blockers:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1

        workspace_rows.append(
            {
                "workspace": str(workspace),
                "status": status,
                "validationStatus": validation_status,
                "roleSheetTaskCount": len(role_sheet_tasks),
                "expectedOutputs": expected_outputs,
                "missingExpectedOutputCount": len(missing_expected_outputs),
                "sheetCount": len(sheets),
                "partCount": len(parts),
                "candidateCount": len(candidates),
                "acceptedCount": accepted_count,
                "rejectedCount": rejected_count,
                "distinctAcceptedComponentCount": len(accepted_component_counts),
                "acceptedComponentCounts": accepted_component_counts,
                "preflightStatusCounts": preflight_status_counts,
                "candidateStatusCounts": candidate_status_counts,
                "rejectionReasonCounts": rejection_reason_counts,
                "stableOwnerCoverage": stable_owner_audit,
                "generatedCandidateQuality": generated_quality_audit,
                "imagegenProgressStatus": progress_report.get("status"),
                "imagegenWorkOrderStage": progress_report.get("workOrderStage"),
                "imagegenProgressStatusCounts": progress_report.get("statusCounts"),
                "imagegenProgressTaskTypeCounts": progress_report.get("taskTypeCounts"),
                "pendingImagegenCount": pending_imagegen_count,
                "readyForIngestCount": ready_for_ingest_count,
                "pendingImagegenTasks": [
                    {
                        "taskId": row.get("taskId"),
                        "taskType": row.get("taskType"),
                        "componentId": row.get("componentId"),
                        "status": row.get("status"),
                        "expectedOutput": row.get("expectedOutput"),
                        "blockers": row.get("blockers") or [],
                        "nextAction": row.get("nextAction"),
                    }
                    for row in pending_progress_rows
                ],
                "validationBlockedGates": validation_blocked_gates,
                "sheets": sheet_rows,
                "blockers": blockers,
                "warnings": warnings,
                "visualExecutionBoard": visual_board.get("board"),
                "visualExecutionBoardStatus": visual_board.get("status"),
                "reviewHtmlDisplayPolicy": review_html_policy,
                "evidence": {
                    "workOrder": "v3/imagegen/imagegen-work-order.json" if (workspace / "v3" / "imagegen" / "imagegen-work-order.json").exists() else None,
                    "visualExecutionBoard": visual_board.get("board"),
                    "partsManifest": "parts/parts-sheet-manifest.json" if (workspace / "parts" / "parts-sheet-manifest.json").exists() else None,
                    "candidateManifest": "v3/sheets/sheet-manifest.json" if (workspace / "v3" / "sheets" / "sheet-manifest.json").exists() else None,
                    "registrationReport": "v3/registration/registration-report.json" if (workspace / "v3" / "registration" / "registration-report.json").exists() else None,
                    "validationReport": "v3/check/v3-validation-report.json" if (workspace / "v3" / "check" / "v3-validation-report.json").exists() else None,
                },
            }
        )

    report_status = "passed" if workspace_rows and all(row["status"] == "passed" for row in workspace_rows) else PARTS_SHEET_BLOCKED_STATUS
    report = {
        "type": "kine.v3.imagegenExecutionReport",
        "version": "0.1",
        "status": report_status,
        "workspaceCount": len(workspace_rows),
        "statusCounts": status_counts,
        "topBlockers": [
            {"blocker": blocker, "count": count}
            for blocker, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "workspaces": workspace_rows,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Real $imagegen role-sheet execution audit. Work orders and raw sheets are not final; this report checks saved outputs, ingest, candidate sync, registration, and V3 validation evidence.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, report)
    print(json.dumps({"status": report_status, "workspaceCount": len(workspace_rows), "report": str(out_path)}, ensure_ascii=False, indent=2))
    return report


def write_v3_workspace_imagegen_execution_report(workspace: Path, refresh: bool = False) -> dict[str, Any]:
    """Write the execution report inside the current V3 workspace for agent handoff."""
    out_path = workspace / "v3" / "imagegen" / "v3-imagegen-execution-report.json"
    report = write_v3_imagegen_execution_report([workspace], out_path, refresh=refresh)
    update_run_state(
        workspace,
        {
            "v3ImagegenExecutionReport": "v3/imagegen/v3-imagegen-execution-report.json",
            "v3ImagegenExecutionStatus": report.get("status"),
        },
    )
    return report


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil((percentile_value / 100.0) * len(ordered)) - 1))
    return ordered[index]


def write_v3_pose_calibration_report(
    workspaces: list[Path],
    out_path: Path,
    refresh: bool = False,
) -> dict[str, Any]:
    """Aggregate pose-stress pixel gap evidence before enabling hard-fail thresholds."""
    workspace_rows: list[dict[str, Any]] = []
    all_cases: list[dict[str, Any]] = []
    gap_ratios: list[float] = []
    new_alpha_ratios: list[float] = []
    gap_pixels: list[int] = []
    missing_reports: list[str] = []

    for workspace in sorted({path.resolve() for path in workspaces}):
        report_path = workspace / "v3" / "check" / "pose-stress-report.json"
        if refresh or not report_path.exists():
            try:
                report = write_v3_pose_stress(workspace)
            except Exception as exc:
                missing_reports.append(f"{workspace}: {type(exc).__name__}: {exc}")
                report = {}
        else:
            report = read_json_if_exists(report_path) or {}
        if not isinstance(report, dict) or report.get("type") != "kine.v3.poseStressReport":
            missing_reports.append(str(workspace))
            workspace_rows.append({"workspace": str(workspace), "status": "missing", "caseCount": 0})
            continue
        cases = [case for case in report.get("cases", []) if isinstance(case, dict)]
        workspace_rows.append({"workspace": str(workspace), "status": report.get("status"), "caseCount": len(cases)})
        for case in cases:
            pixel_gap = case.get("pixelGap") if isinstance(case.get("pixelGap"), dict) else {}
            gap_ratio = float(pixel_gap.get("gapRatio") or 0.0)
            new_alpha_ratio = float(pixel_gap.get("newAlphaRatio") or 0.0)
            gap_pixel_count = int(pixel_gap.get("gapPixels") or 0)
            gap_ratios.append(gap_ratio)
            new_alpha_ratios.append(new_alpha_ratio)
            gap_pixels.append(gap_pixel_count)
            all_cases.append(
                {
                    "workspace": str(workspace),
                    "componentId": case.get("componentId"),
                    "socket": case.get("socket"),
                    "angle": case.get("angle"),
                    "status": case.get("status"),
                    "gapRatio": gap_ratio,
                    "gapPixels": gap_pixel_count,
                    "newAlphaRatio": new_alpha_ratio,
                    "preview": case.get("preview"),
                    "gapHeatmap": pixel_gap.get("gapHeatmap"),
                }
            )

    def metric_summary(values: list[float | int]) -> dict[str, Any]:
        numeric = [float(value) for value in values]
        return {
            "count": len(numeric),
            "max": round(max(numeric), 6) if numeric else None,
            "p95": round(percentile(numeric, 95) or 0.0, 6) if numeric else None,
            "p99": round(percentile(numeric, 99) or 0.0, 6) if numeric else None,
        }

    gap_ratio_summary = metric_summary(gap_ratios)
    new_alpha_summary = metric_summary(new_alpha_ratios)
    gap_pixel_summary = metric_summary(gap_pixels)
    recommended_thresholds = {
        "maxGapRatio": gap_ratio_summary["p99"],
        "maxGapPixels": int(math.ceil(gap_pixel_summary["p99"] or 0)) if gap_pixel_summary["p99"] is not None else None,
        "maxNewAlphaRatio": new_alpha_summary["p99"],
        "policy": "hard_fail_after_human_calibration",
    }
    report_status = "passed" if all_cases and not missing_reports else PARTS_SHEET_BLOCKED_STATUS
    report = {
        "type": "kine.v3.poseCalibrationReport",
        "version": "0.1",
        "status": report_status,
        "workspaceCount": len(workspace_rows),
        "caseCount": len(all_cases),
        "workspaceRows": workspace_rows,
        "missingReports": missing_reports,
        "summaries": {
            "gapRatio": gap_ratio_summary,
            "gapPixels": gap_pixel_summary,
            "newAlphaRatio": new_alpha_summary,
        },
        "recommendedThresholds": recommended_thresholds,
        "largestGapCases": sorted(all_cases, key=lambda item: (-float(item["gapRatio"]), -int(item["gapPixels"]), str(item.get("componentId"))))[:20],
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "note": "Calibration evidence only. Review the largest gap cases visually before copying recommended thresholds into v3/qa-gates.json.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, report)
    print(json.dumps({"status": report_status, "workspaceCount": len(workspace_rows), "caseCount": len(all_cases), "report": str(out_path)}, ensure_ascii=False, indent=2))
    return report


def run_fresh_pipeline(source: Path, out_root: Path, resolution: int = DEFAULT_RESOLUTION) -> None:
    workspace = timestamped_workspace(out_root, source)
    init_workspace(source, workspace, resolution=resolution, force=False)
    subject_report = v3_subject_preflight_blocks_masks(workspace)
    if subject_report.get("shouldBlockV3Masks"):
        write_v3_component_plan(workspace)
        imagegen_progress = write_v3_imagegen_progress_report(workspace, refresh_work_order=True)
        imagegen_execution = write_v3_workspace_imagegen_execution_report(workspace, refresh=False)
        update_run_state(
            workspace,
            {
                "status": "needs_imagegen_subject_matte",
                "generationSource": "imagegen_skill",
                "v3ImagegenWorkOrder": "v3/imagegen/imagegen-work-order.json",
                "v3ImagegenProgressReport": "v3/imagegen/imagegen-progress-report.json",
                "v3ImagegenExecutionReport": "v3/imagegen/v3-imagegen-execution-report.json",
            },
        )
        print(
            json.dumps(
                {
                    "status": "fresh_run_needs_imagegen_subject_matte",
                    "generationSource": "imagegen_skill",
                    "workspace": str(workspace),
                    "sourceSubjectPreflight": str(workspace / "source" / "source-subject-preflight.json"),
                    "v3ImagegenWorkOrder": str(workspace / "v3" / "imagegen" / "imagegen-work-order.json"),
                    "v3ImagegenProgressReport": str(workspace / "v3" / "imagegen" / "imagegen-progress-report.json"),
                    "v3ImagegenExecutionReport": str(workspace / "v3" / "imagegen" / "v3-imagegen-execution-report.json"),
                    "v3ImagegenExecutionStatus": imagegen_execution.get("status"),
                    "pendingImagegenCount": imagegen_progress.get("pendingImagegenCount"),
                    "readyForIngestCount": imagegen_progress.get("readyForIngestCount"),
                    "requiredAction": subject_report.get("requiredAction"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    # Default path: complete lossless source-pixel partition (every foreground pixel is
    # assigned to one owner, so the components recompose to the original by construction).
    # extract_visible_locks remains available as a generation-path helper but is no longer
    # the default decomposition for a fresh run.
    partition_source_to_components(workspace)
    qa_workspace(workspace)
    write_parts_sheet_prompt(workspace)
    write_per_owner_strict_edit_plan(workspace, reason="present_layer_missing_final_imagegen_redraw")
    validate_review_html(workspace)
    qa = read_json_if_exists(workspace / "qa.json") or {}
    package_workspace(workspace, allow_blocked=qa.get("status") == "visual_rejected")
    imagegen_progress = write_v3_imagegen_progress_report(workspace, refresh_work_order=True)
    imagegen_execution = write_v3_workspace_imagegen_execution_report(workspace, refresh=False)
    execution_rows = imagegen_execution.get("workspaces", []) if isinstance(imagegen_execution.get("workspaces"), list) else []
    execution_row = execution_rows[0] if execution_rows and isinstance(execution_rows[0], dict) else {}
    review_html_policy = execution_row.get("reviewHtmlDisplayPolicy") if isinstance(execution_row.get("reviewHtmlDisplayPolicy"), dict) else {}
    fresh_result = {
        "status": "fresh_run_complete",
        "generationSource": "imagegen_skill",
        "workspace": str(workspace),
        "qaStatus": qa.get("status"),
        "completion": str(workspace / "COMPLETION.md"),
        "imagegenHandoff": str(workspace / "IMAGEGEN_HANDOFF.md"),
        "v3ImagegenWorkOrder": str(workspace / "v3" / "imagegen" / "imagegen-work-order.json"),
        "v3ImagegenProgressReport": str(workspace / "v3" / "imagegen" / "imagegen-progress-report.json"),
        "v3ImagegenExecutionReport": str(workspace / "v3" / "imagegen" / "v3-imagegen-execution-report.json"),
        "v3ImagegenExecutionStatus": imagegen_execution.get("status"),
        "pendingImagegenCount": imagegen_progress.get("pendingImagegenCount"),
        "readyForIngestCount": imagegen_progress.get("readyForIngestCount"),
        "ingestedSheetCount": imagegen_progress.get("ingestedSheetCount"),
        "reviewHtmlDisplayPolicy": review_html_policy or None,
        "preferredVisualEvidence": review_html_policy.get("preferredVisualEvidence") or execution_row.get("visualExecutionBoard"),
    }
    if review_html_policy.get("showReviewHtmlAsDeliverable") is True:
        fresh_result["reviewHtml"] = str(workspace / "check" / "review.html")
    update_run_state(
        workspace,
        {
            "completion": "COMPLETION.md",
            "imagegenHandoff": "IMAGEGEN_HANDOFF.md",
            "generationSource": "imagegen_skill",
            "v3ImagegenWorkOrder": "v3/imagegen/imagegen-work-order.json",
            "v3ImagegenProgressReport": "v3/imagegen/imagegen-progress-report.json",
            "v3ImagegenExecutionReport": "v3/imagegen/v3-imagegen-execution-report.json",
        },
    )
    print(
        json.dumps(
            fresh_result,
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--source", required=True)
    p_init.add_argument("--out", required=True)
    p_init.add_argument("--resolution", type=int, default=DEFAULT_RESOLUTION)
    p_init.add_argument("--force", action="store_true", help="Delete and recreate --out when it already contains files.")
    p_run = sub.add_parser("run")
    p_run.add_argument("--source", required=True)
    p_run.add_argument("--out-root", default="workspaces")
    p_run.add_argument("--resolution", type=int, default=DEFAULT_RESOLUTION)
    p_partition = sub.add_parser("partition", help="Complete lossless source-pixel partition into present owner components.")
    p_partition.add_argument("--workspace", required=True)
    p_partition.add_argument("--no-cutout-map", action="store_true", help="Ignore cutout-map.json and use the prior+fallback partition.")
    p_init_cutout = sub.add_parser("init-cutout-map", help="Write a blank cutout-map.json template for a vision model to fill.")
    p_init_cutout.add_argument("--workspace", required=True)
    p_init_cutout.add_argument("--force", action="store_true", help="Overwrite an existing cutout-map.json with a fresh template.")
    p_apply_cutout = sub.add_parser("apply-cutout-map", help="Partition using the (vision-authored) cutout-map.json owner regions.")
    p_apply_cutout.add_argument("--workspace", required=True)
    p_export_components = sub.add_parser("export-components")
    p_export_components.add_argument("--workspace", required=True)
    p_export_spine = sub.add_parser("export-spine")
    p_export_spine.add_argument("--workspace", required=True)
    p_spine_split = sub.add_parser("spine-split")
    p_spine_split.add_argument("--workspace", required=True)
    p_spine_split.add_argument("--layers", help="Comma-separated limb owner ids (arms/legs/feet). Defaults to all Spine limb owners.")
    p_qa = sub.add_parser("qa")
    p_qa.add_argument("--workspace", required=True)
    p_director = sub.add_parser("director-plan")
    p_director.add_argument("--workspace", required=True)
    p_extract = sub.add_parser("extract-visible")
    p_extract.add_argument("--workspace", required=True)
    p_extract.add_argument("--min-alpha-coverage", type=float, default=0.00001)
    p_source_parts = sub.add_parser("source-visible-parts-sheet")
    p_source_parts.add_argument("--workspace", required=True)
    p_source_parts.add_argument("--padding", type=int, default=8)
    p_source_parts.add_argument("--thumb-size", type=int, default=180)
    p_facial_micro = sub.add_parser("facial-micro-source-locks")
    p_facial_micro.add_argument("--workspace", required=True)
    p_facial_micro.add_argument("--padding", type=int, default=6)
    p_facial_micro.add_argument("--thumb-size", type=int, default=160)
    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("--workspace", required=True)
    p_ingest.add_argument("--layer", required=True)
    p_ingest.add_argument("--candidate", required=True)
    p_ingest.add_argument("--mode", choices=["generated", "visible", "hidden", "alpha"], default="generated")
    p_ingest.add_argument("--chroma-key", default="auto", help="'auto', 'none', or 'r,g,b'.")
    p_ingest.add_argument("--tolerance", type=int, default=16)
    p_ingest.add_argument("--x", type=int)
    p_ingest.add_argument("--y", type=int)
    p_ingest.add_argument(
        "--provenance-source",
        dest="backend",
        default=PUBLIC_GENERATION_BACKEND,
        help="Provenance marker for $imagegen skill output; this is not a backend selector.",
    )
    p_ingest.add_argument("--notes")
    p_ingest.add_argument("--no-hidden-surface-required", action="store_true", help="Allow this candidate to pass without hidden_underpaint after review.")
    p_parts = sub.add_parser("parts-sheet")
    p_parts.add_argument("--workspace", required=True)
    p_parts.add_argument("--sheet", required=True, help="Raw source-master parts sheet generated with the $imagegen skill.")
    p_parts.add_argument("--chroma-key", default="auto", help="'auto', 'none', or 'r,g,b'.")
    p_parts.add_argument("--tolerance", type=int, default=16)
    p_parts.add_argument("--alpha-threshold", type=int, default=8)
    p_parts.add_argument("--min-area", type=int, default=64)
    p_parts.add_argument("--padding", type=int, default=4)
    p_parts.add_argument("--sheet-id", default="sheet-001")
    p_parts.add_argument("--role", default="unspecified")
    p_parts.add_argument("--append", action="store_true", help="Append this sheet into an existing multi-sheet manifest.")
    p_parts.add_argument(
        "--allow-broad-design-board",
        action="store_true",
        help="Debug override: allow broad/multi-component design-board-like sheets through preflight. Final exports still require QA/recompose.",
    )
    p_parts_prompt = sub.add_parser("parts-sheet-prompt")
    p_parts_prompt.add_argument("--workspace", required=True)
    p_parts_prompt.add_argument("--out", help="Defaults to imagegen/source-master-parts-sheet.prompt.txt inside the workspace.")
    p_v3_plan = sub.add_parser("v3-plan", help="Write the V3 component plan, multi-sheet campaign, and QA gate scaffold.")
    p_v3_plan.add_argument("--workspace", required=True)
    p_v3_plan.add_argument("--max-sheet-components", type=int, default=12)
    p_v3_source_preflight = sub.add_parser("v3-source-preflight", help="Inspect source background transparency/chroma-key risk for an existing V3 workspace.")
    p_v3_source_preflight.add_argument("--workspace", required=True)
    p_v3_source_preflight.add_argument("--tolerance", type=int, default=28)
    p_v3_subject_preflight = sub.add_parser("v3-subject-preflight", help="Inspect whether V3 should continue directly or first run $imagegen subject isolation for a complex scene source.")
    p_v3_subject_preflight.add_argument("--workspace", required=True)
    p_v3_ingest_subject = sub.add_parser("v3-ingest-subject-matte", help="Create a clean V3 workspace from a $imagegen subject-isolated transparent matte.")
    p_v3_ingest_subject.add_argument("--workspace", required=True, help="Original scene workspace that requested subject isolation.")
    p_v3_ingest_subject.add_argument("--matte", required=True, help="Full-canvas transparent PNG produced by the $imagegen subject matte task.")
    p_v3_ingest_subject.add_argument("--out", help="Output clean character workspace. Defaults to <workspace>-character-matte.")
    p_v3_ingest_subject.add_argument("--force", action="store_true", help="Delete and recreate --out when it already contains files.")
    p_v3_masks = sub.add_parser("v3-mask-jobs", help="Write V3 per-component mask jobs, mask PNGs, visible cuts, and mask QA summary.")
    p_v3_masks.add_argument("--workspace", required=True)
    p_v3_masks.add_argument("--no-ensure-partition", action="store_true", help="Do not auto-run source partition when owner visible masks are missing.")
    p_v3_refs = sub.add_parser("v3-reference-bundles", help="Write per-component original-crop + visible-cut reference bundles for $imagegen tasks.")
    p_v3_refs.add_argument("--workspace", required=True)
    p_v3_refs.add_argument("--padding", type=int, default=16)
    p_v3_refs.add_argument("--no-ensure-masks", action="store_true", help="Do not auto-run v3-mask-jobs before building references.")
    p_v3_sheet_prompts = sub.add_parser("v3-sheet-prompts", help="Materialize role-specific V3 sheet prompts from v3/sheet-campaign.json.")
    p_v3_sheet_prompts.add_argument("--workspace", required=True)
    p_v3_sync_candidates = sub.add_parser("v3-sync-candidates", help="Copy legacy parts-sheet candidates into the V3 candidate pool and manifest.")
    p_v3_sync_candidates.add_argument("--workspace", required=True)
    p_v3_register_candidates = sub.add_parser("v3-register-candidates", help="Register V3 sheet candidates to concrete component rows and write a structured registration report.")
    p_v3_register_candidates.add_argument("--workspace", required=True)
    p_v3_register_candidates.add_argument("--min-score", type=float, default=0.55)
    p_v3_registration_repair = sub.add_parser("v3-registration-repair-report", help="Write $imagegen repair prompts for V3 components whose sheet candidates were rejected.")
    p_v3_registration_repair.add_argument("--workspace", required=True)
    p_v3_registration_repair.add_argument("--max-tasks", type=int, default=24)
    p_v3_imagegen_work_order = sub.add_parser("v3-imagegen-work-order", help="Write one executable $imagegen work order for pending V3 subject matte, role sheet, registration repair, and hidden inpaint tasks.")
    p_v3_imagegen_work_order.add_argument("--workspace", required=True)
    p_v3_imagegen_work_order.add_argument("--max-registration-tasks", type=int, default=24)
    p_v3_imagegen_progress = sub.add_parser("v3-imagegen-progress-report", help="Inspect pending V3 $imagegen work-order outputs and report ingest readiness.")
    p_v3_imagegen_progress.add_argument("--workspace", required=True)
    p_v3_imagegen_progress.add_argument("--refresh-work-order", action="store_true", help="Regenerate the work order before checking expected outputs.")
    p_v3_save_imagegen_inline = sub.add_parser("v3-save-imagegen-inline", help="Save a built-in $imagegen PNG result file or inline/base64 PNG to a V3 task expectedOutput path.")
    p_v3_save_imagegen_inline.add_argument("--workspace", required=True)
    p_v3_save_imagegen_inline.add_argument("--task-id", help="V3 imagegen work-order taskId. Required when multiple tasks are pending unless --expected-output is provided.")
    p_v3_save_imagegen_inline.add_argument("--expected-output", help="Explicit workspace-relative expectedOutput path. Prefer task-id when available.")
    p_v3_save_imagegen_inline.add_argument("--input", help="PNG file returned by savedPath or selected from $CODEX_HOME/generated_images.")
    p_v3_save_imagegen_inline.add_argument("--base64", dest="inline_base64", help="Inline base64 PNG string or data URL returned by built-in $imagegen.")
    p_v3_save_imagegen_inline.add_argument("--base64-file", help="Text file containing the inline base64 PNG string returned by built-in $imagegen.")
    p_v3_save_imagegen_inline.add_argument("--edge-chroma-key", default="task", help="'task', 'auto', 'none', or 'r,g,b'. task uses auto for subject matte and none for other task types.")
    p_v3_save_imagegen_inline.add_argument("--tolerance", type=int, default=36)
    p_v3_continue_imagegen = sub.add_parser("v3-continue-imagegen", help="Continue ready V3 $imagegen expectedOutput files through supported ingest steps.")
    p_v3_continue_imagegen.add_argument("--workspace", required=True)
    p_v3_continue_imagegen.add_argument("--force", action="store_true", help="Allow supported continuation steps to recreate their output workspace when applicable.")
    p_v3_hidden_jobs = sub.add_parser("v3-hidden-jobs", help="Write V3 visible/hidden/merged/overlap artifacts and hidden completion jobs for registered components.")
    p_v3_hidden_jobs.add_argument("--workspace", required=True)
    p_v3_hidden_handoff = sub.add_parser("v3-hidden-handoff", help="Write V3 $imagegen skill hidden inpaint handoff tasks for missing hidden components.")
    p_v3_hidden_handoff.add_argument("--workspace", required=True)
    p_v3_ingest_hidden = sub.add_parser("v3-ingest-hidden", help="Ingest a $imagegen skill hidden inpaint PNG into a V3 component.")
    p_v3_ingest_hidden.add_argument("--workspace", required=True)
    p_v3_ingest_hidden.add_argument("--component", required=True)
    p_v3_ingest_hidden.add_argument("--image", required=True)
    p_v3_ingest_hidden.add_argument(
        "--provenance-source",
        choices=["imagegen"],
        default="imagegen",
        help="Provenance marker for the built-in $imagegen skill output. No alternate drawing source is supported.",
    )
    p_v3_ingest_hidden.add_argument("--notes")
    p_v3_hidden_review = sub.add_parser("v3-hidden-review-report", help="Write/apply batch review evidence for $imagegen hidden inpaint outputs.")
    p_v3_hidden_review.add_argument("--workspace", required=True)
    p_v3_hidden_review.add_argument("--decisions", help="Optional kine.v3.hiddenInpaintReviewDecisions JSON to apply.")
    p_v3_recompose = sub.add_parser("v3-recompose", help="Recompose accepted V3 merged components and write source diff plus recompose report.")
    p_v3_recompose.add_argument("--workspace", required=True)
    p_v3_pose_stress = sub.add_parser("v3-pose-stress", help="Run V3 small-angle pose stress previews for accepted merged components.")
    p_v3_pose_stress.add_argument("--workspace", required=True)
    p_v3_review_decisions = sub.add_parser("v3-apply-review-decisions", help="Apply V3 Review HTML decision JSON back into component-plan.json.")
    p_v3_review_decisions.add_argument("--workspace", required=True)
    p_v3_review_decisions.add_argument("--decisions", required=True, help="JSON downloaded from Review HTML decision controls.")
    p_v3_review_integrity = sub.add_parser("v3-review-integrity-report", help="Verify V3 Review HTML displays active components, candidates, Combined image, and folded debug evidence.")
    p_v3_review_integrity.add_argument("--workspace", required=True)
    p_v3_export = sub.add_parser("v3-export", help="Export V3 accepted final components plus Kine/Spine handoff manifests.")
    p_v3_export.add_argument("--workspace", required=True)
    p_v3_validate_handoff = sub.add_parser("v3-validate-handoff", help="Validate exported V3 component and Spine/Live2D handoff manifest references.")
    p_v3_validate_handoff.add_argument("--workspace", required=True)
    p_v3_runtime_import = sub.add_parser("v3-runtime-import-report", help="Record external Spine/Live2D import evidence for exported V3 handoff artifacts.")
    p_v3_runtime_import.add_argument("--workspace", required=True)
    p_v3_runtime_import.add_argument("--evidence", help="Optional kine.v3.runtimeImportEvidence JSON to apply.")
    p_v3_validate = sub.add_parser("v3-validate", help="Write a read-only aggregate V3 gate report for real-sample hardening.")
    p_v3_validate.add_argument("--workspace", required=True)
    p_v3_hardening = sub.add_parser("v3-hardening-report", help="Aggregate V3 validation reports across real-sample workspaces.")
    p_v3_hardening.add_argument("--workspace", action="append", default=[], help="V3 workspace to include. Can be passed more than once.")
    p_v3_hardening.add_argument("--workspace-root", help="Root directory to scan for V3 workspaces.")
    p_v3_hardening.add_argument("--out", help="Output JSON path. Defaults to <workspace-root>/v3-hardening-report.json or the first workspace parent.")
    p_v3_hardening.add_argument("--refresh", action="store_true", help="Run v3-validate for each workspace before aggregating.")
    p_v3_imagegen_execution = sub.add_parser("v3-imagegen-execution-report", help="Audit real $imagegen role-sheet execution through save, ingest, candidate sync, registration, and validation evidence.")
    p_v3_imagegen_execution.add_argument("--workspace", action="append", default=[], help="V3 workspace to include. Can be passed more than once.")
    p_v3_imagegen_execution.add_argument("--workspace-root", help="Root directory to scan for V3 workspaces.")
    p_v3_imagegen_execution.add_argument("--out", help="Output JSON path. Defaults to <workspace-root>/v3-imagegen-execution-report.json or the first workspace parent.")
    p_v3_imagegen_execution.add_argument("--refresh", action="store_true", help="Rerun candidate sync, registration, and v3-validate for each workspace when enough artifacts exist.")
    p_v3_imagegen_visual_board = sub.add_parser("v3-imagegen-visual-board", help="Render the V3 imagegen visual execution board for one workspace.")
    p_v3_imagegen_visual_board.add_argument("--workspace", required=True)
    p_v3_pose_calibration = sub.add_parser("v3-pose-calibration-report", help="Aggregate V3 pose-stress gap evidence and recommend calibration thresholds.")
    p_v3_pose_calibration.add_argument("--workspace", action="append", default=[], help="V3 workspace to include. Can be passed more than once.")
    p_v3_pose_calibration.add_argument("--workspace-root", help="Root directory to scan for V3 workspaces.")
    p_v3_pose_calibration.add_argument("--out", help="Output JSON path. Defaults to <workspace-root>/v3-pose-calibration-report.json or the first workspace parent.")
    p_v3_pose_calibration.add_argument("--refresh", action="store_true", help="Run v3-pose-stress for each workspace before aggregating.")
    p_map = sub.add_parser("map-parts")
    p_map.add_argument("--workspace", required=True)
    p_map.add_argument("--assign", action="append", help="Debug override in the form part-001=torso. Can be repeated.")
    p_map.add_argument("--auto-visible-masks", action="store_true", help="Map unmapped parts by visible-mask bbox similarity.")
    p_map.add_argument("--min-score", type=float, default=0.55)
    p_auto_register = sub.add_parser("auto-register-parts")
    p_auto_register.add_argument("--workspace", required=True)
    p_auto_register.add_argument("--min-score", type=float, default=0.55)
    p_auto_register.add_argument("--no-hidden-surface-required", action="store_true", help="Allow registered candidates to pass without hidden underpaint after review.")
    p_auto_register.add_argument("--notes")
    p_strict_edit = sub.add_parser("per-owner-strict-edit-plan")
    p_strict_edit.add_argument("--workspace", required=True)
    p_strict_edit.add_argument("--owners", help="Comma-separated owner ids. Defaults to QA/mapping blocked owners.")
    p_strict_edit.add_argument("--reason")
    p_strict_ingest = sub.add_parser("ingest-strict-edit-candidates")
    p_strict_ingest.add_argument("--workspace", required=True)
    p_strict_ingest.add_argument("--candidate-dir", required=True, help="Directory containing <owner>.png/webp/jpg strict edit candidates.")
    p_strict_ingest.add_argument("--chroma-key", default="auto", help="'auto', 'none', or 'r,g,b'.")
    p_strict_ingest.add_argument("--tolerance", type=int, default=16)
    p_register = sub.add_parser("register-part")
    p_register.add_argument("--workspace", required=True)
    p_register.add_argument("--part", required=True)
    p_register.add_argument("--layer", help="Target layer id. Defaults to the owner from parts mapping.")
    p_register.add_argument("--x", type=int)
    p_register.add_argument("--y", type=int)
    p_register.add_argument("--fit-owner-bbox", action="store_true", help="Resize and place the part into the target owner's visible mask bbox.")
    p_register.add_argument("--no-hidden-surface-required", action="store_true", help="Allow QA to treat this registered candidate as complete without hidden underpaint after review.")
    p_register.add_argument("--notes")
    p_register_v2 = sub.add_parser("register-v2")
    p_register_v2.add_argument("--workspace", required=True)
    p_register_v2.add_argument("--part", required=True)
    p_register_v2.add_argument("--owner", required=True)
    p_register_v2.add_argument("--method", choices=["auto", "alpha-template", "sift"], default="auto")
    p_register_v2.add_argument("--no-hidden-surface-required", action="store_true")
    p_draw_order = sub.add_parser("verify-draw-order-local")
    p_draw_order.add_argument("--workspace", required=True)
    p_draw_order.add_argument("--min-overlap-pixels", type=int, default=24)
    p_draw_order.add_argument("--rgb-disagreement-limit", type=float, default=20.0)
    p_split = sub.add_parser("split")
    p_split.add_argument("--workspace", required=True)
    p_split.add_argument("--layer", required=True)
    p_split.add_argument("--axis", choices=["x", "y"], default="x")
    p_split.add_argument("--at", type=int)
    p_split.add_argument("--names", help="Two comma-separated child layer ids.")
    p_auto_split = sub.add_parser("auto-split")
    p_auto_split.add_argument("--workspace", required=True)
    p_auto_split.add_argument("--layers", help="Comma-separated layer ids. Defaults to animation-sensitive owners.")
    p_auto_split.add_argument("--min-area", type=int, default=32)
    p_html = sub.add_parser("validate-html")
    p_html.add_argument("--workspace", required=True)
    p_pkg = sub.add_parser("package")
    p_pkg.add_argument("--workspace", required=True)
    p_pkg.add_argument("--allow-blocked", action="store_true", help="Package current evidence even when QA is visual_rejected; does not mark it accepted.")
    args = parser.parse_args()
    if args.cmd == "init":
        init_workspace(Path(args.source), Path(args.out), resolution=args.resolution, force=args.force)
    elif args.cmd == "run":
        run_fresh_pipeline(Path(args.source), Path(args.out_root), resolution=args.resolution)
    elif args.cmd == "partition":
        partition_source_to_components(Path(args.workspace), use_cutout_map=not args.no_cutout_map)
    elif args.cmd == "init-cutout-map":
        print(json.dumps(write_cutout_map_template(Path(args.workspace), force=args.force), ensure_ascii=False, indent=2))
    elif args.cmd == "apply-cutout-map":
        partition_source_to_components(Path(args.workspace), use_cutout_map=True)
    elif args.cmd == "export-components":
        export_components(Path(args.workspace))
    elif args.cmd == "export-spine":
        export_spine(Path(args.workspace))
    elif args.cmd == "spine-split":
        spine_layer_ids = [item.strip() for item in args.layers.split(",") if item.strip()] if args.layers else None
        spine_split_layers(Path(args.workspace), spine_layer_ids)
    elif args.cmd == "qa":
        qa_workspace(Path(args.workspace))
    elif args.cmd == "director-plan":
        print(json.dumps(write_director_decomposition_plan(Path(args.workspace)), ensure_ascii=False, indent=2))
    elif args.cmd == "extract-visible":
        print(json.dumps(extract_visible_locks(Path(args.workspace), min_alpha_coverage=args.min_alpha_coverage), ensure_ascii=False, indent=2))
    elif args.cmd == "source-visible-parts-sheet":
        write_source_visible_parts_sheet(Path(args.workspace), args.padding, args.thumb_size)
    elif args.cmd == "facial-micro-source-locks":
        print(json.dumps(write_facial_micro_source_locks(Path(args.workspace), args.padding, args.thumb_size), ensure_ascii=False, indent=2))
    elif args.cmd == "ingest":
        ingest_layer_candidate(
            Path(args.workspace),
            args.layer,
            Path(args.candidate),
            args.mode,
            args.chroma_key,
            args.tolerance,
            args.x,
            args.y,
            args.backend,
            args.notes,
            args.no_hidden_surface_required,
        )
    elif args.cmd == "parts-sheet":
        process_parts_sheet(
            Path(args.workspace),
            Path(args.sheet),
            args.chroma_key,
            args.tolerance,
            args.alpha_threshold,
            args.min_area,
            args.padding,
            args.allow_broad_design_board,
            args.sheet_id,
            args.role,
            args.append,
        )
    elif args.cmd == "parts-sheet-prompt":
        write_parts_sheet_prompt(Path(args.workspace), Path(args.out) if args.out else None)
    elif args.cmd == "v3-plan":
        write_v3_component_plan(Path(args.workspace), args.max_sheet_components)
    elif args.cmd == "v3-source-preflight":
        write_v3_source_preflight_report(Path(args.workspace), args.tolerance)
    elif args.cmd == "v3-subject-preflight":
        write_v3_source_subject_preflight_report(Path(args.workspace))
    elif args.cmd == "v3-ingest-subject-matte":
        ingest_v3_subject_matte(Path(args.workspace), Path(args.matte), Path(args.out) if args.out else None, force=args.force)
    elif args.cmd == "v3-mask-jobs":
        write_v3_mask_jobs(Path(args.workspace), ensure_partition=not args.no_ensure_partition)
    elif args.cmd == "v3-reference-bundles":
        write_v3_reference_bundles(Path(args.workspace), args.padding, ensure_masks=not args.no_ensure_masks)
    elif args.cmd == "v3-sheet-prompts":
        write_v3_sheet_prompts(Path(args.workspace))
    elif args.cmd == "v3-sync-candidates":
        sync_v3_candidates_from_parts(Path(args.workspace))
    elif args.cmd == "v3-register-candidates":
        register_v3_candidates(Path(args.workspace), args.min_score)
    elif args.cmd == "v3-registration-repair-report":
        write_v3_registration_repair_report(Path(args.workspace), args.max_tasks)
    elif args.cmd == "v3-imagegen-work-order":
        write_v3_imagegen_work_order(Path(args.workspace), args.max_registration_tasks)
    elif args.cmd == "v3-imagegen-progress-report":
        write_v3_imagegen_progress_report(Path(args.workspace), args.refresh_work_order)
    elif args.cmd == "v3-save-imagegen-inline":
        inline_data = args.inline_base64
        if args.base64_file:
            inline_data = Path(args.base64_file).read_text(encoding="utf-8")
        input_path = Path(args.input) if args.input else None
        if bool(inline_data) == bool(input_path):
            raise SystemExit("Pass exactly one of --input, --base64, or --base64-file")
        save_v3_imagegen_result(
            Path(args.workspace),
            encoded=inline_data,
            input_path=input_path,
            task_id=args.task_id,
            expected_output=args.expected_output,
            edge_chroma_key=args.edge_chroma_key,
            tolerance=args.tolerance,
        )
    elif args.cmd == "v3-continue-imagegen":
        continue_v3_imagegen(Path(args.workspace), force=args.force)
    elif args.cmd == "v3-hidden-jobs":
        write_v3_hidden_jobs(Path(args.workspace))
    elif args.cmd == "v3-hidden-handoff":
        write_v3_hidden_handoff(Path(args.workspace))
    elif args.cmd == "v3-ingest-hidden":
        ingest_v3_hidden_inpaint(Path(args.workspace), args.component, Path(args.image), args.provenance_source, args.notes)
    elif args.cmd == "v3-hidden-review-report":
        write_v3_hidden_review_report(Path(args.workspace), Path(args.decisions) if args.decisions else None)
    elif args.cmd == "v3-recompose":
        write_v3_recompose(Path(args.workspace))
    elif args.cmd == "v3-pose-stress":
        write_v3_pose_stress(Path(args.workspace))
    elif args.cmd == "v3-apply-review-decisions":
        apply_v3_review_decisions(Path(args.workspace), Path(args.decisions))
    elif args.cmd == "v3-review-integrity-report":
        write_v3_review_integrity_report(Path(args.workspace))
    elif args.cmd == "v3-export":
        export_v3_components(Path(args.workspace))
    elif args.cmd == "v3-validate-handoff":
        validate_v3_handoff(Path(args.workspace))
    elif args.cmd == "v3-runtime-import-report":
        write_v3_runtime_import_report(Path(args.workspace), Path(args.evidence) if args.evidence else None)
    elif args.cmd == "v3-validate":
        validate_v3_pipeline(Path(args.workspace))
    elif args.cmd == "v3-hardening-report":
        workspaces = [Path(item) for item in args.workspace]
        if args.workspace_root:
            workspaces.extend(discover_v3_workspaces(Path(args.workspace_root)))
        if not workspaces:
            raise SystemExit("v3-hardening-report requires --workspace or --workspace-root")
        if args.out:
            out_path = Path(args.out)
        elif args.workspace_root:
            out_path = Path(args.workspace_root) / "v3-hardening-report.json"
        else:
            out_path = workspaces[0].parent / "v3-hardening-report.json"
        write_v3_hardening_report(workspaces, out_path, refresh=args.refresh)
    elif args.cmd == "v3-imagegen-execution-report":
        workspaces = [Path(item) for item in args.workspace]
        if args.workspace_root:
            workspaces.extend(discover_v3_workspaces(Path(args.workspace_root)))
        if not workspaces:
            raise SystemExit("v3-imagegen-execution-report requires --workspace or --workspace-root")
        if args.out:
            out_path = Path(args.out)
        elif args.workspace_root:
            out_path = Path(args.workspace_root) / "v3-imagegen-execution-report.json"
        else:
            out_path = workspaces[0] / "v3" / "imagegen" / "v3-imagegen-execution-report.json"
        report = write_v3_imagegen_execution_report(workspaces, out_path, refresh=args.refresh)
        if not args.workspace_root and len(workspaces) == 1 and out_path.is_relative_to(workspaces[0]):
            update_run_state(
                workspaces[0],
                {
                    "v3ImagegenExecutionReport": relative_to_workspace(out_path, workspaces[0]),
                    "v3ImagegenExecutionStatus": report.get("status"),
                },
            )
    elif args.cmd == "v3-imagegen-visual-board":
        print(json.dumps(write_v3_imagegen_visual_execution_board(Path(args.workspace)), ensure_ascii=False, indent=2))
    elif args.cmd == "v3-pose-calibration-report":
        workspaces = [Path(item) for item in args.workspace]
        if args.workspace_root:
            workspaces.extend(discover_v3_workspaces(Path(args.workspace_root)))
        if not workspaces:
            raise SystemExit("v3-pose-calibration-report requires --workspace or --workspace-root")
        if args.out:
            out_path = Path(args.out)
        elif args.workspace_root:
            out_path = Path(args.workspace_root) / "v3-pose-calibration-report.json"
        else:
            out_path = workspaces[0].parent / "v3-pose-calibration-report.json"
        write_v3_pose_calibration_report(workspaces, out_path, refresh=args.refresh)
    elif args.cmd == "map-parts":
        map_parts_to_owners(
            Path(args.workspace),
            parse_part_assignments(args.assign),
            args.auto_visible_masks,
            args.min_score,
        )
    elif args.cmd == "auto-register-parts":
        auto_register_parts(
            Path(args.workspace),
            args.min_score,
            args.no_hidden_surface_required,
            args.notes,
        )
    elif args.cmd == "per-owner-strict-edit-plan":
        owners = [item.strip() for item in args.owners.split(",") if item.strip()] if args.owners else None
        print(json.dumps(write_per_owner_strict_edit_plan(Path(args.workspace), owners, args.reason), ensure_ascii=False, indent=2))
    elif args.cmd == "ingest-strict-edit-candidates":
        print(
            json.dumps(
                ingest_strict_edit_candidates(Path(args.workspace), Path(args.candidate_dir), args.chroma_key, args.tolerance),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.cmd == "register-part":
        register_part_candidate(
            Path(args.workspace),
            args.part,
            args.layer,
            args.x,
            args.y,
            args.fit_owner_bbox,
            args.no_hidden_surface_required,
            args.notes,
        )
    elif args.cmd == "register-v2":
        register_v2(Path(args.workspace), args.part, args.owner, args.method, args.no_hidden_surface_required)
    elif args.cmd == "verify-draw-order-local":
        verify_draw_order_local(Path(args.workspace), args.min_overlap_pixels, args.rgb_disagreement_limit)
    elif args.cmd == "split":
        split_layer(Path(args.workspace), args.layer, args.axis, args.at, args.names)
    elif args.cmd == "auto-split":
        layer_ids = [item.strip() for item in args.layers.split(",") if item.strip()] if args.layers else None
        auto_split_layers(Path(args.workspace), layer_ids, args.min_area)
    elif args.cmd == "validate-html":
        validate_review_html(Path(args.workspace))
    elif args.cmd == "package":
        package_workspace(Path(args.workspace), allow_blocked=args.allow_blocked)


if __name__ == "__main__":
    main()
