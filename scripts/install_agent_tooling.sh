#!/usr/bin/env bash
# Install the coding agent tooling that cannot be vendored into this repo.
# Run it on your own machine (abdul-ai), as your user, from the project folder.
#
#   scripts/install_agent_tooling.sh --dry-run          # print what would run (default)
#   scripts/install_agent_tooling.sh --apply            # run it
#   scripts/install_agent_tooling.sh --apply --only gsd # one component: claude-mem | gsd | plugins
#   add --force to reinstall a component that is already present
#
# Only the documented official installers are used, at pinned versions:
#   claude-mem         npx claude-mem@15.10.0 install --provider claude --runtime worker
#   GSD Core           npx @opengsd/gsd-core@1.20.1 --claude --local   (also --cursor / --opencode)
#   Superpowers, UI UX Pro Max plugins are in app commands; they are printed, not run.
set -euo pipefail

CLAUDE_MEM_VERSION="15.10.0"
GSD_VERSION="1.20.1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="dry-run"; ONLY=""; FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="dry-run" ;;
    --apply) MODE="apply" ;;
    --only) ONLY="$2"; shift ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n 2,16p "$0"; exit 0 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done

say() { printf '[agent-tooling] %s\n' "$*"; }
run() {
  if [[ "${MODE}" == "apply" ]]; then say "RUN  $*"; "$@"; else say "WOULD RUN  $*"; fi
}
want() { [[ -z "${ONLY}" || "${ONLY}" == "$1" ]]; }

if [[ "$(id -u)" == 0 ]]; then
  say "Refusing to run as root. Run it as your own user."; exit 1
fi
command -v npx >/dev/null 2>&1 || { say "npx (Node.js 18+) is required"; exit 1; }
cd "${ROOT}"
say "project: ${ROOT}   mode: ${MODE}"

# ---------------------------------------------------------------- claude-mem
if want claude-mem; then
  if [[ -d "${HOME}/.claude-mem" && ${FORCE} == 0 ]]; then
    say "claude-mem already installed (~/.claude-mem exists); skipping install. Use --force to reinstall."
  else
    # provider claude = local memory on your Anthropic plan; no hosted claude-mem account
    run env CLAUDE_MEM_ONLINE_OPTIN=false npx -y "claude-mem@${CLAUDE_MEM_VERSION}" install --provider claude --runtime worker
    run npx -y "claude-mem@${CLAUDE_MEM_VERSION}" telemetry disable
  fi
  # Keep secrets and scanner output out of memory. claude-mem has no per path exclusion,
  # so commands that touch these paths are skipped (CLAUDE_MEM_SKIP_BASH_PATTERNS).
  PATTERN='(reports/security|\.env\b|\.env\.|trufflehog|gitleaks|secrets?\.(json|ya?ml|toml)|id_rsa|\.pem\b)'
  SETTINGS="${HOME}/.claude-mem/settings.json"
  if [[ "${MODE}" == "apply" ]]; then
    mkdir -p "${HOME}/.claude-mem"
    [[ -f "${SETTINGS}" ]] && cp "${SETTINGS}" "${SETTINGS}.bak-$(date +%Y%m%d%H%M%S)"
    python3 - "${SETTINGS}" "${PATTERN}" <<'PY'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]); pat = sys.argv[2]
d = json.loads(p.read_text() or "{}") if p.exists() else {}
target = d["env"] if isinstance(d.get("env"), dict) and any(k.startswith("CLAUDE_MEM_") for k in d["env"]) else d
cur = target.get("CLAUDE_MEM_SKIP_BASH_PATTERNS", "")
if pat not in cur:
    target["CLAUDE_MEM_SKIP_BASH_PATTERNS"] = f"{cur}|{pat}" if cur else pat
p.write_text(json.dumps(d, indent=2))
print("[agent-tooling] CLAUDE_MEM_SKIP_BASH_PATTERNS set in", p)
PY
  else
    say "WOULD SET CLAUDE_MEM_SKIP_BASH_PATTERNS=${PATTERN} in ${SETTINGS} (backup first)"
  fi
  say "Reminder: wrap anything sensitive you type in <private>...</private> so claude-mem does not store it."
fi

# ---------------------------------------------------------------- GSD Core (project local)
if want gsd; then
  if [[ -f .claude/gsd-install-state.json && ${FORCE} == 0 ]]; then
    say "GSD Core already installed in .claude/ (gsd-install-state.json); skipping. Use --force to reinstall."
  else
    run npx -y "@opengsd/gsd-core@${GSD_VERSION}" --claude --local
    say "Optional: also for Cursor and OpenCode in this project:"
    say "  npx -y @opengsd/gsd-core@${GSD_VERSION} --cursor --local"
    say "  npx -y @opengsd/gsd-core@${GSD_VERSION} --opencode --local"
  fi
fi

# ---------------------------------------------------------------- in app plugins (printed only)
if want plugins; then
  cat <<'MSG'
[agent-tooling] Skills for Superpowers and UI UX Pro Max are already vendored in
  .claude/skills, .cursor/skills and .agents/skills. For a global install instead,
  type these inside the tool (they cannot be scripted from a shell):
    Claude Code:  /plugin install superpowers@claude-plugins-official
                  /plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
                  /plugin install ui-ux-pro-max@ui-ux-pro-max-skill
    Cursor:       /add-plugin superpowers
    OpenCode:     Fetch and follow instructions from https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/.opencode/INSTALL.md
MSG
fi
say "done (${MODE})"
