# KINE Skills Installation

Use this file when an AI assistant is asked to install the `kine-skills` Skill suite.

These Skills are written for the Codex environment and are deeply adapted for image gen workflows.

## Source

- GitHub repo: `https://github.com/verycafe/kine-skills`

Installed Skill packages:

```text
kine-layer-v2-5/
kine-summer-shot/
kine-image-kids/
kine-image-duolingo/
kine-svg-dev/
```

## Target

Install into the default Codex Skill root:

```text
${CODEX_HOME:-$HOME/.codex}/skills
```

Do not clone the GitHub repo directly into the final Skill root. The final runtime location should contain the Skill package directories themselves.

## Install Codex

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
tmp="$(mktemp -d)"
git clone --depth 1 https://github.com/verycafe/kine-skills.git "$tmp/kine-skills"
mkdir -p "$CODEX_HOME/skills"

for skill in \
  kine-layer-v2-5 \
  kine-summer-shot \
  kine-image-kids \
  kine-image-duolingo \
  kine-svg-dev
do
  rm -rf "$CODEX_HOME/skills/$skill"
  cp -R "$tmp/kine-skills/$skill" "$CODEX_HOME/skills/$skill"
done

rm -rf "$tmp"
```

## Verify

After installation, verify that the final Skill root contains all five Skill packages:

```bash
for skill in \
  kine-layer-v2-5 \
  kine-summer-shot \
  kine-image-kids \
  kine-image-duolingo \
  kine-svg-dev
do
  test -f "${CODEX_HOME:-$HOME/.codex}/skills/$skill/SKILL.md" && echo "installed: $skill"
done
```
