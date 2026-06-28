---
name: video-subtitle-translation-upgrade
description: Use this skill when the user asks to update, upgrade, or install the latest video-subtitle-translation skill. It upgrades git-backed installs with git pull and setup, and gives a safe replacement path for copied installs.
---

# Video Subtitle Translation Upgrade

Upgrade `video-subtitle-translation` to the latest version.

## When To Use

Use when the user asks to update this skill, when the main skill reports `UPGRADE_AVAILABLE`, or when the user says "update video-subtitle-translation", "upgrade subtitle translation skill", or "更新字幕 skill".

## Upgrade Flow

1. Detect install root:

```bash
STATE_DIR="${VIDEO_SUBTITLE_TRANSLATION_STATE_DIR:-$HOME/.video-subtitle-translation}"
INSTALL_ROOT="$(cat "$STATE_DIR/install-root" 2>/dev/null || true)"
if [ -z "$INSTALL_ROOT" ]; then
  if [ -L "$HOME/.agents/skills/video-subtitle-translation" ]; then
    INSTALL_ROOT="$(cd "$(dirname "$(readlink "$HOME/.agents/skills/video-subtitle-translation")")/.." && pwd)"
  elif [ -d "$HOME/.agents/repos/video-subtitle-translation/.git" ]; then
    INSTALL_ROOT="$HOME/.agents/repos/video-subtitle-translation"
  fi
fi
echo "INSTALL_ROOT=$INSTALL_ROOT"
```

2. If `INSTALL_ROOT` is a git repo, upgrade with:

```bash
OLD_VERSION="$(cat "$INSTALL_ROOT/VERSION" 2>/dev/null || echo unknown)"
cd "$INSTALL_ROOT"
git pull --ff-only
./setup
NEW_VERSION="$(cat "$INSTALL_ROOT/VERSION" 2>/dev/null || echo unknown)"
mkdir -p "${VIDEO_SUBTITLE_TRANSLATION_STATE_DIR:-$HOME/.video-subtitle-translation}"
echo "$OLD_VERSION" > "${VIDEO_SUBTITLE_TRANSLATION_STATE_DIR:-$HOME/.video-subtitle-translation}/just-upgraded-from"
echo "video-subtitle-translation upgraded: $OLD_VERSION -> $NEW_VERSION"
```

3. If it is not a git repo, explain that the old unzip/copy install cannot self-update reliably. Recommend replacing it with the git-backed install:

```bash
rm -rf "$HOME/.agents/skills/video-subtitle-translation"
mkdir -p "$HOME/.agents/repos"
git clone https://github.com/sosoall/subtitle_translation.git "$HOME/.agents/repos/video-subtitle-translation"
cd "$HOME/.agents/repos/video-subtitle-translation"
./setup
```

If the clone directory already exists, run:

```bash
cd "$HOME/.agents/repos/video-subtitle-translation"
git pull --ff-only
./setup
```

4. Tell the user to restart Codex or open a new session.
