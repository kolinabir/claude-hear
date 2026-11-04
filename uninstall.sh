#!/usr/bin/env bash
# Remove the "hear" skill from Claude Code.
#   ./uninstall.sh           remove the skill link only (keeps models and code)
#   ./uninstall.sh --purge   also delete the downloaded models (~3–4 GB)
set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/hear"
rm -f "$SKILL_DIR/SKILL.md" "$SKILL_DIR/hear.py"
rmdir "$SKILL_DIR" 2>/dev/null || true
echo "✓ Skill removed from $SKILL_DIR"

if [[ "${1:-}" == "--purge" ]]; then
  rm -rf "$HOME/.cache/hear"
  # the HF cache shares blob files between models, so let its own tool decide what is safe to delete
  uvx --from huggingface_hub hf cache rm -y --dry-run=false \
    model/mlx-community/whisper-large-v3-turbo model/mobiuslabsgmbh/faster-whisper-large-v3-turbo \
    model/laion/clap-htsat-unfused model/Xenova/clap-htsat-unfused \
    model/Voldorn/emotion2vec-plus-large-onnx 2>/dev/null || true
  echo "✓ Models deleted. Python packages stay in uv's cache; free them with: uv cache prune"
fi
