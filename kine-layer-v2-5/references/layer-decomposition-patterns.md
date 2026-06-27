# Layer Decomposition Capability Patterns

This note records KINE-LAYER's own implementation patterns. It must not leak external project names, UI text, file names, or code structure into product docs, generated workspaces, HTML output, PSD metadata, or package manifests.

## Directly Useful Ideas

1. **Semantic ownership first**
   Keep each visual part under one semantic owner before rigging or post-splitting.

2. **Fully completed transparent layers**
   A tight source cutout is not enough. Each accepted layer should include hidden or occluded content needed for motion while preserving visible source fidelity.

3. **PSD as an exchange source master**
   Output layered PSD plus PNG layers, manifest, QA evidence, and review HTML.

4. **Draw order is data**
   Record `drawOrderBackToFront` explicitly. Never rely on filename order.

5. **Post-splitting**
   Produce semantic source layers first, then split left/right or front/back components when the source owner requires it.

6. **Human correction is expected**
   Mark questionable layers as `needs_manual_review` or `visual_rejected`; do not claim automation is enough.

7. **Two-stage separation**
   Use a whole-body pass for large owners and a focused head/detail pass for small facial owners.

8. **Visible source is not hidden fill**
   Source-visible pixels remain locked. The `$imagegen` skill fills hidden regions and cleans owner-isolated content under an explicit mask/contract.

## KINE-LAYER Implementation Rules

- Use original KINE-LAYER names, file layout, prompts, manifests, and UI copy.
- Do not copy external function names, command names, screenshots, CSS, or metadata structures.
- Implement capability-equivalent behavior through KINE-LAYER contracts: campaign, layer production, registration, QA, PSD/package, and review UI.
- Keep depth and left/right splitting as explicit post-process stages, not hidden prompt wording.

## Kine-Specific Translation

```text
source image
 -> semantic owner plan
 -> visible lock + hidden underpaint
 -> registered transparent layer
 -> component ledger entry
 -> draw order
 -> QA and review HTML
 -> rig/source-master handoff
```
