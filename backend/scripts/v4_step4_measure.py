"""
V4 step 4 — conservative apply recovery (remeasure on post step-2/3 state).

When legacy blob-apply abstains, optionally apply the true-cosine hybrid #1
if embedding #1 agrees, agreement/final are high, and meaning_ok holds.
Forced weak mode — does not touch _MIN_ACCEPT / _MIN_ANSWER_SCORE.

    python scripts/v4_step4_measure.py

PRIMARY
  applied_and_gold on failing clips increases (ranking → real applies)

GUARDS
  no applied-intent change on currently-passing clips
  no NEW strong + non-gold (HC risk)
  no increase in wrong applied intents on previously-passing set

Writes reports/V4_STEP4_CONSERVATIVE_APPLY.{md,json}.
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


def _decide(enabled: bool, rows: list[dict]) -> dict[str, dict]:
    from app.services import semantic_intent_recovery as SIR
    from app.services.question_bank import question_bank

    SIR.SEMANTIC_BLOB_PROXY = "auto"
    SIR.SCORE_FLOOR_INCLUDE_CURRENT = True
    SIR.CONSERVATIVE_RANK_APPLY = enabled
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
            "hybrid_top5": hyb,
            "gold_rank_hybrid": next((i + 1 for i, x in enumerate(hyb) if x in gold), None),
            "applied_id": applied,
            "applied_mode": dec.match.mode if dec.match is not None else None,
            "applied_score": round(float(dec.match.score), 3) if dec.match is not None else 0.0,
            "applied_is_gold": bool(applied and applied in gold),
            "agreement": round(float(dec.agreement or 0), 3),
            "conservative": (dec.reason).startswith("recovered:conservative_rank"),
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
        print("!! semantic index not ready")
        return 1

    rows = [
        r
        for r in json.loads(V3.read_text(encoding="utf-8"))["results"]
        if not str(r.get("notes") or "").startswith("warmup:")
    ]
    passing = {r["sample_id"] for r in rows if r["intent_ok"]}
    failing = {r["sample_id"] for r in rows if not r["intent_ok"]}
    print(f"clips {len(rows)}  passing {len(passing)}  failing {len(failing)}")

    before = _decide(False, rows)
    after = _decide(True, rows)
    SIR.CONSERVATIVE_RANK_APPLY = True

    def agg(dec: dict, ids: set[str]) -> dict:
        sub = {k: v for k, v in dec.items() if k in ids}
        return {
            "n": len(sub),
            "gold_in_hybrid_top5": sum(1 for v in sub.values() if v["gold_rank_hybrid"]),
            "gold_at_hybrid_1": sum(1 for v in sub.values() if v["gold_rank_hybrid"] == 1),
            "applied_and_gold": sum(1 for v in sub.values() if v["applied_is_gold"]),
            "applied_wrong": sum(
                1
                for v in sub.values()
                if v["applied_id"] and not v["applied_is_gold"]
            ),
            "conservative_applies": sum(1 for v in sub.values() if v["conservative"]),
        }

    fb, fa = agg(before, failing), agg(after, failing)
    pb, pa = agg(before, passing), agg(after, passing)

    changed = [
        {
            "clip": k,
            "before": before[k]["applied_id"],
            "after": after[k]["applied_id"],
            "was_passing": k in passing,
            "after_gold": after[k]["applied_is_gold"],
            "reason": after[k]["reason"],
        }
        for k in before
        if before[k]["applied_id"] != after[k]["applied_id"]
    ]
    broke_passing = [c for c in changed if c["was_passing"]]
    newly_gold = [
        c for c in changed if c["after_gold"] and c["after"] and not before[c["clip"]]["applied_is_gold"]
    ]

    def _hc_bad(row: dict) -> bool:
        return (
            row["applied_mode"] == "strong"
            and not row["applied_is_gold"]
            and row["applied_score"] >= 0.70
        )

    hc_new = [
        {"clip": k, "id": after[k]["applied_id"], "score": after[k]["applied_score"]}
        for k in after
        if _hc_bad(after[k]) and not _hc_bad(before[k])
    ]

    primary_ok = fa["applied_and_gold"] > fb["applied_and_gold"]
    ranking_ok = (
        fa["gold_in_hybrid_top5"] >= fb["gold_in_hybrid_top5"]
        and fa["gold_at_hybrid_1"] >= fb["gold_at_hybrid_1"]
    )
    # Wrong applies on the passing cohort must not rise.
    passing_wrong_ok = pa["applied_wrong"] <= pb["applied_wrong"]
    verdict = (
        "STEP4_PASS"
        if primary_ok and ranking_ok and passing_wrong_ok and not broke_passing and not hc_new
        else "STEP4_FAIL"
    )

    print(
        f"\n  failing  applied_gold {fb['applied_and_gold']} -> {fa['applied_and_gold']}"
        f"   wrong {fb['applied_wrong']} -> {fa['applied_wrong']}"
        f"   conservative {fa['conservative_applies']}"
    )
    print(
        f"  failing  rank top5 {fb['gold_in_hybrid_top5']} -> {fa['gold_in_hybrid_top5']}"
        f"   @1 {fb['gold_at_hybrid_1']} -> {fa['gold_at_hybrid_1']}"
    )
    print(
        f"  passing  applied_gold {pb['applied_and_gold']} -> {pa['applied_and_gold']}"
        f"   wrong {pb['applied_wrong']} -> {pa['applied_wrong']}"
    )
    print(
        f"  applied intent changed on {len(changed)} clips "
        f"({len(broke_passing)} currently passing); newly gold {len(newly_gold)}"
    )
    print(f"  HC risk NEW: {len(hc_new)}")
    print(f"\n  VERDICT: {verdict}")

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "step": "v4 step 4 — conservative apply from true-cosine ranking",
        "change": (
            "When legacy blob-apply abstains: if hybrid-rank #1 == semantic #1, "
            f"final>={0.45}, agree>={0.88}, meaning_ok, margin ok, and current is not "
            "strong → apply that intent as weak only "
            "(CONSERVATIVE_RANK_APPLY)."
        ),
        "untouched": [
            "_MIN_ACCEPT",
            "_MIN_ANSWER_SCORE",
            "strong thresholds",
            "aliases",
            "weights",
            "L2 / compound",
        ],
        "verdict": verdict,
        "primary": {
            "failing_before": fb,
            "failing_after": fa,
            "passing_before": pb,
            "passing_after": pa,
            "newly_gold": newly_gold,
        },
        "guards": {
            "changed_applied": changed,
            "changed_on_currently_passing": broke_passing,
            "hc_risk_new": hc_new,
        },
        "per_clip": {"before": before, "after": after},
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V4_STEP4_CONSERVATIVE_APPLY.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        "# V4 step 4 — conservative apply recovery",
        "",
        f"**Verdict:** {verdict}",
        f"**Created:** {payload['created_at']}",
        "",
        payload["change"],
        "",
        "## Primary — failing clips",
        "",
        "| metric | before | after |",
        "|---|---|---|",
        f"| applied and gold | {fb['applied_and_gold']} | {fa['applied_and_gold']} |",
        f"| applied wrong | {fb['applied_wrong']} | {fa['applied_wrong']} |",
        f"| gold in hybrid top-5 | {fb['gold_in_hybrid_top5']} | {fa['gold_in_hybrid_top5']} |",
        f"| gold at hybrid #1 | {fb['gold_at_hybrid_1']} | {fa['gold_at_hybrid_1']} |",
        f"| conservative applies | {fb['conservative_applies']} | {fa['conservative_applies']} |",
        "",
        "## Guards",
        "",
        "| guard | result |",
        "|---|---|",
        f"| applied intent changed on currently-passing | {len(broke_passing)} "
        f"({'PASS' if not broke_passing else 'FAIL'}) |",
        f"| new strong + non-gold | {len(hc_new)} "
        f"({'PASS' if not hc_new else 'FAIL'}) |",
        f"| passing-cohort wrong applies | {pb['applied_wrong']} -> {pa['applied_wrong']} "
        f"({'PASS' if passing_wrong_ok else 'FAIL'}) |",
        "",
    ]
    if newly_gold:
        md += [
            "## Newly applied gold",
            "",
            "| clip | after id | reason |",
            "|---|---|---|",
        ]
        md += [f"| {c['clip']} | {c['after']} | {c['reason']} |" for c in newly_gold]
        md += [""]
    if broke_passing:
        md += [
            "## Broken passing clips",
            "",
            "| clip | before | after |",
            "|---|---|---|",
        ]
        md += [f"| {c['clip']} | {c['before']} | {c['after']} |" for c in broke_passing]
        md += [""]
    (REPORTS / "V4_STEP4_CONSERVATIVE_APPLY.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORTS / 'V4_STEP4_CONSERVATIVE_APPLY.md'}")
    return 0 if verdict == "STEP4_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
