# Contributing to Video Translator

Thank you for helping build a practical AI video translation and dubbing toolkit for creators, educators, and teams working with multilingual video.

This is an individual project owned by Paulo Amaral, but issues, suggestions, and focused pull requests are welcome.

## How to Contribute

### Report a Bug

Open an issue using the Bug Report template.

Please include:

- The command you ran, with secrets removed
- Your macOS and Python version
- The provider involved, such as Gemini, OpenAI, ElevenLabs, Edge TTS, Demucs, FFmpeg, or WebVTT
- The relevant error message or log excerpt
- What you expected to happen

Do not include API keys, `.env` files, private videos, private subtitles, or full generated transcripts.

### Suggest a Feature

Open an issue using the Feature Request template.

Please describe:

- The workflow problem
- The proposed behavior
- Which part of the project it affects
- Any provider, cost, privacy, or quality tradeoffs

Good feature requests are concrete. For example: "Add a setting to increase background music volume during non-speech gaps" is easier to evaluate than "make audio better."

### Ask a Security Question

Use the Security Guidance issue template only for non-sensitive questions.

Do not disclose vulnerabilities, leaked keys, or private media in a public issue. Follow `SECURITY.md` for private security reports.

### Submit a Pull Request

1. Fork this repository.
2. Create a branch:

```bash
git checkout -b fix/short-description
```

or:

```bash
git checkout -b add/short-feature-name
```

3. Make a focused change.
4. Run the validation checks below.
5. Open a pull request using the PR template.

In the pull request, include a short description of what changed, why it belongs in the project, and how you tested it.

## Contribution Criteria

Contributions are easiest to merge when they:

- Improve translation, transcription, TTS, subtitles, timing, audio mixing, setup, or security
- Keep the command-line and shell interface clear for macOS users
- Preserve privacy by default
- Do not add unnecessary dependencies
- Avoid provider lock-in unless the feature is explicitly provider-specific
- Keep generated media, models, credentials, and local outputs out of Git
- Include documentation when behavior changes

## Ground Rules

- Keep changes focused and easy to review.
- Do not commit `.env`, API keys, videos, generated media, model files, or private subtitles.
- Prefer small pull requests with a clear explanation of the problem and the solution.
- Follow the existing code style and avoid unrelated refactors.
- Keep user-facing shell and CLI text in English.
- Respect provider terms for Gemini, OpenAI, ElevenLabs, Edge TTS, Demucs, FFmpeg, and any other tools used.

## Local Setup

Install FFmpeg first. On macOS, use either Homebrew:

```bash
brew install python ffmpeg
```

or MacPorts:

```bash
sudo port selfupdate
sudo port install python312 ffmpeg
```

Then set up Python:

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

Copy the safe environment template when you need API providers:

```bash
cp .env.example .env
```

Fill only the providers you plan to test. Never commit `.env`.

## Validation

Run these checks before opening a pull request:

```bash
bash -n translate.sh
python -m py_compile main.py video_translator/*.py
git status --short --ignored
```

The ignored section should contain local-only files such as `.env`, `models/`, and `output/`.

For documentation-only changes, shell/Python compilation is still recommended because examples often touch commands or paths.

## Security Checklist

Before committing:

```bash
git diff --cached --name-only
git diff --cached | grep -Ei 'api[_-]?key|secret|token|password|AIza|sk-'
```

If the grep command finds real credentials, stop, remove them, rotate the leaked key, and recommit only safe placeholders.

Also check:

- [ ] `.env` is not staged
- [ ] `output/` is not staged
- [ ] `models/` is not staged
- [ ] source videos are not staged
- [ ] `.vtt` or `.srt` subtitle files are not staged unless they are synthetic public test fixtures
- [ ] no private path, private email thread, or paid provider account detail appears in logs

## Pull Request Description

Please include:

- What changed
- Why it changed
- How it was tested
- Any provider-specific notes, such as Gemini, OpenAI, ElevenLabs, Demucs, or FFmpeg behavior

## Maintainer Review

A maintainer may ask for:

- smaller scope
- clearer documentation
- safer handling of credentials or private media
- tests or manual verification steps
- a different default when a change affects cost, privacy, or output quality

That review is about keeping the tool useful and safe for people processing real videos.
