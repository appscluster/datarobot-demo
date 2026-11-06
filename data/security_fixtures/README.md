# Synthetic security scanner fixtures

Hand written, clearly fake reports in the shape of each tool's JSON output.
They let the ThreatAI demo show scanner findings offline. No value here is a
real credential, CVE, package or cloud account.

| File | Shape |
|---|---|
| gitleaks.json | `gitleaks detect --report-format json` |
| trufflehog.json | `trufflehog filesystem --json --no-verification` (lines collected into a list) |
| trivy.json | `trivy fs --format json` |
| semgrep.json | `semgrep --json` |
| prowler.json | `prowler <provider> --output-formats json-ocsf` |

Each file wraps the tool output as `{"_synthetic": true, "report": ...}` so the
ingest marks the findings as synthetic. Secret scanners are told to skip this
folder (see `security/.gitleaks.toml` and `security/trufflehog-exclude.txt`).
