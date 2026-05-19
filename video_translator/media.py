import os
import shutil
import subprocess
from pathlib import Path

from .config import (
    BACKGROUND_AUDIO_VOLUME,
    DUB_AMBIENCE_DECAY,
    DUB_VOICE_VOLUME,
)
from .utils import run_ffmpeg


def _float_env(name, default):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        print(f"Ignoring invalid {name}={raw_value!r}; using {default}.")
        return default


def combine_audio_segments(audio_dir, final_audio_dir, output_name):
    print("Searching generated audio chunks in", audio_dir)
    audio_dir = Path(audio_dir)
    final_audio_dir = Path(final_audio_dir)
    audio_files = sorted(
        file for file in audio_dir.iterdir()
        if file.suffix == ".mp3"
        and "_raw" not in file.name
        and ".temp" not in file.name
        and not file.name.startswith("tmp")
        and not file.name.startswith(".")
    )
    if not audio_files:
        raise RuntimeError(f"No generated audio chunks found in {audio_dir}")

    list_path = audio_dir / "list.txt"
    with open(list_path, "w", encoding="utf-8") as file:
        for audio_file in audio_files:
            file.write(f"file '{audio_file.resolve().as_posix()}'\n")

    combined_path = final_audio_dir / output_name
    os.makedirs(final_audio_dir, exist_ok=True)
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c:a", "libmp3lame",
            "-q:a", "2",
            str(combined_path),
        ],
        "combining audio chunks",
    )
    print(f"Combined audio file saved as {combined_path}")


def _has_audio_stream(video_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(video_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return "audio" in result.stdout


def prepare_background_audio(video_path, output_dir, mode="original"):
    if mode == "none" or not _has_audio_stream(video_path):
        return None

    output_dir = Path(output_dir)
    background_dir = output_dir / "background"
    background_dir.mkdir(parents=True, exist_ok=True)

    original_audio = background_dir / "original.wav"
    if not original_audio.exists():
        run_ffmpeg(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vn",
                "-ac", "2",
                "-ar", "44100",
                str(original_audio),
            ],
            "extracting the original background audio",
        )

    if mode == "original":
        return original_audio

    if mode != "demucs":
        raise ValueError(f"Unsupported background mode: {mode}")

    if shutil.which("demucs") is None:
        print("Demucs is not installed. Falling back to the low-volume original audio.")
        return original_audio

    demucs_output_root = background_dir / "demucs"
    no_vocals_path = demucs_output_root / "htdemucs" / original_audio.stem / "no_vocals.wav"
    if no_vocals_path.exists():
        return no_vocals_path

    print("Separating vocals from background audio with Demucs...")
    try:
        subprocess.run(
            [
                "demucs",
                "--two-stems", "vocals",
                "-n", "htdemucs",
                "-o", str(demucs_output_root),
                str(original_audio),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Demucs failed with exit code {exc.returncode}. Falling back to original audio.")
        return original_audio

    if not no_vocals_path.exists():
        print("Demucs finished, but no_vocals.wav was not found. Falling back to original audio.")
        return original_audio
    return no_vocals_path


def replace_audio(video_path, audio_path, output_path, background_audio_path=None):
    dub_volume = _float_env("DUB_VOICE_VOLUME", DUB_VOICE_VOLUME)
    bg_volume = _float_env("BACKGROUND_AUDIO_VOLUME", BACKGROUND_AUDIO_VOLUME)
    ambience_decay = max(0.0, _float_env("DUB_AMBIENCE_DECAY", DUB_AMBIENCE_DECAY))
    if background_audio_path is None:
        print("Original video has no audio stream. Adding dubbed audio only...")
        run_ffmpeg(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(output_path),
            ],
            "adding the dubbed audio track",
        )
        return

    print("Adding dubbed audio to video and mixing preserved background audio...")
    dub_filter = (
        f"[1:a:0]aformat=sample_rates=44100:channel_layouts=stereo,volume={dub_volume},"
        "highpass=f=80,lowpass=f=15500,"
        "acompressor=threshold=-16dB:ratio=2.2:attack=8:release=120"
    )
    if ambience_decay > 0:
        dub_filter += f",aecho=0.8:0.88:28:{ambience_decay:.3f}"

    run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-i", str(background_audio_path),
            "-filter_complex",
            (
                f"[2:a:0]aformat=sample_rates=44100:channel_layouts=stereo,volume={bg_volume},"
                "highpass=f=70,lowpass=f=15000,"
                "acompressor=threshold=-18dB:ratio=1.8:attack=20:release=250[bg];"
                f"{dub_filter}[dub_pre];"
                "[dub_pre]aformat=sample_rates=44100:channel_layouts=stereo[dub];"
                "[bg][dub]amix=inputs=2:duration=longest:dropout_transition=0.35:normalize=0,"
                "acompressor=threshold=-12dB:ratio=1.6:attack=12:release=180,"
                "alimiter=limit=0.95[aout]"
            ),
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path),
        ],
        "mixing dubbed audio with the original background track",
    )
