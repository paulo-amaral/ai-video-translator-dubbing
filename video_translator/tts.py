import asyncio
import base64
import os
import re
import requests
import shutil
import tempfile
import wave
from pathlib import Path

from .config import (
    AUDIO_FADE_DURATION,
    AUDIO_MAX_SPEED,
    AUDIO_TARGET_TOLERANCE,
    EDGE_TTS_MAX_RATE,
    EDGE_TTS_VOICES,
    GEMINI_TTS_MODEL,
    GEMINI_TTS_VOICES,
    OPENAI_TTS_MODEL,
    OPENAI_TTS_VOICES,
    VOICE_OPTIONS,
)
from .utils import add_leading_silence, get_audio_duration, run_ffmpeg


class RVCConverter:
    def __init__(self, model_path, device="cuda"):
        import torch

        self.device = device if torch.cuda.is_available() else "cpu"
        self.model_path = model_path
        self.model = self.load_rvc_model(model_path)

    def load_rvc_model(self, model_path):
        try:
            from fairseq import checkpoint_utils

            model_dir = os.path.dirname(model_path)
            pth_files = [file for file in os.listdir(model_dir) if file.endswith(".pth")]
            if not pth_files:
                raise FileNotFoundError(f"RVC model files not found in {model_dir}")

            pth_path = os.path.join(model_dir, pth_files[0])
            models, _cfg, _task = checkpoint_utils.load_model_ensemble_and_task([pth_path])
            model = models[0].to(self.device)
            model.eval()
            print(f"Loaded RVC model from {model_dir}")
            return model
        except Exception as exc:
            print(f"Error loading RVC model: {exc}")
            return None

    def convert_voice(self, audio_path, output_path):
        try:
            if self.model is None:
                return False

            import torch
            import torchaudio

            audio, sample_rate = torchaudio.load(audio_path)
            audio = audio.to(self.device)
            with torch.no_grad():
                if audio.dim() == 1:
                    audio = audio.unsqueeze(0)
                converted_audio = self.model(audio)
                if converted_audio.dim() == 1:
                    converted_audio = converted_audio.unsqueeze(0)
                torchaudio.save(output_path, converted_audio.cpu(), sample_rate)
            return True
        except Exception as exc:
            print(f"RVC conversion error: {exc}")
            return False


async def _save_edge_tts(text, output_path, lang, voice_gender, rate_percent=0):
    import edge_tts

    voice = EDGE_TTS_VOICES.get(lang, {}).get(voice_gender, f"{lang}-{voice_gender.upper()}-Neural")
    rate = f"{rate_percent:+d}%"
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


def _prepare_spoken_text(text):
    text = " ".join(text.replace("\n", " ").split())
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,.!?;:])(?=\S)", r"\1 ", text)
    text = text.replace("...", ".")
    if text and text[-1] not in ".!?":
        text = f"{text}."
    return text


def _edge_rate_for_duration(actual_duration, target_duration):
    if target_duration <= 0 or actual_duration <= target_duration + AUDIO_TARGET_TOLERANCE:
        return 0

    requested_speed = actual_duration / target_duration
    rate_percent = round((min(requested_speed, AUDIO_MAX_SPEED) - 1.0) * 100)
    return min(max(rate_percent, 0), EDGE_TTS_MAX_RATE)


def _save_openai_tts(text, output_path, voice_gender):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    voice = os.environ.get("OPENAI_TTS_VOICE") or OPENAI_TTS_VOICES[voice_gender]
    response = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": os.environ.get("OPENAI_TTS_MODEL", OPENAI_TTS_MODEL),
            "voice": voice,
            "input": text,
            "instructions": os.environ.get(
                "OPENAI_TTS_INSTRUCTIONS",
                (
                    "Speak as a natural professional video dub. Use warm, human pacing, "
                    "subtle emotion, clear articulation, and natural pauses. Avoid sounding "
                    "like a dry narrator."
                ),
            ),
            "response_format": "mp3",
        },
        timeout=120,
    )
    response.raise_for_status()
    with open(output_path, "wb") as file:
        file.write(response.content)


def _save_elevenlabs_tts(text, output_path, voice_gender):
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")

    voice_id = (
        os.environ.get(f"ELEVENLABS_VOICE_ID_{voice_gender.upper()}")
        or os.environ.get("ELEVENLABS_VOICE_ID")
    )
    if not voice_id:
        raise RuntimeError("ELEVENLABS_VOICE_ID is not set")

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
            "voice_settings": {
                "stability": float(os.environ.get("ELEVENLABS_STABILITY", "0.45")),
                "similarity_boost": float(os.environ.get("ELEVENLABS_SIMILARITY_BOOST", "0.8")),
                "style": float(os.environ.get("ELEVENLABS_STYLE", "0.15")),
                "use_speaker_boost": True,
            },
        },
        timeout=120,
    )
    response.raise_for_status()
    with open(output_path, "wb") as file:
        file.write(response.content)


def _gemini_voice_name(voice_gender):
    gender_key = f"GEMINI_TTS_VOICE_{voice_gender.upper()}"
    return (
        os.environ.get(gender_key)
        or os.environ.get("GEMINI_TTS_VOICE")
        or GEMINI_TTS_VOICES[voice_gender]
    )


def _save_gemini_tts(text, output_path, voice_gender):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model = os.environ.get("GEMINI_TTS_MODEL", GEMINI_TTS_MODEL)
    voice_name = _gemini_voice_name(voice_gender)
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                os.environ.get(
                                    "GEMINI_TTS_STYLE_PROMPT",
                                    (
                                        "Read this as natural professional video dubbing. "
                                        "Use warm conversational pacing, subtle emotional nuance, "
                                        "clear articulation, and natural pauses. Avoid a dry narrator tone."
                                    ),
                                )
                                + " "
                                f"{text}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name,
                        }
                    }
                },
            },
        },
        timeout=120,
    )
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        if response.status_code == 404:
            raise RuntimeError(
                f"Gemini TTS model not found: {model}. "
                "Use GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts or check the current "
                "TTS model name in Google AI Studio."
            ) from exc
        raise
    response_data = response.json()

    inline_audio = None
    mime_type = ""
    for candidate in response_data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline_data = part.get("inlineData") or part.get("inline_data")
            if inline_data and inline_data.get("data"):
                inline_audio = inline_data["data"]
                mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or ""
                break
        if inline_audio:
            break
    if not inline_audio:
        raise RuntimeError("Gemini TTS response did not include audio data.")

    audio_bytes = base64.b64decode(inline_audio)
    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav_path = temp_wav.name
    temp_wav.close()

    try:
        if "wav" in mime_type.lower():
            with open(temp_wav_path, "wb") as file:
                file.write(audio_bytes)
        else:
            with wave.open(temp_wav_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(24000)
                wav_file.writeframes(audio_bytes)

        run_ffmpeg(
            ["ffmpeg", "-y", "-i", temp_wav_path, output_path],
            "converting Gemini TTS audio",
        )
    finally:
        Path(temp_wav_path).unlink(missing_ok=True)


def _save_edge_or_gtts(spoken_text, output_path, lang, use_rvc, voice_gender, rvc_model, target_duration):
    try:
        asyncio.run(_save_edge_tts(spoken_text, output_path, lang, voice_gender))
        if target_duration:
            actual_duration = get_audio_duration(output_path)
            rate_percent = _edge_rate_for_duration(actual_duration, target_duration)
            if rate_percent > 0:
                asyncio.run(_save_edge_tts(spoken_text, output_path, lang, voice_gender, rate_percent))
                print(f"Generated audio with Edge TTS using {voice_gender} voice at {rate_percent:+d}% rate")
                return True

        print(f"Generated audio with Edge TTS using {voice_gender} voice")
        return True
    except ImportError:
        print("Edge TTS not installed, falling back to gTTS")
    except Exception as exc:
        print(f"Edge TTS failed: {exc}, falling back to gTTS")

    from gtts import gTTS

    tts = gTTS(spoken_text, lang=VOICE_OPTIONS["gtts"][lang][voice_gender], slow=False)
    temp_path = output_path + ".temp.mp3"
    tts.save(temp_path)

    if use_rvc and rvc_model:
        converter = RVCConverter(rvc_model)
        success = converter.convert_voice(temp_path, output_path)
        if not success:
            print("RVC conversion failed, using original TTS audio")
            shutil.copy(temp_path, output_path)
        os.remove(temp_path)
    else:
        shutil.move(temp_path, output_path)
    return True


def generate_tts_audio(text, output_path, lang="pt", use_rvc=True, voice_gender="female", rvc_model=None, target_duration=None, tts_provider="edge"):
    spoken_text = _prepare_spoken_text(text)
    try:
        if tts_provider == "openai":
            _save_openai_tts(spoken_text, output_path, voice_gender)
            print(f"Generated audio with OpenAI TTS using {voice_gender} voice")
            return True
        if tts_provider == "elevenlabs":
            _save_elevenlabs_tts(spoken_text, output_path, voice_gender)
            print(f"Generated audio with ElevenLabs using {voice_gender} voice")
            return True
        if tts_provider == "gemini":
            _save_gemini_tts(spoken_text, output_path, voice_gender)
            print(f"Generated audio with Gemini TTS using {voice_gender} voice")
            return True
        return _save_edge_or_gtts(spoken_text, output_path, lang, use_rvc, voice_gender, rvc_model, target_duration)
    except Exception as exc:
        if tts_provider in {"openai", "elevenlabs", "gemini"}:
            print(f"{tts_provider} TTS failed: {exc}. Falling back to Edge TTS/gTTS.")
            return _save_edge_or_gtts(spoken_text, output_path, lang, use_rvc, voice_gender, rvc_model, target_duration)
        print(f'TTS error for "{text[:30]}...": {exc}')
        return False


def fit_speech_audio(input_path, output_path, target_duration, max_speed=AUDIO_MAX_SPEED):
    actual_duration = get_audio_duration(input_path)
    if target_duration <= 0:
        raise ValueError(f"Invalid target duration: {target_duration}")

    if actual_duration > target_duration + AUDIO_TARGET_TOLERANCE:
        requested_speed = actual_duration / target_duration
        speed = min(requested_speed, max_speed)
        if requested_speed > max_speed:
            print(
                f"Audio longer than segment ({actual_duration:.2f}s > {target_duration:.2f}s); "
                f"limiting speed to {speed:.2f}x to avoid rushed speech."
            )
        run_ffmpeg(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-filter:a", f"atempo={speed:.3f}",
                str(output_path),
            ],
            "adjusting TTS segment speed",
        )
    elif actual_duration < target_duration - AUDIO_TARGET_TOLERANCE:
        silence_duration = target_duration - actual_duration
        fade_duration = min(AUDIO_FADE_DURATION, max(0.0, actual_duration / 4))
        fade_out_start = max(0.0, actual_duration - fade_duration)
        run_ffmpeg(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-af",
                (
                    f"afade=t=in:st=0:d={fade_duration:.3f},"
                    f"afade=t=out:st={fade_out_start:.3f}:d={fade_duration:.3f},"
                    f"apad=pad_dur={silence_duration:.3f}"
                ),
                str(output_path),
            ],
            "padding TTS segment",
        )
    else:
        shutil.copy(input_path, output_path)

    return get_audio_duration(output_path)


def soften_audio_edges(input_path, output_path):
    duration = get_audio_duration(input_path)
    fade_duration = min(AUDIO_FADE_DURATION, max(0.0, duration / 4))
    if fade_duration <= 0.005:
        shutil.copy(input_path, output_path)
        return duration

    fade_out_start = max(0.0, duration - fade_duration)
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", f"afade=t=in:st=0:d={fade_duration:.3f},afade=t=out:st={fade_out_start:.3f}:d={fade_duration:.3f}",
            str(output_path),
        ],
        "softening TTS segment edges",
    )
    return get_audio_duration(output_path)


def generate_tts_with_timing(texts, output_dir, base_name, segments, target_lang="pt", use_rvc=True, voice_gender="female", rvc_model=None, tts_provider="edge"):
    audio_files = []
    timeline_position = 0.0

    for index, (translated_text, segment) in enumerate(zip(texts, segments)):
        idx = f"{index:04d}"
        raw_path = output_dir / f"{base_name}_{idx}_raw.mp3"
        final_path = output_dir / f"{base_name}_{idx}.mp3"
        temp_fit_file = tempfile.NamedTemporaryFile(suffix=".mp3", dir=output_dir, delete=False)
        fit_path = Path(temp_fit_file.name)
        temp_fit_file.close()
        temp_soft_file = tempfile.NamedTemporaryFile(suffix=".mp3", dir=output_dir, delete=False)
        soft_path = Path(temp_soft_file.name)
        temp_soft_file.close()

        segment_start = float(segment["start"])
        segment_end = float(segment["end"])
        segment_duration = segment_end - segment_start
        leading_silence = max(0.0, segment_start - timeline_position)

        print(f"Segment {index}: target speech duration {segment_duration:.2f}s")
        if not generate_tts_audio(translated_text, str(raw_path), target_lang, use_rvc, voice_gender, rvc_model, segment_duration, tts_provider):
            raise RuntimeError(f"Failed to generate TTS for segment {index}")

        fitted_duration = fit_speech_audio(raw_path, fit_path, segment_duration)
        fitted_duration = soften_audio_edges(fit_path, soft_path)
        fit_path.unlink(missing_ok=True)
        add_leading_silence(soft_path, final_path, leading_silence)
        final_duration = get_audio_duration(final_path)
        timeline_position += final_duration

        print(
            f"Segment {index}: final {final_duration:.2f}s "
            f"(speech {fitted_duration:.2f}s, leading silence {leading_silence:.2f}s)"
        )
        audio_files.append(str(final_path))

    return audio_files
