# KINE-KIDS Prompt Templates

Use these templates by replacing bracketed variables. Keep the style language stable; change the content variables. Render the assembled prompt through `$imagegen` as required by SKILL.md.

## Background

```text
Create a [aspect ratio] children's educational game background in the KINE-KIDS rounded flat style.
Scene/backdrop: [place, such as classroom, beach, farm, kitchen, space station, bedroom, city park, underwater coral area].
Environment elements: [supporting scenery].
Gameplay need: keep [center/foreground/specified area] open for [matching/counting/sorting/finding/dragging].
Style: clean 2D flat vector-like educational app illustration, rounded blob silhouettes, simple geometric shapes, low detail, smooth flat colors, minimal/no outlines, subtle same-color shadows, very limited gradients, no glow.
Composition: decorative elements frame the edges; clear open playable space; uncluttered and readable.
Palette: [scene-appropriate palette], bright, friendly, and child-safe.
Avoid: no characters, no animals unless requested, no text, no logos, no UI buttons, no watermark, no photorealism, no 3D render, no complex texture.
```

## Character Or Animal

```text
Create a cute [character/animal/person/mascot] for a children's educational game in the KINE-KIDS rounded flat style.
Subject: [species/person/role], [age/energy/personality], [pose/action], [prop if any].
Design: oversized round white eyes with small dark pupils, tiny curved smile, simple symbolic nose/mouth, rounded body, simplified limbs, readable silhouette.
Shape language: circles, ovals, beans, pills, rounded rectangles, and soft triangles; low detail; no realistic anatomy.
Style: clean 2D flat vector-like educational app character art, smooth flat colors, minimal/no outlines, subtle same-color shadow shapes, very limited gradients, no glow.
Composition: [full body centered / lineup / action pose / asset sheet], clear spacing, simple background.
Palette: [subject colors], bright and friendly.
Avoid: no text, no logos, no watermark, no scary expression, no realistic fur/skin/feathers, no 3D render, no heavy outlines, no complex costume detail.
```

## Object, Furniture, Appliance, Or Prop

```text
Create a cute reusable [object/furniture/appliance/prop] asset for a children's educational game in the KINE-KIDS rounded flat style.
Subject: [object], designed as a simple child-friendly game asset.
Design: rounded silhouette, exaggerated simple proportions, a few large color blocks, symbolic details only, easy to recognize at small size.
Style: clean 2D flat vector-like educational app object art, smooth flat fills, minimal/no outlines, subtle same-color shadow shapes, very limited gradients, no glow, no realistic material texture.
Composition: isolated centered asset on [plain light background / flat chroma-key background if transparency is needed], generous padding.
Palette: [subject-appropriate colors], cheerful and bright.
Avoid: no text, no logos, no watermark, no photorealism, no 3D render, no detailed texture, no sharp complex edges, no clutter.
```

## Element Sheet

```text
Create a separated asset sheet of [element category] for a children's educational game in the KINE-KIDS rounded flat style.
Elements: [list of objects/plants/props/furniture/appliances/natural items].
Style: clean 2D flat vector-like educational app assets, rounded blob silhouettes, simple geometric construction, low detail, smooth flat colors, minimal/no outlines, subtle same-color shadows, very limited gradients, no glow.
Composition: each element separated with clear spacing on a plain background; no full scene; no labels unless requested.
Palette: [palette], bright and child-friendly.
Avoid: no overlapping elements, no text, no logos, no watermark, no photorealism, no 3D render, no complex texture, no heavy outlines.
```

## Combined Game Scene

```text
Create a [aspect ratio] combined children's educational game scene in the KINE-KIDS rounded flat style.
Scene/backdrop: [place].
Subject(s): [characters/animals/objects].
Gameplay task: [matching/counting/sorting/finding/feeding/cleaning/placing/dragging/etc.].
Props/elements: [supporting elements].
Style: clean 2D flat vector-like educational app game art, rounded blob silhouettes, low detail, smooth flat colors, minimal/no outlines, subtle same-color shadows, simple layered depth, very limited gradients, no glow.
Composition: open gameplay space, clear focal areas, decorative elements around edges, readable at mobile size.
Mood: cheerful, friendly, safe, playful.
Palette: [scene-appropriate palette], bright and balanced.
Avoid: no text unless requested, no logos, no watermark, no photorealism, no 3D render, no complex texture, no heavy outlines, no scary mood, no clutter.
```

## Transparent-Ready Asset Source

Use only when the user asks for transparent/cutout-ready output. Follow `$imagegen` built-in-first chroma-key removal workflow after generation.

```text
Create [subject] in the KINE-KIDS rounded flat style on a perfectly flat solid [#00ff00 or #ff00ff] chroma-key background for background removal.
The background must be one uniform color with no shadows, gradients, texture, reflections, floor plane, or lighting variation.
Subject: [subject details].
Style: clean 2D flat vector-like educational app asset, rounded silhouette, low detail, smooth flat colors, minimal/no outlines, subtle same-color internal shadow shapes only.
Composition: isolated centered subject, crisp edges, generous padding.
Do not use the chroma-key color anywhere in the subject.
Avoid: no cast shadow, no contact shadow, no reflection, no text, no logo, no watermark, no photorealism, no 3D render, no complex texture.
```
