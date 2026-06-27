---
name: kine-image-kids
description: Generate or prompt children educational game images in a consistent KINE-KIDS rounded flat style, using $imagegen for all raster drawing and generation. Use when the user asks to create backgrounds, people, children, animals, mascots, props, furniture, appliances, flowers, grass, trees, UI-like game scenes, asset sheets, object sheets, or "anything" as a raster image while preserving the same cute low-detail educational-game visual language.
---

# Kine Kids Image

## Overview

Use this skill to turn any subject brief into a KINE-KIDS image prompt and, when asked to draw/generate, produce the raster image through `$imagegen`. The style is reusable across arbitrary content: scene, character, animal, object, furniture, appliance, plant, prop, reward item, card, or combined game screen.

This skill defines the visual grammar and owns the prompt. It delegates raster drawing to `$imagegen` and does not replace vectorization, rigging, Rive, or HTML/CSS implementation skills.

## Workflow

1. Classify the output:
   - `background`: empty playable environment, no characters.
   - `character`: one person, child, mascot, animal, creature, or role.
   - `object`: one prop, tool, furniture item, appliance, toy, food, vehicle, plant, or natural object.
   - `element_sheet`: multiple separated reusable elements.
   - `character_sheet`: multiple separated characters or variants.
   - `combined_scene`: background plus characters/objects arranged as a game moment.
   - `ui_game_screen`: combined scene with simple game UI only when the user asks for UI.
2. Extract the variable brief:
   - subject(s)
   - scene/backdrop
   - learning or gameplay task
   - props/elements
   - required mood or action
   - output shape: wide scene, square asset, isolated object, sheet, transparent-ready source, or project asset
3. Preserve the KINE-KIDS style contract below. Replace only the content variables.
4. Assemble the prompt (see Prompt Assembly and `references/prompt-templates.md`).
5. If the user asks to generate/draw, first load and follow `$imagegen`; use its default built-in `image_gen` tool mode for raster generation.
6. Do not use fal.ai, `giggle:fal-skill`, `genmedia`, custom OpenAI API scripts, SVG stand-ins, or HTML/CSS/canvas placeholders for raster drawing.
7. If transparent assets are requested, follow `$imagegen` built-in-first chroma-key workflow. Do not silently switch to CLI/native transparency.
8. Review the result with the quality gates. If it fails, revise one constraint at a time and regenerate through `$imagegen`.
9. Report the final prompt and generated image path when an image is created.

## Style Contract

Always include these style constraints unless the user explicitly asks to depart from the style:

- clean 2D flat vector-like children's educational game illustration
- soft rounded blob silhouettes and simple geometric construction
- low detail, high recognition, thumbnail-readable shapes
- minimal or no outlines; separate forms by color blocks and subtle same-color shadow shapes
- smooth flat fills, no realistic texture, no painterly brushwork, no glossy 3D rendering
- very limited gradients; avoid glow, rim light, cinematic lighting, and rendered illustration depth
- oversized round white eyes with small dark pupils for living characters
- tiny curved smiles, simple symbolic noses/mouths, friendly expressions
- bodies and objects built from circles, ovals, beans, pills, rounded rectangles, and soft triangles
- cheerful, safe, playful, preschool/early-learning mood
- open composition, clear spacing, no clutter
- palette with fresh greens, teals, warm browns, bright friendly accents, and soft pastels adjusted to the subject

## Content Independence Rule

Do not bind the style to forest, animals, grass, or any specific lesson unless the user asks for that content. The content layer is a replaceable variable:

```text
Scene/backdrop: <any place>
Subject: <any person/animal/object/thing>
Task: <any learning or gameplay action>
Props/elements: <any supporting items>
Composition: <background, character, object, sheet, or combined scene>
Palette: <subject-appropriate colors that still stay bright, flat, and child-friendly>
```

For example, the same style can apply to an underwater counting game, a kitchen vocabulary lesson, a classroom sorting task, a space matching game, a farm scene, a single toaster prop, a sofa asset, or a sheet of flowers and trees.

## Prompt Assembly

Use the compact prompt pattern for simple requests:

```text
Create [output type] for a children's educational game in the KINE-KIDS rounded flat style.
Subject/content: [user variables].
Style: clean 2D flat vector-like educational app art, rounded blob silhouettes, low detail, smooth flat colors, minimal/no outlines, subtle same-color shadows, cute readable shapes.
Composition: [wide scene / isolated object / separated sheet / combined game screen].
Mood: cheerful, friendly, safe, playful.
Constraints: no text unless requested, no logos, no watermark, no photorealism, no 3D render, no complex texture, no heavy outlines, no scary mood, no clutter.
```

For precise output types, read `references/prompt-templates.md`.

## Generation (via $imagegen)

Rendering must go through `$imagegen`.

1. Read `$imagegen` before the first generation in a session.
2. Use `$imagegen` default built-in tool mode for normal KINE-KIDS raster generation and editing.
3. Treat the KINE-KIDS prompt assembled here as the `Primary request` / visual spec inside `$imagegen`'s prompt schema.
4. For transparent/cutout-ready requests, use `$imagegen`'s built-in-first chroma-key workflow and local removal helper. Ask before switching to true/native CLI transparency exactly as `$imagegen` requires.
5. If the output is project-bound, follow `$imagegen`'s save-path policy and move or copy the final selected image into the project workspace.
6. Report the final prompt and the saved image path. Do not report fal endpoint ids, genmedia request ids, or model-specific parameters.

## Quality Gates

Revise when:

- the result looks like generic storybook art instead of a flat educational game asset
- objects or characters use too many tiny details
- shapes are sharp, realistic, textured, furry, painterly, or 3D
- characters lack big readable eyes or simple friendly expressions
- a sheet has overlapping assets or background clutter
- a background has characters when the request was background-only
- an object asset is not isolated enough to reuse
- a combined scene lacks open gameplay space
- the palette is muddy, overly dark, or dominated by one dull hue
- the image has too much glow, gradient shading, cinematic lighting, or storybook depth
- text, logos, watermarks, or unintended UI appear

When a gate fails, change one constraint in the prompt and regenerate through `$imagegen`; do not rewrite the whole prompt.

## Handoff Notes

If the user later wants SVG/Rive, treat the generated raster as the accepted visual reference and hand off to the relevant vector or rigging skill. Keep this skill focused on producing and validating the KINE-KIDS visual image style, with generation delegated to `$imagegen`.
