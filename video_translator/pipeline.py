import os
from pathlib import Path

from .config import PROJECT_DIR, SUPPORTED_LANGUAGES
from .media import combine_audio_segments, prepare_background_audio, replace_audio
from .subtitles import load_vtt_segments
from .transcription import transcribe_video
from .translation import translate_text
from .tts import generate_tts_with_timing
from .utils import check_ffmpeg, sanitize_filename


def clear_dub_outputs(tts_chunks_dir, dubbed_audio, final_output):
    for chunk in tts_chunks_dir.glob("*.mp3"):
        chunk.unlink()
    for generated_file in (dubbed_audio, final_output):
        if generated_file.exists():
            generated_file.unlink()


def clear_pipeline_outputs(tts_chunks_dir, transcript_file, translated_file, dubbed_audio, final_output):
    clear_dub_outputs(tts_chunks_dir, dubbed_audio, final_output)
    for generated_file in (transcript_file, translated_file):
        if generated_file.exists():
            generated_file.unlink()


def load_transcript(transcript_file):
    segments = []
    source_lang = "auto"
    with open(transcript_file, "r", encoding="utf-8") as file:
        for line in file:
            if line.startswith("# source_lang:"):
                saved_lang = line.split(":", 1)[1].strip()
                if saved_lang in SUPPORTED_LANGUAGES:
                    source_lang = saved_lang
                continue
            if "] " not in line:
                continue

            timing, text = line.split("] ", 1)
            start, end = timing.strip("[]").split(" - ")
            segments.append({"text": text.strip(), "start": float(start), "end": float(end)})

    return segments, source_lang


def save_transcript(transcript_file, segments, source_lang):
    with open(transcript_file, "w", encoding="utf-8") as file:
        file.write(f"# source_lang: {source_lang}\n")
        for segment in segments:
            text = " ".join(segment["text"].strip().split())
            file.write(f"[{segment['start']:.2f} - {segment['end']:.2f}] {text}\n")


def run_pipeline(video_path, source_lang="auto", target_lang="pt", use_rvc=True, voice_gender="female", rvc_model=None, timing_vtt=None, whisper_model="base", translator_model="auto", translation_provider="local", tts_provider="edge", background_mode="original", use_gpu=False, force_dub=False, force_transcribe=False):
    check_ffmpeg()

    input_path = Path(video_path).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Video file not found: {input_path}")

    base_name = sanitize_filename(input_path.stem)
    output_dir = PROJECT_DIR / "output" / base_name
    tts_chunks_dir = output_dir / "tts-chunks"
    output_dir.mkdir(parents=True, exist_ok=True)
    tts_chunks_dir.mkdir(parents=True, exist_ok=True)

    transcript_file = output_dir / "transcript.txt"
    translated_file = output_dir / "translated.txt"
    dubbed_audio = output_dir / "audio_dubbed.mp3"
    final_output = output_dir / f"{base_name}_dubbed.mp4"

    if force_transcribe:
        print("Regenerating transcript, translation, dubbed audio, and final video outputs.")
        clear_pipeline_outputs(tts_chunks_dir, transcript_file, translated_file, dubbed_audio, final_output)
    elif force_dub:
        print("Regenerating dubbed audio/video outputs.")
        clear_dub_outputs(tts_chunks_dir, dubbed_audio, final_output)

    if timing_vtt and (force_transcribe or not transcript_file.exists()):
        print(f"Using VTT transcript/timing source: {timing_vtt}")
        segments = load_vtt_segments(timing_vtt)
        if not segments:
            raise RuntimeError(f"No usable VTT cues found in {timing_vtt}")
        effective_source_lang = source_lang if source_lang != "auto" else target_lang
        save_transcript(transcript_file, segments, effective_source_lang)
    elif transcript_file.exists():
        print(f"Skipping transcription; found {transcript_file}")
        segments, effective_source_lang = load_transcript(transcript_file)
    else:
        print("Transcribing video...")
        segments, effective_source_lang = transcribe_video(str(input_path), transcript_file, source_lang, whisper_model, use_gpu)

    if not segments:
        raise RuntimeError("No transcript segments were produced.")
    if effective_source_lang == "auto":
        effective_source_lang = "en"
        print("Existing transcript has no source language metadata. Assuming English (en).")

    texts = [segment["text"] for segment in segments]
    if translated_file.exists():
        print(f"Skipping translation; found {translated_file}")
        with open(translated_file, "r", encoding="utf-8") as file:
            translations = [line.strip() for line in file.readlines()]
    else:
        print("Translating text...")
        translations = translate_text(
            texts,
            translated_file,
            effective_source_lang,
            target_lang,
            translator_model,
            translation_provider,
        )

    if len(translations) != len(segments):
        raise RuntimeError(
            f"Translation count ({len(translations)}) does not match segment count ({len(segments)}). "
            "Delete translated.txt and run again."
        )

    expected_audio_files = [str(tts_chunks_dir / f"{base_name}_{index:04d}.mp3") for index in range(len(translations))]
    if all(os.path.exists(file) and os.path.getsize(file) > 0 for file in expected_audio_files):
        print("Skipping TTS; all audio chunks already exist.")
    else:
        print(f"Generating TTS audio with {voice_gender} voice...")
        generated_files = generate_tts_with_timing(
            translations,
            tts_chunks_dir,
            base_name,
            segments,
            target_lang,
            use_rvc,
            voice_gender,
            rvc_model,
            tts_provider,
        )
        print(f"Generated {len(generated_files)} audio files")

    if not dubbed_audio.exists():
        print("Combining audio segments...")
        combine_audio_segments(tts_chunks_dir, output_dir, "audio_dubbed.mp3")
    else:
        print(f"Skipping combination; found {dubbed_audio}")

    if not final_output.exists():
        print("Creating final video...")
        background_audio = prepare_background_audio(input_path, output_dir, background_mode)
        replace_audio(input_path, dubbed_audio, final_output, background_audio)
    else:
        print(f"Skipping final build; found {final_output}")

    print(f"Done. Result: {final_output}")
    return final_output
