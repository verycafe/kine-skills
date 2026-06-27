---
name: kine-svg-dev
description: Use when converting raster character, mascot, prop, or illustration images into layered Kine-ready SVG source masters with semantic groups, component ledgers, manifests, preview evidence, and animation-readiness notes. Trigger for requests like image to layered SVG, Kine SVG DEV, PNG to source master, segmented SVG, editable SVG, or preparing a character image for Kine/Rive-style rigging.
---

# KINE SVG DEV

## Overview

KINE SVG DEV converts polished raster images into layered SVG source masters that can become Kine animation production input. It adapts the user's PSD bridge prompt into an SVG-first workflow:

```text
raster image -> source audit -> component plan -> layered SVG
-> rendered preview -> manifest + component ledger + QA evidence
```

The output is not a Photoshop PSD and not a finished animation. It is a source-master package: editable SVG geometry, semantic layer names, pivots/draw order, and evidence that the SVG still matches the source image.

## Source Prompt Adaptation

The screenshot prompt asks for:

- a Photoshop-openable layered PSD as the only final deliverable
- JSON Bridge style: image generation first, then local Python/Node assembly
- `manifest.json` as the only channel for passing Chinese text, names, colors, sizes, and layer metadata
- non-text visual element extraction before OCR/text reconstruction
- strict merge of intermediate PNG/SVG/script artifacts into the final PSD

For KINE SVG DEV, keep the safety and evidence shape but change the target:

- final deliverable is a layered SVG source-master package, not PSD
- `manifest.json` remains the run source of truth
- each visual component becomes a named SVG group with stable IDs
- text, if present, stays as editable `<text>` plus manifest metadata unless the user requests outlines
- transparent background is preserved; raster-only or hybrid fallbacks must be explicitly labeled
- no claim of rigging, bones, skin, constraints, or runtime animation without separate Kine evidence

## When To Use

Use this skill for images like a full-body astronaut character PNG with large color blocks, clear body parts, accessories, highlights, and shadows where the user wants layered SVG for later animation.

Do not use it for pure OCR, generic icon drawing, PSD output, or a completed Kine animation. If the user asks for motion frames/GIFs, use `kine-pose`; if they ask for Rive import/animation, use `rivesvg` after this source-master package exists.

## Impact Assessment

Before editing or generating assets, classify the request:

- `source_master_only`: layered SVG package and QA evidence
- `animation_ready_plan`: source master plus pivots, owner hierarchy, and blocked hidden surfaces
- `runtime_or_animation`: requires a separate Kine/Rive production step after the SVG source master

Warn inline if the user expects a single raster image to become a perfect fully riggable character. A PNG has lost hidden surfaces, real layer ownership, pivots, and editable shading intent.

## Workflow

### 1. Intake And Manifest

Create a task root, usually:

```text
output/kine-svg-dev/<slug>/
```

Run `scripts/init_kine_svg_dev_task.py` when available. Record:

- source image path, width, height, alpha mode, and source type
- target intent and accepted fallback policy
- deliverable paths
- component categories and QA status

If working inside the Kine repository, follow the repo doc chain before changing repo files. Skill output artifacts may live outside the repo unless the user asks to place them in Kine docs/output.

### 2. Source Audit And Semantic Segmentation

Inspect the image directly before planning layers. Record:

- canvas dimensions and transparency
- subject bounding box
- silhouette-critical parts
- identity markers: face, hair, palette, suit/costume, badges, props
- hidden surfaces that do not exist in the raster source
- areas likely to drift during vectorization: eyes, mouth, fingers, hair tips, highlights, gradients

Before tracing, create an image-specific semantic segmentation plan. Do not use a fixed component list from another image. Derive the groups from the current image by asking:

- What are the primary subjects and sub-subjects?
- Which visible regions are separate by occlusion, material, color family, or functional role?
- Which regions must move together if animated?
- Which small details are identity-critical and must stay separate?
- Which highlights/shadows belong to a parent part instead of becoming independent components?
- Which edges are anti-aliased raster artifacts that should be cleaned, not promoted to layers?

Use this generic discovery flow:

```text
source image
-> primary subjects
-> major assemblies by function/material/occlusion
-> child details by identity/contact/animation role
-> highlights and shadows parented to their owner
-> hidden-surface and cleanup blockers
-> component ledger
```

For a character this may become head/face/hair/torso/arms/legs/clothing/props. For a vehicle it may become body/wheels/windows/lights/doors/shadows. For a UI object it may become frame/screen/buttons/icons/text/highlights. The taxonomy must follow the image, not the example.

Use screen-space left/right when an object has sides, and record the convention.

### 3. Component Plan

Write a component ledger before drawing or tracing. Each component needs:

- stable `id`
- parent owner
- draw-order index
- rough bounding box
- pivot candidate
- static/movable flag
- visual role
- source confidence: `visible`, `inferred`, `missing_hidden_surface`, or `blocked`
- segmentation reason: `material`, `occlusion`, `function`, `identity_detail`, `motion_owner`, `text`, `shadow_highlight`, or `cleanup_artifact`

Prefer 10-30 macro components plus nested detail groups. Do not turn every tiny color island into an independent animation part. If the source PNG contains thousands of colors because of gradients or anti-aliasing, collapse them into the nearest semantic owner before final layering.

### 4. SVG Construction

Choose the conservative path:

- `semantic_redraw`: for large clean color-block illustrations where editable layers matter more than pixel-perfect tracing
- `trace_then_regroup`: for high visual fidelity where source matching matters first
- `hybrid_static_base`: only when vectorization would destroy identity; mark it as not fully editable

Never treat full-image auto trace as the final layered answer by itself. Full-image tracing is only a visual-fidelity candidate. For a true layered SVG, wrap or rebuild paths by the semantic segmentation plan, and reject outputs where anti-aliased fringes, color quantization, or gradient fragments become fake layers.

For high-fidelity raster input, prefer the RIVESVG trace-preserving pattern:

```text
source PNG
-> high-fidelity visual trace
-> render source-vs-trace comparison
-> trace-preserving semantic wrapper rig
-> macro/component map
-> render trace-vs-rig comparison
```

Trace-preserving means:

- preserve original path geometry
- preserve original `transform` attributes
- preserve global draw order
- do not move paths into visually reordered component groups
- use wrapper groups, metadata, or a component map to express ownership
- if regrouping changes the rendered image, reject the grouped SVG and return to the visual trace

When the desired output is both visually faithful and semantic, produce two explicit artifacts:

- `<slug>-trace.svg`: visual-fidelity pure vector trace
- `<slug>-source-master.svg`: trace-preserving semantic wrapper with component metadata

Do not collapse these into one file until trace-vs-source and source-master-vs-trace comparisons both pass.

SVG rules:

- keep the original image coordinate system in `viewBox`
- preserve transparency unless a background is explicitly requested
- use stable group IDs matching the component ledger
- prefer `path`, `rect`, `circle`, `ellipse`, and grouped shapes
- use solid fills and simple gradients only when preview compatibility is verified
- avoid embedded raster images in the final source SVG unless `hybrid_static_base` is declared
- avoid `filter`, `mask`, `foreignObject`, remote URLs, and script
- never flatten semantic groups just to reduce file size

### 5. Preview And QA

Render the SVG to PNG, then compare against the source image. The SVG cannot be called a source-master candidate until:

- canvas size and subject placement match the source
- face and identity markers still read as the same character
- major color blocks and silhouette are preserved
- layer IDs match the component ledger
- transparent regions remain transparent
- no accidental text/path/name corruption exists

Run `scripts/audit_layered_svg.py` when available. If the task uses `rivesvg` scripts, run its `validate_svg.py` and `render_svg.py` as additional gates.

### 6. Kine Readiness Notes

If the user wants later animation, add Kine-readiness fields:

- candidate pivots for head, torso, arms, forearms, hands, hips, thighs, shins, boots, hair, helmet, props
- parent-child owner hierarchy
- draw order and occlusion assumptions
- hidden surfaces that must be redrawn before large motion
- parts safe for transform-only animation
- parts that require mesh/skin/constraints later

Do not claim bones, skin, IK, constraints, timeline, or state-machine completion from this skill alone.

## Deliverables

A complete run should contain:

```text
<slug>-manifest.json
<slug>-component-ledger.json
<slug>-source-audit.json
<slug>-layered.svg
<slug>-preview.png
<slug>-compare.png
<slug>-qa.json
<slug>-kine-readiness.json
```

For quick explorations, at minimum deliver `manifest.json`, `component-ledger.json`, `layered.svg`, and a rendered preview.

## Hard Gates

- Do not invent source layers that are not visible; mark inferred or missing hidden surfaces.
- Do not call a traced blob "rig-ready" unless ownership, pivots, and draw order are documented.
- Do not pass Chinese or other non-ASCII text through shell arguments if scripts can write JSON files instead.
- Do not route through PSD unless the user explicitly asks for PSD output.
- Do not treat OCR text as logo/internal image text unless the user asks to reconstruct it.
- Do not overwrite accepted source-master artifacts; save revisions as new candidates and update the manifest.

## Resource Map

- `scripts/init_kine_svg_dev_task.py`: create a task folder and starter manifest/ledger.
- `scripts/audit_layered_svg.py`: check SVG structure, risky elements, required groups, and manifest consistency.
- `references/layered-svg-contract.md`: detailed package contract and QA fields.
- `references/component-taxonomy.md`: suggested character/prop layer categories.
