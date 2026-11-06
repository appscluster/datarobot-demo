#!/usr/bin/env python3
"""Ingest scanner reports into ThreatAI (SQLite + GraphRAG).

  python3 scripts/security_ingest.py --source auto      # reports/security/*.json, else fixtures
  python3 scripts/security_ingest.py --source fixtures  # synthetic fixtures only
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from agent import graph as graph_mod  # noqa: E402
from agent import security_sources as sec  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["auto", "reports", "fixtures"], default="auto")
    ap.add_argument("--tenant", default=os.environ.get("DEMO_TENANT", sec.DEFAULT_TENANT))
    ap.add_argument("--db", default=os.environ.get("SECURITY_DB", str(sec.DEFAULT_DB)))
    args = ap.parse_args()

    findings, files = sec.collect(args.source, args.tenant)
    sec.store(findings, args.db, replace_tenant=args.tenant)
    g = graph_mod.load_seed(ROOT / "data" / "seed_graph.json")
    sec.merge_into_graph(g, sec.load(args.db))
    graph_mod.persist_to_sqlite(Path("backend/var/graph.db"))
    print(f"ingested {len(findings)} findings for {args.tenant} from {len(files)} files")
    for f in files:
        print(f"  {Path(f).relative_to(ROOT) if Path(f).is_absolute() else f}")
    print(json.dumps(sec.summary(findings), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
