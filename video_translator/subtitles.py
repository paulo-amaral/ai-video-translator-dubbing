import re
from html import unescape
from pathlib import Path


TIMESTAMP_PATTERN = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[.,]\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}[.,]\d{3})"
)
TAG_PATTERN = re.compile(r"<[^>]+>")


def parse_vtt_timestamp(value):
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def clean_vtt_text(lines):
    text = " ".join(line.strip() for line in lines if line.strip())
    text = TAG_PATTERN.sub("", text)
    return " ".join(unescape(text).split())


def load_vtt_segments(vtt_path):
    path = Path(vtt_path).expanduser()
    segments = []
    current_timing = None
    text_lines = []

    with open(path, "r", encoding="utf-8-sig") as file:
        for raw_line in file:
            line = raw_line.strip()
            timing_match = TIMESTAMP_PATTERN.search(line)

            if not line:
                if current_timing and text_lines:
                    text = clean_vtt_text(text_lines)
                    if text:
                        segments.append({**current_timing, "text": text, "words": []})
                current_timing = None
                text_lines = []
                continue

            if timing_match:
                if current_timing and text_lines:
                    text = clean_vtt_text(text_lines)
                    if text:
                        segments.append({**current_timing, "text": text, "words": []})
                current_timing = {
                    "start": parse_vtt_timestamp(timing_match.group("start")),
                    "end": parse_vtt_timestamp(timing_match.group("end")),
                }
                text_lines = []
                continue

            if line == "WEBVTT" or line.startswith(("NOTE", "STYLE", "REGION")):
                continue
            if current_timing:
                text_lines.append(line)

    if current_timing and text_lines:
        text = clean_vtt_text(text_lines)
        if text:
            segments.append({**current_timing, "text": text, "words": []})

    return segments
