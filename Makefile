.PHONY: eval deps test-all lightrag-deps lightrag-index lightrag-smoke test-lightrag agent-tooling security-scan scan-secrets scan-deps scan-sast scan-cloud security-ingest security-ingest-fixtures test-security

deps:
	pip3 install --user -r backend/requirements.txt -r backend/requirements-dev.txt

eval: deps
	PYTHONPATH=. python3 -m pytest -q evals

# ---- Security toolkit (this project only; see security/README.md) ----
security-scan:            ## Gitleaks + TruffleHog + Trivy + Semgrep
	scripts/security_scan.sh all

scan-secrets:             ## Gitleaks (redacted) + TruffleHog (no verification unless TRUFFLEHOG_VERIFY=1)
	scripts/security_scan.sh secrets

scan-deps:                ## Trivy fs: dependency CVEs, IaC config, secrets
	scripts/security_scan.sh deps

scan-sast:                ## Semgrep: insecure code patterns
	scripts/security_scan.sh sast

scan-cloud:               ## Prowler: needs PROWLER_OPT_IN=1 PROWLER_PROVIDER=aws|azure|gcp and your own creds
	scripts/security_scan.sh cloud

security-ingest:          ## reports/security/*.json (or fixtures when empty) -> SQLite + GraphRAG
	python3 scripts/security_ingest.py --source auto

security-ingest-fixtures: ## synthetic fixtures only (offline demo)
	python3 scripts/security_ingest.py --source fixtures

test-security:
	PYTHONPATH=. python3 -m pytest -q tests/test_security_sources.py

# ---- Optional LightRAG retrieval (default off; see docs/LIGHTRAG.md) ----
lightrag-deps:
	pip3 install --user -r backend/requirements-lightrag.txt

lightrag-index:           ## index graph + runbooks + scanner findings into LightRAG (needs Ollama)
	RETRIEVAL_BACKEND=lightrag python3 -m agent.lightrag_backend index

lightrag-smoke:           ## real lightrag-hku with a fake LLM and fake embeddings (offline)
	python3 scripts/lightrag_smoke.py

test-lightrag:
	PYTHONPATH=. python3 -m pytest -q tests/test_lightrag_backend.py

# ---- All offline checks ----
test-all:
	PYTHONPATH=. python3 -m pytest -q evals
	PYTHONPATH=. python3 -m pytest -q tests/test_security_sources.py tests/test_lightrag_backend.py

# ---- Coding agent tooling for Claude Code, Cursor, OpenCode (see docs/AGENT_TOOLING.md) ----
agent-tooling:
	scripts/install_agent_tooling.sh --dry-run
