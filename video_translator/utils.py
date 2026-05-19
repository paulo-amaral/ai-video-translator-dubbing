import os
import re
import shutil
import subprocess
from pathlib import Path

from .config import PROJECT_DIR


def sanitize_filename(name):
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", name).strip("_")
    return sanitized or "video"


def resolve_project_path(path):
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return PROJECT_DIR / candidate


def run_ffmpeg(command, action):
    try:
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or "").strip()
        if len(details) > 1200:
            details = details[-1200:]
        raise RuntimeError(f"FFmpeg failed while {action}.\n{details}") from exc


def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        raise EnvironmentError("ffmpeg not found. Install FFmpeg and add it to PATH.")
    if shutil.which("ffprobe") is None:
        raise EnvironmentError("ffprobe not found. Install FFmpeg and add it to PATH.")


def get_audio_duration(path):
    from mutagen.mp3 import MP3

    return MP3(path).info.length


def add_leading_silence(input_path, output_path, silence_duration):
    if silence_duration <= 0.01:
        shutil.move(input_path, output_path)
        return

    run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-t", f"{silence_duration:.3f}",
            "-i", "anullsrc=r=44100:cl=mono",
            "-i", str(input_path),
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1",
            "-codec:a", "libmp3lame",
            str(output_path),
        ],
        "adding leading silence",
    )
    os.remove(input_path)
