# Security toolkit

Five open source scanners, run against this project only.

| Tool | What it checks | Make target | Report |
|---|---|---|---|
| Gitleaks | secrets in files and git history | `make scan-secrets` | `reports/security/gitleaks.json`, `.sarif` |
| TruffleHog | leaked credentials (verification OFF by default) | `make scan-secrets` | `reports/security/trufflehog.json` |
| Trivy | dependency CVEs, Dockerfile and compose config, secrets | `make scan-deps` | `reports/security/trivy.json`, `.sarif` |
| Semgrep | insecure code patterns (Python, TypeScript, React) | `make scan-sast` | `reports/security/semgrep.json`, `.sarif` |
| Prowler | cloud misconfiguration in your own account | `make scan-cloud` (opt in) | `reports/security/prowler*.ocsf.json` |

`make security-scan` runs Gitleaks, TruffleHog, Trivy and Semgrep. Prowler never
runs as part of it.

## How the tools run

`scripts/security_scan.sh` uses the pinned official Docker image of each tool.
When Docker is missing (or `SECURITY_USE_DOCKER=0`) it falls back to a local
binary on `PATH`. Versions are pinned at the top of the script.

## Safety rules

* Scans target this repository (and, with `TRIVY_IMAGE=...`, an image you built from it). Nothing external.
* TruffleHog runs with `--no-verification`, so it never sends a found credential to a third party API.
  Opt in with `TRUFFLEHOG_VERIFY=1 make scan-secrets` only if you accept that.
* Gitleaks runs with `--redact`, so its report holds `REDACTED` instead of the secret.
* Prowler runs only with `PROWLER_OPT_IN=1` and credentials you supply yourself in the
  environment (`PROWLER_PROVIDER=aws|azure|gcp`, plus the provider's standard env vars or
  `AWS_PROFILE`). It does not read or guess credentials from anywhere else.
* `reports/` is gitignored. Raw reports can still contain secret text (TruffleHog `Raw`), so
  treat them as sensitive and do not share them.

## Into the agent

`make security-ingest` parses `reports/security/*.json` (or the synthetic fixtures in
`data/security_fixtures/` when no reports exist) into the ThreatAI finding model, stores
them in SQLite (`backend/var/security.db`) and adds them to the GraphRAG graph as
`asset -> finding -> tool` nodes. Stored findings keep only rule id, file, line, fingerprint
and a masked preview; raw secret values are never stored. Restart the backend (or call
`POST /api/security/ingest`) to see them in the console with a tool badge.
