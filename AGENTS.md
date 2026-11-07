# AGENTS.md

This repo is Casework, a synthetic lending desk for Emirates NBD Demo. Read [CLAUDE.md](CLAUDE.md) before editing. It has the stack, the product facts, the commands, the rules, and the quality gates.

The running demo decides whether loan model v3 may score personal loans. Loan model v2 stays the live scorer. The desk does not approve a person's loan. Retrieval is SQLite GraphRAG. Drafts come from OmniRoute. LightRAG and the security scanners are optional code and are off.

Sign in is `analyst` / `demo`. Frontend is http://127.0.0.1:43123. Backend is http://127.0.0.1:54123.

Project skills are in `.agents/skills`, with the same copies in `.claude/skills` and `.cursor/skills`. Tooling notes: [docs/AGENT_TOOLING.md](docs/AGENT_TOOLING.md). The lending spec is [docs/superpowers/specs/2026-11-07-lending-usecase.md](docs/superpowers/specs/2026-11-07-lending-usecase.md).
