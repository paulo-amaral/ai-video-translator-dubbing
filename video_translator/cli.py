import argparse
import os
import sys

from .config import BACKGROUND_MODES, MIN_PYTHON, MODEL_CONFIG, SUPPORTED_LANGUAGES, TRANSLATION_PROVIDERS, TTS_PROVIDERS, VOICE_OPTIONS
from .pipeline import run_pipeline
from .utils import resolve_project_path


def build_parser():
    parser = argparse.ArgumentParser(description="Translate video between different languages")
    parser.add_argument("video_path", help="Path to the video file to translate")
    parser.add_argument(
        "--source-lang", "-s",
        choices=["auto", *SUPPORTED_LANGUAGES.keys()],
        default="auto",
        help="Source language (default: auto)",
    )
    parser.add_argument(
        "--target-lang", "-t",
        choices=SUPPORTED_LANGUAGES.keys(),
        default="pt",
        help="Target language (default: pt)",
    )
    parser.add_argument("--no-rvc", action="store_true", help="Disable RVC voice conversion")
    parser.add_argument(
        "--voice-gender", "-g",
        choices=["male", "female"],
        default="female",
        help="Voice gender (default: female)",
    )
    parser.add_argument("--rvc-model", "-m", help="Path to custom RVC model (optional)")
    parser.add_argument(
        "--tts-provider",
        choices=sorted(TTS_PROVIDERS),
        default="edge",
        help="TTS provider to use for dubbed voice (default: edge)",
    )
    parser.add_argument(
        "--background-mode",
        choices=sorted(BACKGROUND_MODES),
        default="original",
        help="Background preservation mode: original, demucs, or none (default: original)",
    )
    parser.add_argument(
        "--timing-vtt",
        help="Use a WebVTT file as the transcript/timing source for smoother dubbing",
    )
    parser.add_argument(
        "--force-dub",
        action="store_true",
        help="Regenerate TTS chunks, dubbed audio, and final video from existing transcript/translation",
    )
    parser.add_argument(
        "--force-transcribe",
        action="store_true",
        help="Regenerate transcript, translation, TTS chunks, dubbed audio, and final video",
    )
    parser.add_argument(
        "--whisper-model", "-w",
        choices=MODEL_CONFIG["whisper"].keys(),
        default="base",
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--translator-model", "-tr",
        choices=["auto", *MODEL_CONFIG["translator"].keys()],
        default="auto",
        help="Translation model (default: auto)",
    )
    parser.add_argument(
        "--translation-provider",
        choices=sorted(TRANSLATION_PROVIDERS),
        default="local",
        help="Translation provider: local models, OpenAI, or Gemini natural dubbing translation (default: local)",
    )
    parser.add_argument("--use-gpu", action="store_true", help="Use GPU for Whisper transcription")
    return parser


def main(argv=None):
    if sys.version_info < MIN_PYTHON:
        raise RuntimeError("This project requires Python 3.9 or newer.")

    parser = build_parser()
    args = parser.parse_args(argv)

    source_label = "Auto detect" if args.source_lang == "auto" else SUPPORTED_LANGUAGES[args.source_lang]
    translator_label = "Auto choose" if args.translator_model == "auto" else args.translator_model
    print(f"Translating from {source_label} to {SUPPORTED_LANGUAGES[args.target_lang]}")
    print(f"Using Whisper {args.whisper_model} model")
    print(f"Using {args.translation_provider} translation provider ({translator_label})")

    rvc_model = None
    use_rvc = not args.no_rvc
    if use_rvc:
        if args.rvc_model:
            rvc_model = str(resolve_project_path(args.rvc_model))
        else:
            rvc_model = str(resolve_project_path(VOICE_OPTIONS["rvc"][args.voice_gender][args.target_lang]))
            if not os.path.exists(rvc_model):
                print(f"RVC model not found at {rvc_model}; falling back to Edge TTS")
                use_rvc = False

    if use_rvc:
        print(f"Using RVC with {args.voice_gender} voice")
    else:
        print(f"Using {args.tts_provider} TTS with {args.voice_gender} voice")
    print(f"Background mode: {args.background_mode}")

    run_pipeline(
        args.video_path,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        use_rvc=use_rvc,
        voice_gender=args.voice_gender,
        rvc_model=rvc_model,
        timing_vtt=str(resolve_project_path(args.timing_vtt)) if args.timing_vtt else None,
        whisper_model=args.whisper_model,
        translator_model=args.translator_model,
        translation_provider=args.translation_provider,
        tts_provider=args.tts_provider,
        background_mode=args.background_mode,
        use_gpu=args.use_gpu,
        force_dub=args.force_dub,
        force_transcribe=args.force_transcribe,
    )
