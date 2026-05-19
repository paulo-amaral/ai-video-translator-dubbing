from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_DIR / "models"
MIN_PYTHON = (3, 9)

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
}

LANGUAGE_CODES = {
    "whisper": {
        "en": "en",
        "es": "es",
        "fr": "fr",
        "de": "de",
        "it": "it",
        "pt": "pt",
        "ja": "ja",
        "ko": "ko",
        "zh": "zh",
    },
    "m2m100": {
        "en": "en",
        "es": "es",
        "fr": "fr",
        "de": "de",
        "it": "it",
        "pt": "pt",
        "ja": "ja",
        "ko": "ko",
        "zh": "zh",
    },
    "nllb": {
        "en": "eng_Latn",
        "es": "spa_Latn",
        "fr": "fra_Latn",
        "de": "deu_Latn",
        "it": "ita_Latn",
        "pt": "por_Latn",
        "ja": "jpn_Jpan",
        "ko": "kor_Hang",
        "zh": "zho_Hans",
    },
    "gtts": {
        "en": "en",
        "es": "es",
        "fr": "fr",
        "de": "de",
        "it": "it",
        "pt": "pt",
        "ja": "ja",
        "ko": "ko",
        "zh": "zh",
    },
}

VOICE_OPTIONS = {
    "gtts": {lang: {"male": lang, "female": lang} for lang in SUPPORTED_LANGUAGES},
    "rvc": {
        gender: {
            lang: f"models/rvc/{gender}/{lang}"
            for lang in SUPPORTED_LANGUAGES
        }
        for gender in ("male", "female")
    },
}

EDGE_TTS_VOICES = {
    "en": {"male": "en-US-GuyNeural", "female": "en-US-JennyNeural"},
    "es": {"male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural"},
    "fr": {"male": "fr-FR-HenriNeural", "female": "fr-FR-DeniseNeural"},
    "de": {"male": "de-DE-ConradNeural", "female": "de-DE-KatjaNeural"},
    "it": {"male": "it-IT-DiegoNeural", "female": "it-IT-ElsaNeural"},
    "pt": {"male": "pt-BR-AntonioNeural", "female": "pt-BR-FranciscaNeural"},
    "ja": {"male": "ja-JP-NanjoNeural", "female": "ja-JP-AiriNeural"},
    "ko": {"male": "ko-KR-InJoonNeural", "female": "ko-KR-SunHiNeural"},
    "zh": {"male": "zh-CN-YunxiNeural", "female": "zh-CN-XiaoxiaoNeural"},
}

OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_TRANSLATION_MODEL = "gpt-5-mini"
OPENAI_TTS_VOICES = {
    "male": "onyx",
    "female": "nova",
}

GEMINI_TRANSLATION_MODEL = "gemini-2.5-flash"
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
GEMINI_TTS_VOICES = {
    "male": "Puck",
    "female": "Kore",
}

TTS_PROVIDERS = {"edge", "openai", "elevenlabs", "gemini"}
TRANSLATION_PROVIDERS = {"local", "openai", "gemini"}
BACKGROUND_MODES = {"original", "demucs", "none"}

MODEL_CONFIG = {
    "whisper": {
        "tiny": {"size": "75M", "quality": "low", "speed": "fast", "cpu_ram": "1GB"},
        "base": {"size": "142M", "quality": "medium", "speed": "medium", "cpu_ram": "1GB"},
        "small": {"size": "466M", "quality": "good", "speed": "medium", "cpu_ram": "2GB"},
        "medium": {"size": "1.5B", "quality": "high", "speed": "slow", "cpu_ram": "5GB"},
        "large": {"size": "2.9B", "quality": "best", "speed": "very slow", "cpu_ram": "10GB"},
    },
    "translator": {
        "m2m100_418M": {"name": "facebook/m2m100_418M", "quality": "medium", "speed": "fast"},
        "m2m100_1.2B": {"name": "facebook/m2m100_1.2B", "quality": "high", "speed": "medium"},
        "nllb_200": {"name": "facebook/nllb-200-distilled-600M", "quality": "good", "speed": "fast"},
        "nllb_600": {"name": "facebook/nllb-200-1.3B", "quality": "best", "speed": "slow"},
    },
}

AUDIO_MAX_SPEED = 1.25
AUDIO_TARGET_TOLERANCE = 0.05
AUDIO_FADE_DURATION = 0.14
EDGE_TTS_MAX_RATE = 25
BACKGROUND_AUDIO_VOLUME = 0.28
DUB_VOICE_VOLUME = 1.0
DUB_AMBIENCE_DECAY = 0.045
TRANSCRIPT_MIN_SEGMENT_DURATION = 1.4
TRANSCRIPT_MAX_SEGMENT_DURATION = 7.0
TRANSCRIPT_MAX_SEGMENT_CHARS = 150
TRANSCRIPT_MERGE_GAP = 0.45
