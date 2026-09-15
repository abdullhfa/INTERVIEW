"""
CLI for the E2E loopback suites (the module has no entry point of its own).

    python scripts/run_suite.py short_length
    python scripts/run_suite.py compound_dev
    python scripts/run_suite.py short_length --limit 8
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("suite")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    from app.services.interview_e2e_loopback import run_e2e_suite

    payload = asyncio.run(run_e2e_suite(suite=args.suite, limit=args.limit))
    summary = payload.get("summary") or {}
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, (dict, list))}, indent=2))
    for key in ("json_path", "html_path", "report_json", "report_html"):
        if payload.get(key):
            print(f"{key}: {payload[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
