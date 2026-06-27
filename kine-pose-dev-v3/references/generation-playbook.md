# Kine Pose Dev V3 Generation Playbook

Date: 2026-06-18

## Purpose

Use this playbook after `references/phase-a-v3-master-plan.md` has defined the V3 contract. It turns the contract into generation and repair instructions for Phase A whole-subject action/state-change frames.

Core boundary:

- Generate or select complete whole-subject action/state-change frames.
- If the subject is a character, apply the stable `$kine-pose` whole-character rules directly.
- Use Layer/Scenario/Qwen-style component reasoning only for planning, occlusion, repair targeting, and QA.
- Never promote component sheets, masks, RGBA layers, pose proxies, control panels, or local repair review panels as selected frames.

## Required Inputs

Before generating a non-trivial frame, load or write:

- stable `$kine-pose` motion contract and matching action-gate profile rules
- `phase-a-v3/animation-director-brief.json`
- `phase-a-v3/semantic-motion-plan.json`
- `phase-a-v3/per-frame-occlusion-plan.json`
- source image and subject type
- optional soft control image for the frame
- previous accepted motion-style reference when available

## Whole-Subject Frame Prompt Template

Use this structure for every candidate:

```text
Create one complete whole-subject action/state-change frame.

Subject identity:
- Subject type: {subjectType}
- Preserve the source subject's identity, silhouette, proportions, material/style treatment, palette, line quality, texture/detail level, and important design details.
- If the subject is a character, preserve face, hair, outfit, proportions, palette, and illustration style.
- Use the source image for identity and style, not as a pose or initial-state lock.

Action beat:
- Frame id: {frameId}
- Beat: {actionBeat}
- Force source: {bodyForceSource}
- Stable anchor: {primaryStableAnchor}

Motion owners:
- Moving owners: {movingOwners}
- Stable owners: {stableOwners}
- Secondary owners: {secondaryOwners}

Contacts and props:
- Contact anchors: {contactAnchors}
- Prop continuity: {propContinuity}

Occlusion and overlap:
- Expected occlusions: {occlusionExpectations}
- Required overlaps: {overlapExpectations}

Hard rejects:
- Reject source-pose or source-state snapback.
- Reject unreadable action or state change.
- Reject detached subparts, joint holes, bad pivots, bad contact, bad overlap, wrong-side motion, prop discontinuity, identity drift, and proxy appearance.

Output requirement:
- Return a single coherent whole-subject image, not a component sheet, mask, rigging sheet, sketch proxy, or QA panel.
```

## Stable Action Gate Carryover

Before a V3 candidate can be selected, review it against the stable `$kine-pose` action gate for the requested motion.

Choose action gates by motion class. Examples:

```text
alternating_locomotion_gate:
- run, walk, march, high-knee, or any left/right alternating motion

contact_support_gate:
- support, landing, rolling, pressing, sitting, sliding, grounded contact, or visible weight

held_prop_interaction_gate:
- hand/paw/handle/tool/weapon/instrument/bag/strap/cable interaction

secondary_dynamics_gate:
- hair, cloth, ribbons, particles, trails, smoke, dust, glow, splash, or follow-through

expression_speech_gate:
- blink, mouth, expression, viseme, face-state acting

mechanism_vehicle_gate:
- wheel, gear, hinge, rotor, lever, pedal, vehicle, mechanical pivot, rider/vehicle relation

sequence_evidence_gate:
- any board, GIF, strip, final preview, or downstream handoff
```

For front-facing run, walk, march, or high-knee loops, this means:

```text
Required gates:
- alternating_locomotion_gate
- contact_support_gate
- sequence_evidence_gate

Required visual questions:
- Does it read immediately as running/walking/marching, not as a warped still?
- Are left/right phases visually distinct?
- Is arm swing opposite the active leg unless the contract states otherwise?
- Does one foot or landing/contact state visibly support body weight?
- Is there no foot sliding, floating, ground penetration, or source-pose snapback?
```

For non-character subjects, replace limb-specific questions with the matching physical/state questions:

```text
- Does the subject read immediately as the requested motion/state change?
- Are force, pivot, contact, material deformation, UI state, or effect continuity plausible?
- Did the frame avoid source-state snapback and local warp artifacts?
```

If the answer is no, return `visual_rejected`. Do not continue into identity/final-preview promotion.

## Soft Control Template

Soft controls should guide the model without freezing anatomy:

```text
soft control for {frameId}
- canvas/framing: {sourceFramingPolicy}
- subject type: {subjectType}
- head direction: {headDirection}
- torso center: {torsoCenter}
- hand points: {handPoints}
- foot/contact points: {footPoints}
- prop handle/tip points: {propPoints}
- attachment start/end: {attachmentPoints}
- mechanism/pivot/state markers: {mechanismOrStatePoints}
- motion arc: {motionArc}
- stable anchor: {primaryStableAnchor}
```

Allowed:

- rough arcs
- body center and limb endpoint marks
- contact anchors
- prop handle/tip anchors
- attachment start/end hints
- pivots, state markers, material deformation anchors, UI-state markers, or effect paths when relevant

Avoid:

- final-looking subject proxies
- hard skeletons that stretch or freeze anatomy
- local cutout rigs as the first path for large pose changes
- controls that contradict the director brief

## Candidate Record Template

Every generated frame must write or update `frame-generation-provenance.json`:

```json
{
  "frames": {
    "{frameId}": {
      "method": "imagegen",
      "model": "{model}",
      "sourceImages": ["phase-a-v3/source.png"],
      "controlImages": ["soft_controls/{frameId}-control.png"],
      "promptSource": "phase-a-v3/animation-director-brief.json + phase-a-v3/per-frame-occlusion-plan.json",
      "programmaticSubjectPixels": false
    }
  }
}
```

`programmaticSubjectPixels` must be `false` for selected frames. `programmaticCharacterPixels` is accepted only as a backward-compatible alias in older records.

## Local Repair Playbook

Use local repair only when the whole-subject candidate is close and the defect is narrow.

Allowed repair targets:

- hand/prop grip
- stale rope/line cleanup
- small contact error
- local overlap hole
- small detached child
- prop endpoint continuity
- small pivot/contact/material/state continuity defect

Forbidden repair targets:

- broad anatomy redraw
- broad subject redraw
- unreadable action
- source-pose or source-state snapback
- local source warp or pseudo-rig output that failed to become a true action pose
- replacing the frame with a component sheet
- changing subject identity or drawing/material treatment
- painting programmatic subject pixels directly into selected frames

Local repair prompt:

```text
Repair only the marked local defect in this whole-subject candidate.

Preserve:
- the complete subject image
- identity, line/material treatment, palette, scale, and canvas
- the action beat and owner relationships

Fix:
- target defect: {repairTarget}
- expected contact/overlap: {expectedContactOrOverlap}

Do not:
- redraw broad anatomy
- alter source identity
- change pose timing
- produce a component sheet, mask, crop panel, or partial asset
```

Promotion rule:

- Save repair outputs under `local_repair_candidates/`.
- Record `localRepairCandidate=true` and method such as `local_repair_model_edit`.
- Promote only after a whole-subject visual gate has `status=pass`, empty failures, `verdict.wholeSubjectActionFrame=pass` or backward-compatible `verdict.wholeCharacterActionFrame=pass`, `verdict.localRepairNotOverpaint=pass`, and `localRepairReview.status=pass`.

## QA Prompt Template

Use this review prompt before adding a frame to `frames_selected`:

```text
Review this candidate as a Phase A whole-subject action/state-change frame.

Check in order:
1. Does the action or state change read immediately as {normalizedAction}?
2. Is the subject still the original subject, not a proxy or simplified redraw?
3. Do moving owners and stable owners match the per-frame contract?
4. Are expected occlusions and overlaps plausible?
5. Are contact anchors stable?
6. Are props or attachments continuous?
7. Are there joint holes, detached subparts, bad pivots, bad contact, bad overlap, wrong-side motion, source-pose/state snapback, or prop discontinuity?
8. Is the candidate a complete subject frame, not a component/layer/control/review artifact?

Return pass only when every required verdict is clean.
```

Minimum visual-gate verdicts:

```json
{
  "actionReadability": "pass",
  "identityPreserved": "pass",
  "originalCharacterTreatment": "pass",
  "notPoseProxy": "pass",
  "ownerMotionCoherence": "pass",
  "occlusionOverlapPlausibility": "pass",
  "contactContinuity": "pass",
  "propContinuity": "pass",
  "provenanceValidity": "pass",
  "wholeSubjectActionFrame": "pass"
}
```

Hard selected-frame disallow:

```text
Do not select frames whose provenance shows local cutout, local warp, mesh deformation,
PIL/Numpy deformation, pseudo-rigging, or broad source-preserving transforms for a large
pose/state change. These can be kept only under candidates/rejected/QA evidence.
```

## Sequence Review Template

Before composing final GIF/strip/board:

```text
Review the selected frames as motion.

Check:
- action reads at playback speed
- no source-pose snapback
- no source-state snapback when the subject is not a posed character
- stable canvas and scale
- contact continuity
- prop continuity
- owner-child relationships remain intact
- loop return is stable when looping
- no frame has hidden caveat, pending review, or blocked failure
```

Final preview may use only:

- `frames_selected`
- final GIF
- final strip
- final board
- selected-frame preview

Final preview must not use:

- candidates
- local repair review panels
- component sheets
- layered/RGBA references
- semantic owner boards
- occlusion/overlap boards
- soft controls
- pose proxies
