# Video Subtitle Translation Skill

[中文](#中文) | [English](#english)

## 中文

一个用于生成双语字幕和翻译字幕的 Agent Skill。你先在剪映/CapCut 或其他剪辑软件里完成剪辑，导出一个视频或音频文件；然后用这个 skill 生成 `.srt` 字幕文件；最后把 SRT 导入剪映/CapCut，继续调整字体、颜色、位置、动画和最终导出。

它不会直接把字幕压进视频里，而是输出可继续编辑的字幕文件。

### 适合谁

- 想给视频生成中英/双语字幕的人
- 想把已有口播视频翻译成另一种语言的人
- 使用剪映/CapCut 剪辑的人
- 想要更自然断句和更准确上下文翻译的人

### 相比剪映/CapCut 自动字幕翻译的优势

- 翻译更准确：翻译时会看上下文，不容易因为一句话被切开而丢失意思。
- 横竖屏自适配：会根据视频是横屏、竖屏还是方形，自动控制每条字幕的屏幕宽度，竖屏会切得更短。
- 按意思断句：会检查字幕片段是否表达完整，避免断句破坏原句意思。
- 输出 SRT：方便导入剪映/CapCut 后继续编辑字幕样式，而不是直接烧录到视频里。

### 产物是什么

最终你会得到一个 `.srt` 字幕文件：

- 双语字幕：原文 + 翻译
- 纯译文字幕：只保留目标语言

过程中还可能产生：

- `segments.json`：识别出来的字幕片段
- `translations.json`：每条字幕对应的翻译

真正需要导入剪映/CapCut 的是 `.srt` 文件。

### 字幕长度如何控制

脚本会根据视频比例自动选择横屏、竖屏或方形字幕长度。参数名仍然叫 `--max-chars` 和 `--soft-chars`，但实际含义更接近“屏幕显示宽度”：

- 中文、日文、韩文等全宽字符大约按 2 个宽度单位计算。
- 英文字母、数字大约按 1 个宽度单位计算。
- 空格也会占宽度。
- `--min-chars 5` 保持为非空白字符数下限，用来避免太短的碎片。

第一轮切分会先看原文。翻译后，Agent 还会检查译文是否过长：如果译文太长，会优先压缩翻译；如果仍然放不下，再按语义拆分原片段。竖屏视频会比横屏更严格。

### 推荐工作流

1. 先在剪映/CapCut 里完成视频剪辑。
2. 从剪辑软件里导出一个视频或音频文件。
3. 使用本 skill 生成双语或翻译 SRT 字幕。
4. 回到剪映/CapCut，使用“导入本地字幕”功能导入生成的 SRT。
5. 在剪辑软件里继续调整字幕字体、颜色、位置、动画和最终导出。

### 环境要求

- Python 3.10+
- 可以访问本地文件系统并执行 shell 命令的 Agent 环境

脚本会自动检查并尽量安装缺失依赖：

- `openai-whisper`
- `ffmpeg`
- `ffprobe`

自动安装支持：

- macOS：通过 Homebrew 安装 `ffmpeg`
- Linux：通过 `apt-get`、`dnf`、`yum`、`pacman` 或 `apk` 安装 `ffmpeg`
- Windows：通过 `winget` 安装 `ffmpeg`

如果自动安装失败，按提示手动安装即可：

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
winget install --id Gyan.FFmpeg -e

# Whisper
python3 -m pip install openai-whisper
```

### Clone 后如何作为 Skill 使用

最简单的方式是把源码 skill 目录复制到你的 skills 目录。

```bash
git clone <this-repo-url>
cd video-subtitle-translation
mkdir -p ~/.agents/skills
cp -R video-subtitle-translation ~/.agents/skills/
```

安装后如果没有立即出现，请重启 Agent 或开启新会话。

### 使用打包好的 `.skill`

Release 包位于 `releases/video-subtitle-translation.skill`。它本质上是一个包含 `SKILL.md` 和脚本的 ZIP 包。

```bash
mkdir -p ~/.agents/skills
unzip releases/video-subtitle-translation.skill -d ~/.agents/skills
```

### 作为 Codex Plugin 安装

本仓库也包含 Codex plugin 和本地 marketplace 配置，适合希望在 Codex 插件列表里安装和管理的用户。

在仓库根目录运行：

```bash
codex plugin marketplace add .
codex plugin list
codex plugin add video-subtitle-translation
```

安装后重启 Codex 或开启新会话。

### 怎么用

生成中文双语字幕：

```text
使用 video-subtitle-translation，把 /path/to/video.mp4 生成中文双语字幕。
```

只生成中文翻译字幕：

```text
使用 video-subtitle-translation，把 /path/to/video.mp4 转录并翻译成中文，只输出中文 SRT。
```

处理已经导出的音频：

```text
使用 video-subtitle-translation，把 /path/to/audio.mp3 生成中文双语字幕。
```

完成后，把生成的 `.srt` 文件导入剪映/CapCut：

```text
剪映/CapCut -> 文本/字幕 -> 导入本地字幕 -> 选择生成的 .srt 文件
```

### 仓库结构

```text
video-subtitle-translation/
  SKILL.md
  scripts/
    transcribe.py
    write_srt.py
plugins/video-subtitle-translation/
  .codex-plugin/plugin.json
  skills/video-subtitle-translation/
releases/
  video-subtitle-translation.skill
```

顶层 `video-subtitle-translation/` 是源码 skill。`plugins/` 下的副本用于 Codex plugin 分发。

### 隐私说明

脚本处理的是本地媒体文件。默认不会调用外部翻译 API，除非你明确要求 Agent 使用外部服务。安装 Python 包、下载 Whisper 模型，或在云端 Agent 环境运行时，可能会连接外部服务。

### 许可证

MIT

## English

An Agent Skill for generating bilingual subtitles and translated subtitles. First edit your video in CapCut/Jianying or another editor and export a video or audio file. Then use this skill to generate an `.srt` subtitle file. Finally, import the SRT back into CapCut/Jianying and continue editing fonts, colors, placement, animation, and final export.

It does not burn subtitles into the video. It outputs an editable subtitle file.

### Who It Is For

- Creators who need bilingual subtitles
- Users who want to translate spoken video into another language
- Editors who want to keep styling control in CapCut/Jianying
- Users who care about better sentence breaks and context-aware translation

### Advantages Over Built-In CapCut/Jianying Subtitle Translation

- More accurate translation: it translates with surrounding context, so meaning is less likely to be lost when a sentence is split.
- Landscape/portrait adaptation: it adjusts subtitle display width for landscape, portrait, or square videos, with stricter limits for vertical videos.
- Meaning-aware breaks: it reviews sentence boundaries so subtitles do not split in ways that damage the meaning.
- SRT output: it produces subtitle files that can still be styled and edited in CapCut/Jianying.

### What It Produces

The final output is an `.srt` subtitle file:

- Bilingual subtitles: source text + translated text
- Translated-only subtitles: target language only

Intermediate files may include:

- `segments.json`: recognized subtitle segments
- `translations.json`: translations by subtitle ID

The file you import into CapCut/Jianying is the `.srt` file.

### How Subtitle Length Is Controlled

The script auto-selects subtitle budgets for landscape, portrait, or square videos. The option names are still `--max-chars` and `--soft-chars`, but they now behave more like display-width budgets:

- Chinese, Japanese, Korean, and other full-width characters count as about 2 width units.
- Latin letters and digits count as about 1 width unit.
- Spaces also take width.
- `--min-chars 5` stays as a non-whitespace character floor to avoid tiny fragments.

The first pass segments the source transcript. After translation, the agent should also check whether the translated line is too long. If it is, it should first make the translation more concise; if that still does not fit, it should split the source segment at a semantic boundary and translate the new segments. Portrait videos are treated more strictly than landscape videos.

### Recommended Workflow

1. Finish editing your video in CapCut/Jianying.
2. Export a video or audio file from the editor.
3. Use this skill to generate a bilingual or translated SRT file.
4. Return to CapCut/Jianying and use Import local subtitles to import the SRT.
5. Continue adjusting subtitle font, color, position, animation, and final export in the editor.

### Requirements

- Python 3.10+
- A local agent environment with filesystem and shell access

The script checks and tries to install missing dependencies automatically:

- `openai-whisper`
- `ffmpeg`
- `ffprobe`

Automatic installation supports:

- macOS: Homebrew `brew install ffmpeg`
- Linux: `apt-get`, `dnf`, `yum`, `pacman`, or `apk`
- Windows: `winget install --id Gyan.FFmpeg -e`

If automatic installation fails, install manually:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
winget install --id Gyan.FFmpeg -e

# Whisper
python3 -m pip install openai-whisper
```

### Use After Cloning

The simplest path is to copy the source skill directory into your skills directory.

```bash
git clone <this-repo-url>
cd video-subtitle-translation
mkdir -p ~/.agents/skills
cp -R video-subtitle-translation ~/.agents/skills/
```

Restart your agent or start a new session if the skill does not appear immediately.

### Use The Packaged `.skill`

The packaged skill is available at `releases/video-subtitle-translation.skill`. It is a ZIP archive containing `SKILL.md` and the bundled scripts.

```bash
mkdir -p ~/.agents/skills
unzip releases/video-subtitle-translation.skill -d ~/.agents/skills
```

### Install As A Codex Plugin

This repository also includes a Codex plugin and local marketplace entry for users who want to install and manage it from Codex plugin tooling.

From the repository root:

```bash
codex plugin marketplace add .
codex plugin list
codex plugin add video-subtitle-translation
```

Restart Codex or start a new thread after installing.

### Usage

Generate Chinese bilingual subtitles:

```text
Use video-subtitle-translation to generate Chinese bilingual subtitles for /path/to/video.mp4.
```

Generate translated-only Chinese subtitles:

```text
Use video-subtitle-translation to transcribe /path/to/video.mp4 and output Chinese-only SRT subtitles.
```

Use an exported audio file:

```text
Use video-subtitle-translation to generate Chinese bilingual subtitles for /path/to/audio.mp3.
```

After it finishes, import the generated `.srt` file into CapCut/Jianying:

```text
CapCut/Jianying -> Text/Subtitles -> Import local subtitles -> choose the generated .srt file
```

### Repository Layout

```text
video-subtitle-translation/
  SKILL.md
  scripts/
    transcribe.py
    write_srt.py
plugins/video-subtitle-translation/
  .codex-plugin/plugin.json
  skills/video-subtitle-translation/
releases/
  video-subtitle-translation.skill
```

The top-level `video-subtitle-translation/` directory is the source skill. The plugin copy is included for Codex plugin distribution.

### Privacy

The bundled scripts process local media files. No translation API is called unless you explicitly ask the agent to use one. Installing Python packages, downloading Whisper models, or running an agent in a cloud environment may contact external services.

### License

MIT
