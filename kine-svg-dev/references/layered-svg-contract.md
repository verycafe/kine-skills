# Layered SVG Contract

## Package Shape

Each KINE SVG DEV package is a source-master candidate, not a final animation.

Required fields in `<slug>-manifest.json`:

```json
{
  "taskId": "example",
  "source": {
    "path": "/absolute/path/source.png",
    "width": 1024,
    "height": 1536,
    "alpha": true,
    "sourceType": "raster_only"
  },
  "intent": "source_master_only",
  "outputs": {
    "componentLedger": "example-component-ledger.json",
    "layeredSvg": "example-layered.svg",
    "previewPng": "example-preview.png",
    "comparePng": "example-compare.png",
    "qaJson": "example-qa.json",
    "kineReadiness": "example-kine-readiness.json"
  },
  "status": "wip"
}
```

Required component ledger fields:

```json
{
  "coordinateConvention": "screen_left_right",
  "components": [
    {
      "id": "helmet_glass",
      "parent": "character",
      "drawOrder": 20,
      "bbox": [360, 40, 300, 330],
      "pivot": [512, 210],
      "movable": false,
      "sourceConfidence": "visible",
      "segmentationReason": "material",
      "role": "transparent helmet glass"
    }
  ]
}
```

`segmentationReason` must explain why the layer exists. Valid values include:

- `material`
- `occlusion`
- `function`
- `identity_detail`
- `motion_owner`
- `text`
- `shadow_highlight`
- `cleanup_artifact`

Use `cleanup_artifact` only for rejected or cleanup notes. Final SVG component layers should not be named after anti-aliased edge fragments, speckles, or color quantization islands.

## SVG Requirements

- root `<svg>` must have `viewBox`
- top-level group IDs should include `source_master`, `canvas_background` if used, and `character` for character assets
- macro component IDs in the ledger must exist as SVG IDs
- preserve transparent canvas unless the user requests a background
- every moving candidate should be a group, not scattered unrelated paths
- use deterministic IDs such as `arm_left_forearm`, not auto-generated IDs
- full-image auto-trace paths must be regrouped under semantic component IDs before a file is called layered source master
- if paths are still only a visual trace, label the package `visual_trace_candidate`, not `layered_source_master`
- for high-fidelity trace-derived source masters, preserve global draw order with per-path wrapper groups instead of physically moving paths into component buckets when that would alter the render
- preserve path `transform` attributes and include them when computing bboxes, pivots, and component ownership
- if semantic grouping changes the rendered image compared with the visual trace, the grouped source master must fail QA

## Trace-Preserving Source Master Shape

When visual fidelity is hard, a valid source-master SVG can use wrappers:

```xml
<g id="character_root" data-preserve-draw-order="true">
  <g id="wrap_0001"
     data-component="helmet_glass"
     data-pivot="512 220"
     data-original-draw-order="1">
    <path id="helmet_glass__trace_path_0001" .../>
  </g>
  <g id="wrap_0002"
     data-component="hair_front"
     data-pivot="500 170"
     data-original-draw-order="2">
    <path id="hair_front__trace_path_0002" .../>
  </g>
</g>
```

The wrapper carries semantic ownership while the path keeps the trace geometry and original stacking. The component ledger or macro map then groups many wrappers under each component.

## QA Requirements

Write `<slug>-qa.json` with:

```json
{
  "status": "pass|wip|blocked|visual_rejected",
  "checks": {
    "canvasMatchesSource": "pass|fail|not_checked",
    "transparentBackground": "pass|fail|not_checked",
    "identityPreserved": "pass|fail|not_checked",
    "ledgerGroupsPresent": "pass|fail|not_checked",
    "riskySvgFeaturesAbsent": "pass|fail|not_checked"
  },
  "failures": [],
  "notes": []
}
```

Only `pass` with empty `failures` is a source-master candidate.
