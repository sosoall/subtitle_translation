#!/usr/bin/env python3
"""
Extract audio and transcribe it with Whisper.

Outputs first-pass subtitle segments built from Whisper word timestamps.
Review them semantically before translation.

Usage:
  python transcribe.py --input /path/to/video.mp4 --output segments.json
  python transcribe.py --input video.mp4 --model auto --lang zh
  python transcribe.py --input video.mp4 --layout auto --subtitle-mode bilingual
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from typing import Any, Dict, List, Optional


SUPPORTED_VIDEO = ["mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "ts",
                   "m2ts", "mpg", "mpeg", "m4v", "3gp", "rmvb", "divx", "f4v"]
SUPPORTED_AUDIO = ["mp3", "wav", "aac", "flac", "m4a", "ogg", "wma", "opus",
                   "ac3", "amr"]

MODEL_CHOICES = ["auto", "tiny", "base", "small", "medium", "large", "turbo"]
LAYOUT_CHOICES = ["auto", "portrait", "landscape", "square"]
MODE_CHOICES = ["bilingual", "translated"]
STRONG_PUNCT = set(".?!。？！")
SOFT_PUNCT = set(",，;；:：、")
PUNCT_BREAK = STRONG_PUNCT | SOFT_PUNCT
PRESETS = {
    "bilingual": {
        "portrait": {"max_chars": 22, "soft_chars": 14, "min_chars": 5},
        "square": {"max_chars": 26, "soft_chars": 18, "min_chars": 5},
        "landscape": {"max_chars": 28, "soft_chars": 20, "min_chars": 5},
    },
    "translated": {
        "portrait": {"max_chars": 26, "soft_chars": 18, "min_chars": 5},
        "square": {"max_chars": 32, "soft_chars": 22, "min_chars": 5},
        "landscape": {"max_chars": 42, "soft_chars": 28, "min_chars": 5},
    },
}


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_install_command(command: List[str], tool_name: str) -> bool:
    print(f"{tool_name} not found; trying: {' '.join(command)}", flush=True)
    try:
        result = subprocess.run(command, check=False)
    except FileNotFoundError:
        return False
    return result.returncode == 0


def install_ffmpeg() -> bool:
    if sys.platform == "darwin" and command_exists("brew"):
        return run_install_command(["brew", "install", "ffmpeg"], "ffmpeg")

    if sys.platform.startswith("linux"):
        if command_exists("apt-get"):
            return (
                run_install_command(["sudo", "apt-get", "update"], "ffmpeg")
                and run_install_command(["sudo", "apt-get", "install", "-y", "ffmpeg"], "ffmpeg")
            )
        if command_exists("dnf"):
            return run_install_command(["sudo", "dnf", "install", "-y", "ffmpeg"], "ffmpeg")
        if command_exists("yum"):
            return run_install_command(["sudo", "yum", "install", "-y", "ffmpeg"], "ffmpeg")
        if command_exists("pacman"):
            return run_install_command(["sudo", "pacman", "-S", "--noconfirm", "ffmpeg"], "ffmpeg")
        if command_exists("apk"):
            return run_install_command(["sudo", "apk", "add", "ffmpeg"], "ffmpeg")

    if sys.platform.startswith("win") and command_exists("winget"):
        return run_install_command(
            ["winget", "install", "--id", "Gyan.FFmpeg", "-e"],
            "ffmpeg",
        )

    return False


def ensure_media_tools():
    missing = [tool for tool in ("ffmpeg", "ffprobe") if not command_exists(tool)]
    if not missing:
        return

    print(f"Missing media tool(s): {', '.join(missing)}", flush=True)
    if install_ffmpeg() and all(command_exists(tool) for tool in ("ffmpeg", "ffprobe")):
        print("ffmpeg and ffprobe installed", flush=True)
        return

    print(
        "Could not install ffmpeg automatically. Install it manually, then rerun.\n"
        "macOS: brew install ffmpeg\n"
        "Ubuntu/Debian: sudo apt-get install ffmpeg\n"
        "Windows: winget install --id Gyan.FFmpeg -e",
        file=sys.stderr,
    )
    sys.exit(1)


def ensure_whisper():
    try:
        import whisper
        return whisper
    except ImportError:
        print("whisper not found; installing openai-whisper...", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "openai-whisper",
             "--break-system-packages", "-q"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("pip install failed with --break-system-packages; trying user install...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "openai-whisper", "--user", "-q"],
                check=True
            )
        try:
            import whisper
            print("openai-whisper installed", flush=True)
            return whisper
        except ImportError:
            print("Still cannot import whisper. Try: python3 -m pip install openai-whisper",
                  file=sys.stderr)
            sys.exit(1)


def resolve_path(path: str) -> str:
    resolved = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(resolved):
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        all_formats = SUPPORTED_VIDEO + SUPPORTED_AUDIO
        if ext and ext not in all_formats:
            print(f"Unknown format '.{ext}'. ffmpeg may still support it.")
        print(f"File not found: {resolved}", file=sys.stderr)
        sys.exit(1)
    return resolved


def extract_audio(video_path: str, audio_path: str):
    print(f"Extracting audio from: {os.path.basename(video_path)}", flush=True)
    r = subprocess.run(
        ["ffmpeg", "-i", video_path,
         "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
         audio_path, "-y"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        stderr = r.stderr.lower()
        if "output file is empty" in stderr or "no streams" in stderr:
            print("No audio stream found. Is this a video-only file?", file=sys.stderr)
        elif "no such file" in stderr:
            print(f"File not found by ffmpeg: {video_path}", file=sys.stderr)
        else:
            print(f"ffmpeg error:\n{r.stderr[-800:]}", file=sys.stderr)
        sys.exit(1)
    print("Audio extracted", flush=True)


def video_dimensions(path: str) -> Optional[tuple[int, int]]:
    r = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            path,
        ],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        return None
    line = r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
    match = re.match(r"^(\d+)x(\d+)$", line)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def detect_layout(path: str, requested: str) -> str:
    if requested != "auto":
        return requested
    dims = video_dimensions(path)
    if not dims:
        print("Layout auto: no video stream or unknown dimensions -> landscape preset", flush=True)
        return "landscape"
    width, height = dims
    if height > width:
        layout = "portrait"
    elif width > height:
        layout = "landscape"
    else:
        layout = "square"
    print(f"Layout auto: {width}x{height} -> {layout}", flush=True)
    return layout


def apply_layout_preset(args, layout: str):
    preset = PRESETS[args.subtitle_mode][layout]
    if args.max_chars is None:
        args.max_chars = preset["max_chars"]
    if args.soft_chars is None:
        args.soft_chars = preset["soft_chars"]
    if args.min_chars is None:
        args.min_chars = preset["min_chars"]
    print(
        "Subtitle preset: "
        f"mode={args.subtitle_mode}, layout={layout}, "
        f"max_chars={args.max_chars}, soft_chars={args.soft_chars}, min_chars={args.min_chars}",
        flush=True
    )


def cuda_vram_gb() -> Optional[float]:
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        props = torch.cuda.get_device_properties(0)
        return props.total_memory / (1024 ** 3)
    except Exception:
        return None


def has_mps() -> bool:
    try:
        import torch
        return bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
    except Exception:
        return False


def choose_model(requested: str) -> str:
    if requested != "auto":
        return requested

    vram = cuda_vram_gb()
    if vram is not None:
        if vram >= 12:
            model = "large"
        elif vram >= 8:
            model = "medium"
        elif vram >= 4:
            model = "small"
        else:
            model = "base"
        print(f"Auto model: CUDA GPU with {vram:.1f} GB VRAM -> {model}", flush=True)
        return model

    if has_mps():
        print("Auto model: Apple Silicon MPS detected -> small", flush=True)
        return "small"

    print("Auto model: CPU or unknown memory -> base", flush=True)
    return "base"


def transcribe(whisper_mod, audio_path: str, model_size: str,
               source_lang: Optional[str] = None) -> Dict[str, Any]:
    print(f"Loading Whisper '{model_size}' model...", flush=True)
    try:
        model = whisper_mod.load_model(model_size)
    except RuntimeError as exc:
        if model_size in {"large", "medium", "small"} and "out of memory" in str(exc).lower():
            fallback = "base"
            print(f"Model load ran out of memory; falling back to '{fallback}'", flush=True)
            model = whisper_mod.load_model(fallback)
            model_size = fallback
        else:
            raise

    kwargs: Dict[str, Any] = {"verbose": False, "word_timestamps": True}
    if source_lang:
        kwargs["language"] = source_lang

    print("Transcribing with word timestamps...", flush=True)
    try:
        result = model.transcribe(audio_path, **kwargs)
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower() and model_size != "base":
            print("Transcription ran out of memory; retrying with 'base'", flush=True)
            model = whisper_mod.load_model("base")
            result = model.transcribe(audio_path, **kwargs)
        else:
            raise

    seg_count = len(result.get("segments", []))
    print(f"{seg_count} raw Whisper segments | detected language: {result.get('language', '?')}",
          flush=True)
    return result


def text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def display_width(text: str) -> int:
    """Approximate subtitle display width across CJK and Latin scripts."""
    width = 0
    for char in text:
        if char.isspace():
            width += 1
        elif unicodedata.combining(char):
            continue
        elif unicodedata.east_asian_width(char) in {"F", "W"}:
            width += 2
        else:
            width += 1
    return width


def word_gap(prev_word: Dict[str, Any], next_word: Dict[str, Any]) -> float:
    prev_end = float(prev_word.get("end", prev_word.get("start", 0)))
    next_start = float(next_word.get("start", prev_end))
    return max(0.0, next_start - prev_end)


def has_trailing_punct(words: List[Dict[str, Any]]) -> bool:
    text = join_words(words)
    return bool(text) and text[-1] in PUNCT_BREAK


def join_words(words: List[Dict[str, Any]]) -> str:
    text = "".join(w.get("word", "") for w in words).strip()
    # Whisper's English word tokens usually include leading spaces. This cleanup
    # preserves CJK text while normalizing extra spaces.
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.?!;:，。？！；：、])", r"\1", text)
    return text.strip()


def flatten_words(raw_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    words: List[Dict[str, Any]] = []
    for seg in raw_segments:
        seg_words = seg.get("words") or []
        if seg_words:
            for word in seg_words:
                if "start" in word and "end" in word and word.get("word", "").strip():
                    words.append({
                        "word": word["word"],
                        "start": float(word["start"]),
                        "end": float(word["end"]),
                    })
        elif seg.get("text", "").strip():
            words.append({
                "word": seg["text"].strip(),
                "start": float(seg["start"]),
                "end": float(seg["end"]),
            })
    return words


def should_break(current_words: List[Dict[str, Any]], next_word: Optional[Dict[str, Any]],
                 max_chars: int, soft_chars: int, min_chars: int,
                 max_secs: float, max_gap: float) -> bool:
    if not current_words:
        return False

    text = join_words(current_words)
    min_length = text_len(text)
    width = display_width(text)
    duration = current_words[-1]["end"] - current_words[0]["start"]
    last_char = text[-1] if text else ""
    gap = word_gap(current_words[-1], next_word) if next_word else math.inf

    if next_word is None:
        return True
    if last_char in STRONG_PUNCT:
        return True
    if last_char in SOFT_PUNCT and min_length >= min_chars:
        return True
    if width >= soft_chars and gap >= max_gap:
        return True
    if duration >= max_secs and gap >= max_gap:
        return True
    if duration >= max_secs * 1.4:
        return True
    return False


def find_semantic_break_index(words: List[Dict[str, Any]], max_chars: int,
                              soft_chars: int, min_chars: int,
                              max_gap: float) -> Optional[int]:
    if len(words) < 2:
        return None

    best_index = None
    best_score = -1.0
    # Only split between tokens. This avoids cutting inside CJK terms when
    # Whisper returns a phrase as one token.
    for index in range(1, len(words)):
        left = words[:index]
        right = words[index:]
        left_text = join_words(left)
        right_text = join_words(right)
        if text_len(left_text) < min_chars or text_len(right_text) < min_chars:
            continue

        left_width = display_width(left_text)
        gap = word_gap(left[-1], right[0])
        last_char = left_text[-1] if left_text else ""

        score = 0.0
        if last_char in STRONG_PUNCT:
            score += 100
        elif last_char in SOFT_PUNCT:
            score += 80
        if gap >= max_gap:
            score += 50 + min(gap, 1.5) * 10

        # Prefer boundaries near the existing max/soft budgets, but do not let
        # width alone outrank punctuation, pause, or semantic review.
        score -= abs(left_width - max_chars) * 0.8
        if left_width >= soft_chars:
            score += 8
        if left_width > max_chars:
            score -= (left_width - max_chars) * 2

        if score > best_score:
            best_score = score
            best_index = index

    if best_index is None:
        return None

    if best_score >= 20:
        return best_index
    return None


def build_subtitle_segments(raw_segments: List[Dict[str, Any]], max_chars: int,
                            soft_chars: int, min_chars: int,
                            max_secs: float, max_gap: float) -> List[Dict[str, Any]]:
    words = flatten_words(raw_segments)
    if not words:
        return [
            {"id": i, "start": s["start"], "end": s["end"], "text": s["text"].strip()}
            for i, s in enumerate(raw_segments)
            if s.get("text", "").strip()
        ]

    segments: List[Dict[str, Any]] = []
    current: List[Dict[str, Any]] = []

    for i, word in enumerate(words):
        current.append(word)
        next_word = words[i + 1] if i + 1 < len(words) else None
        if should_break(current, next_word, max_chars, soft_chars, min_chars, max_secs, max_gap):
            segments.append({
                "id": len(segments),
                "start": round(current[0]["start"], 3),
                "end": round(current[-1]["end"], 3),
                "text": join_words(current),
            })
            current = []
        elif display_width(join_words(current)) > max_chars * 1.35 and not has_trailing_punct(current):
            break_index = find_semantic_break_index(
                current, max_chars, soft_chars, min_chars, max_gap
            )
            if break_index is not None:
                segment_words = current[:break_index]
                current = current[break_index:]
                segments.append({
                    "id": len(segments),
                    "start": round(segment_words[0]["start"], 3),
                    "end": round(segment_words[-1]["end"], 3),
                    "text": join_words(segment_words),
                })

    if current:
        segments.append({
            "id": len(segments),
            "start": round(current[0]["start"], 3),
            "end": round(current[-1]["end"], 3),
            "text": join_words(current),
        })

    return merge_short_segments([s for s in segments if s["text"]], min_chars)


def merge_short_segments(segments: List[Dict[str, Any]], min_chars: int) -> List[Dict[str, Any]]:
    if not segments or min_chars <= 1:
        return segments

    result: List[Dict[str, Any]] = []
    i = 0
    while i < len(segments):
        seg = dict(segments[i])
        if text_len(seg["text"]) >= min_chars or len(segments) == 1:
            result.append(seg)
            i += 1
            continue

        if result:
            prev = result[-1]
            prev["end"] = seg["end"]
            prev["text"] = join_text(prev["text"], seg["text"])
        elif i + 1 < len(segments):
            nxt = dict(segments[i + 1])
            nxt["start"] = seg["start"]
            nxt["text"] = join_text(seg["text"], nxt["text"])
            result.append(nxt)
            i += 1
        else:
            result.append(seg)
        i += 1

    for new_id, seg in enumerate(result):
        seg["id"] = new_id
    return result


def join_text(left: str, right: str) -> str:
    joined = f"{left.rstrip()} {right.lstrip()}".strip()
    return re.sub(r"\s+([,.?!;:，。？！；：、])", r"\1", joined)


def main():
    p = argparse.ArgumentParser(
        description="Transcribe video/audio into first-pass subtitle segments for semantic review."
    )
    p.add_argument("--input", required=True,
                   help="Path to video or audio file (supports ~ and relative paths)")
    p.add_argument("--output", default="segments.json",
                   help="Output JSON path (default: segments.json)")
    p.add_argument("--model", default="auto", choices=MODEL_CHOICES,
                   help="Whisper model size. Default: auto")
    p.add_argument("--lang", default=None,
                   help="Force source language, e.g. zh, en, ja. Default: auto-detect.")
    p.add_argument("--layout", default="auto", choices=LAYOUT_CHOICES,
                   help="Video layout for subtitle length presets. Default: auto")
    p.add_argument("--subtitle-mode", default="bilingual", choices=MODE_CHOICES,
                   help="Subtitle output style used to choose length presets. Default: bilingual")
    p.add_argument("--max-chars", type=int, default=None,
                   help="Override max display-width units per source subtitle card.")
    p.add_argument("--soft-chars", type=int, default=None,
                   help="Override display-width units where pause breaks are preferred.")
    p.add_argument("--min-chars", type=int, default=None,
                   help="Override minimum source characters before punctuation breaks. Default from preset: 5")
    p.add_argument("--max-secs", type=float, default=7.0,
                   help="Safety limit for long cards. Default: 7.0")
    p.add_argument("--max-gap", type=float, default=0.65,
                   help="Pause in seconds that can trigger a break after soft-chars. Default: 0.65")
    args = p.parse_args()

    ensure_media_tools()
    input_path = resolve_path(args.input)
    layout = detect_layout(input_path, args.layout)
    apply_layout_preset(args, layout)

    if args.soft_chars > args.max_chars:
        print("--soft-chars cannot be greater than --max-chars", file=sys.stderr)
        sys.exit(1)
    if args.min_chars > args.max_chars:
        print("--min-chars cannot be greater than --max-chars", file=sys.stderr)
        sys.exit(1)

    whisper_mod = ensure_whisper()
    model_size = choose_model(args.model)

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = os.path.join(tmp, "audio.wav")
        extract_audio(input_path, audio_path)
        result = transcribe(whisper_mod, audio_path, model_size, args.lang)

    raw_segments = result.get("segments", [])
    if not raw_segments:
        print("No speech detected.", file=sys.stderr)
        sys.exit(1)

    segments = build_subtitle_segments(
        raw_segments,
        max_chars=args.max_chars,
        soft_chars=args.soft_chars,
        min_chars=args.min_chars,
        max_secs=args.max_secs,
        max_gap=args.max_gap,
    )

    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(segments)} first-pass subtitle segments -> {args.output}")
    print("Review segment boundaries semantically before translation.")
    print("\nPreview (first 5):")
    for s in segments[:5]:
        dur = s["end"] - s["start"]
        print(f"  [{s['id']:3d}] {s['start']:6.1f}s ({dur:.1f}s) {s['text']}")


if __name__ == "__main__":
    main()
