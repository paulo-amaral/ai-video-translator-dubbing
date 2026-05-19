# Video Translator

Owner: Paulo Amaral

Video Translator is an AI video translation and dubbing toolkit for creators, educators, and teams that need multilingual video workflows on macOS. It transcribes speech with Whisper, translates subtitles and transcripts with local models or API providers, generates natural dubbed speech with local/free and cloud TTS providers, preserves background audio, and assembles final MP4 videos with FFmpeg.

## Features

- Automatic speech transcription with Whisper
- Automatic or manual source-language selection
- Translation to English, Spanish, French, German, Italian, Portuguese, Japanese, Korean, or Chinese
- Local translation with M2M100/NLLB or API translation with OpenAI/Gemini
- Dubbed audio generation with Edge TTS, gTTS fallback, OpenAI, ElevenLabs, or Gemini
- Background audio preservation with optional Demucs vocal separation
- Optional RVC voice conversion
- Optional WebVTT subtitle embedding
- Resume-friendly output files for transcript, translation, audio chunks, and final video
- macOS-friendly terminal helper with guided chat mode

## Project Layout

```text
videoTranslator/
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       └── ci.yml
├── main.py
├── translate.sh
├── requirements.txt
├── requirements-demucs.txt
├── requirements-rvc.txt
├── .env.example
├── CHANGELOG.md
├── COMMITS.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── SECURITY.md
├── video_translator/
│   ├── cli.py
│   ├── config.py
│   ├── media.py
│   ├── pipeline.py
│   ├── transcription.py
│   ├── translation.py
│   ├── tts.py
│   └── utils.py
├── models/       # downloaded model files, ignored by Git
└── output/       # generated videos and intermediate files, ignored by Git
```

## Requirements

- macOS 13 or newer recommended
- Python 3.9 or newer
- FFmpeg
- Internet access for first-time model downloads, translation models, and online TTS
- Apple Silicon or Intel Mac both work; GPU acceleration is only used when supported by the installed PyTorch backend

## macOS Setup

Install Homebrew if you do not already have it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install Python and FFmpeg:

```bash
brew install python ffmpeg
```

If you use MacPorts instead of Homebrew:

```bash
sudo port selfupdate
sudo port install python312 ffmpeg
```

If your shell does not find MacPorts Python automatically, use:

```bash
/opt/local/bin/python3.12 -m venv .venv
```

Clone the repository and create a virtual environment from the `videoTranslator` folder:

```bash
git clone https://github.com/paulo-amaral/ai-video-translator-dubbing.git
cd ai-video-translator-dubbing
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Optional RVC support:

```bash
python -m pip install -r requirements-rvc.txt
```

Optional Demucs background separation:

```bash
python -m pip install -r requirements-demucs.txt
```

Verify the setup:

```bash
./translate.sh --help
ffmpeg -version
```

## Source Code

The source code is organized as a small Python package under `video_translator/`:

- `cli.py`: command-line arguments and execution entry point
- `pipeline.py`: end-to-end orchestration
- `transcription.py`: Whisper and VTT transcript handling
- `translation.py`: local, OpenAI, and Gemini translation providers
- `tts.py`: Edge, gTTS, OpenAI, ElevenLabs, Gemini, timing, and voice chunking
- `media.py`: FFmpeg assembly, background preservation, and final audio mix
- `subtitles.py`: WebVTT parsing helpers
- `utils.py`: shared FFmpeg and filesystem utilities

The shell interface lives in `translate.sh`. It handles guided setup, `.env` loading, video discovery, provider validation, Demucs setup checks, and VTT embedding.

For traceability, `COMMITS.md` maps public commit hashes to short hash tags and descriptions.

## Environment Variables

API-based providers read credentials from `.env` automatically.

Create your local file:

```bash
cp .env.example .env
```

Edit `.env` and fill the provider you want to use:

```bash
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here

OPENAI_API_KEY=your_key_here
OPENAI_TTS_VOICE=nova
OPENAI_TRANSLATION_MODEL=gpt-5-mini

GEMINI_API_KEY=your_key_here
GEMINI_TRANSLATION_MODEL=gemini-2.5-flash
GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts
GEMINI_TTS_VOICE=Kore

BACKGROUND_AUDIO_VOLUME=0.28
DUB_AMBIENCE_DECAY=0.045
```

The `.env` file is ignored by Git. Keep `.env.example` committed as the safe template.

When you select `--tts-provider openai`, `--tts-provider elevenlabs`, `--tts-provider gemini`, `--translation-provider openai`, or `--translation-provider gemini`, `translate.sh` validates the required environment variables before starting the pipeline. If a key or voice ID is missing, it stops early with a setup message instead of silently falling back to another voice.

## Security

- Never commit `.env`, API keys, source videos, generated outputs, model weights, or private subtitles.
- Rotate any API key immediately if it is pasted into an issue, commit, chat log, or terminal recording.
- Review `git status --short --ignored` before publishing. Only source files, docs, requirements, and safe examples should be tracked.
- The project uses GitHub Actions with read-only repository permissions and Dependabot updates for GitHub Actions and Python dependencies.
- See `SECURITY.md` for vulnerability reporting and secret-handling guidance.

## Usage

Guided chat mode:

```bash
./translate.sh
```

In guided chat mode, the script automatically scans a sibling `videos/` folder when it exists. It lists available video files and lets you choose by number. To use another default folder:

```bash
VIDEO_TRANSLATOR_VIDEO_DIR="/path/to/videos" ./translate.sh
```

Direct mode:

```bash
./translate.sh "path/to/video.mp4" --source-lang auto --target-lang pt --voice-gender female --no-rvc
```

Use a more natural cloud TTS provider:

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --tts-provider openai --force-dub
```

Use OpenAI for more natural dubbing-style translation while keeping any TTS provider:

```bash
./translate.sh "path/to/video.mp4" --source-lang en --target-lang pt --translation-provider openai --tts-provider edge --force-transcribe
```

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --tts-provider elevenlabs --force-dub
```

Use Demucs to remove/reduce the original vocal and keep cleaner background music:

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --background-mode demucs --force-dub
```

In guided chat mode, `translate.sh` automatically selects `demucs` as the default background mode when the `demucs` command is installed. If it is not installed and you choose `demucs`, the script offers to install `requirements-demucs.txt`.

Regenerate dubbed audio and the final video while keeping the existing transcript and translation:

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --force-dub
```

Regenerate everything, including the transcript segmentation and translation:

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --force-transcribe
```

Use a WebVTT file as the timing and transcript source for smoother dubbing:

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --timing-vtt "path/to/subtitles.vtt" --force-transcribe
```

Use a stronger Whisper model:

```bash
./translate.sh "path/to/video.mp4" --target-lang de --whisper-model medium --no-rvc
```

Use the Python entry point directly:

```bash
python main.py "path/to/video.mp4" --source-lang auto --target-lang pt --no-rvc
```

## WebVTT Subtitles

There are two VTT-related options:

- `--timing-vtt`: uses VTT cues to guide the dubbing timing and transcript text
- `--vtt`: embeds or burns subtitles into the final MP4

Embed a `.vtt` subtitle track that can be enabled or disabled by the video player:

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --vtt "path/to/subtitles.vtt" --vtt-mode soft --vtt-lang por
```

Use the same VTT for smoother dubbing and final subtitles:

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --timing-vtt "path/to/subtitles.vtt" --vtt "path/to/subtitles.vtt" --vtt-mode soft --vtt-lang por --force-transcribe
```

Burn subtitles into the video image:

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --vtt "path/to/subtitles.vtt" --vtt-mode burn --vtt-lang por
```

VTT modes:

- `soft`: creates a selectable subtitle track in the final MP4
- `burn`: renders subtitles permanently into the video

## Output

Each input video gets its own output folder:

```text
output/
└── video_name/
    ├── tts-chunks/
    ├── transcript.txt
    ├── translated.txt
    ├── audio_dubbed.mp3
    ├── video_name_dubbed.mp4
    └── video_name_dubbed_por_subtitles.mp4
```

The pipeline resumes automatically:

- Existing `transcript.txt` skips transcription
- Existing `translated.txt` skips translation
- Existing TTS chunks skip speech generation
- Existing final video skips video assembly

Use `--force-dub` when you change voice, timing, subtitle, or dubbing behavior and want fresh dubbed audio/video.

Use `--force-transcribe` when you want the improved transcript segmentation to be applied to a video that already has an `output/video_name/transcript.txt` file.

If your VTT is already in the target language and you leave `--source-lang auto`, the tool treats the VTT text as target-language text and skips translation. If the VTT is in the original/source language, pass the source language explicitly, for example `--source-lang en --target-lang pt`.

The final MP4 keeps a low-volume copy of the original audio underneath the dubbed voice so background music and room tone are not lost. The default background level is configured in `video_translator/config.py` as `BACKGROUND_AUDIO_VOLUME`.

For a more natural mix, the final audio also applies a light room ambience to the dubbed voice and ducks the preserved background underneath speech. You can tune that from `.env`:

```bash
BACKGROUND_AUDIO_VOLUME=0.28
DUB_VOICE_VOLUME=1.0
DUB_AMBIENCE_DECAY=0.045
```

If the dub still feels dry, raise `DUB_AMBIENCE_DECAY` slightly, for example `0.06`. If the original music is too quiet, raise `BACKGROUND_AUDIO_VOLUME`, for example `0.34`.

Background modes:

- `original`: mixes a low-volume copy of the original audio under the dub
- `demucs`: separates vocals from the original audio and mixes the no-vocals stem under the dub
- `none`: uses only the dubbed audio

TTS providers:

- `edge`: default, free, uses Edge TTS with gTTS fallback
- `openai`: uses the OpenAI Audio Speech API; requires `OPENAI_API_KEY`
- `elevenlabs`: uses ElevenLabs text-to-speech; requires `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID`
- `gemini`: uses Gemini native TTS; requires `GEMINI_API_KEY`

Translation providers:

- `local`: default, uses M2M100/NLLB models
- `openai`: uses `OPENAI_TRANSLATION_MODEL` for more natural spoken translation; requires `OPENAI_API_KEY`
- `gemini`: uses `GEMINI_TRANSLATION_MODEL` for natural spoken translation; requires `GEMINI_API_KEY`

ElevenLabs credit guidance:

- ElevenLabs self-serve plans commonly count 1 text character as 0.5 credits.
- `translate.sh` estimates credits before running ElevenLabs when it can read text from `--timing-vtt`, `translated.txt`, or `transcript.txt`.
- `--force-dub` and `--force-transcribe` regenerate speech and can consume credits again.
- Test with a short clip first when tuning voices or timing.

## Supported Languages

| Code | Language |
| --- | --- |
| `en` | English |
| `es` | Spanish |
| `fr` | French |
| `de` | German |
| `it` | Italian |
| `pt` | Portuguese |
| `ja` | Japanese |
| `ko` | Korean |
| `zh` | Chinese |

## Whisper Models

| Model | Speed | Quality | Typical RAM |
| --- | --- | --- | --- |
| `tiny` | Fastest | Basic | ~1 GB |
| `base` | Fast | Good | ~1 GB |
| `small` | Medium | Better | ~2 GB |
| `medium` | Slow | High | ~5 GB |
| `large` | Slowest | Best | ~10 GB |

The default model is `base`. Use `small` or `medium` when transcription quality matters more than speed.

## RVC Voice Conversion

RVC is optional. If you do not have RVC models, run with:

```bash
./translate.sh "path/to/video.mp4" --no-rvc
```

If you do have a model, pass it directly:

```bash
./translate.sh "path/to/video.mp4" --rvc-model "models/rvc/female/pt/model.pth"
```

## Troubleshooting

Missing Python dependency:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

FFmpeg not found:

```bash
brew install ffmpeg
```

Whisper install issue:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Dubbing does not sound fluid:

```bash
./translate.sh "path/to/video.mp4" --translation-provider gemini --tts-provider gemini --background-mode demucs --no-rvc --force-transcribe
```

Transcript timing or sentence breaks still feel abrupt:

```bash
./translate.sh "path/to/video.mp4" --no-rvc --force-transcribe
```

Use a VTT timing source when available:

```bash
./translate.sh "path/to/video.mp4" --target-lang pt --no-rvc --timing-vtt "path/to/subtitles.vtt" --force-transcribe
```

Translation or model download fails:

- Confirm internet access
- Re-run the command
- Delete only the affected file in `output/video_name/` if you want that step regenerated

## Notes

- Generated videos, model weights, caches, and local virtual environments are intentionally ignored by Git.
- Keep source videos outside the repository or in a separate ignored folder when they are large.
- The terminal helper prefers `.venv/`, then `venv/`, then parent-folder environments for compatibility with existing local setups.

## Publishing Safety

Before publishing to GitHub:

```bash
git status --short
git check-ignore -v .env output/ models/
```

Only commit `.env.example`, never `.env`. Generated media in `output/`, source videos, downloaded models, virtual environments, and caches should remain untracked.
