# Contributing

Thank you for considering a contribution to Video Translator.

This is an individual project owned by Paulo Amaral, but issues, suggestions, and focused pull requests are welcome.

## Ground Rules

- Keep changes focused and easy to review.
- Do not commit `.env`, API keys, videos, generated media, model files, or private subtitles.
- Prefer small pull requests with a clear explanation of the problem and the solution.
- Follow the existing code style and avoid unrelated refactors.
- Keep user-facing shell and CLI text in English.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Optional dependencies:

```bash
python -m pip install -r requirements-demucs.txt
python -m pip install -r requirements-rvc.txt
```

## Validation

Run these checks before opening a pull request:

```bash
bash -n translate.sh
python -m py_compile main.py video_translator/*.py
git status --short --ignored
```

The ignored section should contain local-only files such as `.env`, `models/`, and `output/`.

## Security Checklist

Before committing:

```bash
git diff --cached --name-only
git diff --cached | grep -Ei 'api[_-]?key|secret|token|password|AIza|sk-'
```

If the grep command finds real credentials, stop, remove them, rotate the leaked key, and recommit only safe placeholders.

## Pull Request Description

Please include:

- What changed
- Why it changed
- How it was tested
- Any provider-specific notes, such as Gemini, OpenAI, ElevenLabs, Demucs, or FFmpeg behavior
