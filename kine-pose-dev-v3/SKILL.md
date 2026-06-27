---
name: kine-pose-dev-v3
description: Develop or operate Kine Pose Dev V3 as a Phase A-only upgrade for image-subject action/state-change frames, sequence-frame evidence, GIF previews, and animation-readable whole-subject motion. Use when refining Kine Pose Phase A production rules with Layer.ai/Scenario-inspired semantic part planning, occlusion-aware frame generation, overlap/contact constraints, local repair gates, and sequence QA. This skill does not produce Phase B source masters, component ledgers, rigs, bones, timelines, or runtime animation.
---

# Kine Pose Dev V3

## Purpose

Use this skill to evolve Kine Pose Phase A only:

```text
source image / subject reference
 -> stable `$kine-pose` motion contract and action gates
 -> animation director brief
 -> semantic motion ownership map
 -> per-frame occlusion / contact / overlap plan
 -> soft pose and component-aware controls
 -> whole-subject candidate frames
 -> local repair candidates when needed
 -> strict visual gates
 -> selected sequence frames / board / GIF / strip
```

This skill does not replace `$kine-pose`; it refines the Phase A route for producing more believable whole-subject action/state-change frames and sequence evidence.

V3 is not limited to character animation. The animated subject may be a person, product, prop, machine, vehicle, UI/icon, environment element, effect, or a character. When the subject is a character, `$kine-pose` whole-character rules apply directly. For non-character subjects, apply the same principle as `whole-subject`: the selected frame must show the complete intended subject/state, not a partial component sheet, mask, control proxy, or local warp artifact.

V3 is not a source-master, rigging, or component-ledger workflow. Layer.ai, Scenario, and Qwen-Image-Layered research is used here as planning and QA inspiration for Phase A, not as a reason to start Phase B work.

## Load Order

When using this skill:

1. Load `$kine-pose` first. Its selected-frame registry, visual gates, provenance, and final-preview rules remain the stable contract.
2. Read `references/v3-skill-blueprint.zh.md` when you need the plain-language product definition, step sequence, or source-of-strength mapping.
3. Read `references/phase-a-v3-master-plan.md` before planning, implementing, or changing V3 work.
4. Read `references/v3-plan-goals.md` before changing Phase A scope or writing V3 rules.
5. Read `references/layer-scenario-research.md` before using Layer.ai, Scenario, layered-reference, occlusion, or component-reasoning ideas for Phase A planning or QA.
6. Read `references/generation-playbook.md` before writing prompts, soft controls, local repair instructions, or visual QA templates.
7. Read `references/HANDOFF.md` before continuing development from this package or handing work to another agent.

## V3 Operating Rules

- V3 is Phase A-only. It produces action frames, sequence-frame evidence, GIFs, strips, boards, and QA records.
- V3 is a strict Phase A superset of `$kine-pose`, not a replacement. Before any V3 semantic-owner or occlusion work can promote frames, the stable `$kine-pose` motion contract and action-gate profile must exist and pass.
- Judge action readability first. If the sequence does not immediately read as the requested action, mark it `visual_rejected` even when identity, framing, records, or deterministic validators look clean.
- Choose action gates by motion class, not by hardcoded examples. Left/right locomotion uses alternating/contact gates; support, held-prop, secondary dynamics, expression/speech, mechanism/vehicle, source-master-boundary, and sequence evidence gates are applied only when the requested image subject and motion need them.
- For run, walk, march, high-knee, or other left/right motion, load and apply `$kine-pose` `alternating_locomotion_gate`, `contact_support_gate`, and `sequence_evidence_gate`; same-side arm/leg, undefined support, foot sliding, source-pose snapback, and visually indistinct phases are hard failures.
- Do not create or claim source masters, component ledgers, rig elements, bones, skin, constraints, timelines, state machines, or runtime animation.
- Treat Layer.ai/Scenario-style decomposition as an animation-planning lens: identify semantic owners, occlusion risks, contact anchors, overlap expectations, and forbidden visual failures before generation.
- Generate or select whole-subject action/state-change frames as the deliverable candidate. Component sheets, masks, RGBA layers, parts sheets, local patches, and control panels are planning, correction, or review evidence only.
- Use the source image to preserve the subject identity, appearance, style, proportions, materials, and important visual treatment. Do not lock the subject to the source pose or initial state when that conflicts with the requested action.
- Prefer model-generated whole-subject frames for large pose or state changes. Local cutout, warp, mesh deformation, PIL/Numpy deformation, pseudo-rigging, or broad source-preserving transforms are review/rejection evidence only for large actions; they cannot enter `frames_selected`.
- Use local masked repair only as candidate evidence for narrow defects such as broken hands, prop anchors, overlap holes, or stale lines. Local repair cannot rescue unreadable action, source-pose snapback, or broad anatomy that should have been generated.
- Require every frame plan to record which body or prop owners move, which areas may be occluded, where overlap must remain plausible, and which contacts must stay stable.
- Reject frames with impossible anatomy, broken owner-child relationships, holes at joints, detached children, wrong-side motion, source-pose snapback, bad contact, or prop discontinuity.
- Keep any decomposed or repaired intermediate out of `frames_selected` unless the final selected image is a whole-subject action/state-change frame with clean visual-gate evidence.
- A user visual rejection overrides every script result. Preserve the rejected GIF/strip/board under `rejected/<iteration>/`, empty or invalidate selected-frame records, and restart from motion contract / pose-control evidence.

## Development Workflow

1. **Capture evidence**
   - Save external research under `references/`.
   - Separate public facts from implementation inference.
   - Translate decomposition research into Phase A frame-generation and QA rules.

2. **Design Phase A contracts**
   - Define an animation director brief.
   - Define semantic owner maps for body parts, props, attachments, and secondary motion.
   - Define per-frame occlusion, contact, overlap, and repair-risk expectations.
   - Define rejection states for impossible anatomy, broken contacts, holes, detached children, identity drift, local overpaint, source-pose snapback, and unreadable action.

3. **Prototype only deterministic checks**
   - Put repeatable checks in `scripts/`.
   - Do not encode model behavior as deterministic.
   - Prefer validators, QA reporters, manifest auditors, and sequence evidence checks over brittle generation scripts.
   - Use `scripts/validate_phase_a_v3_contract.py` to validate a V3 task root.
   - Use `scripts/build_phase_a_v3_evidence.py` to create QA boards; keep these boards out of final preview sources.
   - Use `scripts/test_phase_a_v3_contract.py` for the deterministic fixture regression suite.

4. **Keep Phase Boundaries**
   - Phase A: selected whole-subject action/state-change frames, sequence evidence, board/GIF/strip, and visual-gate QA.
   - Phase B: out of scope for V3.
   - A Phase A output may mention downstream risk, but it must not produce source masters, components, rigs, bones, timelines, or runtime claims.

## Output Shape For V3 Phase A Workspaces

Prefer this structure for future V3 task outputs:

```text
selected-frame-registry.json
selected-sequence-status.json
candidates_unverified/
local_repair_candidates/
visual_gates/
frames_selected/
check/
sheets/
qa/
  final-preview-source.json
  semantic-owner-review-board.svg
  occlusion-overlap-review-board.svg
  contact-anchor-review-board.svg
  contact-anchor-crop-sheet.svg
  local-repair-review-board.svg
  local-repair-before-after-sheet.svg
  sequence-motion-stability-board.svg
phase-a-v3/
  source.png
  intake.json
  manifest.json
  animation-director-brief.json
  semantic-motion-plan.json
  per-frame-occlusion-plan.json
  frame-generation-provenance.json
  phase-a-v3-qa.json
handoff/
  phase_a_status.json
```

The stable task root remains authoritative for selected frames, visual gates, registry, and final previews. `phase-a-v3/` stores V3 planning, provenance, and QA contracts.

## Completion Standard

A V3 workflow or implementation proposal is complete only when it records:

- the base `$kine-pose` Phase A rule it extends
- the Phase A frame-generation problem it solves
- the subject type, semantic owners, occlusion risks, contact anchors, overlap expectations, and forbidden failures for each frame or action phase
- the QA gate that prevents impossible action frames from entering `frames_selected`
- exact verification commands or the reason verification cannot run
- remaining risks and next Phase A implementation steps
