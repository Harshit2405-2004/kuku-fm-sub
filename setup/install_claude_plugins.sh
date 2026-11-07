#!/usr/bin/env bash
# Installs the Claude Code plugins/skills this project uses (see docs/SKILLS_AND_TOOLS.md).
# Run from the REPO ROOT (the folder that has CLAUDE.md):
#   bash setup/install_claude_plugins.sh          # recommended set
#   bash setup/install_claude_plugins.sh --all    # + optional plugins (claude-md-management, context7)
# Plugins are installed at PROJECT scope -> recorded in .claude/settings.json (commit it: it shows Kuku your setup).
# Safe to re-run: already-added marketplaces / installed plugins are just reported.

set -u
SCOPE="project"
WANT_ALL="${1:-}"

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: 'claude' not found. Install Claude Code first:  curl -fsSL https://claude.ai/install.sh | bash"
  exit 1
fi
if [ ! -f "CLAUDE.md" ]; then
  echo "ERROR: run this from the repo root (the folder containing CLAUDE.md)."
  exit 1
fi

echo "Claude Code version: $(claude --version)"
echo
echo "== 1/3 Adding marketplaces =="
claude plugin marketplace add anthropics/claude-plugins-official || echo "   (already added or failed - continuing)"
claude plugin marketplace add anthropics/skills || echo "   (already added or failed - continuing)"

CORE=(
  "superpowers@claude-plugins-official"        # planning, TDD, debugging, verification, code review workflow
  "code-review@claude-plugins-official"        # multi-agent review of a diff
  "example-skills@anthropic-agent-skills"      # includes webapp-testing (Playwright check of the Streamlit app)
  "document-skills@anthropic-agent-skills"     # includes pdf (final 2-page doc)
)
OPTIONAL=(
  "claude-md-management@claude-plugins-official"  # keeps CLAUDE.md tidy
  "context7@claude-plugins-official"              # up-to-date library docs (LiteLLM, Streamlit, Pydantic)
)

PLUGINS=("${CORE[@]}")
if [ "$WANT_ALL" = "--all" ]; then PLUGINS+=("${OPTIONAL[@]}"); fi

echo
echo "== 2/3 Installing plugins (scope: $SCOPE) =="
FAILED=()
for p in "${PLUGINS[@]}"; do
  echo "-> $p"
  if ! claude plugin install "$p" --scope "$SCOPE"; then
    FAILED+=("$p")
  fi
done

echo
echo "== 3/3 Installed plugins =="
claude plugin list || true

echo
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "Some installs failed: ${FAILED[*]}"
  echo "Fix: open Claude Code, run /plugin, go to Discover, search the name and install it there."
else
  echo "All done. Start (or restart) Claude Code in this folder, or run /reload-plugins in an open session."
fi
echo "Check inside Claude Code:  type '/' and look for superpowers:* skills;  run /agents to see independent-reviewer and brief-auditor."