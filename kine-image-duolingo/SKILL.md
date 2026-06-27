---
name: kine-image-duolingo
description: Generate children's educational game images in a Duolingo-style flat vector aesthetic — bold rounded shapes, very high-saturation flat color blocks, no gradients / no texture / minimal outlines, friendly mobile-game art — rendering must use $imagegen and its built-in image_gen tool by default. Use when the user wants the "Duolingo style" / "多邻国风格" flat look for backgrounds, scenes, props, plants, animals, characters, or asset sheets, especially to match the Garden 1-1 garden background. Triggers — "多邻国风格", "Duolingo style", "扁平高饱和的图", "做个扁平背景/场景", "和花园背景统一风格".
---

# Kine Image Duolingo

## Overview

Turn any subject brief into a **Duolingo-style flat vector** image prompt and, when asked to draw/generate, produce the raster image through `$imagegen`. This style is the one that produced the Garden 1-1 garden background (sun + tree + fence + grass + flowers); it is reusable across arbitrary content: scene, background, character, animal, object, plant, prop, reward item, card, or asset sheet.

This skill **defines the visual grammar and owns the prompt**. Actual rendering must use `$imagegen` (`/Users/tvwoo/.codex/skills/.system/imagegen/SKILL.md`), following that skill's default built-in `image_gen` path unless the user explicitly requests and confirms an `$imagegen` CLI fallback. It does not replace vectorization, Rive, or HTML/CSS skills.

**Provenance**: the style contract below is distilled verbatim from the real, verified prompt recorded in `…/garden-1-1-intro/build/sess/session.json` (the garden background). Reuse it to keep new art consistent with that lesson.

### When to use this vs `kine-image-kids`

- **kine-image-duolingo** (this skill): Duolingo aesthetic — even flatter, chunkier, **higher saturation**, mascot faces optional. Use to match the Giggle/Duolingo brand baseline and the existing Garden backgrounds.
- **kine-image-kids** (KINE-KIDS): softer "rounded blob" educational look with mandatory oversized white eyes on living things. Use when you specifically want that face grammar.

Pick by which existing assets you must stay consistent with; do not mix the two contracts in one set.

## Workflow

1. Classify the output: `background` / `character` / `object` / `element_sheet` / `character_sheet` / `combined_scene` / `ui_game_screen` (UI only when asked).
2. Extract the variable brief: subject(s), scene/backdrop, learning or gameplay task, props/elements, mood/action, output shape (wide scene / square asset / isolated object / sheet / transparent-ready / project asset).
3. Preserve the Duolingo Style Contract below; replace only the content variables (see Content Independence Rule).
4. Assemble the prompt (see Prompt Assembly and `references/prompt-templates.md`).
5. If the user asks to generate/draw, first use `$imagegen`, then render through its default built-in `image_gen` tool (Generation section).
6. For transparent cutout assets, follow `$imagegen`'s built-in-first chroma-key workflow and local background removal helper; do not silently switch to CLI fallback.
7. Review with the quality gates; if it fails, revise one constraint at a time and regenerate.
8. Report the final prompt, `$imagegen` mode used, and local image path.

## Duolingo Style Contract

Always include these unless the user explicitly departs from the style:

- **Duolingo-style flat vector illustration**, friendly mobile-game art
- **bold, chunky, rounded shapes**; simple confident geometry; generous forms
- **minimal clean detail**, high recognition, thumbnail-readable silhouettes
- **very high saturation, vibrant flat color blocks**
- **no gradients, no texture**, no painterly brushwork, no glossy 3D rendering
- minimal or no outlines — separate forms by color blocks and a subtle same-hue darker shape for depth
- clean, **uncluttered, open composition**; clear focal subject + breathing space (for game scenes, keep an empty foreground/center for gameplay)
- cheerful, safe, playful, preschool / early-learning mood
- bright sky-blue, fresh greens, warm browns, sunny yellows and bright friendly accents; palette adapts to the subject but stays **bright, flat, saturated**
- living characters (if any): simple friendly faces, small dot eyes + tiny curved smile — keep them flat and minimal (Duolingo-flat, not the big-white-eye KINE grammar)

> Image models may add glossy highlights — always append `absolutely flat fills, no highlight, no gloss, no specular reflection` to enforce the flat contract.

## Content Independence Rule

Do not bind the style to gardens, suns, or any specific lesson unless asked. The content layer is a replaceable variable:

```text
Scene/backdrop: <any place>
Subject: <any person/animal/object/thing>
Task: <any learning or gameplay action>
Props/elements: <any supporting items>
Composition: <background / character / object / sheet / combined scene>
Palette: <subject-appropriate colors that stay bright, flat, saturated, child-friendly>
```

The same contract applies to a counting beach scene, a kitchen vocabulary set, a single toaster prop, a sheet of vehicles, a space matching game, etc.

## Prompt Assembly

Compact pattern for most requests:

```text
Duolingo-style flat vector illustration of [output type / subject], friendly mobile game art.
Content: [user variables].
Style: bold rounded shapes, minimal clean detail, very high saturation vibrant flat colors, no gradients no texture, minimal/no outlines, subtle same-color shadow shapes, clean and uncluttered.
Composition: [wide 16:9 scene with empty foreground / isolated object on white / separated sheet / combined game screen].
Mood: cheerful, friendly, safe, playful.
Constraints: absolutely flat fills, no highlight, no gloss, no specular reflection, no photorealism, no 3D render, no texture, no heavy outlines, no text unless requested, no logos, no watermark, no clutter.
```

For precise output types and the canonical garden-background reference prompt, read `references/prompt-templates.md`.

## Generation (via $imagegen)

Rendering must go through `$imagegen`. Read `/Users/tvwoo/.codex/skills/.system/imagegen/SKILL.md` before the first generation in a session and follow its top-level mode rules.

1. **Default path**: use `$imagegen`'s built-in `image_gen` tool for normal generation and editing. Do not use fal.ai, `genmedia`, `giggle:fal-skill`, or `giggle:image-agent` for drawing in this skill.
2. **Prompt**: pass the assembled Duolingo prompt to `image_gen`. Keep the prompt explicit about flat fills, high saturation, no gradients, no texture, no gloss, and no text unless requested.
3. **Project-bound assets**: after generation, move or copy the selected image from the default `$CODEX_HOME/generated_images/...` location into the target workspace before finishing, following `$imagegen`'s save-path policy.
4. **Transparent assets**: use `$imagegen`'s built-in-first chroma-key sequence: generate on a perfectly flat removable chroma-key background, run `$CODEX_HOME/skills/.system/imagegen/scripts/remove_chroma_key.py`, validate alpha, and only ask about CLI fallback when that workflow is unsuitable or fails.
5. **Batch/multiple assets**: issue one built-in `image_gen` call per distinct asset or variant, as required by `$imagegen`.
6. **Report**: include the final saved path(s), final prompt(s), and that `$imagegen` built-in tool mode was used. If the user explicitly confirmed an `$imagegen` CLI fallback, report that instead.

## Quality Gates

Revise (one constraint at a time) when:

- it looks like generic storybook / painterly art instead of flat Duolingo game art
- gradients, texture, gloss highlights, cinematic lighting, or 3D depth appear
- shapes are thin/sharp/realistic instead of bold and rounded
- the palette is muddy, dull, or low-saturation (Duolingo wants vivid flat color)
- too many tiny details hurt thumbnail readability
- a background-only request contains characters; a sheet has overlapping/cluttered assets
- an object asset is not isolated enough to reuse
- a scene leaves no open foreground/center for gameplay
- text, logos, watermarks, or unintended UI appear

## Handoff Notes

If the user later wants SVG/Rive, treat the generated raster as the accepted visual reference and hand off to the relevant vector/rigging skill. To stay consistent with an existing asset, use `$imagegen` edit/reference-image semantics rather than re-deriving from text. Keep this skill focused on producing and validating the Duolingo flat visual style; generation is delegated to `$imagegen`.
