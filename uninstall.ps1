# Remove the "hear" skill from Claude Code on Windows.
#   .\uninstall.ps1          remove the skill only (keeps models and code)
#   .\uninstall.ps1 -Purge   also delete the downloaded models (~3-4 GB)
param([switch]$Purge)
$ErrorActionPreference = "Stop"

$SkillDir = Join-Path $HOME ".claude\skills\hear"
if (Test-Path $SkillDir) { Remove-Item $SkillDir -Recurse -Force }
Write-Host "Skill removed from $SkillDir"

if ($Purge) {
  $cache = Join-Path $HOME ".cache\hear"
  if (Test-Path $cache) { Remove-Item $cache -Recurse -Force }
  # the HF cache shares blob files between models, so let its own tool decide what is safe to delete
  uvx --from huggingface_hub hf cache rm -y --dry-run=false `
    model/mobiuslabsgmbh/faster-whisper-large-v3-turbo model/laion/clap-htsat-unfused model/Xenova/clap-htsat-unfused `
    model/Voldorn/emotion2vec-plus-large-onnx 2>$null
  Write-Host "Models deleted. Python packages stay in uv's cache; free them with: uv cache prune"
}
