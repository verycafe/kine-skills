# Duolingo Style · Prompt Templates

Style block is constant; swap only the `<content>` variables. Append the flat-enforcement tail to every prompt:
`absolutely flat fills, no highlight, no gloss, no specular reflection, no gradients, no texture, no 3D render, no photorealism, no heavy outlines, no watermark.`

STYLE BLOCK (reuse verbatim):
`Duolingo-style flat vector illustration, friendly mobile game art, bold rounded shapes, minimal clean detail, very high saturation vibrant flat colors, minimal/no outlines, subtle same-color shadow shapes, clean and uncluttered.`

---

## Canonical reference — Garden 1-1 background (the verified source prompt)

This exact prompt (from `garden-1-1-intro/build/sess/session.json`) produced the lesson's garden background; use it as the gold reference / starting point for matching scenes:

```
Duolingo-style flat vector illustration of a cute simple garden scene, bold rounded shapes, minimal clean detail, very high saturation vibrant flat colors, no gradients no texture, friendly mobile game art: one big round leafy tree on the right, a small wooden fence, green grass ground, a few simple flowers, bright blue sky with a sun, empty center foreground bare soil patch, clean and uncluttered
```

Use a landscape-friendly `imagegen` prompt and preserve the empty center foreground.

---

## background (empty playable scene, 16:9)

```
Duolingo-style flat vector illustration of <place> background scene for a children's educational game, friendly mobile game art.
Layout: <key scenery — e.g. rolling green hills, blue sky with clouds, distant bushes, fence>; keep an empty open center/foreground for gameplay; no characters.
Style: bold rounded shapes, minimal clean detail, very high saturation vibrant flat colors, no gradients no texture, minimal/no outlines, clean and uncluttered.
Constraints: absolutely flat fills, no highlight, no gloss, no specular reflection, no 3D, no photorealism, no text, no watermark.
```
→ Use a landscape-friendly `imagegen` prompt.

## object / prop (isolated, white bg → cutout-ready)

```
Duolingo-style flat vector illustration of a single <object>, centered on a clean white background, friendly mobile game art.
Style: bold rounded shape, minimal clean detail, very high saturation vibrant flat color, minimal/no outline, one subtle same-color darker shadow shape for depth.
Constraints: isolated single object, absolutely flat fills, no highlight, no gloss, no gradients, no texture, no 3D, no shadow on ground, no text, no watermark.
```
→ Use a square asset-friendly `imagegen` prompt.

## character / animal / mascot (Duolingo-flat face)

```
Duolingo-style flat vector illustration of <character/animal>, full body, centered on clean white background, friendly mobile game art.
Face: simple friendly flat face, small dot eyes, tiny curved smile (keep flat and minimal).
Style: bold rounded body built from simple shapes, very high saturation vibrant flat colors, minimal/no outlines, subtle same-color shadow shapes.
Constraints: absolutely flat fills, no highlight, no gloss, no gradients, no texture, no 3D render, no text, no watermark.
```
→ Use a square character-friendly `imagegen` prompt.

## element_sheet / character_sheet (multiple separated reusable assets)

```
Duolingo-style flat vector asset sheet: <N> separated <items> arranged in a clean grid on a plain white background, even spacing, no overlap, friendly mobile game art.
Each item: bold rounded shape, minimal clean detail, very high saturation vibrant flat color, minimal/no outline.
Constraints: items clearly separated, no background scenery, absolutely flat fills, no highlight, no gloss, no gradients, no texture, no text, no watermark.
```
→ Use a square sheet-friendly `imagegen` prompt.

## combined_scene (background + subjects as a game moment)

```
Duolingo-style flat vector game scene: <place> with <subjects/props arranged for the gameplay task>, friendly mobile game art.
Composition: clear focal arrangement with open space for interaction; readable at thumbnail size.
Style: bold rounded shapes, minimal clean detail, very high saturation vibrant flat colors, minimal/no outlines, clean and uncluttered.
Constraints: absolutely flat fills, no highlight, no gloss, no gradients, no texture, no 3D, no UI unless requested, no text, no watermark.
```
→ Use a landscape-friendly `imagegen` prompt.

---

## Tips

- To **match an existing Giggle asset** closely, use `imagegen` edit/reference-image semantics with that PNG visible in context rather than re-deriving from text — text alone drifts.
- Duolingo look = **vivid + flat + bold**. If output looks pale or storybook-soft, push "very high saturation" and re-assert "no gradients no texture"; do not add detail.
- Backgrounds: always reserve the empty center/foreground so game elements (seeds, cards, characters) can sit on top later.
