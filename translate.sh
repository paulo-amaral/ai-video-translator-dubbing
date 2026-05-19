#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [[ -t 1 ]]; then
  BOLD="$(tput bold 2>/dev/null || true)"
  DIM="$(tput dim 2>/dev/null || true)"
  RESET="$(tput sgr0 2>/dev/null || true)"
  RED="$(tput setaf 1 2>/dev/null || true)"
  GREEN="$(tput setaf 2 2>/dev/null || true)"
  YELLOW="$(tput setaf 3 2>/dev/null || true)"
  BLUE="$(tput setaf 4 2>/dev/null || true)"
  MAGENTA="$(tput setaf 5 2>/dev/null || true)"
  CYAN="$(tput setaf 6 2>/dev/null || true)"
else
  BOLD=""
  DIM=""
  RESET=""
  RED=""
  GREEN=""
  YELLOW=""
  BLUE=""
  MAGENTA=""
  CYAN=""
fi

die() {
  printf '%sError%s: %s\n' "$RED" "$RESET" "$*" >&2
  exit 1
}

warn() {
  printf '%sWarning%s: %s\n' "$YELLOW" "$RESET" "$*" >&2
}

load_env_file() {
  local env_file="$SCRIPT_DIR/.env"

  [[ -f "$env_file" ]] || return 0
  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
}

assistant_say() {
  printf '\n%sAssistant%s\n' "$CYAN$BOLD" "$RESET" >&2
  printf '  %s\n' "$*" >&2
}

assistant_note() {
  printf '  %s%s%s\n' "$DIM" "$*" "$RESET" >&2
}

user_prompt() {
  printf '\n%sYou%s ' "$MAGENTA$BOLD" "$RESET" >&2
}

section_title() {
  printf '\n%s%s%s\n' "$BOLD" "$*" "$RESET" >&2
  printf '%s\n' '----------------------------------------' >&2
}

show_header() {
  printf '%s' "$BOLD" >&2
  printf '\n' >&2
  printf '  Video Translator Chat\n' >&2
  printf '%s\n' '----------------------------------------' >&2
  printf '%s' "$RESET" >&2
  printf '  Guided flow for translation, dubbing, and subtitles.\n' >&2
}

show_option_list() {
  local options="$1"
  local option

  printf '  Options: ' >&2
  for option in $options; do
    printf '%s ' "$option" >&2
  done
  printf '\n' >&2
}

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
elif [[ -x "venv/bin/python" ]]; then
  PYTHON="venv/bin/python"
elif [[ -x "../.venv/bin/python" ]]; then
  PYTHON="../.venv/bin/python"
elif [[ -x "../venv/bin/python" ]]; then
  PYTHON="../venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  PYTHON="python"
fi

REQUIRED_MODULES=(
  whisper
  torch
  moviepy
  gtts
  edge_tts
  requests
  transformers
  mutagen
  sentencepiece
  numpy
  tqdm
)

LANGUAGES="auto en es fr de it pt ja ko zh"
TARGET_LANGUAGES="en es fr de it pt ja ko zh"
WHISPER_MODELS="auto tiny base small medium large"
TRANSLATOR_MODELS="auto m2m100_418M m2m100_1.2B nllb_200 nllb_600"
TRANSLATION_PROVIDERS="local openai gemini"
TTS_PROVIDERS="edge openai elevenlabs gemini"
BACKGROUND_MODES="original demucs none"
DEFAULT_BACKGROUND_MODE="original"
GEMINI_DEFAULT_TTS_MODEL="gemini-2.5-flash-preview-tts"
VTT_MODES="soft burn"
VIDEO_DIR="${VIDEO_TRANSLATOR_VIDEO_DIR:-$SCRIPT_DIR/../videos}"
if [[ -d "$VIDEO_DIR" ]]; then
  VIDEO_DIR="$(cd "$VIDEO_DIR" && pwd -P)"
fi
VTT_PATH=""
VTT_MODE="soft"
VTT_LANG="por"
TIMING_VTT_PATH=""
CLI_ARGS=()

contains_option() {
  local needle="$1"
  local options="$2"

  for option in $options; do
    if [[ "$option" == "$needle" ]]; then
      return 0
    fi
  done

  return 1
}

load_env_file

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

env_value_is_set() {
  local value="${1:-}"

  [[ -n "$value" ]] || return 1
  [[ "$value" != "your_key_here" ]] || return 1
  [[ "$value" != "your_voice_id_here" ]] || return 1
  [[ "$value" != "..." ]] || return 1
  return 0
}

env_file_contains_key() {
  local key="$1"
  local env_file="$SCRIPT_DIR/.env"

  [[ -f "$env_file" ]] || return 1
  grep -Eq "^[[:space:]]*(export[[:space:]]+)?${key}=" "$env_file"
}

missing_env_message() {
  local key="$1"
  local usage="$2"

  if env_file_contains_key "$key"; then
    die "$key is present in .env but empty or still a placeholder. Fill it before using $usage."
  fi

  die "$key is missing. Add it to .env or export it before using $usage."
}

get_arg_value() {
  local option="$1"
  local short_option="$2"
  local default="$3"
  shift 3

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      "$option")
        [[ "$#" -ge 2 ]] && printf '%s\n' "$2" && return 0
        ;;
      "$short_option")
        [[ -n "$short_option" && "$#" -ge 2 ]] && printf '%s\n' "$2" && return 0
        ;;
      "$option"=*)
        printf '%s\n' "${1#*=}"
        return 0
        ;;
    esac
    shift
  done

  printf '%s\n' "$default"
}

validate_tts_env() {
  local provider="$1"
  local gender="${2:-female}"
  local gender_voice_var
  local gender_upper

  case "$provider" in
    edge)
      return 0
      ;;
    openai)
      if ! env_value_is_set "${OPENAI_API_KEY:-}"; then
        missing_env_message "OPENAI_API_KEY" "--tts-provider openai"
      fi
      ;;
    elevenlabs)
      gender_upper="$(printf '%s' "$gender" | tr '[:lower:]' '[:upper:]')"
      gender_voice_var="ELEVENLABS_VOICE_ID_${gender_upper}"
      if ! env_value_is_set "${ELEVENLABS_API_KEY:-}"; then
        missing_env_message "ELEVENLABS_API_KEY" "--tts-provider elevenlabs"
      fi
      if ! env_value_is_set "${ELEVENLABS_VOICE_ID:-}" && ! env_value_is_set "${!gender_voice_var:-}"; then
        if env_file_contains_key "ELEVENLABS_VOICE_ID" || env_file_contains_key "$gender_voice_var"; then
          die "ELEVENLABS_VOICE_ID or $gender_voice_var is present in .env but empty or still a placeholder. Fill a voice ID before using --tts-provider elevenlabs."
        fi
        die "ELEVENLABS_VOICE_ID or $gender_voice_var is missing. Add a voice ID to .env."
      fi
      ;;
    gemini)
      if ! env_value_is_set "${GEMINI_API_KEY:-}"; then
        missing_env_message "GEMINI_API_KEY" "--tts-provider gemini"
      fi
      if ! env_value_is_set "${GEMINI_TTS_MODEL:-}"; then
        export GEMINI_TTS_MODEL="$GEMINI_DEFAULT_TTS_MODEL"
      elif [[ "${GEMINI_TTS_MODEL}" == "gemini-3-flash-preview-tts" ]]; then
        warn "GEMINI_TTS_MODEL=gemini-3-flash-preview-tts is not available on the Gemini TTS endpoint."
        warn "Using $GEMINI_DEFAULT_TTS_MODEL instead."
        export GEMINI_TTS_MODEL="$GEMINI_DEFAULT_TTS_MODEL"
      fi
      ;;
    *)
      die "Unsupported TTS provider: $provider"
      ;;
  esac
}

validate_translation_env() {
  local provider="$1"

  case "$provider" in
    local)
      return 0
      ;;
    openai)
      if ! env_value_is_set "${OPENAI_API_KEY:-}"; then
        missing_env_message "OPENAI_API_KEY" "--translation-provider openai"
      fi
      ;;
    gemini)
      if ! env_value_is_set "${GEMINI_API_KEY:-}"; then
        missing_env_message "GEMINI_API_KEY" "--translation-provider gemini"
      fi
      ;;
    *)
      die "Unsupported translation provider: $provider"
      ;;
  esac
}

validate_background_mode() {
  local mode="$1"

  if [[ "$mode" == "demucs" ]] && ! command_exists demucs; then
    warn "Demucs is not installed. Install with: $PYTHON -m pip install -r requirements-demucs.txt"
    warn "The Python pipeline will fall back to original background audio if Demucs is unavailable."
  fi
}

has_cli_flag() {
  local flag="$1"
  shift

  for arg in "$@"; do
    [[ "$arg" == "$flag" ]] && return 0
  done

  return 1
}

default_background_mode() {
  if command_exists demucs; then
    printf 'demucs\n'
  else
    printf '%s\n' "$DEFAULT_BACKGROUND_MODE"
  fi
}

maybe_install_demucs_prompt() {
  local mode="$1"
  local interactive="${2:-yes}"

  [[ "$mode" == "demucs" ]] || return 0
  command_exists demucs && return 0

  assistant_say "Demucs is not installed. Demucs gives cleaner background music by reducing the original vocals."
  assistant_note "Install command: $PYTHON -m pip install -r requirements-demucs.txt"
  if [[ "$interactive" != "yes" ]]; then
    return 0
  fi

  if prompt_yes_no "Install Demucs now" "n"; then
    "$PYTHON" -m pip install -r requirements-demucs.txt
    if ! command_exists demucs; then
      warn "Demucs command was not found after install. The pipeline may still fall back to original background audio."
    fi
  fi
}

estimate_elevenlabs_usage() {
  local video_arg="$1"
  local timing_vtt="${2:-}"

  "$PYTHON" - "$video_arg" "$timing_vtt" <<'PY'
import sys
from pathlib import Path

from video_translator.config import PROJECT_DIR
from video_translator.subtitles import load_vtt_segments
from video_translator.utils import sanitize_filename

video = Path(sys.argv[1]).expanduser()
timing_vtt = sys.argv[2]
texts = []

try:
    if timing_vtt:
        texts = [segment["text"] for segment in load_vtt_segments(timing_vtt)]
    else:
        output_dir = PROJECT_DIR / "output" / sanitize_filename(video.stem)
        translated = output_dir / "translated.txt"
        transcript = output_dir / "transcript.txt"
        source = translated if translated.exists() else transcript
        if source.exists():
            for line in source.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                if "] " in line:
                    line = line.split("] ", 1)[1]
                texts.append(line.strip())
except Exception:
    texts = []

characters = sum(len(text) for text in texts)
credits = characters / 2
if characters:
    print(f"{characters}|{credits:.0f}|known")
else:
    print("0|0|unknown")
PY
}

extract_timing_vtt_arg() {
  get_arg_value "--timing-vtt" "" "" "$@"
}

show_elevenlabs_credit_notice() {
  local video_arg="$1"
  local timing_vtt="${2:-}"
  local usage
  local characters
  local credits
  local status

  usage="$(estimate_elevenlabs_usage "$video_arg" "$timing_vtt")"
  IFS='|' read -r characters credits status <<< "$usage"

  if [[ "$status" == "known" ]]; then
    assistant_say "ElevenLabs estimate: about $characters text characters, or roughly $credits credits."
    assistant_note "ElevenLabs self-serve plans commonly count 1 text character as 0.5 credits."
  else
    assistant_say "ElevenLabs credit estimate is not available yet because no VTT/transcript/translation text was found."
    assistant_note "A practical rough estimate is 350-500 credits per spoken minute."
  fi
}

quality_preflight() {
  local provider="$1"
  local background="$2"
  local video_arg="$3"
  local timing_vtt="${4:-}"
  shift 4

  if [[ "$provider" == "elevenlabs" ]]; then
    show_elevenlabs_credit_notice "$video_arg" "$timing_vtt"
    if has_cli_flag "--force-dub" "$@" || has_cli_flag "--force-transcribe" "$@"; then
      warn "This run will regenerate speech and can consume ElevenLabs credits again."
    fi
  fi

  maybe_install_demucs_prompt "$background" "no"
}

is_help_request() {
  for arg in "$@"; do
    case "$arg" in
      -h|--help) return 0 ;;
    esac
  done

  return 1
}

first_video_arg() {
  local skip_next=0

  for arg in "$@"; do
    if [[ "$skip_next" -eq 1 ]]; then
      skip_next=0
      continue
    fi

    case "$arg" in
      -h|--help|--no-rvc|--force-dub|--force-transcribe|--use-gpu)
        ;;
      -s|-t|-g|-m|-w|-tr|--source-lang|--target-lang|--voice-gender|--rvc-model|--translation-provider|--tts-provider|--background-mode|--whisper-model|--translator-model|--timing-vtt|--vtt|--vtt-mode|--vtt-lang)
        skip_next=1
        ;;
      --source-lang=*|--target-lang=*|--voice-gender=*|--rvc-model=*|--translation-provider=*|--tts-provider=*|--background-mode=*|--whisper-model=*|--translator-model=*|--timing-vtt=*|--vtt=*|--vtt-mode=*|--vtt-lang=*)
        ;;
      -*)
        ;;
      *)
        printf '%s\n' "$arg"
        return 0
        ;;
    esac
  done

  return 1
}

check_cli_video_arg() {
  local video_arg
  local expanded_video_arg

  video_arg="$(first_video_arg "$@" || true)"
  if [[ -z "$video_arg" ]]; then
    return 0
  fi

  expanded_video_arg="${video_arg/#\~/$HOME}"
  if [[ ! -f "$expanded_video_arg" ]]; then
    die "Video not found: $expanded_video_arg"
  fi
}

parse_wrapper_options() {
  CLI_ARGS=()

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --vtt)
        [[ "$#" -ge 2 ]] || die "--vtt requires a .vtt path"
        VTT_PATH="$2"
        shift 2
        ;;
      --vtt=*)
        VTT_PATH="${1#*=}"
        shift
        ;;
      --vtt-mode)
        [[ "$#" -ge 2 ]] || die "--vtt-mode must be soft or burn"
        VTT_MODE="$2"
        shift 2
        ;;
      --vtt-mode=*)
        VTT_MODE="${1#*=}"
        shift
        ;;
      --vtt-lang)
        [[ "$#" -ge 2 ]] || die "--vtt-lang requires a language code, for example: por"
        VTT_LANG="$2"
        shift 2
        ;;
      --vtt-lang=*)
        VTT_LANG="${1#*=}"
        shift
        ;;
      *)
        CLI_ARGS+=("$1")
        shift
        ;;
    esac
  done
}

validate_vtt_options() {
  [[ -z "$VTT_PATH" ]] && return 0

  VTT_PATH="${VTT_PATH/#\~/$HOME}"
  [[ -f "$VTT_PATH" ]] || die "VTT file not found: $VTT_PATH"
  contains_option "$VTT_MODE" "$VTT_MODES" || die "Invalid --vtt-mode: $VTT_MODE. Use: $VTT_MODES"
  [[ -n "$VTT_LANG" ]] || die "--vtt-lang cannot be empty"
}

translated_output_for() {
  "$PYTHON" -c 'import sys; from pathlib import Path; from video_translator.config import PROJECT_DIR; from video_translator.utils import sanitize_filename; p = Path(sys.argv[1]).expanduser().resolve(); b = sanitize_filename(p.stem); print(PROJECT_DIR / "output" / b / f"{b}_dubbed.mp4")' "$1"
}

add_vtt_to_video() {
  local original_video="$1"
  local final_video
  local output_video

  [[ -z "$VTT_PATH" ]] && return 0

  final_video="$(translated_output_for "$original_video")"
  [[ -f "$final_video" ]] || die "Final video not found for VTT embedding: $final_video"

  case "$VTT_MODE" in
    soft)
      output_video="${final_video%.mp4}_${VTT_LANG}_subtitles.mp4"
      ffmpeg -y -i "$final_video" -i "$VTT_PATH" -c:v copy -c:a copy -c:s mov_text -metadata:s:s:0 "language=$VTT_LANG" "$output_video"
      ;;
    burn)
      output_video="${final_video%.mp4}_${VTT_LANG}_burned_subtitles.mp4"
      ffmpeg -y -i "$final_video" -vf "subtitles=$VTT_PATH" -c:a copy "$output_video"
      ;;
    *)
      die "Invalid VTT mode: $VTT_MODE"
      ;;
  esac

  printf 'Video with VTT created: %s\n' "$output_video"
}

check_python() {
  command_exists "$PYTHON" || die "Python was not found. Install Python 3.9+ or create a virtual environment."

  if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    die "This project requires Python 3.9 or newer. Current Python: $("$PYTHON" -V 2>&1)"
  fi
}

missing_python_modules() {
  "$PYTHON" -c 'import importlib.util, sys; missing = [m for m in sys.argv[1:] if importlib.util.find_spec(m) is None]; print(" ".join(missing)); raise SystemExit(1 if missing else 0)' "$@" || return 0
}

check_python_modules() {
  local missing

  missing="$(missing_python_modules "${REQUIRED_MODULES[@]}")"
  if [[ -n "$missing" ]]; then
    printf 'Missing Python dependencies: %s\n' "$missing" >&2
    printf 'Install them with:\n  %q -m pip install -r requirements.txt\n' "$PYTHON" >&2
    exit 1
  fi
}

check_ffmpeg() {
  if ! command_exists ffmpeg; then
    printf 'FFmpeg was not found in PATH.\n' >&2
    printf 'On macOS, install it with:\n  brew install ffmpeg\n' >&2
    exit 1
  fi
  if ! command_exists ffprobe; then
    printf 'ffprobe was not found in PATH.\n' >&2
    printf 'On macOS, install FFmpeg with:\n  brew install ffmpeg\n' >&2
    exit 1
  fi
}

preflight() {
  [[ -f "main.py" ]] || die "main.py was not found in $SCRIPT_DIR"
  [[ -f "requirements.txt" ]] || warn "requirements.txt was not found in $SCRIPT_DIR"

  check_python

  if ! is_help_request "$@"; then
    check_python_modules
    check_ffmpeg
  fi
}

prompt_required_file() {
  local label="${1:-Video path}"
  local answer

  while true; do
    user_prompt
    printf '%s: ' "$label" >&2
    if ! read -r answer; then
      die "Input canceled"
    fi

    answer="${answer/#\~/$HOME}"

    if [[ -f "$answer" ]]; then
      printf '%s\n' "$answer"
      return 0
    fi

    assistant_say "I could not find that file. Try again with the full path."
  done
}

collect_files_for_extensions() {
  local directory="$1"
  local extensions="$2"
  local find_args=()
  local extension

  [[ -d "$directory" ]] || return 0

  find_args+=("(")
  for extension in $extensions; do
    if [[ "${#find_args[@]}" -gt 1 ]]; then
      find_args+=("-o")
    fi
    find_args+=("-iname" "*.$extension")
  done
  find_args+=(")")

  find "$directory" -maxdepth 1 -type f "${find_args[@]}" -print | sort
}

prompt_file_from_directory() {
  local label="$1"
  local directory="$2"
  local extensions="$3"
  local answer
  local index
  local files=()
  local file
  local file_list

  if [[ -d "$directory" ]]; then
    file_list="$(mktemp)"
    collect_files_for_extensions "$directory" "$extensions" > "$file_list"
    while IFS= read -r file; do
      files+=("$file")
    done < "$file_list"
    rm -f "$file_list"
  fi

  if [[ "${#files[@]}" -gt 0 ]]; then
    assistant_say "I found ${#files[@]} file(s) in $directory."
    index=1
    for file in "${files[@]}"; do
      printf '  [%d] %s\n' "$index" "$(basename "$file")" >&2
      index=$((index + 1))
    done
    printf '  [m] Manual path\n' >&2

    while true; do
      user_prompt
      if [[ "${#files[@]}" -eq 1 ]]; then
        printf '%s [1]: ' "$label" >&2
      else
        printf '%s [1-%d or path]: ' "$label" "${#files[@]}" >&2
      fi
      if ! read -r answer; then
        die "Input canceled"
      fi

      answer="${answer:-1}"
      if [[ "$answer" == "m" || "$answer" == "M" ]]; then
        prompt_required_file "$label"
        return 0
      fi
      if [[ "$answer" =~ ^[0-9]+$ ]] && (( answer >= 1 && answer <= ${#files[@]} )); then
        printf '%s\n' "${files[$((answer - 1))]}"
        return 0
      fi

      answer="${answer/#\~/$HOME}"
      if [[ -f "$answer" ]]; then
        printf '%s\n' "$answer"
        return 0
      fi

      assistant_say "I could not match that choice to a file. Choose a number or enter a full path."
    done
  fi

  if [[ -d "$directory" ]]; then
    assistant_say "No matching files found in $directory. Enter the path manually."
  else
    assistant_say "Video directory not found: $directory. Enter the path manually."
  fi
  prompt_required_file "$label"
}

prompt_choice() {
  local label="$1"
  local default="$2"
  local options="$3"
  local answer

  while true; do
    assistant_note "$label"
    show_option_list "$options"
    user_prompt
    printf 'Choose [%s]: ' "$default" >&2
    if ! read -r answer; then
      die "Input canceled"
    fi

    answer="${answer:-$default}"

    if contains_option "$answer" "$options"; then
      printf '%s\n' "$answer"
      return 0
    fi

    assistant_say "Invalid option: $answer"
  done
}

prompt_yes_no() {
  local label="$1"
  local default="$2"
  local answer

  while true; do
    assistant_note "$label"
    user_prompt
    printf 'Answer y/n [%s]: ' "$default" >&2
    if ! read -r answer; then
      die "Input canceled"
    fi

    answer="${answer:-$default}"

    case "$answer" in
      y|Y|yes|YES) return 0 ;;
      n|N|no|NO) return 1 ;;
      *) assistant_say "Answer with y or n." ;;
    esac
  done
}

preflight "$@"

if [[ "$#" -gt 0 ]]; then
  parse_wrapper_options "$@"

  if is_help_request "${CLI_ARGS[@]}"; then
    "$PYTHON" main.py "${CLI_ARGS[@]}"
    printf '\nWrapper VTT options:\n'
    printf '  --vtt PATH          Incorporate a .vtt file into the final translated video\n'
    printf '  --vtt-mode MODE     soft for selectable subtitles, burn for always-visible subtitles (default: soft)\n'
    printf '  --vtt-lang CODE     Subtitle language metadata, example: por, eng, tet (default: por)\n'
    printf '\nDubbing timing option:\n'
    printf '  --timing-vtt PATH   Use a .vtt file as the transcript/timing source for smoother dubbing\n'
    exit 0
  fi

  validate_vtt_options
  check_cli_video_arg "${CLI_ARGS[@]}"
  tts_provider="$(get_arg_value "--tts-provider" "" "edge" "${CLI_ARGS[@]}")"
  translation_provider="$(get_arg_value "--translation-provider" "" "local" "${CLI_ARGS[@]}")"
  voice_gender="$(get_arg_value "--voice-gender" "-g" "female" "${CLI_ARGS[@]}")"
  background_mode="$(get_arg_value "--background-mode" "" "original" "${CLI_ARGS[@]}")"
  timing_vtt_arg="$(extract_timing_vtt_arg "${CLI_ARGS[@]}")"
  validate_translation_env "$translation_provider"
  validate_tts_env "$tts_provider" "$voice_gender"
  validate_background_mode "$background_mode"
  video_path="$(first_video_arg "${CLI_ARGS[@]}" || true)"
  quality_preflight "$tts_provider" "$background_mode" "$video_path" "$timing_vtt_arg" "${CLI_ARGS[@]}"
  "$PYTHON" main.py "${CLI_ARGS[@]}"
  add_vtt_to_video "$video_path"
  exit 0
fi

show_header
assistant_say "Let's configure your video translation as a short guided chat. I will auto-detect the source language and choose the translation model by default."
assistant_note "Available target languages: $TARGET_LANGUAGES"
assistant_note "Default media folder: $VIDEO_DIR"

video_path="$(prompt_file_from_directory "Video path" "$VIDEO_DIR" "mp4 m4v mov webm mkv")"
target_lang="$(prompt_choice "Target language" "pt" "$TARGET_LANGUAGES")"
voice_gender="$(prompt_choice "Voice gender" "female" "male female")"

source_lang="auto"
whisper_model="base"
translator_model="auto"
if prompt_yes_no "Advanced model/language options" "n"; then
  source_lang="$(prompt_choice "Source language" "auto" "$LANGUAGES")"
  whisper_model="$(prompt_choice "Whisper model" "base" "$WHISPER_MODELS")"
  translator_model="$(prompt_choice "Translator model" "auto" "$TRANSLATOR_MODELS")"
fi

if [[ "$whisper_model" == "auto" ]]; then
  whisper_model="base"
fi

cmd=(
  "$PYTHON" main.py "$video_path"
  --source-lang "$source_lang"
  --target-lang "$target_lang"
  --voice-gender "$voice_gender"
  --whisper-model "$whisper_model"
  --translator-model "$translator_model"
)

translation_provider="$(prompt_choice "Translation provider" "local" "$TRANSLATION_PROVIDERS")"
if [[ "$translation_provider" == "openai" ]]; then
  assistant_note "OpenAI translation is usually more natural for dubbing than local M2M100/NLLB, but it uses API credits."
fi
validate_translation_env "$translation_provider"
cmd+=(--translation-provider "$translation_provider")

tts_provider="$(prompt_choice "TTS provider" "edge" "$TTS_PROVIDERS")"
background_default="$(default_background_mode)"
assistant_note "Demucs is selected automatically when installed because it preserves background music more cleanly."
background_mode="$(prompt_choice "Background preservation" "$background_default" "$BACKGROUND_MODES")"
validate_tts_env "$tts_provider" "$voice_gender"
validate_background_mode "$background_mode"
cmd+=(--tts-provider "$tts_provider" --background-mode "$background_mode")
maybe_install_demucs_prompt "$background_mode" "yes"

if prompt_yes_no "Use GPU for Whisper" "n"; then
  cmd+=(--use-gpu)
fi

if prompt_yes_no "Regenerate existing dubbed audio/video" "n"; then
  cmd+=(--force-dub)
fi

if prompt_yes_no "Regenerate transcript and translation too" "n"; then
  cmd+=(--force-transcribe)
fi

if prompt_yes_no "Use RVC voice conversion" "n"; then
  assistant_note "Provide an RVC model path if you want a custom voice. You can leave it empty."
  user_prompt
  printf 'RVC model path (optional): ' >&2
  if ! read -r rvc_model; then
    die "Input canceled"
  fi

  if [[ -n "$rvc_model" ]]; then
    rvc_model="${rvc_model/#\~/$HOME}"
    if [[ ! -e "$rvc_model" ]]; then
      die "RVC model not found: $rvc_model"
    fi
    cmd+=(--rvc-model "$rvc_model")
  fi
else
  cmd+=(--no-rvc)
fi

if prompt_yes_no "Incorporate VTT subtitles after translation" "n"; then
  VTT_PATH="$(prompt_file_from_directory "VTT file path" "$VIDEO_DIR" "vtt")"
  VTT_MODE="$(prompt_choice "VTT mode" "soft" "$VTT_MODES")"
  assistant_note "Subtitle metadata language code. Examples: por, eng, tet."
  user_prompt
  printf 'VTT language code [por]: ' >&2
  if ! read -r VTT_LANG; then
    die "Input canceled"
  fi
  VTT_LANG="${VTT_LANG:-por}"
  validate_vtt_options

  if prompt_yes_no "Use this VTT as the dubbing timing source" "y"; then
    TIMING_VTT_PATH="$VTT_PATH"
    cmd+=(--timing-vtt "$TIMING_VTT_PATH" --force-transcribe)
  fi
fi

if [[ "$tts_provider" == "elevenlabs" ]]; then
  show_elevenlabs_credit_notice "$video_path" "$TIMING_VTT_PATH"
  if [[ " ${cmd[*]} " == *" --force-dub "* || " ${cmd[*]} " == *" --force-transcribe "* ]]; then
    warn "This run will regenerate speech and can consume ElevenLabs credits again."
  fi
fi

section_title "Summary"
printf '  Video: %s\n' "$video_path" >&2
printf '  Target: %s\n' "$target_lang" >&2
printf '  Voice: %s\n' "$voice_gender" >&2
printf '  Whisper: %s\n' "$whisper_model" >&2
printf '  Translator: %s\n' "$translator_model" >&2
printf '  Translation provider: %s\n' "$translation_provider" >&2
printf '  TTS provider: %s\n' "$tts_provider" >&2
printf '  Background: %s\n' "$background_mode" >&2
if [[ -n "$VTT_PATH" ]]; then
  printf '  VTT: %s (%s, %s)\n' "$VTT_PATH" "$VTT_MODE" "$VTT_LANG" >&2
fi
if [[ -n "$TIMING_VTT_PATH" ]]; then
  printf '  Dubbing timing VTT: %s\n' "$TIMING_VTT_PATH" >&2
fi

printf '\n%sCommand%s\n  ' "$BOLD" "$RESET" >&2
printf '%q ' "${cmd[@]}" >&2
if [[ -n "$VTT_PATH" ]]; then
  printf -- '--vtt %q --vtt-mode %q --vtt-lang %q ' "$VTT_PATH" "$VTT_MODE" "$VTT_LANG" >&2
fi
printf '\n' >&2

if prompt_yes_no "Run now" "y"; then
  assistant_say "Great. Starting the translation now."
  "${cmd[@]}"
  add_vtt_to_video "$video_path"
  exit 0
fi

assistant_say "Canceled. The command above is ready to run manually when you want."
