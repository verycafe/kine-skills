# Kine Pose Dev V3 Handoff

Date: 2026-06-18

## Current State

Created skill package:

```text
/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/
```

Base skill:

```text
/Users/tvwoo/.codex/skills/kine-pose/SKILL.md
```

This V3 package is now scoped as a Phase A-only development skill. It should guide future work on making Kine Pose action/state-frame and GIF production more believable and less prone to impossible whole-subject motion.

V3 is not limited to character animation. Use it for image-subject animation: characters, products, props, machines, vehicles, UI/icons, environment elements, effects, or any static image subject that needs believable sequence-frame evidence.

## Why V3 Exists

Recent Kine Pose Phase A runs exposed the core failure:

```text
single source image
 -> weak action planning or over-rigid pose controls
 -> whole-subject frames that look animated but break common sense
 -> holes, detached parts, broken props, bad pivots/contact, wrong overlap, source-state snapback, and unreadable GIFs
```

The fix is not to start Phase B or build source masters. The fix is to make Phase A generation decomposition-aware:

```text
stable `$kine-pose` motion contract and action gates
 -> source image / subject type
animation director brief
 -> semantic motion owners
 -> per-frame occlusion / contact / overlap plan
 -> whole-subject generation
 -> local repair candidates
 -> strict visual gates
 -> selected frames / board / GIF / strip
```

## External Research Incorporated

Read:

- `references/v3-skill-blueprint.zh.md`
- `references/phase-a-v3-master-plan.md`
- `references/layer-scenario-research.md`
- `references/v3-plan-goals.md`

Main research conclusions:

- Layer.ai's Create Spine Components shows the right animation-prep target: semantic body parts, clean edges, proportions, and overlap-friendly pieces.
- Scenario's Split an Image Into Components exposes a practical node pattern: list components, segment, reconstruct hidden/cropped content, and remove background.
- Qwen-Image-Layered shows that semantic RGBA decomposition is possible, but its layers are only planning or repair references for V3 Phase A.

Do not claim any private Layer.ai or Scenario algorithm. Treat all architecture notes as public-fact-based inference.

## Required Skill Behavior

Future agents using `$kine-pose-dev-v3` should:

1. Load `$kine-pose` for the stable Phase A registry, provenance, visual-gate, audit, and final-preview rules.
2. Keep V3 Phase A-only.
3. Use Layer/Scenario/Qwen ideas to improve action planning, occlusion reasoning, overlap expectations, local repair, and QA.
4. Generate or select only whole-subject action/state-change frames as deliverable candidates.
5. Keep component sheets, masks, RGBA layers, and local repairs as planning or review evidence unless they produce a final whole-subject frame that passes normal selection.
6. Write exact verification commands and actual outcomes.

## Proposed Development Backlog

### 1. Phase A Contract Draft

Create a JSON schema or Python dataclass for:

```text
animation-director-brief.json
semantic-motion-plan.json
per-frame-occlusion-plan.json
frame-generation-provenance.json
phase-a-v3-qa.json
```

Minimum per-frame fields:

- `subjectType`
- `frameId`
- `actionBeat`
- `movingOwners`
- `stableOwners`
- `contactAnchors`
- `occlusionExpectations`
- `overlapExpectations`
- `propContinuity`
- `forbiddenFailures`
- `generationProvenance`
- `visualQa`

### 2. Validator Script

Use `scripts/validate_phase_a_v3_contract.py` to check:

- every selected frame has a V3 Phase A frame contract
- required files and evidence paths exist
- moving/stable owners are declared for non-trivial action frames
- contact anchors exist when the action depends on support, grip, or prop continuity
- occlusion and overlap expectations exist when parts cross, joints bend, props are held, pivots rotate, state changes, or contact changes
- generation provenance exists and does not claim programmatic subject pixels for selected frames
- local source warp/cutout/pseudo-rig outputs are rejected for large pose/state changes
- selected frames include stable `$kine-pose` action-gate verdicts
- selected-frame visual QA blocks known failure reasons such as `joint_hole`, `detached_child`, `bad_contact`, `prop_discontinuity`, `source_pose_snapback`, or `unreadable_action`

### 3. Candidate And Repair Aids

Prototype optional helpers for:

- Layer-like parts sheets as motion/occlusion references
- Scenario-like split component folders as local repair planning evidence
- Qwen-Image-Layered RGBA outputs as owner/occlusion references

Each helper should create candidate or QA artifacts only. It must not mark frames selected.

### 4. QA Evidence Builders

Use `scripts/build_phase_a_v3_evidence.py` to generate:

- semantic owner review board
- occlusion/overlap risk board
- contact anchor crop sheet
- local repair before/after sheet
- sequence motion-stability board
- failure crops for holes, detached children, bad contact, prop discontinuity, and wrong overlap

### 5. Stable Kine Pose Integration

After local V3 Phase A contracts are stable, sync only the accepted Phase A rules back into the installed `$kine-pose` skill.

Do not port source-master, component-ledger, rig, or Phase B logic into V3.

## Suggested Workspace Output

Future V3 Phase A production work should write:

```text
selected-frame-registry.json
selected-sequence-status.json
candidates_unverified/
local_repair_candidates/
visual_gates/
frames_selected/
qa/
  final-preview-source.json
phase-a-v3/
  source.png
  intake.json
  manifest.json
  animation-director-brief.json
  semantic-motion-plan.json
  per-frame-occlusion-plan.json
  frame-generation-provenance.json
  phase-a-v3-qa.json
qa/
  semantic-owner-review-board.svg
  occlusion-overlap-review-board.svg
  contact-anchor-review-board.svg
  contact-anchor-crop-sheet.svg
  local-repair-review-board.svg
  local-repair-before-after-sheet.svg
  sequence-motion-stability-board.svg
  handoff/
    phase-a-status.json
    blocked-reason.json
```

The stable task root remains authoritative for `frames_selected`, registry, visual gates, and final-preview sources. `phase-a-v3/` is the sidecar contract namespace.

## Status Vocabulary

Use these statuses:

- `candidate`
- `needs_review`
- `selected`
- `visual_rejected`
- `blocked`

Use these failure reasons:

- `unreadable_action`
- `source_pose_snapback`
- `identity_drift`
- `owner_motion_incoherent`
- `joint_hole`
- `detached_child`
- `bad_contact`
- `bad_overlap`
- `prop_discontinuity`
- `wrong_side_motion`
- `local_repair_overpaint`
- `missing_provenance`
- `missing_occlusion_plan`
- `missing_contact_anchor`
- `final_preview_not_selected_source`

## Acceptance Criteria For This Skill Package

The skill package is ready for first Phase A use when:

- `SKILL.md` has no template placeholders and says V3 is Phase A-only.
- `references/phase-a-v3-master-plan.md` lists the complete final objective, workstreams, artifacts, validators, fixtures, milestones, and verification commands.
- `references/v3-skill-blueprint.zh.md` states the plain-language V3 product definition, step sequence, and source-of-strength mapping.
- `references/layer-scenario-research.md` captures the Layer.ai and Scenario research as Phase A planning/QA input.
- `references/v3-plan-goals.md` captures Phase A goals, non-goals, contracts, and acceptance gates.
- `references/HANDOFF.md` gives future agents enough context to continue Phase A development.
- `references/generation-playbook.md` gives prompt/control/local-repair/QA templates.
- `scripts/validate_phase_a_v3_contract.py` and `scripts/test_phase_a_v3_contract.py` pass on the checked-in fixtures.
- `scripts/build_phase_a_v3_evidence.py` builds QA boards and keeps them out of final preview sources.
- `scripts/validate_skill_package.py` passes.
- `skill-creator` `quick_validate.py` passes when available.

## Immediate Next Step

Use the V3 validator, fixture suite, evidence builder, and generation playbook on the next real difficult Phase A task. Confirm that failures such as `unreadable_action`, `joint_hole`, `detached_child`, `bad_contact`, `bad_pivot`, `prop_discontinuity`, `source_pose_snapback`, `source_state_snapback`, or `local_transform_selected_for_large_action` are blocked before any final GIF/strip/board is shown as deliverable evidence.
