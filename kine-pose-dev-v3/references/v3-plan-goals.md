# Kine Pose Dev V3 Plan And Goals

Date: 2026-06-18

## Goal

Create a Phase A-only Kine Pose V3 workflow that prevents nonsensical whole-subject action/state-change frames and broken GIF/sequence evidence.

V3 is not limited to character animation. The source image may contain a person, product, prop, machine, vehicle, UI/icon, environment element, effect, or a character. Character animation is one common case; the general contract is image subject -> believable whole-subject sequence-frame evidence.

The observed failure mode is:

```text
single source image
 -> weak or over-rigid pose control
 -> whole-subject candidate frames with bad structure, holes, detached parts, broken props, bad pivots/contact, or unreadable action
 -> GIF that looks animated but violates common sense
```

V3 should improve Phase A by making action-frame generation decomposition-aware without turning Phase A into source-master or rigging work.

## Product Objective

Kine Pose V3 should produce better Phase A deliverables:

```text
source image + motion/state-change request
 -> stable `$kine-pose` motion contract and action-gate choice
 -> animation director brief
 -> semantic motion ownership map
 -> per-frame occlusion / contact / overlap plan
 -> whole-subject candidate generation
 -> local repair candidates when needed
 -> visual gates
 -> selected sequence frames / board / GIF / strip
```

The bridge is not Phase B. The bridge is from fuzzy user motion/state-change intent to believable whole-subject frame evidence.

## Non-Goals

- Do not clone Layer.ai, Scenario, Spine, Live2D, or Moho.
- Do not claim to know private algorithms from public marketing pages.
- Do not build source masters, component ledgers, rigs, bones, skin, constraints, timelines, state machines, or runtime animation.
- Do not treat source-pixel masks, RGBA layers, or parts sheets as final deliverables.
- Do not skip `$kine-pose` selected-frame, provenance, visual-gate, and final-preview rules.
- Do not let automatic component maps drive accepted frames without visual review.

## V3 Design Principles

1. **V3 is a strict Phase A superset.**
   V3 must keep `$kine-pose` action planning, action-gate profiles, selected-frame registry, provenance, visual gates, audit rules, and final-preview rules. V3 only adds semantic-owner, occlusion, overlap, contact, and repair-risk reasoning on top.

2. **Action readability is the first gate.**
   A frame or sequence that does not immediately read as the requested action or state change fails, even if it preserves identity or passes record validation. Gates are chosen by motion class: alternating motion, contact/support, held-prop interaction, secondary dynamics, expression/speech, mechanism/vehicle, source-master boundary, and sequence evidence.

3. **Phase A remains whole-subject.**
   The final selected image for each frame is a complete subject action/state-change frame. If the subject is a character, this means a whole-character frame; if the subject is not a character, it means the complete object/mechanism/UI/effect state.

4. **Decomposition is a planning lens.**
   Layer.ai and Scenario show that good animation prep depends on semantic parts, occlusion, hidden content, clean edges, and overlaps. In V3, those ideas become frame-planning and QA constraints.

5. **Source identity locks appearance, not pose.**
   The source image preserves subject identity, silhouette, proportions, material/style treatment, palette, line quality, texture/detail level, and important design details. It must not force source-pose or source-state snapback.

6. **Local source deformation is not large-action generation.**
   Local cutout, warp, mesh deformation, PIL/Numpy deformation, and pseudo-rigging are review or rejection evidence for large pose/state changes. They cannot be promoted to selected frames for broad motion or state changes that require model-generated whole-subject frames.

7. **Motion owners must be explicit.**
   Every action phase should know which subject parts, properties, props, attachments, contacts, pivots, states, and secondary elements are allowed to move/change and which should stay stable.

8. **Occlusion and overlap must be plausible in the final frame.**
   If a limb crosses, a hinge turns, a prop contacts a surface, a UI state changes, or an effect overlaps the source subject, the generated frame must plausibly solve the visible overlap. It does not need to output hidden component art.

9. **Local repair remains candidate-only.**
   Masked edits, inpainted fixes, cleaned lines, and repaired local details can rescue a frame, but the result must still pass as one whole-subject selected frame.

## Proposed V3 Phase A Artifact Contract

For each frame or action phase:

```json
{
  "frameId": "frame_012",
  "subjectType": "character | product | prop | mechanism | vehicle | ui_icon | environment_element | effect | other",
  "actionBeat": "right knee lifts while left foot supports",
  "movingOwners": ["right_leg", "left_arm", "hair_back"],
  "stableOwners": ["face", "torso_core"],
  "contactAnchors": [
    {"owner": "left_foot", "target": "ground", "required": true}
  ],
  "occlusionExpectations": [
    {"frontOwner": "right_thigh", "backOwner": "shorts", "risk": "holes_at_hip"}
  ],
  "overlapExpectations": ["right_hip", "right_knee", "left_foot_ground"],
  "propContinuity": [],
  "forbiddenFailures": [
    "source_pose_snapback",
    "detached_child",
    "joint_hole",
    "wrong_side_motion"
  ],
  "generationProvenance": {
    "method": "imagegen",
    "model": "recorded-model-id",
    "sourceImages": [],
    "controlImages": [],
    "programmaticSubjectPixels": false
  },
  "visualQa": {
    "actionReadability": "pending",
    "identityPreserved": "pending",
    "ownerMotionCoherence": "pending",
    "occlusionOverlapPlausibility": "pending",
    "contactContinuity": "pending",
    "sequenceStability": "pending"
  }
}
```

## Acceptance Gates

V3 selected-frame acceptance requires:

- `$kine-pose` motion contract exists for the requested action
- matching `$kine-pose` action-gate profile verdicts are exactly `pass`
- `actionReadability=pass`
- `identityPreserved=pass`
- `notPoseProxy=pass`
- `ownerMotionCoherence=pass`
- `occlusionOverlapPlausibility=pass`
- `contactContinuity=pass` when contact exists
- `propContinuity=pass` when props or attachments exist
- `sequenceStability=pass` before final board/GIF/strip
- `generationProvenance` present for every selected frame
- final preview from selected-frame or final-sequence evidence only
- no selected frame is a local source warp, cutout, pseudo-rig, or broad programmatic deformation for a large pose/state change

## Recommended Implementation Plan

### Stage 1: Documentation And Re-scope

- Make V3 explicitly Phase A-only.
- Convert Layer.ai, Scenario, and Qwen layered research into Phase A planning and QA rules.
- Define frame-level semantic motion and occlusion contracts.

### Stage 2: Local Validators

- Validate required Phase A V3 frame contracts.
- Validate no selected frame is missing semantic motion, occlusion, contact, and provenance records.
- Validate no local repair candidate is promoted without clean whole-subject visual gate.
- Validate no local source warp/cutout/pseudo-rig output is promoted for large pose/state changes.
- Validate final GIF/strip/board uses selected-frame sources only.

### Stage 3: Candidate Generation Aids

- Use Layer-like parts sheets as motion/occlusion reference only.
- Use Scenario-like component split outputs as repair-risk or prompt-planning evidence only.
- Use Qwen-Image-Layered RGBA outputs as optional candidate references for owner/occlusion understanding only.
- Never mark decomposed outputs as accepted frames.

### Stage 4: Visual QA And Sequence Tests

- Build contact sheets for owner motion, occlusion/overlap risk, contact anchors, and local repair evidence.
- Detect or require review for holes, detached children, wrong draw order, prop discontinuity, source-pose snapback, and unreadable action.
- Keep all pass/fail evidence attached to the selected-frame registry.

## Success Definition

The V3 workflow succeeds when a future agent can take a single source image and motion/state-change request and produce:

- accepted Phase A whole-subject action/state-change frames, or a clear Phase A rejection
- a motion director brief
- semantic owner and occlusion plans for every selected frame
- candidate and repair provenance
- QA evidence proving why frames are selected or rejected
- a clean board/GIF/strip made only from selected frames

The V3 workflow fails if it produces attractive frames or a GIF that still has impossible anatomy, holes, detached parts, broken props, source-pose snapback, or unreadable action.
