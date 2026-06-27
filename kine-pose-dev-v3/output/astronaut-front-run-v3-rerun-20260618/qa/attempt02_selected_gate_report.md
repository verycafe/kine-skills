# Kine Pose Dev V3 Phase A QA Report

Run: astronaut-front-run-v3-rerun-20260618

Decision: PASS for Phase A selected review sequence.

Selected source: attempt02 frames 069-092 from `bytedance/seedance-2.0/fast/image-to-video`.

Why it passes:
- Reads as front-facing running-in-place, not a warped still image.
- Shows alternating knees and opposite arm swing.
- Uses whole-subject model-generated frames; no local pose warp or component puppet frame enters selected.
- Full body remains visible with stable green background.

Residual risks:
- Mild AI detail flicker in suit panels/gloves.
- Loop seam is review-acceptable, not mathematically perfect.
- This is Phase A evidence only, not Phase B rig/source-master.

Key outputs:
- Selected GIF: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/sheets/selected_run_24fps.gif`
- Selected board: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/sheets/selected_run_board.png`
- Selected strip: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/sheets/selected_run_strip_24.png`
- Registry: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/selected-frame-registry.json`
