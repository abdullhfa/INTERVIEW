"""
V4 step 5 — L2 / Compound Variant D trailing rescue.

Keeps the trailing-clause discriminator, carries prior-part subject context,
excludes parent / already-selected intents. Does not touch _MIN_ANSWER_SCORE
or general accept thresholds.

    python scripts/v4_step5_measure.py

PRIMARY
  mean gold-part coverage on compound clips rises
  at least one new gold part recovered (or coverage lift)
  surfaced_correct_rank1 on trailing drops does not fall (prefer rise)

GUARDS
  wrong = 0  (no newly selected non-gold intents)
  no compound clip loses gold coverage
  _MIN_ANSWER_SCORE unchanged (0.58)

Writes reports/V4_STEP5_VARIANT_D_COMPOUND.{md,json}.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V3 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V3_REPORT.json"

_TRAILING = re.compile(
    r"^\s*(?:and\s+|then\s+)?"
    r"(?:say|tell me|point me to|give me|explain|describe)?\s*"
    r"(when|what do you do|what you do|which|how|whether|why)\b",
    re.I,
)


def _cov(selected: list[str], gold: list[str]) -> float:
    g = set(gold or [])
    if not g:
        return 1.0
    return len(g & set(selected or [])) / len(g)


def _run_compounds(rows: list[dict], enabled: bool) -> dict[str, dict]:
    import app.services.compound_question_pipeline as CQP
    from app.services.compound_question_pipeline import resolve_compound_question
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index

    CQP.COMPOUND_VARIANT_D_RESCUE = enabled
    out: dict[str, dict] = {}
    for r in rows:
        transcript = r.get("transcript") or ""
        gold = list(r.get("expected_intent_ids") or [])
        res = resolve_compound_question(transcript)
        selected = list(res.selected_intents or [])
        gold_set = set(gold)
        sel_set = set(selected)
        rescues = [
            c
            for c in (res.candidate_intents or [])
            if isinstance(c, dict) and c.get("source") == "variant_d_trailing_rescue"
        ]
        # Offline-style surfaced_correct_rank1 on trailing clauses.
        # Exclude only parent + earlier parts (not this clause's accept) so
        # accept-vs-abstain does not erase a correct cosine surface.
        surfaced = 0
        trailing_cases = 0
        subs = list(res.sub_questions or [])
        cands = [c for c in (res.candidate_intents or []) if isinstance(c, dict)]

        def _accepted_id_for(sub_q: str) -> str | None:
            for c in cands:
                if (
                    c.get("sub_question") == sub_q
                    and c.get("accepted")
                    and c.get("intent_id")
                    and c.get("source") != "variant_d_trailing_rescue"
                ):
                    return str(c["intent_id"])
            for c in cands:
                if c.get("sub_question") == sub_q and c.get("accepted") and c.get("intent_id"):
                    return str(c["intent_id"])
            return None

        for i, sq in enumerate(subs):
            if i == 0 or not _TRAILING.match(sq):
                continue
            parent_id = None
            for j in range(i - 1, -1, -1):
                parent_id = _accepted_id_for(subs[j])
                if parent_id:
                    break
            if not parent_id or not semantic_intent_index.ready:
                continue
            trailing_cases += 1
            pe = question_bank.get(parent_id)
            exclude: set[str] = {parent_id}
            for j in range(i):
                eid = _accepted_id_for(subs[j])
                if eid:
                    exclude.add(eid)
            missing = gold_set - exclude
            hits = semantic_intent_index.top_k(sq, k=15)
            topic = pe.topic if pe else None

            def sort_key(h):
                same = 1 if (topic and h.profile and h.profile.topic == topic) else 0
                return (same, h.score)

            ranked = [
                h
                for h in sorted(hits, key=sort_key, reverse=True)
                if h.intent_id not in exclude
            ]
            if ranked and ranked[0].intent_id in missing:
                surfaced += 1

        out[r["sample_id"]] = {
            "selected": selected,
            "gold": gold,
            "coverage": round(_cov(selected, gold), 4),
            "gold_hit": len(gold_set & sel_set),
            "gold_n": len(gold_set),
            "wrong_ids": sorted(sel_set - gold_set),
            "rescues": [
                {
                    "sub_question": c.get("sub_question"),
                    "intent_id": c.get("intent_id"),
                    "is_gold": c.get("intent_id") in gold_set,
                }
                for c in rescues
            ],
            "surfaced_correct_rank1": surfaced,
            "trailing_cases": trailing_cases,
            "notes": list(res.decomposition_notes or []),
        }
    return out


def main() -> int:
    if not V3.is_file():
        print(f"missing {V3}")
        return 1

    import app.services.compound_question_pipeline as CQP
    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()

    # Guard: thresholds must stay frozen for this step.
    if abs(float(CQP._MIN_ANSWER_SCORE) - 0.58) > 1e-9:
        print(f"FAIL: _MIN_ANSWER_SCORE drifted to {CQP._MIN_ANSWER_SCORE}")
        return 2

    rows = [
        r
        for r in json.loads(V3.read_text(encoding="utf-8"))["results"]
        if not str(r.get("notes") or "").startswith("warmup:")
        and (r.get("question_type_label") or "") == "compound"
    ]
    print(f"compound clips: {len(rows)}")

    before = _run_compounds(rows, enabled=False)
    after = _run_compounds(rows, enabled=True)
    CQP.COMPOUND_VARIANT_D_RESCUE = True

    mean_b = sum(v["coverage"] for v in before.values()) / max(1, len(before))
    mean_a = sum(v["coverage"] for v in after.values()) / max(1, len(after))
    gold_parts_b = sum(v["gold_hit"] for v in before.values())
    gold_parts_a = sum(v["gold_hit"] for v in after.values())
    surf_b = sum(v["surfaced_correct_rank1"] for v in before.values())
    surf_a = sum(v["surfaced_correct_rank1"] for v in after.values())

    coverage_drops = [
        {
            "clip": k,
            "before": before[k]["coverage"],
            "after": after[k]["coverage"],
            "before_sel": before[k]["selected"],
            "after_sel": after[k]["selected"],
        }
        for k in before
        if after[k]["coverage"] + 1e-9 < before[k]["coverage"]
    ]
    coverage_gains = [
        {
            "clip": k,
            "before": before[k]["coverage"],
            "after": after[k]["coverage"],
            "new_gold": sorted(
                set(after[k]["selected"]) & set(after[k]["gold"])
                - set(before[k]["selected"])
            ),
            "rescues": after[k]["rescues"],
        }
        for k in before
        if after[k]["coverage"] > before[k]["coverage"] + 1e-9
    ]

    # Wrong = newly selected intents that are not gold (on any clip).
    new_wrongs: list[dict] = []
    for k in before:
        before_extra = set(before[k]["wrong_ids"])
        after_extra = set(after[k]["wrong_ids"])
        added = after_extra - before_extra
        if added:
            new_wrongs.append({"clip": k, "ids": sorted(added)})

    rescue_gold = sum(
        1
        for v in after.values()
        for r in v["rescues"]
        if r.get("is_gold")
    )
    rescue_wrong = sum(
        1
        for v in after.values()
        for r in v["rescues"]
        if r.get("intent_id") and not r.get("is_gold")
    )

    primary_ok = mean_a > mean_b + 1e-9 and gold_parts_a > gold_parts_b
    surf_ok = surf_a >= surf_b
    wrong_ok = len(new_wrongs) == 0 and rescue_wrong == 0
    no_drop_ok = len(coverage_drops) == 0
    threshold_ok = abs(float(CQP._MIN_ANSWER_SCORE) - 0.58) < 1e-9

    verdict = (
        "STEP5_PASS"
        if primary_ok and surf_ok and wrong_ok and no_drop_ok and threshold_ok
        else "STEP5_FAIL"
    )

    print(
        f"\n  mean gold-part coverage  {mean_b:.4f} -> {mean_a:.4f}"
        f"\n  gold parts hit (sum)     {gold_parts_b} -> {gold_parts_a}"
        f"\n  surfaced_correct_rank1   {surf_b} -> {surf_a}"
        f"\n  coverage gains           {len(coverage_gains)}"
        f"\n  coverage drops           {len(coverage_drops)}"
        f"\n  new wrong intents        {len(new_wrongs)}"
        f"\n  rescues gold/wrong       {rescue_gold}/{rescue_wrong}"
        f"\n  _MIN_ANSWER_SCORE        {CQP._MIN_ANSWER_SCORE}"
    )
    for g in coverage_gains:
        print(f"    gain {g['clip']} {g['before']:.3f}->{g['after']:.3f} +{g['new_gold']}")
    print(f"\n  VERDICT: {verdict}")

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "step": "v4 step 5 — L2 Variant D compound trailing rescue",
        "change": (
            "After harvest: for dropped/duplicate trailing (or pronoun-heavy) "
            "sub-questions, re-rank with clause kept + parent subject carry + "
            "same-topic soft filter + exclude parent/already; accept via existing "
            "_accept_match only (COMPOUND_VARIANT_D_RESCUE)."
        ),
        "untouched": [
            "_MIN_ANSWER_SCORE",
            "_MIN_KEEP_SCORE",
            "_MIN_MARGIN",
            "strong thresholds",
            "aliases",
            "weights",
            "L1 / semantic recovery gates",
        ],
        "verdict": verdict,
        "primary": {
            "mean_coverage_before": round(mean_b, 4),
            "mean_coverage_after": round(mean_a, 4),
            "gold_parts_before": gold_parts_b,
            "gold_parts_after": gold_parts_a,
            "surfaced_correct_rank1_before": surf_b,
            "surfaced_correct_rank1_after": surf_a,
            "coverage_gains": coverage_gains,
            "rescue_gold": rescue_gold,
            "rescue_wrong": rescue_wrong,
        },
        "guards": {
            "new_wrong_intents": new_wrongs,
            "coverage_drops": coverage_drops,
            "min_answer_score": CQP._MIN_ANSWER_SCORE,
        },
        "per_clip": {"before": before, "after": after},
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V4_STEP5_VARIANT_D_COMPOUND.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        "# V4 step 5 — L2 Variant D compound trailing rescue",
        "",
        f"**Verdict:** {verdict}",
        f"**Created:** {payload['created_at']}",
        "",
        payload["change"],
        "",
        "## Primary",
        "",
        "| metric | before | after |",
        "|---|---|---|",
        f"| mean gold-part coverage | {mean_b:.4f} | {mean_a:.4f} |",
        f"| gold parts hit (sum) | {gold_parts_b} | {gold_parts_a} |",
        f"| surfaced_correct_rank1 | {surf_b} | {surf_a} |",
        f"| rescue gold / wrong | — | {rescue_gold} / {rescue_wrong} |",
        "",
        "## Guards",
        "",
        "| guard | result |",
        "|---|---|",
        f"| new wrong intents | {len(new_wrongs)} "
        f"({'PASS' if wrong_ok else 'FAIL'}) |",
        f"| coverage drops | {len(coverage_drops)} "
        f"({'PASS' if no_drop_ok else 'FAIL'}) |",
        f"| _MIN_ANSWER_SCORE unchanged (0.58) | {CQP._MIN_ANSWER_SCORE} "
        f"({'PASS' if threshold_ok else 'FAIL'}) |",
        "",
    ]
    if coverage_gains:
        md += [
            "## Coverage gains",
            "",
            "| clip | before | after | new gold |",
            "|---|---|---|---|",
        ]
        md += [
            f"| {g['clip']} | {g['before']:.3f} | {g['after']:.3f} | "
            f"{', '.join(g['new_gold']) or '—'} |"
            for g in coverage_gains
        ]
        md += [""]
    (REPORTS / "V4_STEP5_VARIANT_D_COMPOUND.md").write_text(
        "\n".join(md), encoding="utf-8"
    )
    print(f"wrote {REPORTS / 'V4_STEP5_VARIANT_D_COMPOUND.md'}")
    return 0 if verdict == "STEP5_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
