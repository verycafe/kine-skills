# Kine Pose Dev V3 Fresh Run Handoff

Task: image-based front-facing running animation from `/Users/tvwoo/Downloads/色块宇航员.png`.

Result: Phase A selected sequence ready.

Selected sequence:
- Source attempt: attempt02
- Model endpoint: `bytedance/seedance-2.0/fast/image-to-video`
- Request ID: `019edb20-e015-7442-8119-85d06a5312bc`
- Source video URL: https://v3b.fal.media/files/b/0a9eccdf/HG6lTMUDx4MP8lfCSYcRk_video.mp4
- Selected source frames: attempt02 frames 069-092
- Selected frame count: 24

Outputs:
- Selected GIF: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/sheets/selected_run_24fps.gif`
- Selected MP4: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/sheets/selected_run_24fps.mp4`
- Selected board: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/sheets/selected_run_board.png`
- Selected strip: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/sheets/selected_run_strip_24.png`
- Selected frames: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/frames_selected`
- Registry: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/selected-frame-registry.json`
- Visual gate: `/Users/tvwoo/Projects/KINE-SKILLS/kine-pose-dev-v3/output/astronaut-front-run-v3-rerun-20260618/visual_gates/attempt02_segment_069_092_gate.json`

Important constraints honored:
- Fresh task root; no previous bad/historical files imported.
- Phase A only. No Source Master, no component ledger, no rig.
- Selected frames are whole-subject model-generated frames.
- Local scripts only created contracts, soft controls, copied model frames, and assembled evidence previews.

Residual QA notes:
- The action reads as front-facing running-in-place with alternating knees and arms.
- There is mild AI detail flicker in suit/gloves, typical of image-to-video.
- Loop seam is acceptable for review, not mathematically perfect.
