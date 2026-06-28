---
name: video-subtitle-translation
description: Use this skill when the user wants to generate bilingual subtitles, translate subtitles, create SRT files for CapCut/Jianying, transcribe local video or audio, or clean subtitle timing and sentence breaks. Triggers on "生成双语字幕", "翻译字幕", "剪映字幕", "CapCut subtitles", "导入本地字幕", "SRT", "transcribe video", "translate subtitles", "bilingual subtitles", and "generate subtitles".
---

# Video Subtitle Translation

Generate bilingual or translated SRT subtitle files from a local video/audio file. The output is a subtitle file for editing tools such as CapCut/Jianying, not a rendered video with burned-in subtitles.

## Preamble - Run First

Run this update check at the start of each use when shell access is available:

```bash
_ROOT="$(cat "${VIDEO_SUBTITLE_TRANSLATION_STATE_DIR:-$HOME/.video-subtitle-translation}/install-root" 2>/dev/null || true)"
if [ -n "$_ROOT" ] && [ -x "$_ROOT/bin/video-subtitle-translation-update-check" ]; then
  _UPD="$("$_ROOT/bin/video-subtitle-translation-update-check" 2>/dev/null || true)"
else
  _UPD=""
fi
[ -n "$_UPD" ] && echo "$_UPD" || true
```

If output shows `UPGRADE_AVAILABLE <old> <new>`, tell the user:

```text
video-subtitle-translation v<new> is available. You are on v<old>. Want me to update it now?
```

If the user agrees, read `video-subtitle-translation-upgrade/SKILL.md` and follow its upgrade flow. If the user declines, snooze this version for 24 hours:

```bash
STATE_DIR="${VIDEO_SUBTITLE_TRANSLATION_STATE_DIR:-$HOME/.video-subtitle-translation}"
mkdir -p "$STATE_DIR"
echo "<new> $(($(date +%s) + 86400))" > "$STATE_DIR/update-snoozed"
```

If output shows `JUST_UPGRADED <old> <new>`, tell the user "Running video-subtitle-translation v<new>."

## User Outcome

Help the user turn an edited video or exported audio file into:

- A bilingual SRT: original text plus translated text.
- A translated-only SRT: target-language subtitles only.
- Subtitle timing and sentence breaks that fit the video layout.

The user should import the generated `.srt` into CapCut/Jianying or another editor, then continue editing font, color, position, animation, and final export there.

## Positioning

Compared with CapCut/Jianying's built-in subtitle translation workflow, this skill focuses on better meaning preservation:

1. It translates with full surrounding context, so meaning is less likely to be lost because a sentence was split.
2. It adapts subtitle card length to portrait, square, or landscape videos, so vertical videos are less likely to overflow.
3. It reviews and adjusts breaks by meaning, so subtitles do not split in ways that damage the sentence.

Do not claim this skill burns subtitles into the video. It outputs SRT files for downstream editing.

## Required Inputs

Before starting, confirm:

1. The local video/audio path.
2. Target language. If missing, ask: "您想翻译成什么语言？"
3. Output mode: `bilingual` by default, or `translated` if the user wants translated subtitles only.
4. Whether the user has already finished editing and exported a video/audio file. If not, explain that the intended workflow is: finish editing first -> export video/audio -> generate SRT -> import SRT back into CapCut/Jianying.

## Supported Files

The script uses ffmpeg, so common video and audio formats are supported: `mp4`, `mkv`, `avi`, `mov`, `webm`, `flv`, `wmv`, `ts`, `m4v`, `mp3`, `wav`, `aac`, `flac`, `m4a`, `ogg`, `opus`, and many others.

## Dependencies

The transcription script checks dependencies before running:

- Installs `openai-whisper` with pip if missing.
- Installs `ffmpeg`/`ffprobe` automatically when possible:
  - macOS: Homebrew `brew install ffmpeg`
  - Linux: `apt-get`, `dnf`, `yum`, `pacman`, or `apk` when available
  - Windows: `winget install --id Gyan.FFmpeg -e` when available

If automatic installation fails, give the exact manual install command from the script output and stop.

## Step 1 - Transcribe And Segment

Use `--model auto` unless the user requests a specific Whisper model. Use `--layout auto` so the script detects portrait, square, or landscape video and chooses subtitle lengths that fit the screen.

```bash
python3 /path/to/skill/scripts/transcribe.py \
  --input "/path/to/video.mp4" \
  --output "/tmp/segments.json" \
  --model auto \
  --layout auto \
  --subtitle-mode bilingual
```

For translated-only subtitles:

```bash
python3 /path/to/skill/scripts/transcribe.py \
  --input "/path/to/video.mp4" \
  --output "/tmp/segments.json" \
  --model auto \
  --layout auto \
  --subtitle-mode translated
```

Optional source language:

```bash
python3 /path/to/skill/scripts/transcribe.py \
  --input "/path/to/video.mp4" \
  --output "/tmp/segments.json" \
  --model auto \
  --layout auto \
  --subtitle-mode bilingual \
  --lang zh
```

Default layout presets keep the existing `--max-chars`, `--soft-chars`, and `--min-chars` option names. In the script, `max` and `soft` are now display-width budgets, not raw character counts: CJK/full-width characters count roughly as 2 units, Latin letters/digits count as 1 unit, and spaces count as 1 unit. `min-chars` remains a non-whitespace character floor so very short fragments are still merged.

| Mode | Portrait | Square | Landscape |
|---|---|---|---|
| `bilingual` | `--max-chars 22 --soft-chars 14 --min-chars 5` | `--max-chars 26 --soft-chars 18 --min-chars 5` | `--max-chars 28 --soft-chars 20 --min-chars 5` |
| `translated` | `--max-chars 26 --soft-chars 18 --min-chars 5` | `--max-chars 32 --soft-chars 22 --min-chars 5` | `--max-chars 42 --soft-chars 28 --min-chars 5` |

These presets are applied to the source transcript during first-pass segmentation:

- Segment length is based on the source transcript.
- Do not split only because the translated text might be longer.
- For portrait videos, be stricter than landscape, but meaning still comes first.

## Step 2 - Review Sentence Breaks

Read the full `segments.json` before translating:

```bash
cat /tmp/segments.json
```

Each entry:

```json
{"id": 42, "start": 125.3, "end": 128.1, "text": "because the algorithm needs"}
```

Treat these segments as a machine-generated draft. Before translating, revise breaks so each subtitle card is understandable on its own and fits the layout.

Rules:

1. Preserve the original wording from Whisper. You may fix obvious terminology mistakes or transcription typos, but do not paraphrase or rewrite what the speaker said.
2. Meaning is the first priority. Width limits are secondary.
3. Keep complete meaning units together when possible.
4. Split at clear clause boundaries when both sides remain understandable.
5. Never split inside a word, term, name, fixed expression, product name, or noun phrase. For example, do not split inside `竖屏`.
6. Do not leave dangling fragments such as "which can help me find" or "out whether this is".
7. For vertical videos, prefer shorter cards, but not at the cost of splitting a word or damaging meaning.
8. If changing boundaries, keep timestamps monotonic and IDs sequential.

Example:

```text
Weak:
[1] I just found this AI tool which can help me find
[2] out what to post every day.

Better:
[1] I just found this AI tool,
[2] which can help me find what to post every day.
```

## Step 3 - Translate With Context

Do not call an external translation API unless the user explicitly asks. Translate the reviewed segments yourself with full context.

For long files, work in batches of about 150 segments with 15-20 overlapping context segments. Preserve IDs exactly. If a translation becomes unclear because the source break is bad, revise the reviewed source segments first, then translate again.

Translation rules:

1. Translate according to the reviewed source segment boundaries.
2. Do not re-split based on translated-language length alone.
3. Keep translations concise, but do not omit meaning.
4. Preserve punctuation style for commas, quotation marks, colons, and similar in both source and target language.
5. Remove terminal periods/full stops from final subtitle text. Keep commas, quotation marks, colons, semicolons, question marks, and exclamation marks when they carry meaning.

Prompt pattern:

```text
Translate the following subtitle segments to [TARGET LANGUAGE].

These are semantic subtitle cards for a video.
Use surrounding segments as context.
Keep translations concise enough for subtitles.
Do not omit meaning to make the line shorter.
Keep commas, quotation marks, and colons when useful.
Do not end subtitles with a period/full stop.
Preserve every ID exactly.

Return ONLY valid JSON: {"41": "translation", "42": "translation"}

[41] because the algorithm needs
[42] to process data in real time.
```

Save translations as JSON:

```bash
cat > /tmp/translations.json << 'EOF'
{"0": "翻译文本", "1": "翻译文本"}
EOF
```

## Step 4 - Write SRT

```bash
python3 /path/to/skill/scripts/write_srt.py \
  --segments /tmp/segments.json \
  --translations /tmp/translations.json \
  --output /tmp/output_bilingual.srt \
  --mode bilingual
```

`--mode bilingual` writes original plus translation.
`--mode translated` writes translation only.

The SRT writer removes terminal periods/full stops from both original and translated lines. It preserves commas, quotation marks, colons, question marks, and exclamation marks.

## Step 5 - Deliver And Explain How To Use

Give the user the full SRT path and explain the next step:

```text
Output saved: /tmp/output_bilingual.srt

Next: open CapCut/Jianying, use Import local subtitles, choose this SRT file,
then continue adjusting font, color, position, animation, and final export there.
```

Mention intermediate files only if useful:

- `segments.json`: first-pass subtitle segments.
- `translations.json`: translated text by subtitle ID.
- `.srt`: the file to import into the editing app.

## Common Fixes

| Problem | Fix |
|---|---|
| File not found | Check the path and quote paths with spaces. |
| No audio stream | Ask for a file with audio, or export audio from the editing project. |
| ffmpeg install failed | Install manually: macOS `brew install ffmpeg`; Ubuntu/Debian `sudo apt-get install ffmpeg`; Windows `winget install --id Gyan.FFmpeg -e`. |
| Whisper install failed | Run `python3 -m pip install openai-whisper`. |
| Wrong source language | Re-run with `--lang en`, `--lang zh`, etc. |
| Subtitles too long for vertical video | Re-run with `--layout portrait` or lower `--max-chars` and `--soft-chars`. |
| Breaks hurt meaning | Revise `segments.json` before translating, then regenerate the SRT. |
