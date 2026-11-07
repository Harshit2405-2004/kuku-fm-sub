# Installs the Claude Code plugins/skills this project uses (see docs/SKILLS_AND_TOOLS.md).
# Run from the REPO ROOT (the folder that has CLAUDE.md), in PowerShell:
#   powershell -ExecutionPolicy Bypass -File setup\install_claude_plugins.ps1          # recommended set
#   powershell -ExecutionPolicy Bypass -File setup\install_claude_plugins.ps1 -All     # + optional plugins
# Plugins are installed at PROJECT scope -> recorded in .claude\settings.json (commit it).
param([switch]$All)

$Scope = "project"

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "ERROR: 'claude' not found. Install Claude Code first:  irm https://claude.ai/install.ps1 | iex"
  exit 1
}
if (-not (Test-Path "CLAUDE.md")) {
  Write-Host "ERROR: run this from the repo root (the folder containing CLAUDE.md)."
  exit 1
}

Write-Host "Claude Code version: $(claude --version)"
Write-Host "`n== 1/3 Adding marketplaces =="
claude plugin marketplace add anthropics/claude-plugins-official
if ($LASTEXITCODE -ne 0) { Write-Host "   (already added or failed - continuing)" }
claude plugin marketplace add anthropics/skills
if ($LASTEXITCODE -ne 0) { Write-Host "   (already added or failed - continuing)" }

$Core = @(
  "superpowers@claude-plugins-official",      # planning, TDD, debugging, verification, review workflow
  "code-review@claude-plugins-official",      # multi-agent review of a diff
  "example-skills@anthropic-agent-skills",    # includes webapp-testing
  "document-skills@anthropic-agent-skills"    # includes pdf
)
$Optional = @(
  "claude-md-management@claude-plugins-official",
  "context7@claude-plugins-official"
)
$Plugins = $Core
if ($All) { $Plugins += $Optional }

Write-Host "`n== 2/3 Installing plugins (scope: $Scope) =="
$Failed = @()
foreach ($p in $Plugins) {
  Write-Host "-> $p"
  claude plugin install $p --scope $Scope
  if ($LASTEXITCODE -ne 0) { $Failed += $p }
}

Write-Host "`n== 3/3 Installed plugins =="
claude plugin list

if ($Failed.Count -gt 0) {
  Write-Host "`nSome installs failed: $($Failed -join ', ')"
  Write-Host "Fix: open Claude Code, run /plugin, go to Discover, search the name and install it there."
} else {
  Write-Host "`nAll done. Start (or restart) Claude Code in this folder, or run /reload-plugins in an open session."
}
Write-Host "Check inside Claude Code: type '/' and look for superpowers:* skills; run /agents to see independent-reviewer and brief-auditor."