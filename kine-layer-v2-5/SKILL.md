---
name: kine-layer-v3
description: Experimental KINE-LAYER V3 source-master workflow for developing semantic component-plan-first character decomposition. Use when decomposing a raster character into animation-ready layers using component planning, multi-sheet generation, per-owner masks, hidden-surface completion, alpha cleanup, source-recompose gates, review HTML, PSD/PNG manifests, or when improving the next-generation KINE-LAYER pipeline beyond V2.
---

# Kine Layer V3

## Purpose

Use this skill for V3 development of KINE-LAYER source-master generation:

```text
source image
 -> component_plan
 -> bounded multi-sheet campaign
 -> per-component mask jobs / source lock
 -> hidden completion / overlap zones
 -> alpha cleanup
 -> source recompose + pose-stress gates
 -> review / PSD / PNG / Spine-ready handoff
```

V3 keeps V2's working CLI, QA, registration, packaging, and review machinery, but changes the default mental model: a parts sheet is not the plan. The plan comes first; generated sheets are bounded evidence for named owners.

## Scope / Precedence / Completion Contract

When `$kine-layer-v3` is invoked, this `SKILL.md` is the active V3 workflow contract. Global or project `AGENTS.md` files remain useful generic defaults, but they must not downgrade V3 into a minimal plan-only or work-order-only implementation.

For V3, completion means the generated `$imagegen` outputs have been saved into the workspace, ingested, synced into candidates, registered, recomposed, reviewed, and validated as either accepted or clearly blocked. A task is incomplete if it only produced an imagegen work order, a raw sheet, a transparent sheet, a visible cut, a candidate sheet, or a chat-visible generated image.

Every V3 workspace writes `KINE_LAYER_V3_CONTRACT.md`. Read it before continuing an existing workspace. It repeats the local rule that work orders and sheet assets are not final, and that `v3/check/v3-validation-report.json` plus review/registration/recompose/export reports are the source of truth.

If `v3/imagegen/imagegen-progress-report.json` has pending `$imagegen` tasks, do not present the V3 run as complete. The final/status message must say which ImageGen outputs are still missing, unsaved, un-ingested, rejected, or waiting for the next stage. Debug artifacts such as semantic-decomposition boards, annotated maps, source-visible crops, raw sheets, transparent sheets, and candidate sheets are evidence only; they are never replacement deliverables for the V3 source-master pipeline.

`CODEX_HOME` isolation is a debugging or Skill QA tool only. It is not the normal user workflow for running V3.

## Validation Before Optimization

Do not optimize V3 Skill behavior from a written plan alone. Before changing V3 decomposition, prompt, registration, or review semantics, run a small `$imagegen` validation gate:

```text
Generate 3-6 random character source images with $imagegen
 -> save every source image into the project/workspace
 -> write an expected split ledger for each source
 -> render a contact sheet that shows the source images and split decisions
 -> run at least one real role-sheet execution when the ledger passes
 -> render a visual execution board for the real role-sheet run
 -> only then decide whether the Skill change is validated or blocked
```

The small validation gate must produce image evidence, not only text:

- source images saved in the workspace
- expected split ledger
- contact sheet / visual ledger
- validation report with `passed`, `blocked_not_final`, or rejected reasons
- for real role-sheet tests, a visual execution board showing raw sheet, transparent sheet, split parts, registration result, recompose, and diff

If the real role sheet does not pass, do not claim the Skill optimization is complete. Record the result as blocked evidence and use it to choose the next narrow implementation target.

## Validation Terminology

Use precise validation labels in V3 work:

- `code regression validation`: script compile checks, unit tests, schema checks, fixture-based tests, and report field assertions. These checks prove that implementation paths still execute, but they do not prove that V3 works on real generated images.
- `true-image pipeline validation`: a real source image has produced `$imagegen` output, that output was saved at the task's `expectedOutput`, ingested, synced into candidates, registered, recomposed, reviewed, and summarized by `v3-imagegen-execution-report` / `v3-validate`.
- `true-image partial validation`: real `$imagegen` outputs entered the pipeline and reached some downstream gates, but the run still has pending outputs, rejected candidates, missing hidden completion, failed export, or other blockers.

Do not summarize a V3 optimization as "verified", "validated", or "done" when only `code regression validation` has run. In that case say exactly that code regression passed and true-image pipeline validation is still not run.

When a real workspace is blocked, report the blocked stage plainly. For example: role sheets ingested and candidates registered, but hidden inpaint outputs are still missing. Do not collapse that into a generic success or a generic failure.

## First Command

For any V3 workspace, start by writing the V3 scaffold:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-plan \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/component-plan.json
v3/sheet-campaign.json
v3/qa-gates.json
```

These files are binding development artifacts:

- `component-plan.json`: every KINE owner plus animation component rows, role, visibility, identity/source/generation track, mask requirement, hidden-completion requirement, and overlap-zone requirement.
- `sheet-campaign.json`: bounded multi-sheet generation plan split by role, not one giant fragile board.
- `qa-gates.json`: explicit gates for plan completeness, masks, hidden completion, alpha cleanup, source recompose, and pose stress.

## V3 Rules

- Do not ask image generation to invent the decomposition plan. Generate the plan first.
- All drawing/image output must use the `$imagegen` skill. Do not implement an API version, CLI fallback, or alternate drawing backend for KINE-LAYER.
- V3 uses a dual-track check after source routing: local masks/reference bundles provide source-locked boundary evidence, while `$imagegen` produces subject mattes, role sheets, repair candidates, and hidden completion candidates. Neither track alone is final; accepted components must pass registration, recompose, and QA gates.
- Prefer several role-specific parts sheets over one overloaded sheet:
  - `head_identity`
  - `body_clothes`
  - `limbs`
  - `feet_footwear`
  - `props_accessories`
- A mixed visual validation board is useful for judging layout and prompt quality, but it is not a registrable V3 role sheet unless it is ingested with a `sheet-id` that exists in `v3/sheet-campaign.json` and therefore carries `allowedOwners` / `allowedComponents`. If registration reports `candidate_component_pool_missing`, the next action is to save and ingest the missing role-specific sheet outputs, not to tune visual similarity thresholds.
- For role-specific puppet-board sheets, V3 may add conservative `ownerHint` / `ownerCandidate` metadata from sheet role, part position, and coarse color evidence when no manual mapping exists. This only narrows the component pool before normal registration scoring; it must never accept a candidate, bypass source similarity, or override QA/recompose gates.
- Before creating role-sheet prompts, make a visual split decision from the actual image. This is an Agent reasoning step, not a new API: inspect the source/reference board and decide whether garments should stay coherent, split left/right, split front/back, or split by rigid plates. The prompt may only expose drawing-facing `generationTargets`; it must not expose internal thigh/shin/foot registration rows as direct drawing requests.
- Reconcile LLM semantic owners with local pixel evidence before treating any mask as a component truth. LLM/Agent visual understanding decides what stable owners should exist; local alpha clusters, bbox, visible cuts, and crops only provide pixel evidence. If the two disagree, do not accept either side blindly. When the Agent visually sees a stable object that local scripts may miss, it must write `v3/stable-object-notes.json` before role-sheet prompts. Use an `objects` array with semantic fields such as `id`, `type`, `role`, `relationship`, `description`, and optional source `bbox`/`region`. This file is the durable handoff from image understanding into the scripted `stable-object-ledger.json`.
- Foreign stable owner resolution is mandatory: if component A's region contains stable owner B, first check the semantic ledger. If B has no owner slice yet, create B as its own owner or interaction group. If B already has owner evidence, remove B pixels or matching B alpha clusters from A's `cleanOwnerMask`. A may then continue as source-visible owner evidence, while B remains its own owner. Do not reject A merely because the original hard cut contained B.
- `visible_cut` and `mask_region` are source-visible evidence, not automatic hidden-inpaint targets. A registrable owner should use `cleanOwnerMask` plus an explicit completion allowance for hidden surface, overlap, and sockets. ImageGen should fill only missing/hidden/overlap pixels for source-visible owners, not repaint already visible boots, props, clothing layers, hands, or heads wholesale.
- If a `source-visible-*` local candidate registers cleanly and no manual review or explicit hidden target says a hidden surface is missing, mark hidden completion as not required for that component. Do not create a hidden-inpaint `$imagegen` task just because the owner is normally animation-ready; otherwise the model is forced to invent a complete replacement component with no source-canvas target.
- V3 default decomposition has a binding component taxonomy:
  - `final-layer`: animation-ready parts such as whole face/head identity, hair front/back, torso, hips, arms, legs, feet, head accessory, and major props.
  - `source-locked-detail`: face micro details such as eyes, iris/pupil, brows, nose, mouth, ears, ear accessories, and glasses. These are source/reference evidence by default, not independent generated final components.
  - `interaction-group`: hand-held props or contact areas such as hand + glove, hand + umbrella handle, or hand + tool. Keep the contact group coherent unless a later explicit face/prop rig mode asks for separation.
  - `garment-layer`: pants, skirts, coats, sleeves, and boots split by animation joints and overlap needs, not by seams, cuffs, wrinkles, buttons, or loose cloth fragments.
- Split garments and equipment by animation behavior, material, and overlap need, not by a fixed template:
  - Plain standing pants may remain one coherent pants layer, or split into left/right legs when that is better for the rig.
  - Split pants into thigh/shin only when a future explicit knee-rig mode is enabled and the visual split decision says the source supports it. Default V3 role sheets must not ask `$imagegen` for thigh/shin rows.
  - Skirts, dresses, robes, coats, and capes split by cloth layer, front/back occlusion, and swing area; never by folds, trims, buttons, seams, or decorative fragments.
  - Armor splits by rigid plate and joint overlap; never by highlights, scratches, rivets, or tiny trim.
- Face and facial micro owners are identity/source-locked evidence first. Do not redraw tiny organs as independent generated identity changes. Default V3 is 2D skeletal character decomposition, not a face-puppet mode; eye/mouth/brow separation requires an explicit future mode.
- Source-locked identity rows such as `face` do not require generated hidden completion by default. They may keep source-visible reconstruction evidence, but they must not create hidden-inpaint `$imagegen` tasks unless an explicit future face/identity rig mode or manual review decision asks for it.
- Hand-held and worn-contact objects default to `interaction-group`: hand + umbrella handle, hand + glove, hand + tool, hand + bag strap, or hand + weapon grip must preserve contact pixels together. Separate the prop from the hand only when a downstream rig explicitly needs independent prop motion, and then record the socket/pivot relationship.
- Stable prop coverage is a hard quality gate: if the source or role sheets show a stable held/worn object such as a knife, sword, staff, umbrella, bag, shield, gun, or tool, the V3 plan/export must contain a matching `props` owner or interaction-group. A hand/arm candidate that contains a weapon or tool is not ordinary arm pollution; it is evidence that the stable prop ledger is incomplete.
- Stable object recognition is a generation prerequisite, not only a blocker. Before writing role-sheet prompts, V3 must write `v3/stable-object-ledger.json`. Active stable objects such as weapons, staffs, umbrellas, bags, books, shields, tools, instruments, worn pouches, straps, back-mounted devices, or other persistent character-owned objects must activate the `props` owner, enter `v3/component-plan.json`, enter `v3/sheet-campaign.json`, enter `v3/sheet-prompts.json`, and enter `v3/imagegen/imagegen-work-order.json` as explicit `generationTargets`. Tiny details such as buttons, seams, highlights, wrinkles, logos, rivets, scratches, and texture marks are `non-component-detail` and must not create props sheets.
- Stable object role sheets and repair sheets must use real reference packages: full source image, object-local crop, nearby-contact crop, clean owner mask or visible evidence, and source anchor/calibration guides. The prompt must preserve object type, direction, material, grip/contact relation, and source-canvas scale. It must not replace a knife with another weapon, turn a staff into another tool, detach handles/straps/fingers, generate floating fragments, or create multi-view design-board alternates.
- If `stable_owner_missing_props` or an active stable-object ledger remains after role sheets were ingested, V3 must create a `stable_object_repair` `$imagegen` task. That repair task is not final art: it must be saved at `expectedOutput`, ingested as a parts sheet, synced into candidates, registered, recomposed, exported, and validated through `v3-continue-imagegen`.
- Generated candidate proportion consistency is a hard quality gate: record each role-sheet candidate's sheet bbox, target source bbox, scale factors, aspect drift, outside-mask ratio, and rejection reasons. If all real `$imagegen` candidates fail while `source-visible-*` fallback candidates pass, report this as generated candidate quality failure instead of hiding it behind a passing source-visible reconstruction.
- Proportion control is local to each source part. V3 must not force every generated component to a universal sheet scale. Each drawing-facing `generationTarget` should carry `targetSourceBbox` / `sourceScaleAnchor` from the corresponding source-canvas part or stable object. `$imagegen` should match that target's source width, height, aspect, and canvas-relative scale: a boot must follow the source boot scale, a head must follow the source head scale, and a weapon must follow the source weapon scale.
- A generated parts sheet is only candidate art. It becomes a component only after owner mapping, alpha cleanup, source-canvas registration, and QA.
- Role sheet QA must reject over-fragmented head micro sheets, garment-fragment sheets, broken hand-held interaction groups, and under-split connected limb sheets before candidate registration.
- Hidden/occluded content is a separate gate only when a component has an explicit hidden/overlap target or manual review asks for it. A source-visible local candidate can pass the default V3 flow when registration, recompose, pose-stress, Review integrity, export, and validation gates pass; it must not be routed into hidden-inpaint by default.
- Final claims must distinguish:
  - source-locked reconstruction
  - generated completion candidates
  - accepted final components
  - blocked evidence
- Review HTML should prioritize visual inspection: Original, Combined/candidate sheet, Components. Debug QA metrics may exist in JSON or a folded debug drawer, but should not dominate the page or appear in the header summary.
- Review must still show missing, rejected, or no-image V3 components as placeholder cards so component count and failure state remain visible. V3 Review supports status filtering, per-card detail toggles, and large image preview for visual inspection.
- Do not expose `review.html` as the user-facing deliverable while V3 is still blocked, has pending `$imagegen` tasks, has no accepted registered components, or has not passed `v3/check/v3-validation-report.json`. In that state `review.html` is a debug/review artifact only; show `v3/imagegen/imagegen-execution-board.png`, `v3/imagegen/v3-imagegen-execution-report.json`, and `v3/imagegen/imagegen-progress-report.json` instead.

## Standard Flow

1. Initialize or reuse a workspace:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py run \
  --source /absolute/path/source.png \
  --out-root /absolute/path/workspaces
```

Initialization writes `source/source-background-preflight.json` and `source/source-subject-preflight.json`.

V3 routes the source before component splitting:

- If the source already has high-confidence useful alpha, continue directly. Existing alpha is not automatically trusted: sparse alpha, edge scene fragments, too-small boxes, or low-confidence subject geometry must route to subject isolation instead of component splitting.
- If the source has an opaque flat border background such as green screen, V3 removes only the background-color region connected to the canvas edge before partitioning and records `source/preprocessed-alpha.png`. Isolated same-color pixels inside the character, such as green eyes or green costume details, are preserved.
- If the source is an opaque non-flat scene, such as a character in front of an aircraft, grass, sky, buildings, or other complex background, V3 must not generate component masks or visible cuts from that scene source. It writes a `$imagegen` subject matte task first. The V3 agent must then call the `$imagegen` skill, save the matte at the task's `expectedOutput`, ingest it, and continue V3 on the clean character workspace. Do not hand this back to the user as a manual command sequence.

Initialization also preserves an un-keyed, normalized original reference at `source/original-normalized.png`. Use this as the color/detail authority when chroma-key cleanup may have removed source-like colors inside the character.

For an existing workspace, these commands are internal recovery/debug anchors for inspecting source background and subject routing state:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-source-preflight \
  --workspace /absolute/path/workspace

python3 skill-v3/scripts/kine_layer_workspace.py v3-subject-preflight \
  --workspace /absolute/path/workspace
```

When `v3-subject-preflight` reports `needs_imagegen_subject_matte`, the user-facing flow is still automatic:

```text
V3 agent reads the subject matte work order
 -> loads source.png into the $imagegen context
 -> uses the $imagegen skill in built-in mode to remove scene/background objects
 -> saves a full-canvas high-resolution PNG at expectedOutput
 -> runs v3-continue-imagegen internally
 -> continues V3 on the resulting clean character workspace
```

For built-in `$imagegen`, a generated image that is only visible in chat is not pipeline evidence. The Agent must file it into the work order's `expectedOutput` path before continuing. `$imagegen` outputs should be requested as PNG. PNG may be opaque or transparent; if the built-in tool returns an opaque chroma-key PNG, V3 locally removes only the requested edge-connected chroma-key background before ingest.

If built-in `$imagegen` returns a file path through `savedPath` or by writing under `$CODEX_HOME/generated_images`, the Agent must file that PNG through the internal adapter before continuing:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-save-imagegen-inline \
  --workspace /absolute/path/scene-workspace \
  --task-id subject-matte:source-character \
  --input /absolute/path/to/imagegen-output.png \
  --edge-chroma-key task
```

If built-in `$imagegen` returns `savedPath: null` but exposes an inline PNG/base64 image result, the Agent must save that inline result through the same adapter before continuing:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-save-imagegen-inline \
  --workspace /absolute/path/scene-workspace \
  --task-id subject-matte:source-character \
  --base64-file /absolute/path/imagegen-result.base64.txt \
  --edge-chroma-key task
```

This command is not a drawing backend. It only files an already generated `$imagegen` PNG result at the task's `expectedOutput`, removes only edge-connected chroma-key background when requested, writes `v3/imagegen/imagegen-result-save-report.json`, and leaves ingest/QA gates in control.

`v3-save-imagegen-inline` status must be read literally:

- `saved_ready_for_ingest`: the generated PNG was saved and `v3-imagegen-progress-report` says the task can be ingested.
- `saved_blocked_not_final`: the generated PNG was saved, but the task still cannot be ingested. Read `blockers` / `outputInspection`; common blockers include hidden output canvas-size mismatch, empty alpha, unreadable image, or rejected sheet preflight.
- `blocked_not_final`: the result could not be filed safely.

Never treat "saved" file existence alone as continuation success.

After the subject matte is saved, use the internal continuation command:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-continue-imagegen \
  --workspace /absolute/path/scene-workspace
```

`v3-continue-imagegen` consumes already-saved `expectedOutput` PNG files and dispatches ready tasks to existing structured ingest functions. For subject matte it creates the clean character workspace. For role sheets and registration repairs it ingests the parts sheet and reruns candidate sync, registration, hidden jobs, recompose, Review HTML refresh, review integrity, and validation. For hidden inpaint it ingests the component hidden PNG and reruns hidden review, recompose, pose stress, Review HTML refresh, review integrity, and validation. It does not generate images and it does not add any drawing backend.

The shell commands below are recovery/debug anchors only. They are not the normal user workflow:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-imagegen-work-order \
  --workspace /absolute/path/scene-workspace

# after $imagegen saves imagegen/v3/source-character-matte.png:
python3 skill-v3/scripts/kine_layer_workspace.py v3-ingest-subject-matte \
  --workspace /absolute/path/scene-workspace \
  --matte /absolute/path/scene-workspace/imagegen/v3/source-character-matte.png \
  --out /absolute/path/clean-character-workspace
```

2. Write the V3 plan:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-plan \
  --workspace /absolute/path/workspace
```

3. Write component mask jobs:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-mask-jobs \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/masks/jobs/<component>.json
v3/masks/<component>.mask.png
v3/masks/<component>.clean_owner_mask.png
v3/masks/<component>.source_visible_mask.png
v3/masks/<component>.source_visible_cut.png
v3/masks/<component>.foreign_removed_mask.png
v3/masks/<component>.visible_cut.png
v3/masks/mask-summary.json
```

Mask jobs record `maskSource` in the job JSON, component plan, and summary. Current sources are `source_partition_*`, `vlm_cutout_map_region` from `cutout-map.json` / `v3/visual-split-decision.json`, and `registered_candidate_alpha` from already registered source-canvas candidate evidence. V3 does not trust an unregistered parts-sheet crop as a final mask source.
When a component mask contains another stable owner that already has owner evidence, `v3-mask-jobs` writes both the original source-visible mask and the cleaned owner mask. The cleaned mask is the default `mask` / `visibleCut`; the original hard-cut evidence remains available as `sourceVisibleMask` / `sourceVisibleCut`. Foreign-owner subtraction is conservative: only trusted independent owners, such as props or discrete accessories, may be removed automatically. Broad body/clothing/limb bbox evidence is recorded in `foreignOwnerResolution.skippedOwners` and must be handled by registration/recompose QA instead of destructive subtraction.

4. Write per-component reference bundles:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-reference-bundles \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/references/reference-bundles.json
v3/references/components/<component-id>/reference-bundle.json
v3/references/components/<component-id>/original_region.png
v3/references/components/<component-id>/original_masked.png
v3/references/components/<component-id>/processed_region.png
v3/references/components/<component-id>/mask_region.png
v3/references/components/<component-id>/clean_owner_mask_region.png
```

Reference priority for `$imagegen` tasks:

- `source/original-normalized.png`: identity, global style, and full-body proportions.
- `original_region.png`: local color, facial/detail, material, and pixels that may have been lost by chroma-key cleanup.
- `visible_cut.png` / `mask_region.png`: source-visible evidence for shape and alpha boundary only; these are not the color authority and are not final component masks when polluted by another stable owner.
- `cleanOwnerMask` / `clean_owner_mask_region.png` / owner-guide evidence, when present: the preferred local boundary evidence after semantic owner reconciliation. It must document which foreign owners were created or subtracted, and it still does not bypass registration, recompose, or review QA.
- Experimental validation workspaces may include `v3/calibration/source-silhouette.png`, `source-edge-lineart.png`, `source-anchor-map.png`, and `source-calibration-board.png` as ControlNet-style visual references for contour, internal lines, pose/anchor placement, and recompose alignment. These files are not a new drawing backend and do not prove a component is accepted. Only promote their rules into default behavior after a real `$imagegen` run shows improved sheet output and the downstream registration/recompose gates explain the result.
- If a reference bundle marks a visible cut or mask as `referenceStrength=weak_fragment` or `useAsPrimaryReference=false`, treat it as diagnostic evidence only. Use the original region, full source, visual split decision, and any validated calibration guides as stronger references.

Execution contract for `$imagegen` tasks:

- Do not rely on prompt text paths alone. Built-in `$imagegen` does not automatically read local file paths mentioned in a prompt.
- Every `v3/imagegen/imagegen-work-order.json` task may include `inputImages`; before calling `$imagegen`, load every `inputImages[].path` into the image context. V3 also writes `v3/imagegen/reference-boards/*.reference-contact.png` for each task. If the execution surface cannot load many separate local images, load that reference-contact board into context instead; it visibly contains the same inputs and is saved as execution evidence.
- For every role sheet, registration repair, and hidden inpaint task, the required reference package is:
  1. `source-original-full`: identity, global style, and proportions.
  2. `component-original-region`: the unprocessed source crop for local color/detail/material.
  3. `component-clean-owner-mask`: cleaned owner boundary after subtracting trusted independent foreign owners; broad body/clothing bbox overlaps remain diagnostic evidence instead of being destructively erased.
  4. `component-visible-cut` plus `component-mask-region`: shape, silhouette, alpha boundary, and registration evidence.
- If `inputImages` is missing for a component task, regenerate `v3-reference-bundles`, `v3-sheet-prompts`, and `v3-imagegen-work-order` before drawing. Do not proceed with only the text prompt except for subject matte isolation, which still must load `source.png`.

`v3-sheet-prompts`, `v3-registration-repair-report`, and `v3-hidden-handoff` auto-create these bundles when missing.

5. Generate bounded role sheets from `v3/sheet-campaign.json`.

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-sheet-prompts \
  --workspace /absolute/path/workspace
```

6. Ingest each sheet with append semantics:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py parts-sheet \
  --workspace /absolute/path/workspace \
  --sheet /absolute/path/sheet.raw.png \
  --sheet-id sheet-001 \
  --role head_identity \
  --append \
  --chroma-key auto
```

7. Sync split sheet candidates into the V3 candidate pool:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-sync-candidates \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/candidates/<sheet-id>-<part-id>.png
v3/sheets/sheet-manifest.json
```

8. Register and QA:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-register-candidates \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/registration/registration-report.json
v3/registration/<component-id>/<candidate-id>.registered.png
```

Then run the legacy QA/review checks while V3 recompose gates are still being developed:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py qa \
  --workspace /absolute/path/workspace

python3 skill-v3/scripts/kine_layer_workspace.py validate-html \
  --workspace /absolute/path/workspace
```

V3 candidate registration is component-level evidence. `auto-register-parts` is still available for the V2 owner-level path, but it is not the V3 registration gate.
If a sheet produces candidates but `v3/registration/registration-report.json` has `acceptedCount: 0`, aggregate validation must block with `no_candidates_accepted`; rejected candidates are useful diagnostics, not accepted components.
Registration reports must include human-readable rejection details alongside internal codes. Codes such as `owner_pollution`, `source_similarity_failed`, `shape_mismatch`, and `identity_drift` are not enough on their own; reports and repair tasks should explain in plain language what failed and which next action is expected. These explanations are diagnostics only and must not relax registration, recompose, or QA gates.

9. Write registration repair tasks when candidates are rejected:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-registration-repair-report \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/registration/registration-repair-report.json
v3/registration/REGISTRATION_REPAIR_HANDOFF.md
v3/registration/repair-prompts/<component-id>.prompt.txt
```

The report turns rejected reasons such as `source_similarity_failed`, `owner_pollution`, `shape_mismatch`, and `hidden_area_missing` into concrete `$imagegen` repair tasks for components that do not yet have an accepted candidate. It does not accept repaired art. Save repaired output at the task's `expectedOutput`, run its `ingestCommand`, then rerun `v3-sync-candidates`, `v3-register-candidates`, `v3-recompose`, and `v3-validate`.

To produce one execution checklist for all pending `$imagegen` tasks:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-imagegen-work-order \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/imagegen/imagegen-work-order.json
v3/imagegen/IMAGEGEN_WORK_ORDER.md
```

The work order is staged, not one giant checklist:

```text
stage 1: role_sheets
  -> generate only role-specific parts sheets
  -> save each sheet at expectedOutput
  -> run ingestCommand
  -> run v3-continue-imagegen

stage 2: repair_and_hidden
  -> generated only after role sheets have been ingested and candidate sync / registration / recompose / validation have refreshed
  -> generate registration repairs or hidden inpaint only for components that still need them
  -> save each output at expectedOutput
  -> run ingestCommand
  -> run v3-continue-imagegen again
```

Every task in `imagegen-work-order.json` must include `agentAction`, `completionCriteria`, `expectedOutput`, and `ingestCommand`. The Agent must execute these fields, not merely list them in the final answer. A parts sheet visible in chat but not saved at `expectedOutput` is not pipeline evidence and must not be presented as a final result.

Initial role-specific parts sheet tasks come from `v3-sheet-prompts`. Each sheet must be saved at its `expectedOutput` path and then ingested with the listed `parts-sheet --append --chroma-key auto` command. Registration repair and hidden inpaint tasks must not be generated or treated as active until all role sheets in the current campaign have been saved and ingested.

If a generated sheet was saved under an ad-hoc sheet id such as `controlled_layout_mixed`, it may still be useful visual evidence, but V3 registration must block with `candidate_component_pool_missing` until the real role-specific `sheet-001`, `sheet-002`, etc. outputs are saved and ingested. Do not interpret this blocker as proof that the art is visually bad; it means the candidate has no component pool to match against.

Fresh `run` automatically refreshes the work order, progress report, and workspace-local execution report before it finishes, then records them in `run-state.json` as `v3ImagegenWorkOrder`, `v3ImagegenProgressReport`, and `v3ImagegenExecutionReport`. This prevents a raw sheet or semantic-decomposition package from being treated as the final artifact while the save/ingest/register/hidden/export steps are still missing.

After saving `$imagegen` outputs at their `expectedOutput` paths, inspect ingest readiness:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-imagegen-progress-report \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/imagegen/imagegen-progress-report.json
```

The progress report checks missing outputs, unreadable images, empty alpha, hidden-output canvas-size mismatches, and already-ingested hidden outputs. It does not ingest or accept art; it only tells you which tasks are ready to run their listed ingest command.

After a ready output exists, run:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-continue-imagegen \
  --workspace /absolute/path/workspace
```

`v3-continue-imagegen` must refresh the next work-order stage and `v3/imagegen/v3-imagegen-execution-report.json` after ingest. It must also refresh the staged work order when there are no ready outputs and the run is only waiting on pending `$imagegen` tasks; stale pending tasks are not allowed to survive after component-plan, hidden requirement, or handoff rules change. If it reports `needs_imagegen`, the run is still waiting for another `$imagegen` output; use the execution report's pending task list to say which expected outputs are missing or ready for ingest. If it reports `blocked_not_final`, report the blocker plainly instead of wrapping a semantic-decomposition or debug package as the deliverable.

10. Write hidden completion jobs:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-hidden-jobs \
  --workspace /absolute/path/workspace
```

This writes the V3 hidden four-pack for each component:

```text
v3/hidden/<component-id>/registered_merged.png
v3/hidden/<component-id>/registered_merge_report.json
v3/hidden/<component-id>/registered_merge_conflicts.png
v3/hidden/<component-id>/visible_cut.png
v3/hidden/<component-id>/hidden_inpaint.png
v3/hidden/<component-id>/merged_component.png
v3/hidden/<component-id>/qa_overlap.png
v3/hidden/hidden-report.json
```

The command does not pretend missing hidden art is complete. Components that need hidden completion but have no usable hidden pixels stay `missing`. If a component has multiple registered candidates, hidden extraction uses deterministic merged source-canvas evidence instead of only the first candidate. The merge is written with a score-sorted order report and, when candidates overlap, a conflict heatmap for later real-sample calibration.

When hidden pixels are still missing, write explicit `$imagegen` skill tasks:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-hidden-handoff \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/hidden/hidden-inpaint-handoff.json
v3/hidden/HIDDEN_INPAINT_HANDOFF.md
```

Each task names the component, prompt, visible cut, registered evidence, expected full-canvas transparent output, and exact ingest command. `$imagegen` is the only drawing path for KINE-LAYER; do not create an API version, CLI fallback, or alternate drawing backend. After `$imagegen` output is saved at the expected path:

Hidden inpaint handoff tasks must be executable without consulting another incomplete file. Every task must include `taskId`, `taskType`, `inputImages`, `referenceContactBoard`, `agentAction`, `completionCriteria`, `expectedOutput`, and `ingestCommand`. The staged `v3/imagegen/imagegen-work-order.json` may aggregate these tasks, but `v3/hidden/hidden-inpaint-handoff.json` must remain complete enough for a later Agent to load the reference board, call `$imagegen`, save the output, ingest it, and continue.

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-ingest-hidden \
  --workspace /absolute/path/workspace \
  --component torso \
  --image /absolute/path/workspace/v3/hidden/torso/imagegen_hidden_inpaint.png \
  --provenance-source imagegen
```

Ingest updates `hidden_inpaint.png`, `merged_component.png`, `qa_overlap.png`, `job.json`, `hidden-report.json`, `component-plan.json`, and writes `hidden-inpaint-provenance.json`.
`v3-ingest-hidden` rejects hidden art that substantially overlaps the source-visible `visible_cut`; `$imagegen` hidden output must add only hidden/occluded/overlap pixels, not repaint visible source pixels.

11. Review `$imagegen` hidden inpaint outputs:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-hidden-review-report \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/hidden/review/hidden-inpaint-review-report.json
```

The report lists each `$imagegen` hidden output, provenance, hidden pixel count, visible-overlap status, QA overlap image, and whether human review is still required. To apply batch review decisions:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-hidden-review-report \
  --workspace /absolute/path/workspace \
  --decisions /absolute/path/workspace/v3-hidden-review-decisions.json
```

The decisions JSON must use type `kine.v3.hiddenInpaintReviewDecisions` with `accepted`, `rejected`, or `needs_revision` rows. Manual `accepted` is evidence only. Manual `rejected` or `needs_revision` writes back to `v3/component-plan.json` and blocks final export.

12. Run V3 source recompose:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-recompose \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/check/recompose.png
v3/check/source-diff.png
v3/check/recompose-report.json
```

Only accepted components with `mergedComponent` evidence are composed. Missing registration or merged artifacts are reported, not filled from source locks. The report includes `perComponentQuality` for source-visible mismatch diagnosis, so a failed Combined image can be traced back to the component that introduced missing alpha or RGB drift. Failed component-visible checks also write `v3/check/component-quality/<component-id>/visible-mismatch-heatmap.png`.

13. Run V3 pose stress:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-pose-stress \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/check/pose-stress/<case>.png
v3/check/pose-stress/<case>.gap.png
v3/check/pose-stress-report.json
```

The command writes small-angle pivot/socket preview evidence for accepted merged components. Each report case includes `pixelGap` diagnostics for alpha retention, gap pixels, new alpha pixels, gap bbox, and an optional gap heatmap. `v3/qa-gates.json` can set `pose_stress.pixelGapPolicy` to `diagnostic` or `hard_fail`, with `maxGapRatio`, `maxGapPixels`, and `maxNewAlphaRatio` thresholds. It is a gate, not a full rig simulation: missing pivots, missing overlap evidence, or missing draw order are reported as failures, while pixel gap thresholds should be switched to `hard_fail` only after real character calibration.

14. Aggregate pose gap calibration evidence:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-pose-calibration-report \
  --workspace-root /absolute/path/workspaces \
  --refresh
```

This writes:

```text
<workspace-root>/v3-pose-calibration-report.json
```

The report aggregates `gapRatio`, `gapPixels`, and `newAlphaRatio` across V3 pose-stress cases, lists the largest gap cases, and recommends thresholds for later human-calibrated `hard_fail` use. It does not modify `v3/qa-gates.json`; copy thresholds only after visual review of the largest gap cases.

15. Apply Review decisions when a human reviewer marks V3 cards in `review.html`:

Before applying decisions, verify that Review is showing the current V3 evidence:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-review-integrity-report \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/review/review-integrity-report.json
```

The report verifies that `review.html` exposes active V3 components, split parts-sheet candidates, rejected candidates, the correct Combined/candidate-sheet image, and folded debug evidence. It blocks stale or partial Review pages, including cases where Combined shows an old hard cutout, only a head, too few component cards, or visible debug text such as reconstruction QA metrics.

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-apply-review-decisions \
  --workspace /absolute/path/workspace \
  --decisions /absolute/path/workspace/v3-review-decisions.json
```

The Review page stores decisions locally in the browser and downloads a `kine.v3.reviewDecisions` JSON file. Applying it writes `v3/review/review-decisions-applied.json` and annotates `v3/component-plan.json`. Manual `rejected` blocks export; manual `accepted` is review evidence only and does not bypass review integrity, recompose, pose-stress, or hidden-completion gates.

16. Export V3 accepted final components:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-export \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/export/components/*.png
v3/export/components-manifest.json
v3/export/kine-handoff-manifest.json
v3/export/source-master-v3.psd  # only when export provenance is final-exportable
```

The export is blocked unless V3 recompose, pose-stress, stable-owner coverage, generated-candidate quality, and export-provenance gates pass. Only accepted merged components are exported. A PSD for the normal final path may only contain accepted generated/merged component assets; `source-visible-*` fallback layers are debug/source-lock evidence and must not be labeled as a normal final redrawn PSD. If the run can only export source-visible fallback components, `components-manifest.json` must be `blocked_not_final` or explicitly mark the PSD/export as `source-visible-fallback`, not `final_exportable`.
`components-manifest.json` and `kine-handoff-manifest.json` include `runtimeTargets.spine` and `runtimeTargets.live2d` with bone/slot, parent, socket, pivot, placement, and draw-order metadata for downstream rigging. These are handoff contracts only; V3 does not claim to generate Spine meshes, Live2D deformers, weights, or animation curves.

17. Validate exported handoff manifest references:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-validate-handoff \
  --workspace /absolute/path/workspace
```

This writes:

```text
v3/export/handoff-validation-report.json
```

The command checks exported component PNG references, placement versus source canvas bounds, non-empty alpha, Spine slot/image/attachment/bone references, and Live2D part/texture references. It is schema and reference validation only; it does not prove a complete Spine or Live2D rig import.

18. Record external Spine/Live2D import evidence:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-runtime-import-report \
  --workspace /absolute/path/workspace \
  --evidence /absolute/path/workspace/v3-runtime-import-evidence.json
```

This writes:

```text
v3/export/runtime-import-report.json
```

The evidence JSON must use type `kine.v3.runtimeImportEvidence` with `imports` rows for `spine` and `live2d`. A row can be `passed`, `failed`, or `skipped`; `passed` records downstream confidence, while failed evidence remains visible as an external runtime blocker. This records manual or external-tool import evidence only. It does not generate Spine meshes, Live2D deformers, weights, or animation curves.

19. Write the aggregate V3 validation report:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-validate \
  --workspace /absolute/path/workspace
```

This writes `v3/check/v3-validation-report.json` by reading the current V3 artifacts. It is a read-only hardening report: missing or failed source-master gates stay blocked and are never promoted to final components. If `$imagegen` hidden outputs exist, `hidden_inpaint_review` must pass before aggregate validation can pass. External Spine/Live2D runtime import evidence is recorded separately by `v3-runtime-import-report`; missing external import evidence does not block the default V3 source-master validation, but actual failed runtime import evidence remains visible in the report.

20. Aggregate real-sample hardening reports across workspaces:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-hardening-report \
  --workspace-root /absolute/path/workspaces \
  --refresh
```

This writes:

```text
<workspace-root>/v3-hardening-report.json
```

Use this after running several real characters through V3. The report summarizes workspace pass/block counts, per-gate status counts, top blockers, and blocked gates per workspace. It does not generate art, call an API, or promote blocked components. Pass `--workspace` more than once to aggregate explicit workspaces, and `--out` to choose a custom report path.

21. Audit real `$imagegen` role-sheet execution:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-imagegen-execution-report \
  --workspace /absolute/path/workspace \
  --refresh
```

Use this whenever testing whether `$imagegen` actually followed the V3 decomposition contract. It reads the work order, saved `expectedOutput` files, parts-sheet ingest evidence, sheet preflight reports, V3 candidate sync, registration report, and V3 validation report. It distinguishes:

- `no_imagegen_execution`: no real role-sheet output entered the pipeline.
- `imagegen_execution_failed`: role-sheet output was saved/ingested but sheet preflight or registration failed.
- `imagegen_execution_partial`: at least one candidate registered, but hidden/recompose/export validation is still incomplete.
- `passed`: aggregate V3 validation passed.

This report is the preferred evidence for debugging "only isolated subject", "sheet generated but not ingested", "sheet over-fragmented", and "0 accepted candidates" cases. Screenshots, work orders, raw sheets, and chat-visible images are not enough.

For a single `--workspace`, `v3-imagegen-execution-report` writes `v3/imagegen/v3-imagegen-execution-report.json` inside that workspace. For `--workspace-root`, it writes an aggregate report at `<workspace-root>/v3-imagegen-execution-report.json`. The report includes pending `$imagegen` task counts and the exact `expectedOutput` paths that are missing or ready for ingest.

`v3-imagegen-execution-report` also writes a per-workspace board at `v3/imagegen/imagegen-execution-board.png`. You can refresh that board directly:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py v3-imagegen-visual-board \
  --workspace /absolute/path/workspace
```

For real role-sheet validation, the visual execution board must show, in one readable image or HTML page:

- the source image
- the loaded reference package or reference-contact board
- raw `$imagegen` role sheets
- transparent sheets after chroma-key cleanup
- parts contact sheets
- accepted and rejected candidate evidence
- V3 recompose and source diff

Without this visual execution board, the validation is incomplete even if JSON reports exist.

22. Package only when QA state is honestly represented:

```bash
python3 skill-v3/scripts/kine_layer_workspace.py package \
  --workspace /absolute/path/workspace \
  --allow-blocked
```

## Development Boundary

V3 is experimental. Keep V2 stable. Put V3-only behavior in `skill-v3/` unless the user explicitly asks to backport it.
