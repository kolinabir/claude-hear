#!/usr/bin/env bash
# Install the "hear" skill for Claude Code on macOS or Linux (Windows: install.ps1).
#   ./install.sh           link the skill (installs ffmpeg and uv if missing)
#   ./install.sh --warm    also download all models now (~2.5 GB) by listening to a test clip
# Run it from a clone, or via curl: it then clones to ~/.claude-hear (override with CLAUDE_HEAR_DIR).
set -euo pipefail

REPO_URL="https://github.com/kolinabir/claude-hear.git"
SKILL_DIR="$HOME/.claude/skills/hear"
WARM=0
for arg in "$@"; do
  case "$arg" in
    --warm) WARM=1 ;;
    -h|--help) sed -n 2,5p "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

say_step() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

say_step "Checking this computer"
os="$(uname -s)"; arch="$(uname -m)"
case "$os" in
  Darwin)
    if [[ "$arch" == "arm64" ]]; then
      major="$(sw_vers -productVersion | cut -d. -f1)"
      (( major >= 14 )) || die "On Apple Silicon, hear needs macOS 14 or newer (you have $(sw_vers -productVersion))."
      echo "Apple Silicon, macOS $(sw_vers -productVersion): Whisper runs on the GPU (MLX)"
    else
      echo "Intel Mac: Whisper runs on the CPU (faster-whisper), slower than Apple Silicon"
    fi ;;
  Linux)
    if command -v nvidia-smi >/dev/null; then echo "Linux with an NVIDIA GPU: Whisper runs on CUDA when its libraries are installed"
    else echo "Linux: Whisper runs on the CPU (faster-whisper)"; fi ;;
  *) die "Unsupported system: $os. On Windows, run install.ps1 in PowerShell." ;;
esac

say_step "Checking ffmpeg and uv"
if ! command -v ffmpeg >/dev/null; then
  if command -v brew >/dev/null; then brew install ffmpeg
  elif command -v apt-get >/dev/null; then sudo apt-get install -y ffmpeg
  elif command -v dnf >/dev/null; then sudo dnf install -y ffmpeg
  elif command -v pacman >/dev/null; then sudo pacman -S --noconfirm ffmpeg
  else die "ffmpeg is missing. Install it with your package manager, then rerun."
  fi
fi
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "ffmpeg: $(command -v ffmpeg)"
echo "uv:     $(command -v uv)"

say_step "Getting the code"
here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [[ -n "$here" && -f "$here/skills/hear/hear.py" ]]; then
  SRC="$here"
  echo "Using this clone: $SRC"
else
  SRC="${CLAUDE_HEAR_DIR:-$HOME/.claude-hear}"
  if [[ -d "$SRC/.git" ]]; then
    git -C "$SRC" pull --ff-only
  else
    git clone --depth 1 "$REPO_URL" "$SRC"
  fi
  echo "Code in: $SRC"
fi

say_step "Linking the skill into Claude Code"
mkdir -p "$SKILL_DIR"
for f in SKILL.md hear.py; do
  target="$SKILL_DIR/$f"
  if [[ -e "$target" && ! -L "$target" ]]; then
    mv "$target" "$target.bak"
    echo "Backed up your old $f to $f.bak"
  fi
  ln -sfn "$SRC/skills/hear/$f" "$target"
done
chmod +x "$SRC/skills/hear/hear.py"
echo "$SKILL_DIR → $SRC/skill"

if (( WARM )); then
  say_step "Downloading models (~2.5 GB, a few minutes, once)"
  tmp="$(mktemp -d)"
  ffmpeg -v error -f lavfi -i "sine=frequency=220:duration=3" "$tmp/tone.wav"  # any audio triggers every download
  uv run --script "$SRC/skills/hear/hear.py" "$tmp/tone.wav" --out "$tmp/out"
  rm -rf "$tmp"
fi

printf '\n\033[32m✓ Installed.\033[0m Open Claude Code and ask: "listen to ~/Downloads/clip.mp4"\n'
(( WARM )) || echo "  The first listen downloads ~2.5 GB of models. Run \"$SRC/install.sh\" --warm to do it now."
