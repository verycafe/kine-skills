#!/usr/bin/env python3
"""Regression tests for the Kine Pose Dev V3 contract validator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_phase_a_v3_contract.py"
FIXTURE_ROOT = ROOT / "fixtures" / "phase-a-v3"


EXPECTED_FAILURES = {
    "bad-missing-director-brief": "missing_director_brief",
    "bad-missing-semantic-motion-plan": "missing_semantic_motion_plan",
    "bad-missing-occlusion-plan": "missing_occlusion_plan",
    "bad-selected-frame-missing-contract": "selected_frame_missing_contract",
    "bad-missing-moving-owner": "missing_moving_owner",
    "bad-missing-stable-owner": "missing_stable_owner",
    "bad-missing-contact-anchor": "missing_contact_anchor",
    "bad-missing-overlap-expectation": "missing_overlap_expectation",
    "bad-missing-provenance": "missing_generation_provenance",
    "bad-programmatic-character-pixels": "programmatic_subject_pixels",
    "bad-local-repair-promoted": "local_repair_promoted_without_clean_gate",
    "bad-local-transform-selected": "local_transform_selected_for_large_action",
    "bad-missing-stable-action-gate": "missing_stable_action_gate",
    "bad-final-preview-source": "final_preview_not_selected_source",
    "bad-source-pose-snapback-not-blocked": "source_pose_snapback",
    "bad-detached-child-not-blocked": "detached_child",
    "bad-component-sheet-selected": "selected_frame_not_whole_subject",
}


def run_validator(fixture: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), str(FIXTURE_ROOT / fixture)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{fixture}: validator did not return JSON.\nstdout={proc.stdout}\nstderr={proc.stderr}") from exc
    return proc.returncode, data


def assert_codes(fixture: str, expected: str) -> None:
    code, data = run_validator(fixture)
    codes = {item["code"] for item in data.get("errors", [])}
    if code == 0 or data.get("status") != "fail" or expected not in codes:
        raise AssertionError(
            f"{fixture}: expected failure code {expected}, got return={code}, status={data.get('status')}, codes={sorted(codes)}\n"
            + json.dumps(data, ensure_ascii=False, indent=2)
        )


def main() -> int:
    if not FIXTURE_ROOT.exists():
        raise SystemExit(f"Missing fixture root: {FIXTURE_ROOT}. Run scripts/generate_phase_a_v3_fixtures.py first.")

    code, data = run_validator("minimal-pass")
    if code != 0 or data.get("status") != "pass":
        raise AssertionError("minimal-pass expected pass:\n" + json.dumps(data, ensure_ascii=False, indent=2))

    for fixture, expected in EXPECTED_FAILURES.items():
        assert_codes(fixture, expected)

    print(
        json.dumps(
            {
                "status": "pass",
                "passedFixtures": ["minimal-pass"],
                "failedAsExpected": EXPECTED_FAILURES,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
