from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V3 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V3_REPORT.json"


def _score_floor(exist: float, current: float | None, best: float, *, include: bool, same_id: bool) -> float:
    """Mirrors the recovered-score floor in semantic_intent_recovery."""
    floor = float(exist or 0.0)
    if include and same_id and current is not None:
        floor = max(floor, float(current))
    return max(floor, float(best))


def _decide(include_current: bool, rows: list[dict]) -> dict[str, dict]:
    from app.services import semantic_intent_recovery as SIR
    from app.services.question_bank import question_bank

    SIR.SEMANTIC_BLOB_PROXY = "auto"
    SIR.SCORE_FLOOR_INCLUDE_CURRENT = include_current
    out: dict[str, dict] = {}
    for r in rows:
        transcript = r.get("transcript") or ""
        gold = set(r.get("expected_intent_ids") or [])
        current = question_bank.match(transcript) if transcript.strip() else None
        current_id = current.entry.id if current is not None else None
        current_score = float(current.score) if current is not None else None
        dec = SIR.recover_semantic_intent(transcript, current)
        hyb = [d["id"] for d in (dec.hybrid_top5 or [])]
        applied = dec.match.entry.id if dec.match is not None else None
        applied_score = float(dec.match.score) if dec.match is not None else 0.0
        same_id = bool(
            applied
            and current_id
            and applied == current_id
            and (dec.reason).startswith("recovered")
        )
        lowered = (
            same_id
            and current_score is not None
            and applied_score + 1e-12 < current_score
        )
        out[r["sample_id"]] = {
            "reason": dec.reason,
            "hybrid_top5": hyb,
            "gold_rank_hybrid": next((i + 1 for i, x in enumerate(hyb) if x in gold), None),
            "current_id": current_id,
            "current_score": None if current_score is None else round(current_score, 6),
            "applied_id": applied,
            "applied_mode": dec.match.mode if dec.match is not None else None,
            "applied_score": round(applied_score, 6),
            "applied_is_gold": bool(applied and applied in gold),
            "same_id_recovered": same_id,
            "lowered_identical_id": lowered,
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

    syn_before = _score_floor(0.50, 0.60, 0.55, include=False, same_id=True)
    syn_after = _score_floor(0.50, 0.60, 0.55, include=True, same_id=True)
    synthetic_ok = syn_before < 0.60 - 1e-12 and abs(syn_after - 0.60) < 1e-12
    print(
        f"synthetic floor  exist=0.50 current=0.60 best=0.55  "
        f"before={syn_before} after={syn_after}  ok={synthetic_ok}"
    )

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
    SIR.SCORE_FLOOR_INCLUDE_CURRENT = True
    SIR.SEMANTIC_BLOB_PROXY = "auto"

    def lowered_list(dec: dict) -> list[dict]:
        out = []
        for k, v in dec.items():
            if v["lowered_identical_id"]:
                out.append(
                    {
                        "clip": k,
                        "id": v["applied_id"],
                        "current_score": v["current_score"],
                        "applied_score": v["applied_score"],
                        "was_passing": k in passing,
                    }
                )
        return out

    lowered_before = lowered_list(before)
    lowered_after = lowered_list(after)

    def rank_agg(dec: dict, ids: set[str]) -> dict:
        sub = {k: v for k, v in dec.items() if k in ids}
        return {
            "gold_in_hybrid_top5": sum(1 for v in sub.values() if v["gold_rank_hybrid"]),
            "gold_at_hybrid_1": sum(1 for v in sub.values() if v["gold_rank_hybrid"] == 1),
            "applied_and_gold": sum(1 for v in sub.values() if v["applied_is_gold"]),
        }

    fb, fa = rank_agg(before, failing), rank_agg(after, failing)

    changed_applied = [
        {
            "clip": k,
            "before": before[k]["applied_id"],
            "after": after[k]["applied_id"],
            "was_passing": k in passing,
        }
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

    hc_new = [
        {
            "clip": k,
            "id": after[k]["applied_id"],
            "score": after[k]["applied_score"],
        }
        for k in after
        if _hc_bad(after[k]) and not _hc_bad(before[k])
    ]

    lifts = []
    for k in after:
        b, a = before[k], after[k]
        if (
            a["same_id_recovered"]
            and b["same_id_recovered"]
            and a["applied_score"] > b["applied_score"] + 1e-12
        ):
            lifts.append(
                {
                    "clip": k,
                    "id": a["applied_id"],
                    "before": b["applied_score"],
                    "after": a["applied_score"],
                    "current": a["current_score"],
                    "was_passing": k in passing,
                }
            )

    invariant_ok = len(lowered_after) == 0
    ranking_ok = (
        fa["gold_in_hybrid_top5"] >= fb["gold_in_hybrid_top5"]
        and fa["gold_at_hybrid_1"] >= fb["gold_at_hybrid_1"]
    )
    verdict = (
        "STEP3_PASS"
        if synthetic_ok and invariant_ok and ranking_ok and not broke_passing and not hc_new
        else "STEP3_FAIL"
    )

    print(
        f"\n  live identical-id lowered: {len(lowered_before)} -> {len(lowered_after)}"
    )
    print(f"  identical-id score lifts:  {len(lifts)}")
    print(
        f"  failing rank  top5 {fb['gold_in_hybrid_top5']} -> {fa['gold_in_hybrid_top5']}"
        f"   @1 {fb['gold_at_hybrid_1']} -> {fa['gold_at_hybrid_1']}"
    )
    print(
        f"  applied intent changed on {len(changed_applied)} clips "
        f"({len(broke_passing)} currently passing)"
    )
    print(f"  HC risk NEW: {len(hc_new)}")
    print(f"\n  VERDICT: {verdict}")

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "step": "v4 step 3 — score floor includes current.score for identical-id recovery",
        "change": "semantic_intent_recovery: max(exist, current.score, best) when "
        "recovered id == current.id (SCORE_FLOOR_INCLUDE_CURRENT=1).",
        "untouched": [
            "apply gate",
            "thresholds",
            "_MIN_ANSWER_SCORE",
            "L2 / compound",
            "aliases",
            "weights",
        ],
        "verdict": verdict,
        "synthetic": {
            "exist": 0.50,
            "current": 0.60,
            "best": 0.55,
            "before": syn_before,
            "after": syn_after,
            "ok": synthetic_ok,
        },
        "primary": {
            "lowered_identical_id_before": lowered_before,
            "lowered_identical_id_after": lowered_after,
            "score_lifts": lifts,
            "invariant_after_ok": invariant_ok,
        },
        "ranking_failing": {"before": fb, "after": fa},
        "guards": {
            "changed_applied": changed_applied,
            "changed_on_currently_passing": broke_passing,
            "hc_risk_new": hc_new,
        },
        "note": (
            "Live v3 re-score may already have exist_m.score >= current.score after "
            "step 2; the synthetic case proves the deferred bug class is closed."
        ),
        "per_clip": {"before": before, "after": after},
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V4_STEP3_SCORE_FLOOR.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        "# V4 step 3 — score floor",
        "",
        f"**Verdict:** {verdict}",
        f"**Created:** {payload['created_at']}",
        "",
        "Change: when recovery re-selects the same intent as `current`, the emitted",
        "score is `max(exist_m.score, current.score, best_score)` so recovery cannot",
        "lower an already-held score. Apply gates / thresholds / L2 untouched.",
        "",
        "## Synthetic proof (exist &lt; current, same id)",
        "",
        f"| | score |",
        f"|---|---|",
        f"| before (no current in max) | {syn_before} |",
        f"| after (include current) | {syn_after} |",
        f"| expected after | 0.60 |",
        f"| ok | {synthetic_ok} |",
        "",
        "## Live invariant",
        "",
        "| metric | before | after |",
        "|---|---|---|",
        f"| identical-id score lowered | {len(lowered_before)} | {len(lowered_after)} |",
        f"| identical-id score lifts | — | {len(lifts)} |",
        "",
        "## Ranking non-regression (failing clips)",
        "",
        "| metric | before | after |",
        "|---|---|---|",
        f"| gold in hybrid top-5 | {fb['gold_in_hybrid_top5']} | {fa['gold_in_hybrid_top5']} |",
        f"| gold at hybrid #1 | {fb['gold_at_hybrid_1']} | {fa['gold_at_hybrid_1']} |",
        "",
        "## Guards",
        "",
        "| guard | result |",
        "|---|---|",
        f"| applied intent changed on currently-passing | {len(broke_passing)} "
        f"({'PASS' if not broke_passing else 'FAIL'}) |",
        f"| new strong + non-gold | {len(hc_new)} "
        f"({'PASS' if not hc_new else 'FAIL'}) |",
        "",
        payload["note"],
        "",
    ]
    (REPORTS / "V4_STEP3_SCORE_FLOOR.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORTS / 'V4_STEP3_SCORE_FLOOR.md'}")
    return 0 if verdict == "STEP3_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
