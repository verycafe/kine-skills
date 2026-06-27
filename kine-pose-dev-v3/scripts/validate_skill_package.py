#!/usr/bin/env python3
"""Validate the Kine Pose Dev V3 skill package scaffolding."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "SKILL.md",
    "agents/openai.yaml",
    "references/v3-skill-blueprint.zh.md",
    "references/phase-a-v3-master-plan.md",
    "references/generation-playbook.md",
    "references/layer-scenario-research.md",
    "references/v3-plan-goals.md",
    "references/HANDOFF.md",
    "scripts/validate_phase_a_v3_contract.py",
    "scripts/test_phase_a_v3_contract.py",
    "scripts/build_phase_a_v3_evidence.py",
    "scripts/generate_phase_a_v3_fixtures.py",
    "fixtures/phase-a-v3/minimal-pass/phase-a-v3/animation-director-brief.json",
    "fixtures/phase-a-v3/bad-missing-director-brief/phase-a-v3/semantic-motion-plan.json",
]


def main() -> int:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        print("missing required files:")
        for path in missing:
            print(f"- {path}")
        return 1

    failures: list[str] = []
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        todo_marker = "TO" + "DO"
        bracketed_todo_marker = "[TO" + "DO"
        if todo_marker in text or bracketed_todo_marker in text:
            failures.append(f"{relative}: contains template placeholder marker")
        if relative.endswith(".md") and len(text.strip()) < 200:
            failures.append(f"{relative}: unexpectedly short")

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for required in [
        "kine-pose",
        "Phase A-only",
        "whole-subject",
        "occlusion",
        "overlap",
        "references/v3-skill-blueprint.zh.md",
        "references/phase-a-v3-master-plan.md",
        "references/generation-playbook.md",
        "references/HANDOFF.md",
    ]:
        if required not in skill:
            failures.append(f"SKILL.md: missing required phrase {required!r}")

    if failures:
        print("validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("kine-pose-dev-v3 package validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
