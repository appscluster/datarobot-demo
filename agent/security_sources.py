"""Security scanner findings as ThreatAI finding sources.

Parses JSON output from Gitleaks, TruffleHog, Trivy, Semgrep and Prowler
(OCSF or legacy JSON) into the app's finding model, redacts every secret
value, stores the result in SQLite and merges it into the active GraphRAG
graph as finding -> asset -> tool nodes.

Defensive only: this module reads report files. It never runs a scanner,
never verifies credentials and never contacts a third party.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path("backend/var/security.db")
REPORTS_DIR = ROOT / "reports" / "security"
FIXTURES_DIR = ROOT / "data" / "security_fixtures"
DEFAULT_TENANT = "tenant_demo_acme"
SEVERITIES = ("critical", "high", "medium", "low", "info")
TOOLS = ("gitleaks", "trufflehog", "trivy", "semgrep", "prowler")
TOOL_LABELS = {"gitleaks": "Gitleaks", "trufflehog": "TruffleHog", "trivy": "Trivy", "semgrep": "Semgrep", "prowler": "Prowler"}
_ID_SAFE = re.compile(r"[^A-Za-z0-9-]+")


@dataclass
class SecurityFinding:
    finding_id: str
    tenant_id: str
    source_tool: str
    rule_id: str
    title: str
    severity: str
    asset_id: str
    asset_label: str
    category: str  # secret | dependency | misconfig | sast | cloud
    file: Optional[str] = None
    line: Optional[int] = None
    fingerprint: str = ""
    masked_preview: Optional[str] = None
    weakness_id: Optional[str] = None
    remediation: str = ""
    references: List[str] = field(default_factory=list)
    synthetic: bool = False
    status: str = "open"
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ----------------------------------------------------------------- helpers

def mask_secret(value: Optional[str]) -> Optional[str]:
    """Masked preview: at most the first 4 characters, never the full value."""
    if not value:
        return None
    v = str(value).strip()
    if len(v) < 12:
        return "*" * 8
    return v[:4] + "*" * 8 + f" ({len(v)} chars)"


def _safe_id(text: str, maxlen: int = 40) -> str:
    s = _ID_SAFE.sub("-", str(text)).strip("-")
    return (s[:maxlen].strip("-")) or "x"


def _fp(*parts: Any) -> str:
    """Location fingerprint. Built from tool, rule, file and line, never from the secret."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return h[:16]


def _finding_id(tool: str, fingerprint: str, tenant_id: str = DEFAULT_TENANT) -> str:
    if tenant_id != DEFAULT_TENANT:
        fingerprint = _fp(fingerprint, tenant_id)
    prefix = {"gitleaks": "GL", "trufflehog": "TH", "trivy": "TV", "semgrep": "SG", "prowler": "PW"}[tool]
    return f"F-{prefix}-{fingerprint[:10]}"


def norm_severity(raw: Any, default: str = "medium") -> str:
    s = str(raw or "").strip().lower()
    mapping = {
        "critical": "critical", "high": "high", "error": "high",
        "medium": "medium", "moderate": "medium", "warning": "medium",
        "low": "low", "info": "info", "informational": "info", "note": "info",
        "unknown": "low",
    }
    return mapping.get(s, default)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _scrub(obj: Any, secrets: Iterable[str]) -> Any:
    """Belt and braces: replace any raw secret that slipped into a string field."""
    secrets = [s for s in secrets if s and len(str(s)) >= 4]
    if not secrets:
        return obj
    if isinstance(obj, str):
        for s in secrets:
            obj = obj.replace(str(s), "[REDACTED]")
        return obj
    if isinstance(obj, list):
        return [_scrub(x, secrets) for x in obj]
    if isinstance(obj, dict):
        return {k: _scrub(v, secrets) for k, v in obj.items()}
    return obj


def _repo_asset(project: str) -> Tuple[str, str]:
    return f"asset:repo-{_safe_id(project)}", f"Repo {project}"


def _load_json_or_jsonl(path: Path) -> Any:
    text = Path(path).read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows


def _is_synthetic(data: Any) -> bool:
    if isinstance(data, dict):
        return bool(data.get("_synthetic"))
    return False


def _unwrap(data: Any, key: Optional[str] = None) -> Any:
    """Fixtures wrap tool output as {"_synthetic": true, "report": ...}."""
    if isinstance(data, dict) and "_synthetic" in data and "report" in data:
        return data["report"]
    return data


SECRET_REMEDIATION = (
    "Revoke and rotate this credential with its issuer, remove it from the source and git history "
    "through a reviewed change, and load it from a secrets manager or environment variable."
)


# ----------------------------------------------------------------- parsers

def parse_gitleaks(data: Any, tenant_id: str, project: str = "DataRobot-Demo") -> List[SecurityFinding]:
    synthetic = _is_synthetic(data)
    rows = _unwrap(data) or []
    asset_id, asset_label = _repo_asset(project)
    out = []
    for r in rows if isinstance(rows, list) else []:
        secret = r.get("Secret") or ""
        match = r.get("Match") or ""
        rule = r.get("RuleID") or "unknown-rule"
        file = r.get("File")
        line = r.get("StartLine")
        fp = _fp("gitleaks", rule, file, line)  # no commit: history and tree hits dedupe
        f = SecurityFinding(
            finding_id=_finding_id("gitleaks", fp, tenant_id), tenant_id=tenant_id, source_tool="gitleaks",
            rule_id=rule, title=f"Secret ({rule}) committed in {file}:{line}", severity="high",
            asset_id=asset_id, asset_label=asset_label, category="secret", file=file, line=line,
            fingerprint=fp, masked_preview=mask_secret(secret) if secret and secret != "REDACTED" else "[redacted by gitleaks]",
            weakness_id="weakness:CWE-798", remediation=SECRET_REMEDIATION, synthetic=synthetic,
        )
        out.append(_scrub_finding(f, [secret, match]))
    return out


def _scrub_finding(f: SecurityFinding, secrets: Iterable[str]) -> SecurityFinding:
    d = f.to_dict()
    preview = d.pop("masked_preview")
    d = _scrub(d, secrets)
    d["masked_preview"] = preview
    return SecurityFinding(**d)


def _th_location(r: Dict[str, Any]) -> Tuple[Optional[str], Optional[int]]:
    data = (r.get("SourceMetadata") or {}).get("Data") or {}
    for v in data.values():
        if isinstance(v, dict):
            file = v.get("file") or v.get("File") or v.get("path")
            line = v.get("line") or v.get("Line")
            if file or line:
                return file, line
    return None, None


def parse_trufflehog(data: Any, tenant_id: str, project: str = "DataRobot-Demo") -> List[SecurityFinding]:
    synthetic = _is_synthetic(data)
    rows = _unwrap(data) or []
    if isinstance(rows, dict):
        rows = [rows]
    asset_id, asset_label = _repo_asset(project)
    out = []
    for r in rows:
        if not isinstance(r, dict) or "DetectorName" not in r:
            continue  # skip log lines
        raw = r.get("Raw") or ""
        raw2 = r.get("RawV2") or ""
        det = r.get("DetectorName") or "unknown"
        file, line = _th_location(r)
        verified = bool(r.get("Verified"))
        fp = _fp("trufflehog", det, file, line, r.get("DecoderName"))
        f = SecurityFinding(
            finding_id=_finding_id("trufflehog", fp, tenant_id), tenant_id=tenant_id, source_tool="trufflehog",
            rule_id=f"{det}{' (verified)' if verified else ' (unverified)'}",
            title=f"{det} credential found in {file}:{line}" + (" (verified live)" if verified else ""),
            severity="critical" if verified else "high", asset_id=asset_id, asset_label=asset_label,
            category="secret", file=file, line=line, fingerprint=fp,
            masked_preview=mask_secret(raw), weakness_id="weakness:CWE-798",
            remediation=SECRET_REMEDIATION, synthetic=synthetic,
        )
        out.append(_scrub_finding(f, [raw, raw2, r.get("Redacted") or ""]))
    return out


def parse_trivy(data: Any, tenant_id: str, project: str = "DataRobot-Demo") -> List[SecurityFinding]:
    synthetic = _is_synthetic(data)
    rep = _unwrap(data) or {}
    artifact = rep.get("ArtifactName") or project
    atype = rep.get("ArtifactType") or "filesystem"
    if atype == "container_image":
        asset_id, asset_label = f"asset:img-{_safe_id(artifact)}", f"Image {artifact}"
    else:
        asset_id, asset_label = _repo_asset(project)
    out = []
    for res in rep.get("Results") or []:
        target = res.get("Target")
        for v in res.get("Vulnerabilities") or []:
            vid = v.get("VulnerabilityID") or "UNKNOWN"
            pkg = v.get("PkgName")
            inst = v.get("InstalledVersion")
            fixed = v.get("FixedVersion")
            fp = _fp("trivy", "vuln", target, pkg, inst, vid)
            cwe = (v.get("CweIDs") or [None])[0]
            rem = (f"Upgrade {pkg} from {inst} to {fixed} in {target} through a reviewed dependency change, then rerun the dependency check."
                   if fixed else f"No fixed version of {pkg} yet; track {vid}, limit exposure of the affected path and pin a patched release when published.")
            out.append(SecurityFinding(
                finding_id=_finding_id("trivy", fp, tenant_id), tenant_id=tenant_id, source_tool="trivy", rule_id=vid,
                title=f"{vid} in {pkg} {inst}" + (f" (fixed in {fixed})" if fixed else ""),
                severity=norm_severity(v.get("Severity")), asset_id=asset_id, asset_label=asset_label,
                category="dependency", file=target, line=None, fingerprint=fp,
                weakness_id=f"weakness:{_safe_id(cwe)}" if cwe else None, remediation=rem,
                references=[u for u in [v.get("PrimaryURL")] if u], synthetic=synthetic,
            ))
        for m in res.get("Misconfigurations") or []:
            if str(m.get("Status", "FAIL")).upper() == "PASS":
                continue
            mid = m.get("AVDID") or m.get("ID") or "MISCONFIG"
            line = (m.get("CauseMetadata") or {}).get("StartLine")
            fp = _fp("trivy", "misconfig", target, mid, line)
            out.append(SecurityFinding(
                finding_id=_finding_id("trivy", fp, tenant_id), tenant_id=tenant_id, source_tool="trivy", rule_id=mid,
                title=f"{m.get('Title') or mid} in {target}", severity=norm_severity(m.get("Severity")),
                asset_id=asset_id, asset_label=asset_label, category="misconfig", file=target, line=line,
                fingerprint=fp, remediation=(m.get("Resolution") or "Adjust the configuration in a reviewed change."),
                references=[u for u in [m.get("PrimaryURL")] if u], synthetic=synthetic,
            ))
        for s in res.get("Secrets") or []:
            match = s.get("Match") or ""
            rid = s.get("RuleID") or "secret"
            line = s.get("StartLine")
            fp = _fp("trivy", "secret", target, rid, line)
            f = SecurityFinding(
                finding_id=_finding_id("trivy", fp, tenant_id), tenant_id=tenant_id, source_tool="trivy", rule_id=rid,
                title=f"Secret ({rid}) in {target}:{line}", severity=norm_severity(s.get("Severity"), "high"),
                asset_id=asset_id, asset_label=asset_label, category="secret", file=target, line=line,
                fingerprint=fp, masked_preview="[redacted]", weakness_id="weakness:CWE-798",
                remediation=SECRET_REMEDIATION, synthetic=synthetic,
            )
            secret_lines = [ln.get("Content", "") for ln in ((s.get("Code") or {}).get("Lines") or [])]
            out.append(_scrub_finding(f, [match] + secret_lines))
    return out


def _first_sentences(msg: str, limit: int = 240) -> str:
    if len(msg) <= limit:
        return msg
    cut = msg[:limit]
    end = cut.rfind(". ")
    return cut[: end + 1] if end > 40 else cut.rsplit(" ", 1)[0] + "..."


def parse_semgrep(data: Any, tenant_id: str, project: str = "DataRobot-Demo") -> List[SecurityFinding]:
    synthetic = _is_synthetic(data)
    rep = _unwrap(data) or {}
    asset_id, asset_label = _repo_asset(project)
    out = []
    for r in rep.get("results") or []:
        extra = r.get("extra") or {}
        meta = extra.get("metadata") or {}
        rule = r.get("check_id") or "semgrep-rule"
        path = r.get("path")
        line = (r.get("start") or {}).get("line")
        cwe = meta.get("cwe")
        if isinstance(cwe, list):
            cwe = cwe[0] if cwe else None
        cwe_id = None
        if cwe:
            mm = re.search(r"CWE-\d+", str(cwe))
            cwe_id = f"weakness:{mm.group(0)}" if mm else None
        fp = _fp("semgrep", rule, path, line)
        msg = (extra.get("message") or rule).strip().split("\n")[0]
        sev = norm_severity(meta.get("impact") or extra.get("severity"))
        short_rule = rule.split(".")[-1]
        out.append(SecurityFinding(
            finding_id=_finding_id("semgrep", fp, tenant_id), tenant_id=tenant_id, source_tool="semgrep", rule_id=rule,
            title=f"{short_rule} in {path}:{line}", severity=sev, asset_id=asset_id, asset_label=asset_label,
            category="sast", file=path, line=line, fingerprint=fp, weakness_id=cwe_id,
            remediation=f"Refactor the flagged code following the rule guidance: {_first_sentences(msg)}",
            references=[u for u in (meta.get("references") or [])[:2] if isinstance(u, str)], synthetic=synthetic,
        ))
    # extra.lines is deliberately ignored: it can contain source text, including secrets.
    return out


def parse_prowler(data: Any, tenant_id: str, project: str = "DataRobot-Demo") -> List[SecurityFinding]:
    synthetic = _is_synthetic(data)
    rows = _unwrap(data) or []
    if isinstance(rows, dict):
        rows = rows.get("findings") or [rows]
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if "status_code" in r or "finding_info" in r:  # OCSF
            status = str(r.get("status_code") or "").upper()
            if status != "FAIL":
                continue
            info = r.get("finding_info") or {}
            check = (r.get("metadata") or {}).get("event_code") or info.get("uid") or "prowler-check"
            title = info.get("title") or check
            res = (r.get("resources") or [{}])[0]
            resource = res.get("uid") or res.get("name") or "resource"
            region = res.get("region") or (r.get("cloud") or {}).get("region")
            provider = ((r.get("cloud") or {}).get("provider") or "cloud").lower()
            account = (((r.get("cloud") or {}).get("account") or {}).get("uid")) or "account"
            rem = ((r.get("remediation") or {}).get("desc")) or "Fix the configuration through a reviewed infrastructure as code change."
            sev = norm_severity(r.get("severity"))
        else:  # legacy Prowler JSON
            if str(r.get("Status") or "").upper() != "FAIL":
                continue
            check = r.get("CheckID") or "prowler-check"
            title = r.get("CheckTitle") or check
            resource = r.get("ResourceId") or r.get("ResourceArn") or "resource"
            region = r.get("Region")
            provider = (r.get("Provider") or "aws").lower()
            account = r.get("AccountId") or "account"
            rem = (((r.get("Remediation") or {}).get("Recommendation") or {}).get("Text")) or "Fix the configuration through a reviewed infrastructure as code change."
            sev = norm_severity(r.get("Severity"))
        fp = _fp("prowler", provider, account, check, resource, region)
        out.append(SecurityFinding(
            finding_id=_finding_id("prowler", fp, tenant_id), tenant_id=tenant_id, source_tool="prowler", rule_id=check,
            title=f"{title} ({resource})", severity=sev,
            asset_id=f"asset:cloud-{_safe_id(provider)}-{_safe_id(account)}", asset_label=f"{provider.upper()} account {account}",
            category="cloud", file=None, line=None, fingerprint=fp, remediation=rem, synthetic=synthetic,
        ))
    return out


PARSERS = {
    "gitleaks": parse_gitleaks,
    "trufflehog": parse_trufflehog,
    "trivy": parse_trivy,
    "semgrep": parse_semgrep,
    "prowler": parse_prowler,
}


def detect_tool(path: Path) -> Optional[str]:
    name = path.name.lower()
    for t in TOOLS:
        if name.startswith(t):
            return t
    return None


def parse_file(path: Path | str, tenant_id: str, tool: Optional[str] = None, project: str = "DataRobot-Demo") -> List[SecurityFinding]:
    p = Path(path)
    tool = tool or detect_tool(p)
    if tool not in PARSERS:
        return []
    if p.suffix.lower() == ".sarif":
        return []  # SARIF is kept for IDEs and code hosts; JSON is the ingest format
    return PARSERS[tool](_load_json_or_jsonl(p), tenant_id, project)


def collect(source: str = "auto", tenant_id: str = DEFAULT_TENANT, reports_dir: Path = REPORTS_DIR,
            fixtures_dir: Path = FIXTURES_DIR) -> Tuple[List[SecurityFinding], List[str]]:
    """source: reports | fixtures | auto (reports when present, fixtures otherwise)."""
    files: List[Path] = []
    if source in ("reports", "auto") and Path(reports_dir).is_dir():
        files = sorted(p for p in Path(reports_dir).glob("*.json") if detect_tool(p))
    if source == "fixtures" or (source == "auto" and not files):
        files = sorted(p for p in Path(fixtures_dir).glob("*.json") if detect_tool(p))
    found: Dict[str, SecurityFinding] = {}
    for f in files:
        for item in parse_file(f, tenant_id):
            found[item.finding_id] = item
    return list(found.values()), [str(f) for f in files]


# ----------------------------------------------------------------- storage

def _connect(db_path: Path | str) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.execute(
        """CREATE TABLE IF NOT EXISTS security_findings (
            finding_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, source_tool TEXT NOT NULL,
            rule_id TEXT, title TEXT, severity TEXT, status TEXT, asset_id TEXT, asset_label TEXT,
            category TEXT, file TEXT, line INTEGER, fingerprint TEXT, masked_preview TEXT,
            weakness_id TEXT, remediation TEXT, refs TEXT, synthetic INTEGER, updated_at TEXT)"""
    )
    return con


def store(findings: List[SecurityFinding], db_path: Path | str = DEFAULT_DB, replace_tenant: Optional[str] = None) -> int:
    con = _connect(db_path)
    if replace_tenant:
        con.execute("DELETE FROM security_findings WHERE tenant_id = ?", (replace_tenant,))
    ts = _now()
    for f in findings:
        con.execute(
            "INSERT OR REPLACE INTO security_findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f.finding_id, f.tenant_id, f.source_tool, f.rule_id, f.title, f.severity, f.status, f.asset_id,
             f.asset_label, f.category, f.file, f.line, f.fingerprint, f.masked_preview, f.weakness_id,
             f.remediation, json.dumps(f.references), int(f.synthetic), f.updated_at or ts),
        )
    con.commit()
    con.close()
    return len(findings)


def load(db_path: Path | str = DEFAULT_DB, tenant_id: Optional[str] = None) -> List[SecurityFinding]:
    if not Path(db_path).exists():
        return []
    con = _connect(db_path)
    q = "SELECT finding_id, tenant_id, source_tool, rule_id, title, severity, status, asset_id, asset_label, category, file, line, fingerprint, masked_preview, weakness_id, remediation, refs, synthetic, updated_at FROM security_findings"
    args: Tuple = ()
    if tenant_id:
        q += " WHERE tenant_id = ?"
        args = (tenant_id,)
    rows = con.execute(q + " ORDER BY finding_id", args).fetchall()
    con.close()
    out = []
    for r in rows:
        out.append(SecurityFinding(
            finding_id=r[0], tenant_id=r[1], source_tool=r[2], rule_id=r[3], title=r[4], severity=r[5], status=r[6],
            asset_id=r[7], asset_label=r[8], category=r[9], file=r[10], line=r[11], fingerprint=r[12],
            masked_preview=r[13], weakness_id=r[14], remediation=r[15], references=json.loads(r[16] or "[]"),
            synthetic=bool(r[17]), updated_at=r[18],
        ))
    return out


def summary(findings: List[SecurityFinding]) -> Dict[str, Dict[str, int]]:
    s: Dict[str, Dict[str, int]] = {}
    for f in findings:
        s.setdefault(f.source_tool, {k: 0 for k in SEVERITIES})
        s[f.source_tool][f.severity] = s[f.source_tool].get(f.severity, 0) + 1
    return s


# ----------------------------------------------------------------- graph merge

_UNSAFE_HINTS = [r"shut\s*down", r"shutdown", r"wipe", r"delete", r"drop\s+table", r"rm\s+-rf", r"reboot", r"exploit", r"payload", r"\bscan\b"]


def safe_remediation(text: str, category: str) -> str:
    """Keep drafts inside the checker's non destructive wording. Scanner advice that
    mentions destructive verbs is replaced with a neutral, reviewable instruction."""
    if text and not any(re.search(p, text, flags=re.IGNORECASE) for p in _UNSAFE_HINTS):
        return text
    if category == "secret":
        return SECRET_REMEDIATION
    return "Review the flagged code or configuration with its owner and fix it in a reviewed change, then rerun the security check."


def merge_into_graph(graph: Any, findings: List[SecurityFinding]) -> int:
    """Add finding -> asset -> tool nodes (asset SCANNED_BY tool, file asset PART_OF repo).
    Edge order keeps the asset as the first neighbour of each finding so drafts cite
    the finding and asset ids, which the checker accepts."""
    from .graph import Node, Edge
    if graph is None:
        return 0
    added = 0
    owner_id = "owner:team-appsec"

    def add_node(nid: str, ntype: str, label: str, tenant: str, props: Dict[str, Any]) -> str:
        """Shared nodes (tool, owner, weakness, asset) are per tenant: when the id is
        already owned by another tenant, a tenant suffixed id is used instead."""
        existing = graph._nodes.get(nid)
        if existing is not None and existing.tenant_id != tenant:
            nid = f"{nid}-t{hashlib.sha256(tenant.encode()).hexdigest()[:6]}"
            existing = graph._nodes.get(nid)
        if existing is None:
            graph._nodes[nid] = Node(id=nid, type=ntype, label=label, tenant_id=tenant, props=props)
        return nid

    def add_edge(src: str, etype: str, dst: str):
        e = Edge(src=src, type=etype, dst=dst)
        graph._edges.append(e)
        graph._adj.setdefault(src, []).append(e)
        graph._adj.setdefault(dst, []).append(Edge(src=dst, type=etype, dst=src))

    for f in findings:
        nid = f"finding:{f.finding_id}"
        if nid in graph._nodes:
            continue
        t = f.tenant_id
        # finding -> asset (the file, image or cloud account) -> tool; the file is PART_OF the repo
        root_id = add_node(f.asset_id, "asset", f.asset_label, t, {"kind": "repo" if f.asset_id.startswith("asset:repo-") else f.category})
        if f.file:
            fa = f"asset:file-{_safe_id(f.file, 48)}-{_fp(f.file)[:4]}"
            asset_id = add_node(fa, "asset", f.file, t, {"kind": "file", "path": f.file})
            if not any(e.dst == root_id for e in graph._adj.get(asset_id, [])):
                add_edge(asset_id, "PART_OF", root_id)
        else:
            asset_id = root_id
        owner = add_node(owner_id, "owner", "AppSec", t, {})
        tool_id = add_node(f"tool:{f.source_tool}", "tool", TOOL_LABELS.get(f.source_tool, f.source_tool), t, {"open_source": True})
        props = {
            "title": f.title, "theme": "code_security", "severity": f.severity, "gold_band": f.severity,
            "status": f.status, "asset_ids": [asset_id], "updated_at": f.updated_at or _now(),
            "source_tool": f.source_tool, "rule_id": f.rule_id, "category": f.category, "file": f.file,
            "line": f.line, "fingerprint": f.fingerprint, "masked_preview": f.masked_preview,
            "remediation": safe_remediation(f.remediation, f.category), "owner_id": owner, "references": f.references, "synthetic": f.synthetic,
        }
        add_node(nid, "finding", f.finding_id, t, props)
        add_edge(asset_id, "HAS_FINDING", nid)
        if f.weakness_id:
            wid = add_node(f.weakness_id, "weakness", f.weakness_id.split(":", 1)[1], t, {})
            add_edge(nid, "RELATED_WEAKNESS", wid)
        if not any(e.dst == tool_id for e in graph._adj.get(asset_id, [])):
            add_edge(asset_id, "SCANNED_BY", tool_id)
        if not any(e.dst == owner for e in graph._adj.get(root_id, [])):
            add_edge(root_id, "OWNED_BY", owner)
        added += 1
    return added


def remove_from_graph(graph: Any) -> None:
    """Drop previously merged security findings (used before a re-ingest)."""
    if graph is None:
        return
    drop = {nid for nid, n in graph._nodes.items() if n.type == "finding" and n.props.get("source_tool")}
    if not drop:
        return
    for nid in drop:
        graph._nodes.pop(nid, None)
    graph._edges[:] = [e for e in graph._edges if e.src not in drop and e.dst not in drop]
    graph._adj.clear()
    for e in graph._edges:
        graph._adj.setdefault(e.src, []).append(e)
        graph._adj.setdefault(e.dst, []).append(type(e)(src=e.dst, type=e.type, dst=e.src))
