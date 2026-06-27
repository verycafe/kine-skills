# Component Taxonomy

Use this taxonomy as a starting point, then adapt it to the actual image. The skill must infer components from the current image. Do not hardcode one asset's parts as a universal template.

## Generic Discovery Rules

Build the component taxonomy from visible evidence:

- primary subject: the main actor/object/logo/interface/prop in the image
- assembly: a visually and functionally coherent part of the subject
- material region: glass, metal, skin, cloth, plastic, hair, screen, paper, liquid, flame, smoke, etc.
- occlusion region: front/mid/back surfaces that overlap differently
- motion owner: a part that would transform as one unit in animation
- identity detail: face, eyes, mouth, logo mark, signature accessory, product feature, readable text
- contact/detail region: hands, handles, wheels, joints, buttons, straps, hinges, contact shadows
- parented shading: highlight/shadow shapes that must move with a parent part
- cleanup artifact: anti-aliased fringe, quantization speckle, low-alpha edge pixel, compression noise

The output taxonomy should be image-specific. Example mappings:

- character: body regions, face, hair/fur, clothes/armor, limbs, accessories, held props
- vehicle: chassis, wheels, windows, lights, trim, doors, shadow, reflections
- product: body shell, screen, buttons, ports, labels, highlights, shadow
- UI/screenshot-like art: frame, panels, icons, text, controls, shadows, highlights
- environment/object scene: foreground subject, support surface, background props, cast shadows

Cleanup artifacts must not become components. Merge or delete them during SVG cleanup.

## Character

- `character`: root owner for the full subject
- `head_face`: face skin, ears, nose, mouth, cheeks
- `eyes_left/right`: eye whites, iris, pupil, catchlights
- `brows_left/right`: eyebrows and expression accents
- `hair_back`, `hair_mid`, `hair_front`: separated by occlusion and motion role
- `neck_collar`: neck, collar, helmet gasket, scarf, or similar connector
- `torso`: main body owner
- `torso_white_armor`, `torso_black_under_suit`: suit shell and undersuit
- `arms_left/right`, `forearms_left/right`, `hands_left/right`, `gloves_left/right`
- `hips_pelvis`, `legs_left/right`, `knees_left/right`, `boots_left/right`

## Costume And Props

- `helmet_shell`, `helmet_glass`, `helmet_side_units`
- `badges`, `panels`, `straps`, `belts`, `buckles`
- `prop_<name>` for held or attached props
- `contact_shadow` for grounding shadows

## Shading

Keep highlights and shadows grouped under their owner when they must move with that owner:

- `torso_highlights`
- `helmet_glass_highlights`
- `hair_shadow`
- `boot_shadow_left/right`

Do not animate a highlight independently unless it has a separate material or lighting reason.
