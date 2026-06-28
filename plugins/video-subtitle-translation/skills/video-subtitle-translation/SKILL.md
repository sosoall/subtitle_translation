---
name: video-subtitle-translation
description: Use this skill when the user wants to generate bilingual subtitles, translate subtitles, create SRT files for CapCut/Jianying, transcribe local video or audio, or clean subtitle timing and sentence breaks. Triggers on "生成双语字幕", "翻译字幕", "剪映字幕", "CapCut subtitles", "导入本地字幕", "SRT", "transcribe video", "translate subtitles", "bilingual subtitles", and "generate subtitles".
---

# Video Subtitle Translation

Generate bilingual or translated SRT subtitle files from a local video/audio file. The output is a subtitle file for editing tools such as CapCut/Jianying, not a rendered video with burned-in subtitles.

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

These presets are applied to the source transcript during first-pass segmentation. After translation, also check the translated line against the same layout goal:

- In `bilingual` mode, both the source line and translated line must be comfortable for the video layout.
- In `translated` mode, the translated line is the primary display constraint.
- For portrait videos, be stricter than landscape. If in doubt, split shorter.

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

1. Keep complete meaning units together when possible.
2. Split at clear clause boundaries when both sides remain understandable.
3. Do not leave dangling fragments such as "which can help me find" or "out whether this is".
4. Do not split fixed expressions, names, product names, or noun phrases unless they are too long to fit.
5. For bilingual subtitles, keep source cards short enough that the original and translation can both fit comfortably.
6. For vertical videos, prefer shorter cards even if landscape would allow longer text.
7. If changing boundaries, keep timestamps monotonic and IDs sequential.

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

For long files, work in batches of about 150 segments with 15-20 overlapping context segments. Preserve IDs exactly. If a translation becomes unclear because the source break is bad, revise the reviewed segments first, then translate again.

After translation, do a layout pass before writing SRT:

1. Compare source and translation lengths by approximate display width, not just raw characters.
2. If a translation is too long for the detected layout, first make the translation more concise while preserving meaning.
3. If concise translation is still too long, split the source segment at a clear semantic boundary, adjust timestamps proportionally when needed, then translate the new segments.
4. Keep portrait videos tighter than landscape because bilingual subtitles need two readable lines.

Prompt pattern:

```text
Translate the following subtitle segments to [TARGET LANGUAGE].

These are semantic subtitle cards for a video.
Use surrounding segments as context.
Keep translations concise enough for subtitles.
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
