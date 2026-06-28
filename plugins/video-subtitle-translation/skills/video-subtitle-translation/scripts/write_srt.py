#!/usr/bin/env python3
"""
Step 3: Combine segments.json + translations.json into a bilingual SRT file.

Usage:
  python write_srt.py --segments segments.json --translations translations.json \
                      --output output.srt [--mode bilingual|translated]
"""

import argparse
import json
import os
import re


TERMINAL_PERIODS = ".。"
TERMINAL_PERIOD_RE = re.compile(r"[.。]+(?=[$\\s\"'”’）)\]}》」』】]*$)")


def ts(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(total_ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def clean_subtitle_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    while True:
        cleaned = TERMINAL_PERIOD_RE.sub("", text).strip()
        if cleaned == text:
            break
        text = cleaned
    return text


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--segments",     required=True)
    p.add_argument("--translations", required=True)
    p.add_argument("--output",       required=True)
    p.add_argument("--mode", default="bilingual", choices=["bilingual", "translated"])
    args = p.parse_args()

    with open(args.segments, encoding="utf-8") as f:
        segments = json.load(f)
    with open(args.translations, encoding="utf-8") as f:
        translations = json.load(f)

    # Support both {"0": "..."} (string keys) and {0: "..."} (int keys)
    tmap = {int(k): v for k, v in translations.items()}

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            original = clean_subtitle_text(seg["text"])
            translated = clean_subtitle_text(tmap.get(seg["id"], original))
            f.write(f"{i}\n")
            f.write(f"{ts(seg['start'])} --> {ts(seg['end'])}\n")
            if args.mode == "bilingual":
                f.write(f"{original}\n{translated}\n\n")
            else:
                f.write(f"{translated}\n\n")

    print(f"SRT written: {args.output}  ({len(segments)} entries, mode={args.mode})")

    # Preview first 3
    print("\nPreview:")
    print("-" * 50)
    with open(args.output, encoding="utf-8") as f:
        count = 0
        block = []
        for line in f:
            block.append(line)
            if line.strip() == "" and block:
                if count < 3:
                    print("".join(block).rstrip())
                    print()
                    count += 1
                block = []


if __name__ == "__main__":
    main()
