.PHONY: eval deps security-scan scan-secrets scan-deps scan-sast scan-cloud security-ingest security-ingest-fixtures test-security

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
