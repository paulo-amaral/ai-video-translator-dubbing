import json
import os

import requests

from .config import (
    GEMINI_TRANSLATION_MODEL,
    LANGUAGE_CODES,
    MODEL_CONFIG,
    MODELS_DIR,
    OPENAI_TRANSLATION_MODEL,
    SUPPORTED_LANGUAGES,
)


def choose_translator_model(source_lang, target_lang):
    complex_scripts = {"ja", "ko", "zh"}
    if source_lang in complex_scripts or target_lang in complex_scripts:
        return "nllb_200"
    return "m2m100_418M"


def _write_translations(output_path, translations):
    with open(output_path, "w", encoding="utf-8") as file:
        for line in translations:
            file.write(line + "\n")


def _extract_openai_text(response_data):
    if response_data.get("output_text"):
        return response_data["output_text"]

    output_parts = []
    for item in response_data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                output_parts.append(content["text"])
    return "\n".join(output_parts).strip()


def _extract_gemini_text(response_data):
    output_parts = []
    for candidate in response_data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if part.get("text"):
                output_parts.append(part["text"])
    return "\n".join(output_parts).strip()


def _translation_prompt(texts, source_lang, target_lang):
    return {
        "source_language": SUPPORTED_LANGUAGES[source_lang],
        "target_language": SUPPORTED_LANGUAGES[target_lang],
        "style": "natural spoken dubbing translation",
        "rules": [
            "Return only a valid JSON array of strings.",
            "Return exactly one translated string for each input string, in the same order.",
            "Keep the translation natural for spoken voice-over/dubbing.",
            "Adapt idioms and sentence rhythm so the result sounds spoken, not written.",
            "Keep each translated segment concise enough to fit the source timing.",
            "When translating to Portuguese, prefer natural Brazilian Portuguese.",
            "Preserve meaning, names, numbers, and terminology.",
            "Avoid explanations, markdown, numbering, or extra text.",
        ],
        "segments": texts,
    }


def _translate_text_openai(texts, output_path, source_lang, target_lang):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    source_name = SUPPORTED_LANGUAGES[source_lang]
    target_name = SUPPORTED_LANGUAGES[target_lang]
    model = os.environ.get("OPENAI_TRANSLATION_MODEL", OPENAI_TRANSLATION_MODEL)
    translations = []
    batch_size = 20

    print(f"Using OpenAI translation model: {model}")
    for index in range(0, len(texts), batch_size):
        batch_texts = texts[index:index + batch_size]
        prompt = _translation_prompt(batch_texts, source_lang, target_lang)
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "instructions": (
                    "You are a professional audiovisual translator. "
                    "Translate for natural dubbing, not literal subtitles."
                ),
                "input": json.dumps(prompt, ensure_ascii=False),
            },
            timeout=180,
        )
        response.raise_for_status()
        output_text = _extract_openai_text(response.json())
        translated_batch = json.loads(output_text)
        if not isinstance(translated_batch, list) or len(translated_batch) != len(batch_texts):
            raise RuntimeError("OpenAI translation returned an unexpected segment count.")

        for original, translated_text in zip(batch_texts, translated_batch):
            print(f"Original ({source_name}): {original[:50]}...")
            print(f"Translated ({target_name}): {translated_text[:50]}...")
            translations.append(str(translated_text))

    _write_translations(output_path, translations)
    print(f"Translated {len(translations)} segments with OpenAI")
    return translations


def _translate_text_gemini(texts, output_path, source_lang, target_lang):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    source_name = SUPPORTED_LANGUAGES[source_lang]
    target_name = SUPPORTED_LANGUAGES[target_lang]
    model = os.environ.get("GEMINI_TRANSLATION_MODEL", GEMINI_TRANSLATION_MODEL)
    translations = []
    batch_size = 20

    print(f"Using Gemini translation model: {model}")
    for index in range(0, len(texts), batch_size):
        batch_texts = texts[index:index + batch_size]
        prompt = _translation_prompt(batch_texts, source_lang, target_lang)
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
                                    "You are a professional audiovisual translator. "
                                    "Translate for natural dubbing, not literal subtitles.\n\n"
                                    f"{json.dumps(prompt, ensure_ascii=False)}"
                                )
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
            timeout=180,
        )
        response.raise_for_status()
        output_text = _extract_gemini_text(response.json())
        translated_batch = json.loads(output_text)
        if not isinstance(translated_batch, list) or len(translated_batch) != len(batch_texts):
            raise RuntimeError("Gemini translation returned an unexpected segment count.")

        for original, translated_text in zip(batch_texts, translated_batch):
            print(f"Original ({source_name}): {original[:50]}...")
            print(f"Translated ({target_name}): {translated_text[:50]}...")
            translations.append(str(translated_text))

    _write_translations(output_path, translations)
    print(f"Translated {len(translations)} segments with Gemini")
    return translations


def _translate_text_local(texts, output_path, source_lang="en", target_lang="pt", model_name="auto"):
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        from huggingface_hub import snapshot_download
        import torch
    except ImportError as exc:
        raise ImportError("Required packages not found. Install them: pip install -r requirements.txt") from exc

    if model_name == "auto":
        model_name = choose_translator_model(source_lang, target_lang)

    print(f"Loading translation model: {model_name}...")
    model_config = MODEL_CONFIG["translator"][model_name]
    model_family = "nllb" if model_name.startswith("nllb") else "m2m100"

    cache_dir = str(MODELS_DIR)
    os.makedirs(cache_dir, exist_ok=True)
    snapshot_download(
        repo_id=model_config["name"],
        cache_dir=cache_dir,
        local_files_only=False,
        resume_download=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_config["name"], cache_dir=cache_dir)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_config["name"], cache_dir=cache_dir)

    if torch.cuda.is_available():
        model = model.cuda()
        print("Using GPU for translation")

    translations = []
    batch_size = 4
    for index in range(0, len(texts), batch_size):
        batch_texts = texts[index:index + batch_size]
        try:
            tokenizer.src_lang = LANGUAGE_CODES[model_family][source_lang]
            if model_family == "m2m100":
                tokenizer.tgt_lang = LANGUAGE_CODES[model_family][target_lang]

            encoded = tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
            if torch.cuda.is_available():
                encoded = {key: value.cuda() for key, value in encoded.items()}

            target_code = LANGUAGE_CODES[model_family][target_lang]
            forced_bos_token_id = (
                tokenizer.get_lang_id(target_code)
                if model_family == "m2m100"
                else tokenizer.convert_tokens_to_ids(target_code)
            )
            generated_tokens = model.generate(
                **encoded,
                forced_bos_token_id=forced_bos_token_id,
                max_length=512,
                num_beams=5,
                length_penalty=0.8,
                no_repeat_ngram_size=3,
                early_stopping=True,
            )
            translated = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)

            for original, translated_text in zip(batch_texts, translated):
                print(f"Original ({SUPPORTED_LANGUAGES[source_lang]}): {original[:50]}...")
                print(f"Translated ({SUPPORTED_LANGUAGES[target_lang]}): {translated_text[:50]}...")
                translations.append(translated_text)
        except Exception as exc:
            print(f"Translation error for batch {index // batch_size}: {exc}")
            translations.extend(batch_texts)

    _write_translations(output_path, translations)
    print(f"Translated {len(translations)} segments")
    return translations


def translate_text(texts, output_path, source_lang="en", target_lang="pt", model_name="auto", translation_provider="local"):
    if source_lang == target_lang:
        print(f"Source and target language are both {target_lang}; using text without translation.")
        _write_translations(output_path, texts)
        return texts

    if translation_provider == "openai":
        try:
            return _translate_text_openai(texts, output_path, source_lang, target_lang)
        except Exception as exc:
            print(f"OpenAI translation failed: {exc}. Falling back to local translation.")
    if translation_provider == "gemini":
        try:
            return _translate_text_gemini(texts, output_path, source_lang, target_lang)
        except Exception as exc:
            print(f"Gemini translation failed: {exc}. Falling back to local translation.")

    return _translate_text_local(texts, output_path, source_lang, target_lang, model_name)
