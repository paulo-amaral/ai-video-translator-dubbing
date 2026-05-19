import os

from .config import (
    LANGUAGE_CODES,
    SUPPORTED_LANGUAGES,
    TRANSCRIPT_MAX_SEGMENT_CHARS,
    TRANSCRIPT_MAX_SEGMENT_DURATION,
    TRANSCRIPT_MERGE_GAP,
    TRANSCRIPT_MIN_SEGMENT_DURATION,
)


def _device_for_transcription(use_gpu):
    import torch

    if not use_gpu:
        print("Using CPU for transcription")
        return "cpu"

    if not torch.cuda.is_available():
        print("GPU requested but CUDA is not available. Falling back to CPU.")
        return "cpu"

    print(f"Using GPU: {torch.cuda.get_device_name(0)}")
    print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    return "cuda"


def transcribe_video(video_path, transcript_path, source_lang="auto", model_size="base", use_gpu=False):
    try:
        import whisper
    except ImportError as exc:
        raise ImportError("Missing transcription dependency. Install requirements.txt first.") from exc

    print(f"Loading Whisper {model_size} model...")
    device = _device_for_transcription(use_gpu)

    try:
        model = whisper.load_model(
            model_size,
            device=device,
            download_root=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"),
        )
    except Exception as exc:
        print(f"Error loading model: {exc}")
        if "CUDA" not in str(exc):
            raise
        print("CUDA error detected. Falling back to CPU.")
        device = "cpu"
        model = whisper.load_model(
            model_size,
            device="cpu",
            download_root=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"),
        )

    transcribe_kwargs = {
        "word_timestamps": True,
        "temperature": 0.0,
    }
    if source_lang != "auto":
        transcribe_kwargs["language"] = LANGUAGE_CODES["whisper"][source_lang]

    if device == "cpu":
        transcribe_kwargs.update({
            "fp16": False,
            "beam_size": 3,
            "best_of": 3,
            "condition_on_previous_text": False,
        })
    else:
        transcribe_kwargs.update({
            "fp16": True,
            "beam_size": 5,
            "best_of": 5,
            "condition_on_previous_text": True,
        })

    print("Starting transcription...")
    result = model.transcribe(video_path, **transcribe_kwargs)
    detected_lang = result.get("language") or source_lang
    if detected_lang not in SUPPORTED_LANGUAGES:
        if source_lang == "auto":
            raise RuntimeError(f"Detected source language '{detected_lang}' is not supported by this project.")
        detected_lang = source_lang
    print(f"Source language: {SUPPORTED_LANGUAGES[detected_lang]} ({detected_lang})")

    segments = _split_word_segments(result.get("segments", []))
    with open(transcript_path, "w", encoding="utf-8") as file:
        file.write(f"# source_lang: {detected_lang}\n")
        for segment in segments:
            text = " ".join(segment["text"].strip().split())
            file.write(f"[{segment['start']:.2f} - {segment['end']:.2f}] {text}\n")

    print(f"Transcribed {len(segments)} segments")
    return segments, detected_lang


def _split_word_segments(raw_segments):
    processed_segments = []
    current_segment = {"text": "", "start": None, "end": None, "words": []}
    sentence_endings = {".", "!", "?", "..."}

    for segment in raw_segments:
        words = segment.get("words", [])
        if not words and segment.get("text"):
            processed_segments.append({
                "text": segment["text"],
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "words": [],
            })
            continue

        for word in words:
            if current_segment["start"] is None:
                current_segment = {
                    "text": word["word"],
                    "start": word["start"],
                    "end": word["end"],
                    "words": [word],
                }
                continue

            current_duration = current_segment["end"] - current_segment["start"]
            next_duration = word["end"] - current_segment["start"]
            current_text = current_segment["text"].strip()
            ends_with_sentence = any(current_text.endswith(end) for end in sentence_endings)
            has_minimum_duration = current_duration >= TRANSCRIPT_MIN_SEGMENT_DURATION
            would_exceed_duration = next_duration > TRANSCRIPT_MAX_SEGMENT_DURATION
            would_exceed_length = len(current_text) + len(word["word"]) + 1 > TRANSCRIPT_MAX_SEGMENT_CHARS

            if (ends_with_sentence and has_minimum_duration) or would_exceed_duration or would_exceed_length:
                processed_segments.append(current_segment)
                current_segment = {
                    "text": word["word"],
                    "start": word["start"],
                    "end": word["end"],
                    "words": [word],
                }
            else:
                current_segment["text"] += " " + word["word"]
                current_segment["end"] = word["end"]
                current_segment["words"].append(word)

    if current_segment["text"]:
        processed_segments.append(current_segment)

    return _merge_short_segments(processed_segments)


def _merge_short_segments(segments):
    merged_segments = []

    for segment in segments:
        if not merged_segments:
            merged_segments.append(segment)
            continue

        previous = merged_segments[-1]
        previous_duration = previous["end"] - previous["start"]
        gap = segment["start"] - previous["end"]
        combined_duration = segment["end"] - previous["start"]
        combined_text_length = len(previous["text"]) + len(segment["text"]) + 1
        should_merge = (
            previous_duration < TRANSCRIPT_MIN_SEGMENT_DURATION
            and gap <= TRANSCRIPT_MERGE_GAP
            and combined_duration <= TRANSCRIPT_MAX_SEGMENT_DURATION
            and combined_text_length <= TRANSCRIPT_MAX_SEGMENT_CHARS
        )

        if should_merge:
            previous["text"] = f"{previous['text']} {segment['text']}"
            previous["end"] = segment["end"]
            previous["words"].extend(segment.get("words", []))
        else:
            merged_segments.append(segment)

    return merged_segments
