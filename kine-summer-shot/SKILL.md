---
name: kine-summer-shot
description: Create clean 2K production storyboard boards / animation planning sheets before individual frame generation for narrative image/video scenes. Use when the user asks for 分镜板, storyboard boards, production boards, cinematic shot design, image/video shot planning, consistent character storyboard expansion, or self-reviewed visual prompts, especially when using imagegen/pastel and when camera angle, action direction, scene geometry, lighting continuity, timing, animation behavior, or story logic must be checked.
---

# Kine Summer Shot

## Purpose

Use this skill to turn a scene premise, reference character, and visual style into a clean production storyboard board first. The board is the approval artifact before making separate 9:16 frames or video shots.

Always treat the storyboard board as an animation production design document, not a collage of unrelated cinematic images. It must describe spatial logic, camera movement, shot order, character continuity, timing, lighting progression, and likely animation behavior.

The default visual language is a white-background production board: clean page layout, rounded rectangular sections, readable technical labels, arrows, icons, palette swatches, timing notes, top-view maps, side-camera previews, and shot breakdown panels. Avoid turning the whole board into a dark poster, splash art, or full-bleed atmosphere painting unless the user explicitly asks for that.

## Required Skill Order

1. If generating images, load and follow `$imagegen` at `/Users/tvwoo/.codex/skills/.system/imagegen/SKILL.md`.
2. If the user names a visual style skill such as `$pastel`, load that skill too and obey it in the image prompt.
3. If the user supplies reference images, preserve explicit identity cues and label them in the prompt as character/style/environment references.

## Workflow

1. Parse the request into:
   - scene objective and emotional beat
   - character identity cues
   - environment and fixed landmarks
   - action direction and start/end positions
   - requested camera angle, lens feel, framing, aspect ratio, duration, timing, and shot count
   - style, color, lighting, and resolution constraints
2. Design a single storyboard board first. Do not jump directly to individual final frames unless the user explicitly asks to skip the board.
3. Compose the board as a clean production planning sheet with these sections:
   - title bar: scene name, camera/action focus, shot count, duration, palette swatches, tone keywords
   - character/action reference: key identity cues, costume, props, scale notes, pose or cycle key poses
   - environment and scene design: wide establishing layout with fixed landmarks
   - corrected geometry / top-view blocking: camera positions, character path, entry/exit points, movement axis, major props
   - side-camera preview: what the camera sees, with the requested shot angle and movement direction
   - shot breakdown: numbered panels with time range, shot size, lens feel, camera movement, action, emotion
   - animation / production notes: cycle timing, prop swing, wind/light pass, continuity anchors, camera constraints
   - lighting/mood/style notes: visible light direction, shadow logic, texture, resolution
   - optional audio notes: BGM/SFX/narration only when relevant
4. Request a 2K-quality storyboard board. Prefer a clear landscape board layout for planning, even when final shots are vertical.
5. Inspect the generated board against the Kine-Summer-Shot Review Gate below.
6. If any critical review item fails, iterate the prompt with a targeted correction before presenting the board.
7. After the board is accepted, generate individual frames from the approved board and reference images, maintaining the board's blocking and continuity.

## Production Board Layout Contract

By default, request this page style:

- white or warm-off-white background with clean margins, not a full-bleed illustration
- thin dividers or rounded section boxes, no heavy ornamental frames
- large readable section headings and concise technical labels
- a title bar across the top with scene focus, shot count, duration, palette swatches, and tone words
- a left reference column for character, body crop, costume, props, or cycle key poses
- a top-view plan with arrows for subject path, camera track, light/wind direction, and fixed landmarks
- a side-camera preview that shows exactly what the camera should see
- a shot breakdown row/grid with numbered panels and time ranges
- a bottom production-notes band for animation, lighting, camera, timing, and continuity notes
- use simple icons, arrows, colored markers, and palette dots to carry meaning

Text is allowed and encouraged for production planning boards. Keep it short, large, and simple so the model has a better chance of rendering it legibly. Never rely on small text as the only carrier of a critical story fact; pair labels with arrows, diagrams, silhouettes, color coding, and repeated landmarks.

## Style Balance

When a visual style skill such as `$pastel` is active, apply the style to the drawings inside the board and to the soft painterly treatment of thumbnails, references, and diagrams. Preserve the production-board structure above. Do not let the style turn the entire board into an immersive poster or a dark atmospheric concept painting.

## Prompt Frame

Use this structure when prompting image generation:

```text
Create a 2K clean white production storyboard board / animation planning sheet for [scene].
Style: [visual style], consistent with reference character [identity cues].
Board layout: clean white page with rounded section boxes; title bar with scene focus, shot count, duration, palette swatches, and tone words; character/action reference; corrected geometry or top-view blocking; side-camera preview; numbered shot breakdown with time ranges; animation/production notes; lighting/mood/style notes.
Narrative continuity: [cause/effect, shot progression].
Camera language: [shot sizes, lens feel, camera movement, director/cinematographer references if useful].
Blocking: [start point], [movement axis], [end point], [fixed landmarks].
Lighting: [time of day], [shadow direction], [dappled light or moving light patches if requested].
Production annotations: large concise labels, arrows, icons, color-coded markers, timecodes, and diagram notes; use labels plus visual arrows, never tiny text alone.
Hard constraints: [geometry, body crop, direction, costume, props, readable-label limits].
Self-check before final image: the board must read as a production planning sheet, not a poster; all panels obey the same geography, movement direction, character identity, timing, and story logic.
```

Name director or photographer references as influence on camera language only. Do not copy a living artist's exact style; translate references into neutral cinematography terms such as low tracking shot, compressed telephoto, shallow depth, wide establishing, handheld observational, or symmetrical blocking.

## Kine-Summer-Shot Review Gate

Before returning a board, perform this review. Treat failures in camera, direction, geometry, identity, or story logic as blocking.

| Category | Pass Criteria |
| --- | --- |
| Board layout | The result reads as a clean production storyboard / animation planning sheet with white-page structure, section headings, diagrams, arrows, palette swatches, shot panels, and production notes. It is not a full-bleed poster or a loose collage. |
| Camera and framing | The requested angle and shot size are obeyed. If the user asks for lower body only, no face or upper torso appears. If the user asks side tracking, the camera is side-on, not diagonal or overhead. |
| Direction and geometry | Movement axis is unambiguous and consistent across wide design, top-view blocking, and panels. Arrows, path, feet, doors, roads, and landmarks agree. |
| Action mechanics | Walk cycles, hands, feet, props, bag straps, door thresholds, and body balance are plausible. No extra limbs, twisted ankles, floating feet, or impossible hand grips. |
| Character consistency | Outfit, silhouette, hair, bag, shoes, body scale, and temperament match the reference unless the user requests a change. |
| Scene continuity | Background elements do not drift between shots unless the camera logically moves. Fixed anchors stay fixed. Crowds, vehicles, signage, doors, and props remain physically reasonable. |
| Lighting continuity | Time of day, light direction, shadows, and color temperature remain coherent. If dappled light is requested, it is visible as changing patches over ground, clothes, bag, legs, and shoes. |
| Story logic | Shot order has cause and effect. The viewer can understand where the character came from, where she is going, what interrupts or changes, and why the next shot follows. |
| Text and symbols | Section headings, timecodes, arrows, icons, labels, color markers, and palette dots support the plan. Text is large and simple enough for planning; critical story facts are also shown visually. |
| Deliverable quality | Board is high-resolution, readable, and saved/presented as the primary artifact before individual frames. |

Report the review briefly with `Pass`, `Needs Fix`, or `Risk` notes. If the board fails a critical item, fix it before presenting unless the user explicitly asks to see failures.

## Common Failure Corrections

- Poster drift: if the board becomes an atmospheric poster or full-bleed illustration, force a white production-sheet layout with margins, section boxes, diagrams, shot panels, palette dots, arrows, and production notes.
- Missing technical annotations: add large labels for top view, camera preview, shot breakdown, timing, light/wind direction, character path, and continuity anchors. Keep labels short and pair them with arrows or icons.
- Unreadable tiny text: reduce text quantity, enlarge key headings, and communicate the same facts through diagrams, arrows, numbered panels, and color-coded markers.
- Crosswalk crossing: never show the character walking along the zebra stripes. In a side-view tracking shot, the character moves left-to-right or right-to-left across the frame while zebra stripes read as vertical bands crossing the frame, perpendicular to her path. In top-view blocking, the walking path is straight curb-to-curb and perpendicular to the stripe bands.
- Direction correction: if only the character direction is wrong, preserve background geometry and landmarks. Do not regenerate a different street, crosswalk, train door, or cafe layout unless requested.
- Dappled light: make it a visible animation layer. Show leaf-and-building light patches at different positions across the ground, skirt, coat hem, bag, legs, and shoes from panel to panel.
- Subway/train doorway: maintain which side is train interior and which side is platform. Characters exiting move train-to-platform; characters entering move platform-to-train. Door frame, threshold, handrails, and waiting passengers must agree.
- Touch or collision beats: show body contact only where physically plausible, such as shoulder/bag brushing. Preserve personal space, gaze direction, and next-step balance.
- Crowd modernity: update background commuter clothes to contemporary casual/business styles when requested. Avoid unintended period looks unless the scene is period-specific.
- Hands and feet: simplify when needed. Clear silhouettes and grounded shoes are better than detailed but anatomically broken fingers or ankles.

## Final Response

When using this skill, return:

- the storyboard board preview or saved path
- a one-paragraph explanation of the production-board logic
- a short Kine-Summer-Shot Review Gate summary
- any remaining risks, such as text legibility or model uncertainty

Do not present individual frame generation as complete until the storyboard board has passed the review or the user has explicitly approved moving on despite risks.
