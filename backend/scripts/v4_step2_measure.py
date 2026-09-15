"""
V4 step 2 — measure the hybrid-ranking fix (conservative blob-proxy split).

Runs the real `recover_semantic_intent` over every scored v3 transcript twice —
once with the pre-v4 behaviour (`always`) and once with the fix (`auto`) — and
diffs the decisions. Nothing else is changed: no weight, threshold, alias, apply
gate or `_MIN_ANSWER_SCORE`.

Conservative `auto` (warm index):
  • hybrid_top5 ranking uses real cosine only (no blob fill in `sem`)
  • apply decision still uses the legacy blob fill — so currently-passing
    recovery applies do not flip, and strong+non-gold from ranking-only
    changes cannot appear

    python scripts/v4_step2_measure.py

Writes reports/V4_STEP2_HYBRID_RANKING.{md,json}.

WHAT SUCCESS LOOKS LIKE FOR THIS STEP
The apply gate is deliberately untouched, so the end-to-end intent rate is
expected to stay roughly flat. Step 2 is judged on ranking, not on pass rate:

  PRIMARY   gold reaches the hybrid top-5 more often, and rank 1 more often,
            on the failing clips
  GUARD     no clip that currently passes changes its applied intent
  GUARD     no applied match becomes `strong` on a non-gold intent (HC risk)

If the primary improves and both guards hold, step 2 is done and step 3 (the
conservative apply recovery) is what converts ranking into pass rate.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V3 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V3_REPORT.json"


def _decide(mode: str, rows: list[dict]) -> dict[str, dict]:
    """Re-run recovery for every clip under one proxy mode."""
    from app.services import semantic_intent_recovery as SIR
    from app.services.question_bank import question_bank

    SIR.SEMANTIC_BLOB_PROXY = mode
    out: dict[str, dict] = {}
    for r in rows:
        transcript = r.get("transcript") or ""
        gold = set(r.get("expected_intent_ids") or [])
        current = question_bank.match(transcript) if transcript.strip() else None
        dec = SIR.recover_semantic_intent(transcript, current)
        hyb = [d["id"] for d in (dec.hybrid_top5 or [])]
        applied = dec.match.entry.id if dec.match is not None else None
        out[r["sample_id"]] = {
            "reason": dec.reason,
            "abstain_reason": dec.abstain_reason,
            "hybrid_top5": hyb,
            "gold_rank_hybrid": next((i + 1 for i, x in enumerate(hyb) if x in gold), None),
            "applied_id": applied,
            "applied_mode": dec.match.mode if dec.match is not None else None,
            "applied_score": round(float(dec.match.score), 3) if dec.match is not None else 0.0,
            "applied_is_gold": bool(applied and applied in gold),
            "agreement": round(float(dec.agreement or 0), 3),
            "reranker_used": (dec.reranker_used),
        }
    return out


def main() -> int:
    if not V3.is_file():
        print(f"missing {V3}")
        return 1
    from app.services import semantic_intent_recovery as SIR
    from app.services.semantic_intent_index import semantic_intent_index
    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()
    if not semantic_intent_index.ready:
        print("!! semantic index not ready — with a cold index `auto` and `always` are")
        print("   identical by design, so this measurement is meaningless. Fix the")
        print("   embedder first.")
        return 1

    rows = [r for r in json.loads(V3.read_text(encoding="utf-8"))["results"]
            if not str(r.get("notes") or "").startswith("warmup:")]
    passing = {r["sample_id"] for r in rows if r["intent_ok"]}
    failing = {r["sample_id"] for r in rows if not r["intent_ok"]}
    print(f"clips {len(rows)}  passing {len(passing)}  failing {len(failing)}")

    before = _decide("always", rows)
    after = _decide("auto", rows)
    SIR.SEMANTIC_BLOB_PROXY = "auto"

    def agg(dec: dict, ids: set[str]) -> dict:
        sub = {k: v for k, v in dec.items() if k in ids}
        return {
            "n": len(sub),
            "gold_in_hybrid_top5": sum(1 for v in sub.values() if v["gold_rank_hybrid"]),
            "gold_at_hybrid_1": sum(1 for v in sub.values() if v["gold_rank_hybrid"] == 1),
            "applied_and_gold": sum(1 for v in sub.values() if v["applied_is_gold"]),
            "abstained": sum(1 for v in sub.values()
                             if str(v["reason"]).startswith("abstain")),
        }

    primary = {"failing_before": agg(before, failing), "failing_after": agg(after, failing),
               "passing_before": agg(before, passing), "passing_after": agg(after, passing)}

    changed_applied = [
        {"clip": k, "before": before[k]["applied_id"], "after": after[k]["applied_id"],
         "was_passing": k in passing}
        for k in before
        if before[k]["applied_id"] != after[k]["applied_id"]
    ]
    broke_passing = [c for c in changed_applied if c["was_passing"]]

    def _hc_bad(row: dict) -> bool:
        return (
            row["applied_mode"] == "strong"
            and not row["applied_is_gold"]
            and row["applied_score"] >= 0.70
        )

    # "becomes" — only NEW strong+non-gold applies, not pre-existing ones.
    hc_risk = [
        {"clip": k, "id": after[k]["applied_id"], "score": after[k]["applied_score"],
         "before_id": before[k]["applied_id"], "before_mode": before[k]["applied_mode"]}
        for k in after
        if _hc_bad(after[k]) and not _hc_bad(before[k])
    ]
    rank_moves = [
        {"clip": k, "before": before[k]["gold_rank_hybrid"], "after": after[k]["gold_rank_hybrid"]}
        for k in before
        if before[k]["gold_rank_hybrid"] != after[k]["gold_rank_hybrid"]
    ]

    fb, fa = primary["failing_before"], primary["failing_after"]
    primary_ok = (fa["gold_in_hybrid_top5"] > fb["gold_in_hybrid_top5"]
                  or fa["gold_at_hybrid_1"] > fb["gold_at_hybrid_1"])
    verdict = ("STEP2_PASS" if primary_ok and not broke_passing and not hc_risk
               else "STEP2_FAIL")

    print(f"\n  failing clips  gold_in_top5 {fb['gold_in_hybrid_top5']} -> {fa['gold_in_hybrid_top5']}"
          f"   gold@1 {fb['gold_at_hybrid_1']} -> {fa['gold_at_hybrid_1']}"
          f"   applied_gold {fb['applied_and_gold']} -> {fa['applied_and_gold']}")
    pb, pa = primary["passing_before"], primary["passing_after"]
    print(f"  passing clips  gold_in_top5 {pb['gold_in_hybrid_top5']} -> {pa['gold_in_hybrid_top5']}"
          f"   applied_gold {pb['applied_and_gold']} -> {pa['applied_and_gold']}")
    print(f"  applied intent changed on {len(changed_applied)} clips "
          f"({len(broke_passing)} of them currently passing)")
    print(f"  HC risk NEW (strong + non-gold + score>=0.70): {len(hc_risk)}")
    print(f"  gold hybrid rank moved on {len(rank_moves)} clips")
    print(f"\n  VERDICT: {verdict}")

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "step": "v4 step 2 — hybrid ranking (conservative: rank without blob, apply with legacy blob)",
        "change": "semantic_intent_recovery SEMANTIC_BLOB_PROXY=auto on a warm index: "
                  "hybrid_top5 ranks on real cosine only; apply decision still uses the "
                  "pre-v4 blob fill so successful recovery applies do not flip. "
                  "Cold index / SEMANTIC_BLOB_PROXY=always keep full legacy behaviour.",
        "untouched": ["_W_* weights", "_MIN_ACCEPT / accept_floor", "_MIN_ANSWER_SCORE",
                      "apply gate", "aliases", "semantic top_k", "STT", "compound architecture"],
        "verdict": verdict,
        "primary": primary,
        "guards": {"applied_intent_changed": changed_applied,
                   "changed_on_currently_passing": broke_passing,
                   "hc_risk": hc_risk},
        "gold_rank_moves": rank_moves,
        "per_clip": {"before": before, "after": after},
    }
    (REPORTS / "V4_STEP2_HYBRID_RANKING.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# V4 step 2 — hybrid ranking", "",
        f"**Verdict:** {verdict}", f"**Created:** {payload['created_at']}", "",
        "Change: warm+auto splits ranking from apply — hybrid_top5 drops the blob",
        "proxy (real cosine only); apply still uses the legacy blob fill. Cold index",
        "and `always` keep pre-v4 behaviour. No thresholds or apply gates touched.", "",
        "## Primary — ranking on the failing clips", "",        "| metric | before | after |", "|---|---|---|",
        f"| gold in hybrid top-5 | {fb['gold_in_hybrid_top5']} | {fa['gold_in_hybrid_top5']} |",
        f"| gold at hybrid rank 1 | {fb['gold_at_hybrid_1']} | {fa['gold_at_hybrid_1']} |",
        f"| applied and gold | {fb['applied_and_gold']} | {fa['applied_and_gold']} |",
        "", "## Guards", "",
        "| guard | result |", "|---|---|",
        f"| applied intent changed on a currently-passing clip | {len(broke_passing)} "
        f"({'PASS' if not broke_passing else 'FAIL'}) |",
        f"| new strong + non-gold applies (HC risk) | {len(hc_risk)} "
        f"({'PASS' if not hc_risk else 'FAIL'}) |",
        "",
        "## Note on pass rate", "",
        "The apply gate was deliberately left alone, so `applied_and_gold` and the overall",
        "intent rate are expected to stay flat. Step 2 buys ranking; step 3 converts it.",
        "",
    ]
    if broke_passing:
        md += ["## Clips whose applied intent changed while passing", "",
               "| clip | before | after |", "|---|---|---|"]
        md += [f"| {c['clip']} | {c['before']} | {c['after']} |" for c in broke_passing]
        md += [""]
    (REPORTS / "V4_STEP2_HYBRID_RANKING.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORTS / 'V4_STEP2_HYBRID_RANKING.md'}")
    return 0 if verdict == "STEP2_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
