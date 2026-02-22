#!/usr/bin/env bash

# Check if Agent Teams feature is enabled.
# This plugin REQUIRES Agent Teams for parallel dimension analysis.

if [ "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS}" != "1" ]; then
  cat <<'EOF'
╔══════════════════════════════════════════════════════════════════╗
║  FEATURE-INVENTORY PLUGIN: Agent Teams REQUIRED                 ║
║                                                                  ║
║  This plugin requires Claude Code Agent Teams to function.       ║
║  Agent Teams enables parallel analysis across 9 dimensions.      ║
║                                                                  ║
║  To enable, add to ~/.claude/settings.json:                      ║
║                                                                  ║
║    {                                                             ║
║      "env": {                                                    ║
║        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"               ║
║      }                                                           ║
║    }                                                             ║
║                                                                  ║
║  Or set in your shell:                                           ║
║                                                                  ║
║    export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1                 ║
║                                                                  ║
║  Then restart Claude Code.                                       ║
║                                                                  ║
║  Running /feature-inventory without Agent Teams will FAIL.       ║
╚══════════════════════════════════════════════════════════════════╝
EOF
fi
