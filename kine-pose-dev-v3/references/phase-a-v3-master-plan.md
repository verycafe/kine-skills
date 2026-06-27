# Kine Pose Dev V3 Phase A Master Plan

Date: 2026-06-18

## Table Of Contents

- Mission
- Final Deliverable
- Product Boundary
- Architecture
- End-To-End Workflow
- Data Contracts
- Deterministic Validators To Build
- Fixtures To Build
- Stage Goals And Plan
- Acceptance Criteria For Final Goal
- Verification Commands
- Risks And Guardrails

## Mission

Kine Pose Dev V3 is a Phase A-only upgrade. Its final goal is to make image-based subject action/state-change generation produce believable whole-subject frames, sequence-frame evidence, GIFs, strips, and boards.

V3 is not limited to character animation. The image subject may be a person, product, prop, machine, vehicle, UI/icon, environment element, effect, or a character. When the subject is a character, the stable `$kine-pose` whole-character wording applies directly; otherwise use the same rule as `whole-subject`.

V3 exists because previous Phase A outputs could look animated while violating common sense:

```text
bad action planning
 -> weak or over-rigid pose control
 -> impossible whole-subject frames
 -> holes, detached subparts, bad contact, broken props, source-pose/state snapback
 -> final GIF that should have been rejected
```

V3 fixes this by adding semantic-owner reasoning before generation and stronger visual gates after generation. It does not create source masters, component ledgers, rigs, bones, skin, constraints, timelines, state machines, or runtime animation.

## Final Deliverable

A successful V3 Phase A run produces:

- selected whole-subject action/state-change frames
- selected-frame registry updates
- sequence-frame evidence
- final GIF, strip, and board
- motion/sequence QA evidence
- precise rejected-candidate records
- a final status of `deliverable_candidate`, `accepted`, `visual_rejected`, `blocked`, or `wip`

The selected visual asset for each frame is always a complete subject frame for the requested action/state. Component sheets, masks, layered RGBA outputs, and local repairs are planning or review evidence only.

## Product Boundary

In scope:

- source-image-to-action/state-frame generation
- action beat planning
- animation director brief
- semantic motion owner planning
- per-frame occlusion, contact, overlap, and prop-risk planning
- soft controls and prompt constraints
- whole-subject candidate generation
- masked or local repair candidates for narrow defects
- visual gates
- selected-frame-only GIF/strip/board composition
- deterministic validators for records, evidence, provenance, and source paths

Out of scope:

- source master creation
- component ledger creation
- source-layer acceptance
- rigging
- bones, skin, IK, mesh, constraints
- timeline or state-machine authoring
- runtime animation claims
- using generated parts sheets as final selected frames

## Architecture

V3 sits on top of stable `$kine-pose` Phase A:

```text
$kine-pose base rules
  -> task scaffold
  -> selected-frame registry
  -> visual gates
  -> audit/compose scripts
  -> final preview source rules

kine-pose-dev-v3 additions
  -> animation director brief
  -> semantic motion owner map
  -> per-frame occlusion/contact/overlap contract
  -> repair-risk plan
  -> stricter Phase A QA vocabulary
  -> V3-specific validators and fixtures
```

V3 may use Layer.ai, Scenario, and Qwen-Image-Layered research as an animation-planning lens:

```text
semantic parts
 -> owner motion
 -> occlusion risk
 -> overlap expectation
 -> contact anchor
 -> local repair target
 -> visual QA
```

V3 must not use those tools or ideas to justify Phase B work.

## End-To-End Workflow

### 0. Intake

Record:

- source image
- subject type and visible subject identity/style/material cues
- motion or state-change request
- target duration and output type
- source framing intent
- visible props, attachments, contact surfaces, and secondary elements
- explicit user dislikes or prior failed outputs

Required output:

```text
phase-a-v3/source.png
phase-a-v3/intake.json
```

### 0.5 Stable Phase A Action Gate Preflight

V3 must inherit `$kine-pose` Phase A before adding semantic-owner reasoning.

Record:

- stable `$kine-pose` motion contract
- action-gate profile selection
- required visual verdicts from those profiles
- action-readability hard rejects
- whether the requested action or state change requires model-generated whole-subject frames
- whether any local transform output is allowed only as review/rejection evidence

For example, front-facing run, walk, march, high-knee, or similar alternating locomotion uses:

```text
alternating_locomotion_gate
contact_support_gate
sequence_evidence_gate
action_plan_gate
source_framing_gate
soft_control_gate
canvas_stability_gate
```

Completion gate:

- no candidate may enter `frames_selected` unless action readability and every declared action-gate verdict pass first.
- if a user or independent review says the action is not readable, the sequence is `visual_rejected` even if deterministic validators pass.

### 1. Animation Director Brief

Write a professional action plan before generation.

Record:

- normalized action
- loop or one-shot behavior
- frame count and exposure policy
- action beats
- anticipation, main action, follow-through, settle
- force source or state-change driver
- primary stable anchor
- what may move and what must stay stable
- missing in-between states
- crop/scale/framing policy
- hard rejects

Required output:

```text
phase-a-v3/animation-director-brief.json
```

Completion gate:

- no generation may start until the director brief exists for non-trivial motion.

### 2. Semantic Motion Plan

Translate the brief into subject/part/property ownership.

Record:

- moving owners
- stable owners
- owner-child relationships
- secondary motion owners
- prop owners
- attachment owners
- contact owners
- mechanism/property/state owners when the subject is not a character
- forbidden owner swaps

Required output:

```text
phase-a-v3/semantic-motion-plan.json
```

Completion gate:

- every non-trivial action phase has at least one moving owner and one stable or support owner.

### 3. Per-Frame Occlusion / Contact / Overlap Plan

For every frame or action phase, record:

- `frameId`
- `actionBeat`
- `movingOwners`
- `stableOwners`
- `contactAnchors`
- `occlusionExpectations`
- `overlapExpectations`
- `propContinuity`
- `forbiddenFailures`

Required output:

```text
phase-a-v3/per-frame-occlusion-plan.json
```

Completion gate:

- any crossing part, bent joint, held prop, contact surface, flexible attachment, mechanical pivot, material deformation, UI state, or visible state transition must have an explicit expectation.

### 4. Soft Controls

Create soft controls from the contract.

Allowed controls:

- head direction
- body center
- hand/foot/contact points
- prop handle and tip
- attachment start/end
- rotation pivots, state markers, material/deformation anchors, or UI state markers when relevant
- rough motion arcs
- stable canvas anchor

Forbidden controls:

- final-looking character proxies
- hard skeletons that stretch or freeze anatomy
- controls that override the director brief

Required output:

```text
soft_controls/
```

Completion gate:

- every generated frame has a control reference or a recorded reason why it does not need one.

### 5. Whole-Subject Candidate Generation

Generate complete subject frames.

Rules:

- candidates go to `candidates_unverified/`
- source reference locks subject identity/style/material treatment, not source pose or initial state
- prompt/control must include action beat, owners, contact, and forbidden failures
- candidate must be judged first on action readability
- every candidate records `generationProvenance`
- large pose or state changes must be model-generated or model-edited whole-subject frames; local cutout, warp, PIL/Numpy deformation, mesh deformation, or pseudo-rigging can only create rejected/review evidence

Required output:

```text
candidates_unverified/
phase-a-v3/frame-generation-provenance.json
```

Completion gate:

- no candidate may enter `frames_selected` without a clean visual gate.

### 6. Local Repair Candidates

Use local repair only when the whole-subject candidate is close but has a narrow defect.

Allowed repair targets:

- hand/prop grip
- stale line or rope cleanup
- small contact error
- local overlap hole
- small detached child
- prop endpoint continuity
- small mechanical/contact/state continuity defect

Forbidden repair targets:

- broad anatomy redraw
- broad subject redraw
- replacing the frame with a component sheet
- patching over unreadable action
- patching over source-pose snapback or local warp that failed to become a real action pose
- programmatic subject-pixel drawing in a selected frame

Required output:

```text
local_repair_candidates/
local-repair-review/
```

Completion gate:

- repaired output remains a candidate until it passes a whole-subject visual gate.

### 7. Visual Gates

Every selected frame must pass:

- action readability
- identity preservation
- original subject treatment
- not pose proxy
- owner motion coherence
- occlusion/overlap plausibility
- contact continuity when contact exists
- prop continuity when prop exists
- source framing when source framing matters
- provenance validity

Required output:

```text
visual_gates/<frameId>.json
qa/semantic-owner-review-board.svg
qa/occlusion-overlap-review-board.svg
qa/contact-anchor-crop-sheet.svg
```

Completion gate:

- any caveat frame remains review evidence and cannot enter `frames_selected`.

### 8. Selected Frame Registry

Promote only clean frames.

Rules:

- selected frame must be a whole-subject action/state-change frame
- selected path must live under `frames_selected/`
- visual gate must be exact `pass`
- failures must be empty
- selected image must match gate record
- do not set `doNotRegenerate=true` before user acceptance

Required output:

```text
frames_selected/
selected-frame-registry.json
```

### 9. Sequence QA

Review the selected frames as motion, not isolated stills.

Check:

- action reads at speed
- loop return is stable when looping
- frame-to-frame owner continuity
- no side flips
- contact continuity
- prop continuity
- stable scale and canvas
- no source-pose snapback
- no frame with hidden caveat

Required output:

```text
qa/sequence-motion-gate.json
qa/sequence-motion-stability-board.svg
```

### 10. Final Evidence Composition

Compose only after audit passes.

Allowed final preview sources:

- `frames_selected`
- final GIF
- final strip
- final board
- selected-frame preview

Forbidden final preview sources:

- candidate sheets
- component sheets
- soft controls
- pose proxies
- local repair review panels
- rejected sheets
- control-vs-candidate panels

Required output:

```text
check/final.gif
check/final-strip.png
sheets/final-board.png
qa/final-preview-source.json
```

## Data Contracts

### `animation-director-brief.json`

Required fields:

- `taskId`
- `subjectType`
- `motionIntent`
- `normalizedAction`
- `durationSeconds`
- `fps`
- `selectedActionFrameCount`
- `exposurePolicy`
- `actionGateProfiles`
- `requiredVisualVerdicts`
- `actionBeats`
- `primaryStableAnchor`
- `motionBudget`
- `sourceFramingPolicy`
- `hardRejects`
- `status`

### `semantic-motion-plan.json`

Required fields:

- `taskId`
- `owners`
- `movingOwners`
- `stableOwners`
- `ownerChildRules`
- `propOwners`
- `contactOwners`
- `secondaryOwners`
- `forbiddenOwnerChanges`
- `status`

### `per-frame-occlusion-plan.json`

Required fields:

- `taskId`
- `frames`
- `frames[].frameId`
- `frames[].subjectType`
- `frames[].actionBeat`
- `frames[].movingOwners`
- `frames[].stableOwners`
- `frames[].actionGateProfiles`
- `frames[].requiredVisualVerdicts`
- `frames[].contactAnchors`
- `frames[].occlusionExpectations`
- `frames[].overlapExpectations`
- `frames[].forbiddenFailures`

### `phase-a-v3-qa.json`

Required fields:

- `taskId`
- `frameQa`
- `sequenceQa`
- `reviewer`
- `reviewIndependence`
- `status`
- `failures`
- `evidence`

## Deterministic Validators To Build

### `scripts/validate_phase_a_v3_contract.py`

Validate:

- required files exist
- every selected frame has a frame contract
- frame IDs match registry entries
- non-trivial frames declare moving/stable owners
- contacts have contact anchors
- occlusion/overlap risks are declared when required
- selected frames have provenance
- local repair outputs are not promoted without clean whole-subject gate
- local warp/cutout/pseudo-rig outputs are not promoted for large pose/state changes
- stable `$kine-pose` action-gate verdicts are present for selected frames
- final preview source is selected-frame or final-sequence evidence only

Stable error codes:

- `missing_director_brief`
- `missing_semantic_motion_plan`
- `missing_occlusion_plan`
- `selected_frame_missing_contract`
- `missing_moving_owner`
- `missing_stable_owner`
- `missing_contact_anchor`
- `missing_overlap_expectation`
- `missing_generation_provenance`
- `programmatic_subject_pixels`
- `local_repair_promoted_without_clean_gate`
- `local_transform_selected_for_large_action`
- `missing_stable_action_gate`
- `final_preview_not_selected_source`

### `scripts/test_phase_a_v3_contract.py`

Run the checked-in fixtures and assert:

- good fixture passes
- missing director brief fails
- missing semantic motion plan fails
- missing occlusion plan fails
- selected frame without a frame contract fails
- missing moving/stable owners fail
- missing contact anchor fails
- missing overlap expectation fails
- missing provenance fails
- programmatic subject pixels fail
- detached child not blocked fails
- source-pose snapback not blocked fails
- local repair promoted without clean gate fails
- local warp/cutout/pseudo-rig promoted for a large action fails
- selected frame missing stable action-gate verdicts fails
- final preview from candidate source fails
- component sheet selected as a whole-subject frame fails

### Existing `$kine-pose` Scripts To Keep Using

Do not rewrite these in V3 unless the stable skill is intentionally changed:

- `init_kine_pose_task.py`
- `audit_kine_pose_task.py`
- `compose_sequence_evidence.py`
- `test_kine_pose_pipeline_guards.py`

V3 validators should add Phase A contract checks around the stable task structure.

## Fixtures To Build

```text
fixtures/phase-a-v3/minimal-pass/
fixtures/phase-a-v3/bad-missing-director-brief/
fixtures/phase-a-v3/bad-missing-semantic-motion-plan/
fixtures/phase-a-v3/bad-missing-occlusion-plan/
fixtures/phase-a-v3/bad-selected-frame-missing-contract/
fixtures/phase-a-v3/bad-missing-moving-owner/
fixtures/phase-a-v3/bad-missing-stable-owner/
fixtures/phase-a-v3/bad-missing-contact-anchor/
fixtures/phase-a-v3/bad-missing-overlap-expectation/
fixtures/phase-a-v3/bad-missing-provenance/
fixtures/phase-a-v3/bad-programmatic-character-pixels/
fixtures/phase-a-v3/bad-local-repair-promoted/
fixtures/phase-a-v3/bad-local-transform-selected/
fixtures/phase-a-v3/bad-missing-stable-action-gate/
fixtures/phase-a-v3/bad-final-preview-source/
fixtures/phase-a-v3/bad-source-pose-snapback-not-blocked/
fixtures/phase-a-v3/bad-detached-child-not-blocked/
fixtures/phase-a-v3/bad-component-sheet-selected/
```

Fixtures may use tiny placeholder PNGs for deterministic tests. Visual truth is represented by QA JSON and evidence-path presence, not by scripts interpreting image pixels.

## Visual QA Vocabulary

Frame statuses:

- `candidate`
- `needs_review`
- `selected`
- `visual_rejected`
- `blocked`

Failure reasons:

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

## Stage Goals And Plan

### Stage 1: Re-scope And Master Plan

Done when:

- V3 is clearly Phase A-only
- master plan exists
- Layer/Scenario/Qwen research is reframed as Phase A planning and QA input
- package validation passes

### Stage 2: Contract Validator

Done when:

- `validate_phase_a_v3_contract.py` exists
- minimal-pass and bad fixtures exist
- good fixture passes
- bad fixtures fail with stable error codes
- local source warp / cutout / pseudo-rig selected frames fail for large pose or state changes
- selected frames missing stable action-gate verdicts fail
- package validation passes

### Stage 3: Evidence Builders

Done when:

- semantic owner review board builder exists
- occlusion/overlap board builder exists
- contact anchor crop sheet builder exists
- local repair before/after sheet builder exists
- generated boards are registered as QA evidence, not final preview

### Stage 4: Generation Playbook

Done when:

- prompt/control templates include action beat, owners, contacts, occlusion, overlap, and forbidden failures
- `references/generation-playbook.md` contains prompt/control templates and the local repair playbook
- Layer/Scenario/Qwen references are explicitly marked as planning/review evidence
- no helper suggests selecting component sheets as final frames

### Stage 5: Stable Skill Integration

Done when:

- Stage 2 through Stage 4 pass on realistic tasks
- accepted rules are ported into `$kine-pose` references/scripts
- stable `$kine-pose` tests pass
- V3 remains a development skill or is retired after merge

## Acceptance Criteria For Final Goal

The final V3 goal is achieved when:

- a new difficult image-subject motion or state-change task starts with a director brief and semantic motion plan
- every selected frame has occlusion/contact/overlap expectations
- every selected frame has provenance and a clean visual gate
- local repairs cannot bypass whole-subject selection
- local source warp/cutout/pseudo-rig outputs cannot be selected for large pose/state changes
- final GIF/strip/board are selected-frame-only
- known bad sequences are blocked by deterministic validators
- visual QA has stable failure reasons for impossible anatomy and broken motion
- stable `$kine-pose` can adopt the accepted Phase A improvements without importing Phase B behavior

## Verification Commands

Run from the V3 skill root:

```bash
/usr/bin/python3 scripts/validate_skill_package.py
/usr/bin/python3 -m py_compile scripts/*.py
/usr/bin/python3 scripts/generate_phase_a_v3_fixtures.py --root fixtures/phase-a-v3 --force
/usr/bin/python3 scripts/validate_phase_a_v3_contract.py fixtures/phase-a-v3/minimal-pass
/usr/bin/python3 scripts/test_phase_a_v3_contract.py
/usr/bin/python3 scripts/build_phase_a_v3_evidence.py fixtures/phase-a-v3/minimal-pass
```

When checking stable `$kine-pose` compatibility:

```bash
/usr/bin/python3 /Users/tvwoo/.codex/skills/kine-pose/scripts/test_kine_pose_pipeline_guards.py
```

## Risks And Guardrails

- Scripts cannot judge artistic truth. They can only require independent QA records and evidence paths.
- Decomposition references can improve planning, but selected frames must remain whole-subject frames.
- Local repair can hide large generation failure. If action is unreadable, reject the frame instead of repairing.
- Overly rigid controls can create stiff or stretched anatomy. Prefer semantic soft controls.
- Good single frames can still produce bad GIFs. Sequence QA is mandatory.
- Do not let V3 drift into Phase B. If a task needs source master, rig, or runtime animation, use another workflow after Phase A is accepted.
