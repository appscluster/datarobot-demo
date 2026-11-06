# Agent tooling

Tools for Claude Code, Cursor and OpenCode working in this project. Pins are the
upstream commit (or package version) fetched on 2026-11-06.

| Tool | Repo | Pinned | How it is wired | How to update |
|---|---|---|---|---|
| Superpowers | [obra/superpowers](https://github.com/obra/superpowers) | `22f0b463e7a5e579904dd6211a520321035526f7` | **Vendored**: all 15 skills from `skills/` copied into `.claude/skills`, `.cursor/skills`, `.agents/skills`. Global alternative: `/plugin install superpowers@claude-plugins-official` (Claude Code), `/add-plugin superpowers` (Cursor). | Re-copy `skills/*` from a newer commit, update this pin. |
| Claude Code | [anthropics/claude-code](https://github.com/anthropics/claude-code) | `90380efca7f9d73e206fac453f841b6acd664f4d` (reference only) | **Not vendored** (it is the CLI). Project guidance in `CLAUDE.md`; `AGENTS.md` points to it. | Install or update the CLI per its README. Keep `CLAUDE.md` current. |
| UI UX Pro Max | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | `b7d5353e0130feb8c5574ef1251f8a1db1873ccb` (CLI `ui-ux-pro-max-cli@2.15.0`) | **Vendored**: `.claude/skills/ui-ux-pro-max` from upstream into all three skill folders. The companion skills (design, brand, ui-styling, slides, banner-design, design-system) are not vendored. | `npx ui-ux-pro-max-cli init --ai claude` (and `--ai cursor`, `--ai universal`), or re-copy from upstream. |
| Claude Mem | [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | `f09068514365a7b6fa01bf7e3af2a20118f55df7` (npm `claude-mem@15.10.0`) | **Scripted, not installed from the box**: `scripts/install_agent_tooling.sh --apply --only claude-mem` runs the official `npx claude-mem install --provider claude --runtime worker` for your user, turns telemetry off, and sets `CLAUDE_MEM_SKIP_BASH_PATTERNS` so commands touching `reports/security`, `.env` and secret scanners are not captured. | Bump `CLAUDE_MEM_VERSION` in the script, or `npx claude-mem update`. |
| Learn Claude Code | [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | `7226f555d48900076eba126acf37c9ed5f002b5d` | **Documented only** (educational). | Nothing to update. |
| GSD (Get Shit Done) | [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) (archived) → [open-gsd/gsd-core](https://github.com/open-gsd/gsd-core) | old `bdcaab2c752d9a33a1a1ca9acf3a3c81fb991815`; current `f3f3a182627f56267028cf3145239ef8d8154635` (npm `@opengsd/gsd-core@1.20.1`) | **Scripted**: `scripts/install_agent_tooling.sh --apply --only gsd` runs `npx @opengsd/gsd-core@1.20.1 --claude --local` in the project. Not vendored because the installer writes absolute paths into the generated `.claude/` files (checked on the box). | Bump `GSD_VERSION` in the script and rerun with `--force`. |
| Claude Code Best Practice | [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | `722071c519f760c6ed3084f370547666e1cb51a0` | **Folded into `CLAUDE.md`** (plan before edit, tests define behaviour, small changes, no guessed APIs, no secrets, quality gates). | Reread and adjust `CLAUDE.md`. |
| Awesome Claude Code | [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | `31b517448cf9e7bf537ca3400549a5b27aa88ec6` | **Documented only** (curated list). | Nothing to update. |
| LightRAG | [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) | `aaebfe1bb8d55deb6a4304d357a3bf4c92fcd40a` (PyPI `lightrag-hku==1.5.7`) | **App feature, optional**: `agent/lightrag_backend.py`, `RETRIEVAL_BACKEND=lightrag`, compose profile `lightrag`, Ollama only. See `docs/LIGHTRAG.md`. | Bump `backend/requirements-lightrag.txt`, rerun `make test-lightrag lightrag-smoke`. |

## Skill folders

`.agents/skills` is the shared folder (OpenCode, Codex and other agents), with the same skills
copied into `.claude/skills` (Claude Code) and `.cursor/skills` (Cursor). Existing skills with the
same name are never overwritten by these copies. Licences: `.agents/skills/SUPERPOWERS-LICENSE`,
`.agents/skills/UI-UX-PRO-MAX-LICENSE`. Taste, Impeccable, humanizer, grill-me and decisions
are not part of this commit; if you have them installed they stay as they are.

## Install on abdul-ai

    scripts/install_agent_tooling.sh             # dry run, prints every command
    scripts/install_agent_tooling.sh --apply     # claude-mem for your user + GSD Core in this project

## claude-mem and secrets

claude-mem records tool use into a local memory store. It must never capture secrets.

* Use `--provider claude` (local, your plan). The hosted claude-mem observer is not used.
* `CLAUDE_MEM_SKIP_BASH_PATTERNS` skips commands that touch `reports/security`, `.env`, secret files
  and the secret scanners. claude-mem has no per path exclusion for file reads, so do not open raw
  scanner reports or `.env` files in a Claude Code session; use `make security-ingest` and the redacted
  findings instead.
* Wrap anything sensitive you type in `<private>...</private>`.
* To stop it entirely for this project, add the project path to `CLAUDE_MEM_EXCLUDED_PROJECTS`
  in `~/.claude-mem/settings.json`.
