#!/usr/bin/env bash
# Defensive security scans for THIS project only.
# Usage: scripts/security_scan.sh [all|secrets|deps|sast|cloud]
# Env:
#   SECURITY_USE_DOCKER=auto|1|0   use pinned Docker images (default auto)
#   TRUFFLEHOG_VERIFY=1            opt in to TruffleHog credential verification (default off)
#   TRIVY_IMAGE=<image:tag>        also check an image you built from this repo
#   SEMGREP_CONFIGS="p/python ..." registry rulesets (default below)
#   PROWLER_OPT_IN=1 PROWLER_PROVIDER=aws|azure|gcp   required for the cloud audit
set -euo pipefail

GITLEAKS_VERSION="v8.30.1"
TRUFFLEHOG_VERSION="3.99.8"
TRIVY_VERSION="0.76.2"
SEMGREP_VERSION="1.184.0"
PROWLER_VERSION="5.47.0"

GITLEAKS_IMAGE="zricethezav/gitleaks:${GITLEAKS_VERSION}"
TRUFFLEHOG_IMAGE="trufflesecurity/trufflehog:${TRUFFLEHOG_VERSION}"
TRIVY_IMAGE_TOOL="aquasec/trivy:${TRIVY_VERSION}"
SEMGREP_IMAGE="semgrep/semgrep:${SEMGREP_VERSION}"
PROWLER_IMAGE="prowlercloud/prowler:${PROWLER_VERSION}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/reports/security"
mkdir -p "${OUT}"
cd "${ROOT}"

SEMGREP_CONFIGS="${SEMGREP_CONFIGS:-p/python p/typescript p/react p/secrets p/dockerfile}"
USE_DOCKER="${SECURITY_USE_DOCKER:-auto}"
if [[ "${USE_DOCKER}" == "auto" ]]; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then USE_DOCKER=1; else USE_DOCKER=0; fi
fi

log() { printf '[security] %s\n' "$*"; }
need_bin() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "SKIP $1: Docker is not available and no local '$1' binary is on PATH. Install it or run with Docker."
    return 1
  fi
}
drun() { docker run --rm -v "${ROOT}:/src" -w /src "$@"; }

scan_gitleaks() {
  log "Gitleaks (secrets in files and git history, redacted output)"
  local args=(--config security/.gitleaks.toml --redact --no-banner --exit-code 0)
  # working tree first, then git history when this is a git checkout
  local runs=("dir:gitleaks")
  [[ -d .git ]] && runs+=("git:gitleaks-history")
  for r in "${runs[@]}"; do
    local mode="${r%%:*}" name="${r##*:}"
    if [[ "${USE_DOCKER}" == 1 ]]; then
      drun "${GITLEAKS_IMAGE}" "${mode}" . "${args[@]}" --report-format json --report-path "/src/reports/security/${name}.json"
      drun "${GITLEAKS_IMAGE}" "${mode}" . "${args[@]}" --report-format sarif --report-path "/src/reports/security/${name}.sarif"
    else
      need_bin gitleaks || return 0
      gitleaks "${mode}" . "${args[@]}" --report-format json --report-path "${OUT}/${name}.json"
      gitleaks "${mode}" . "${args[@]}" --report-format sarif --report-path "${OUT}/${name}.sarif"
    fi
  done
}

scan_trufflehog() {
  local verify=(--no-verification)
  if [[ "${TRUFFLEHOG_VERIFY:-0}" == 1 ]]; then
    verify=()
    log "TruffleHog with VERIFICATION ON (you opted in: found credentials are tested against their issuers)"
  else
    log "TruffleHog (verification OFF: no credential is sent to any third party)"
  fi
  local args=(filesystem . --json --no-update --exclude-paths security/trufflehog-exclude.txt "${verify[@]}")
  if [[ "${USE_DOCKER}" == 1 ]]; then
    drun "${TRUFFLEHOG_IMAGE}" "${args[@]}" > "${OUT}/trufflehog.jsonl" 2> "${OUT}/trufflehog.log" || true
  else
    need_bin trufflehog || return 0
    trufflehog "${args[@]}" > "${OUT}/trufflehog.jsonl" 2> "${OUT}/trufflehog.log" || true
  fi
  # one JSON array for the ingest; lines that are not findings are dropped
  python3 - "${OUT}/trufflehog.jsonl" "${OUT}/trufflehog.json" <<'PY'
import json, sys
rows = []
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    line = line.strip()
    if line.startswith("{"):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "DetectorName" in obj:
            rows.append(obj)
json.dump(rows, open(sys.argv[2], "w"), indent=1)
print(f"[security] trufflehog findings: {len(rows)}")
PY
  rm -f "${OUT}/trufflehog.jsonl"
}

scan_trivy() {
  log "Trivy fs (dependency CVEs, IaC config, secrets)"
  if [[ "${USE_DOCKER}" == 1 ]]; then
    drun -v trivy-cache:/root/.cache/trivy "${TRIVY_IMAGE_TOOL}" fs --config security/trivy.yaml --format json --output /src/reports/security/trivy.json .
    drun -v trivy-cache:/root/.cache/trivy "${TRIVY_IMAGE_TOOL}" fs --config security/trivy.yaml --format sarif --output /src/reports/security/trivy.sarif .
  else
    need_bin trivy || return 0
    trivy fs --config security/trivy.yaml --format json --output "${OUT}/trivy.json" .
    trivy fs --config security/trivy.yaml --format sarif --output "${OUT}/trivy.sarif" .
  fi
  if [[ -n "${TRIVY_IMAGE:-}" ]]; then
    log "Trivy image ${TRIVY_IMAGE} (an image you built from this repo)"
    if [[ "${USE_DOCKER}" == 1 ]]; then
      docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v trivy-cache:/root/.cache/trivy -v "${OUT}:/out" \
        "${TRIVY_IMAGE_TOOL}" image --format json --output /out/trivy-image.json "${TRIVY_IMAGE}"
    else
      trivy image --format json --output "${OUT}/trivy-image.json" "${TRIVY_IMAGE}"
    fi
  fi
}

scan_semgrep() {
  log "Semgrep (SAST: ${SEMGREP_CONFIGS} + security/semgrep.yml)"
  local cfg=(--config security/semgrep.yml)
  for c in ${SEMGREP_CONFIGS}; do cfg+=(--config "$c"); done
  local common=(--metrics=off --exclude node_modules --exclude .venv --exclude reports --exclude data/security_fixtures --exclude _design_pack --exclude .agents --exclude .claude --exclude .cursor)
  if [[ "${USE_DOCKER}" == 1 ]]; then
    drun "${SEMGREP_IMAGE}" semgrep scan "${cfg[@]}" "${common[@]}" --json --output /src/reports/security/semgrep.json --sarif-output /src/reports/security/semgrep.sarif .
  else
    need_bin semgrep || return 0
    semgrep scan "${cfg[@]}" "${common[@]}" --json --output "${OUT}/semgrep.json" --sarif-output "${OUT}/semgrep.sarif" .
  fi
}

scan_prowler() {
  if [[ "${PROWLER_OPT_IN:-0}" != 1 || -z "${PROWLER_PROVIDER:-}" ]]; then
    cat <<'MSG'
[security] Prowler did NOT run.
  Prowler audits a live cloud account, so it only runs when you opt in with
  your own credentials:
    PROWLER_OPT_IN=1 PROWLER_PROVIDER=aws AWS_PROFILE=<your-profile> make scan-cloud
  (azure and gcp use their standard env vars). Nothing was read or guessed.
MSG
    return 0
  fi
  log "Prowler ${PROWLER_PROVIDER} audit of YOUR account (credentials from your environment only)"
  if [[ "${USE_DOCKER}" == 1 ]]; then
    local envs=()
    for v in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_REGION AWS_DEFAULT_REGION \
             AZURE_CLIENT_ID AZURE_TENANT_ID AZURE_CLIENT_SECRET GOOGLE_APPLICATION_CREDENTIALS; do
      [[ -n "${!v:-}" ]] && envs+=(-e "$v")
    done
    local mounts=()
    [[ -n "${AWS_PROFILE:-}" && -d "${HOME}/.aws" ]] && mounts+=(-v "${HOME}/.aws:/home/prowler/.aws:ro")
    docker run --rm "${envs[@]}" "${mounts[@]}" -v "${OUT}:/out" "${PROWLER_IMAGE}" \
      "${PROWLER_PROVIDER}" --output-formats json-ocsf --output-directory /out --output-filename prowler
  else
    need_bin prowler || return 0
    prowler "${PROWLER_PROVIDER}" --output-formats json-ocsf --output-directory "${OUT}" --output-filename prowler
  fi
  [[ -f "${OUT}/prowler.ocsf.json" ]] && cp "${OUT}/prowler.ocsf.json" "${OUT}/prowler.json"
  true
}

target="${1:-all}"
log "mode: $([[ ${USE_DOCKER} == 1 ]] && echo docker || echo local-binaries), reports: reports/security/"
case "${target}" in
  all)     scan_gitleaks; scan_trufflehog; scan_trivy; scan_semgrep
           log "Prowler is not part of 'all'. Use 'make scan-cloud' with your own credentials." ;;
  secrets) scan_gitleaks; scan_trufflehog ;;
  deps)    scan_trivy ;;
  sast)    scan_semgrep ;;
  cloud)   scan_prowler ;;
  *) echo "usage: $0 [all|secrets|deps|sast|cloud]"; exit 2 ;;
esac
log "done"
