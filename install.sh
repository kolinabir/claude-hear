#!/usr/bin/env bash
# Install the "hear" skill for Claude Code.
#   ./install.sh           link the skill (installs ffmpeg and uv if missing)
#   ./install.sh --warm    also download all models now (~3 GB) by listening to a test clip
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

say_step "Checking this Mac"
[[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]] || die "hear needs an Apple Silicon Mac (it runs Whisper on MLX)."
major="$(sw_vers -productVersion | cut -d. -f1)"
(( major >= 14 )) || die "hear needs macOS 14 or newer (you have $(sw_vers -productVersion))."
echo "Apple Silicon, macOS $(sw_vers -productVersion)"

say_step "Checking ffmpeg and uv"
if ! command -v ffmpeg >/dev/null; then
  command -v brew >/dev/null || die "ffmpeg is missing. Install Homebrew (https://brew.sh) or ffmpeg, then rerun."
  brew install ffmpeg
fi
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "ffmpeg: $(command -v ffmpeg)"
echo "uv:     $(command -v uv)"

say_step "Getting the code"
here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [[ -n "$here" && -f "$here/skill/hear.py" ]]; then
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
  ln -sfn "$SRC/skill/$f" "$target"
done
chmod +x "$SRC/skill/hear.py"
echo "$SKILL_DIR → $SRC/skill"

if (( WARM )); then
  say_step "Downloading models (~3 GB, a few minutes, once)"
  tmp="$(mktemp -d)"
  say -o "$tmp/hello.aiff" "Hello. This is a test, so the hear skill can download its models."
  uv run --script "$SRC/skill/hear.py" "$tmp/hello.aiff" --out "$tmp/out"
  rm -rf "$tmp"
fi

printf '\n\033[32m✓ Installed.\033[0m Open Claude Code and ask: "listen to ~/Downloads/clip.mp4"\n'
(( WARM )) || echo "  The first listen downloads ~3 GB of models. Run \"$SRC/install.sh\" --warm to do it now."
