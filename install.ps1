# Install the "hear" skill for Claude Code on Windows.
#   .\install.ps1          copy the skill (installs ffmpeg and uv if missing)
#   .\install.ps1 -Warm    also download all models now (~3 GB) by listening to a test tone
# Run it from a clone, or via irm | iex: it then clones to ~\.claude-hear (override with $env:CLAUDE_HEAR_DIR).
# Run it again to update.
param([switch]$Warm)
$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/kolinabir/claude-hear.git"
$SkillDir = Join-Path $HOME ".claude\skills\hear"

function Step($text) { Write-Host "`n> $text" -ForegroundColor Cyan }
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [Environment]::GetEnvironmentVariable("Path", "User") + ";$HOME\.local\bin"
}

Step "Checking this PC"
if (Have "nvidia-smi") { Write-Host "NVIDIA GPU found: Whisper uses CUDA when its libraries are installed, else the CPU" }
else { Write-Host "No NVIDIA GPU: Whisper runs on the CPU (about 1-2x the clip length)" }

Step "Checking ffmpeg, git and uv"
if (-not (Have "ffmpeg")) {
  if (-not (Have "winget")) { throw "ffmpeg is missing and winget isn't available. Install ffmpeg, add it to PATH, then rerun." }
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  Refresh-Path
}
if (-not (Have "git")) {
  winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
  Refresh-Path
}
if (-not (Have "uv")) {
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  Refresh-Path
}
foreach ($c in "ffmpeg", "git", "uv") {
  if (-not (Have $c)) { throw "$c was installed but isn't on PATH yet. Open a new PowerShell window and rerun." }
  Write-Host ("{0,-7} {1}" -f "${c}:", (Get-Command $c).Source)
}

Step "Getting the code"
$here = if ($PSScriptRoot) { $PSScriptRoot } else { "" }
if ($here -and (Test-Path (Join-Path $here "skill\hear.py"))) {
  $Src = $here
  Write-Host "Using this clone: $Src"
} else {
  $Src = if ($env:CLAUDE_HEAR_DIR) { $env:CLAUDE_HEAR_DIR } else { Join-Path $HOME ".claude-hear" }
  if (Test-Path (Join-Path $Src ".git")) { git -C $Src pull --ff-only }
  else { git clone --depth 1 $RepoUrl $Src }
  Write-Host "Code in: $Src"
}

Step "Copying the skill into Claude Code"
# copied, not linked: Windows symlinks need admin or Developer Mode
if (Test-Path $SkillDir) { Remove-Item $SkillDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Split-Path $SkillDir) | Out-Null
Copy-Item (Join-Path $Src "skill") $SkillDir -Recurse
Get-ChildItem $SkillDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Write-Host "$SkillDir (rerun this script after pulling updates)"

if ($Warm) {
  Step "Downloading models (~3 GB, a few minutes, once)"
  $tmp = Join-Path ([IO.Path]::GetTempPath()) ("hear-" + [guid]::NewGuid())
  New-Item -ItemType Directory $tmp | Out-Null
  ffmpeg -v error -f lavfi -i "sine=frequency=220:duration=3" (Join-Path $tmp "tone.wav")
  uv run --script (Join-Path $SkillDir "hear.py") (Join-Path $tmp "tone.wav") --out (Join-Path $tmp "out")
  Remove-Item $tmp -Recurse -Force
}

Write-Host "`nInstalled. Open Claude Code and ask: `"listen to C:\Users\you\Downloads\clip.mp4`"" -ForegroundColor Green
if (-not $Warm) { Write-Host "  The first listen downloads ~3 GB of models. Run install.ps1 -Warm to do it now." }
