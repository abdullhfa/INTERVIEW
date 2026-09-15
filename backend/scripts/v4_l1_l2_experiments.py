"""
V4 pre-code experiments L1 and L2 — measurement only, no pipeline change.

    python scripts/v4_l1_l2_experiments.py
    python scripts/v4_l1_l2_experiments.py --only l1
    python scripts/v4_l1_l2_experiments.py --only l2

Writes reports/V4_L1_L2_EXPERIMENTS.{json,md}.

L1 — separates Candidate Generation vs Hybrid Ranking vs Apply gates:
  - gold semantic rank over full index (buckets 1–5 / 6–25 / >25)
  - gold in hybrid top-5 vs applied
  - VERDICT with next-step recommendation
  - variants A/B/C (current / no blob-proxy / score-floor observation)

L2 — trailing clauses. Variants:
  A  clause alone (current)
  B  topic_hint = parent topic
  C  pronoun → parent subject substitution
  D  clause kept + parent topic soft context + parent intent excluded;
     rank1 judged by real embedding cosine (surfaced_correct_rank1)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V3 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V3_REPORT.json"


def _load_v3() -> list[dict]:
    d = json.loads(V3.read_text(encoding="utf-8"))
    return [r for r in d["results"] if not str(r.get("notes") or "").startswith("warmup:")]


def _gold_rank(hits: list, gold: set[str]) -> Optional[int]:
    for i, h in enumerate(hits):
        hid = h.intent_id if hasattr(h, "intent_id") else getattr(h, "entry", None)
        if hid is None and hasattr(h, "entry"):
            hid = h.entry.id
        if isinstance(hid, str) and hid in gold:
            return i + 1
        if hasattr(h, "entry") and h.entry.id in gold:
            return i + 1
    return None


def _bucket(rank: Optional[int]) -> str:
    if rank is None:
        return "absent"
    if rank <= 5:
        return "1-5"
    if rank <= 25:
        return "6-25"
    return ">25"


# ───────────────────────────── L1 ─────────────────────────────
def run_l1() -> dict:
    from app.services import semantic_intent_recovery as SIR
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index
    from app.services.warm_start import warm_system_blocking

    print("  warming…", flush=True)
    warm_system_blocking()
    if not semantic_intent_index.ready:
        print("!! semantic index not ready — aborting L1", flush=True)
        return {"error": "semantic index not ready"}

    n_intents = len(semantic_intent_index._ids)  # noqa: SLF001 — measurement
    deep_k = min(n_intents, max(50, n_intents))

    rows = _load_v3()
    # Focus on the L1 failure class, but keep all intent fails for pool stats.
    failures = [
        r
        for r in rows
        if not r.get("intent_ok")
        and (r.get("question_type_label") or "") == "indirect_paraphrase"
    ]
    if not failures:
        failures = [r for r in rows if not r.get("intent_ok")]

    print(f"  L1 clips: {len(failures)} (deep_k={deep_k}, bank={n_intents})", flush=True)

    depth_rows: list[dict] = []
    for r in failures:
        transcript = (r.get("raw_transcript") or r.get("transcript") or "").strip()
        gold = set(r.get("expected_intent_ids") or [])
        hits = semantic_intent_index.top_k(transcript, k=deep_k) if transcript else []
        rank = _gold_rank(hits, gold)
        bucket = _bucket(rank)
        # hybrid from the official v3 log (not re-scored) for pool presence
        sem_log = r.get("semantic_recovery") or {}
        hyb = [x.get("id") for x in (sem_log.get("hybrid_top5") or [])]
        sem5 = [x.get("id") for x in (sem_log.get("semantic_top5") or [])]
        gold_in_hyb = any(g in hyb for g in gold)
        gold_in_sem5 = any(g in sem5 for g in gold)
        hyb_rank = next((i + 1 for i, x in enumerate(hyb) if x in gold), None)
        depth_rows.append(
            {
                "id": r.get("sample_id"),
                "gold": sorted(gold),
                "semantic_rank": rank,
                "semantic_bucket": bucket,
                "gold_in_semantic_top5": gold_in_sem5,
                "gold_in_hybrid_top5": gold_in_hyb,
                "hybrid_rank": hyb_rank,
                "abstain_reason": sem_log.get("abstain_reason") or sem_log.get("reason"),
                "hyb_top1": (hyb[0] if hyb else None),
                "transcript": transcript[:120],
            }
        )
        print(
            f"    {r.get('sample_id')}: sem_rank={rank} bucket={bucket} "
            f"hyb_rank={hyb_rank} gold_in_hyb={gold_in_hyb}",
            flush=True,
        )

    buckets = Counter(d["semantic_bucket"] for d in depth_rows)
    n = len(depth_rows) or 1
    in_pool_sem5 = sum(1 for d in depth_rows if d["gold_in_semantic_top5"])
    in_pool_hyb = sum(1 for d in depth_rows if d["gold_in_hybrid_top5"])
    at_hyb1 = sum(1 for d in depth_rows if d.get("hybrid_rank") == 1)
    # Cases where retrieval found gold beyond default top-5 window
    in_6_25 = buckets.get("6-25", 0)
    beyond_25 = buckets.get(">25", 0) + buckets.get("absent", 0)
    in_1_5 = buckets.get("1-5", 0)

    # VERDICT: pick the dominant bottleneck among failures
    # Priority follows the user's decision tree.
    if in_6_25 >= max(in_1_5, beyond_25) and in_6_25 > 0:
        primary = "CANDIDATE_GENERATION_DEPTH"
        next_step = "Raise semantic retrieval depth/top_k (gold mostly rank 6–25)."
    elif beyond_25 > in_1_5 and beyond_25 >= in_6_25:
        primary = "PROFILE_OR_EMBEDDING_QUALITY"
        next_step = "Deep track: profile/embedding quality (gold mostly >25 or absent)."
    elif in_pool_hyb >= max(1, n // 3) and at_hyb1 < in_pool_hyb:
        primary = "HYBRID_RANKING"
        next_step = "Gold reaches hybrid pool but loses rank — fix hybrid ranking/mix."
    elif at_hyb1 > 0 and at_hyb1 == in_pool_hyb:
        primary = "APPLY_GATES"
        next_step = "Gold at hybrid#1 but not applied — inspect apply/abstain gates (do not touch yet)."
    elif in_pool_sem5 > in_pool_hyb:
        primary = "HYBRID_RANKING"
        next_step = "Gold in semantic top-5 but demoted out of hybrid — hybrid demotion."
    else:
        primary = "MIXED"
        next_step = "Split failure modes; see per-clip table before choosing one lever."

    # Refine: if gold in sem top5 often but not hybrid → hybrid demotion overrides depth
    demoted = sum(
        1
        for d in depth_rows
        if d["gold_in_semantic_top5"] and not d["gold_in_hybrid_top5"]
    )
    gate_blocked = sum(
        1 for d in depth_rows if d.get("hybrid_rank") is not None and d.get("hybrid_rank") == 1
    )
    # Official v3 applied=0 always for fails; count gold anywhere in hyb still abstained
    in_hyb_not_applied = in_pool_hyb  # all these failed intent_ok

    if demoted >= max(in_6_25, beyond_25, 1) and demoted >= 3:
        primary = "HYBRID_RANKING"
        next_step = (
            f"Gold demoted out of hybrid on {demoted}/{len(depth_rows)} clips "
            "(semantic hit, hybrid miss) — ranking before depth."
        )
    elif in_6_25 > demoted and in_6_25 >= beyond_25 and in_6_25 >= 3:
        primary = "CANDIDATE_GENERATION_DEPTH"
        next_step = "Raise retrieval depth/top_k — majority gold sits in rank 6–25."
    elif beyond_25 >= 3 and beyond_25 > in_6_25 and beyond_25 > demoted:
        primary = "PROFILE_OR_EMBEDDING_QUALITY"
        next_step = "Profile/embedding quality — majority gold rank >25 or absent."
    elif in_hyb_not_applied >= 3 and demoted < 3 and in_6_25 < 3:
        primary = "APPLY_GATES"
        next_step = (
            "Gold often in hybrid pool but never applied — apply/abstain path "
            "(observe only; do not change thresholds yet)."
        )

    verdict = {
        "VERDICT": primary,
        "next_step": next_step,
        "n_failures": len(depth_rows),
        "semantic_rank_buckets": dict(buckets),
        "counts": {
            "rank_1_5": in_1_5,
            "rank_6_25": in_6_25,
            "rank_gt_25_or_absent": beyond_25,
            "gold_in_semantic_top5": in_pool_sem5,
            "gold_in_hybrid_top5": in_pool_hyb,
            "gold_at_hybrid_1": at_hyb1,
            "semantic_hit_hybrid_demote": demoted,
            "hybrid_present_still_failed": in_hyb_not_applied,
        },
        "decision_tree": {
            "if_majority_6_25": "raise retrieval depth/top_k",
            "if_majority_gt_25": "profile/embedding quality track",
            "if_in_pool_but_loses": "hybrid ranking",
            "if_hyb1_but_not_applied": "apply gates later — not now",
        },
    }
    print(f"  L1 VERDICT: {primary}", flush=True)
    print(f"  buckets: {dict(buckets)}", flush=True)

    # Variants A/B (re-score) — secondary; C from logs
    out_variants: dict[str, Any] = {}
    per_clip: dict[str, Any] = {}

    def rescore(r: dict) -> dict:
        transcript = (r.get("raw_transcript") or r.get("transcript") or "").strip()
        current = question_bank.match(transcript) if transcript else None
        dec = SIR.recover_semantic_intent(transcript, current)
        gold = set(r.get("expected_intent_ids") or [])
        hyb = [d["id"] for d in (dec.hybrid_top5 or [])]
        rank = next((i + 1 for i, x in enumerate(hyb) if x in gold), None)
        applied_id = dec.match.entry.id if dec.match is not None else None
        return {
            "reason": dec.reason,
            "abstain_reason": dec.abstain_reason,
            "hybrid": hyb,
            "gold_rank_hybrid": rank,
            "applied_id": applied_id,
            "applied_is_gold": applied_id in gold if applied_id else False,
        }

    for variant in ("A_current", "B_no_blob_proxy"):
        print(f"  rescoring variant {variant}…", flush=True)
        original_blob = None
        if variant == "B_no_blob_proxy":
            original_blob = SIR._profile_blob_norm

            def patched(profile, limit, _o=original_blob):
                return "" if limit == 360 else _o(profile, limit)

            SIR._profile_blob_norm = patched
        rescored = {}
        for r in failures:
            try:
                rescored[r["sample_id"]] = rescore(r)
            except Exception as exc:  # noqa: BLE001 — measurement harness
                rescored[r["sample_id"]] = {"error": f"{type(exc).__name__}: {exc}"}
        if original_blob is not None:
            SIR._profile_blob_norm = original_blob

        in_hybrid = sum(1 for v in rescored.values() if v.get("gold_rank_hybrid"))
        at_one = sum(1 for v in rescored.values() if v.get("gold_rank_hybrid") == 1)
        applied_gold = sum(1 for v in rescored.values() if v.get("applied_is_gold"))
        out_variants[variant] = {
            "n_failures": len(failures),
            "gold_in_hybrid_top5": in_hybrid,
            "gold_at_hybrid_1": at_one,
            "applied_and_gold": applied_gold,
        }
        per_clip[variant] = rescored
        print(
            f"  L1 {variant:18} gold_in_hybrid={in_hybrid:2}  "
            f"gold@1={at_one:2}  applied_gold={applied_gold:2}",
            flush=True,
        )

    lowered = []
    for r in rows:
        s = r.get("semantic_recovery") or {}
        hyb = s.get("hybrid_top5") or []
        if not hyb:
            continue
        top = hyb[0]
        applied = max(float(top.get("exist") or 0), float(top.get("final") or 0))
        if top.get("id") == r.get("match_id") and applied < float(r.get("match_score") or 0):
            lowered.append(
                {
                    "clip": r["sample_id"],
                    "was": r.get("match_score"),
                    "would_be": round(applied, 3),
                    "intent_ok": r["intent_ok"],
                }
            )
    out_variants["C_score_floor_observation"] = {
        "clips_where_apply_would_lower_identical_id": len(lowered),
        "of_those_currently_passing": sum(1 for x in lowered if x["intent_ok"]),
        "examples": lowered[:8],
    }
    print(
        f"  L1 C_score_floor    lower-identical-id on {len(lowered)} clips "
        f"({out_variants['C_score_floor_observation']['of_those_currently_passing']} passing)",
        flush=True,
    )

    return {
        "VERDICT": verdict,
        "depth": {"deep_k": deep_k, "per_clip": depth_rows},
        "variants": out_variants,
        "per_clip_rescore": per_clip,
    }


# ───────────────────────────── L2 ─────────────────────────────
_TRAILING = re.compile(
    r"^\s*(?:and\s+|then\s+)?(?:say|tell me|point me to|give me|explain|describe)?\s*"
    r"(when|what do you do|which|how|whether|why)\b",
    re.I,
)
_PRONOUN = re.compile(r"\b(one|it|that|them|those|this)\b", re.I)


def _subject_of(question: str) -> str:
    q = question.strip().rstrip("?.").strip()
    m = re.search(
        r"\b(?:what is|what are|tell me what|explain what|describe|point me to|give me)\s+"
        r"(?:an?\s+|the\s+|your\s+)?(.+)$",
        q,
        re.I,
    )
    if m:
        return m.group(1).strip()
    return q


def run_l2() -> dict:
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index
    from app.services.warm_start import warm_system_blocking

    print("  warming…", flush=True)
    warm_system_blocking()
    rows = _load_v3()

    cases: list[dict[str, Any]] = []
    for r in rows:
        if (r.get("question_type_label") or "") != "compound":
            continue
        tr = r.get("compound_trace") or {}
        if not isinstance(tr, dict):
            tr = {}
        subs = [str(s) for s in (tr.get("sub_questions") or [])]
        missed_raw = r.get("missed_parts") or tr.get("missed_parts") or []
        missed = [str(x) for x in missed_raw]
        if not missed or len(subs) < 2:
            continue
        cand = {
            str(c.get("sub_question") or ""): c
            for c in (tr.get("candidate_intents") or [])
            if isinstance(c, dict)
        }
        already: set[str] = set()
        for sid in tr.get("selected_intents") or []:
            if isinstance(sid, str) and sid:
                already.add(sid)
        for c in tr.get("candidate_intents") or []:
            if not isinstance(c, dict):
                continue
            iid = c.get("intent_id")
            if c.get("accepted") and isinstance(iid, str) and iid:
                already.add(iid)
        for m in missed:
            idx = subs.index(m) if m in subs else -1
            if idx <= 0:
                idx = next(
                    (i for i, s in enumerate(subs) if s and m and (s in m or m in s)),
                    -1,
                )
            if idx <= 0:
                continue
            parent_text = subs[idx - 1]
            parent = cand.get(parent_text) or {}
            parent_id = parent.get("intent_id") if isinstance(parent, dict) else None
            if not isinstance(parent_id, str) or not parent_id:
                for c in tr.get("candidate_intents") or []:
                    if not isinstance(c, dict):
                        continue
                    iid = c.get("intent_id")
                    if c.get("accepted") and isinstance(iid, str) and iid:
                        parent_id = iid
                        parent_text = str(c.get("sub_question") or parent_text)
                        break
            if not isinstance(parent_id, str) or not parent_id:
                continue
            gold_ids = [str(x) for x in (r.get("expected_intent_ids") or [])]
            cases.append(
                {
                    "clip": str(r.get("sample_id") or ""),
                    "parent_text": parent_text,
                    "parent_id": parent_id,
                    "clause": m,
                    "gold": gold_ids,
                    "already_selected": sorted(already),
                    "gold_still_missing": sorted(set(gold_ids) - already),
                    "trailing": bool(_TRAILING.match(m)),
                }
            )

    print(f"  L2 trailing dropped clauses found: {len(cases)}", flush=True)
    results: list[dict[str, Any]] = []

    for c in cases:
        parent_id = str(c["parent_id"])
        clause = str(c["clause"])
        parent_text = str(c["parent_text"])
        pe = question_bank.get(parent_id)
        parent_topic = pe.topic if pe else None
        subject = _subject_of(pe.question if pe else parent_text)
        resolved = _PRONOUN.sub(subject, clause, count=1)
        exclude = set(str(x) for x in c["already_selected"]) | {parent_id}
        gold_missing = set(str(x) for x in c["gold_still_missing"])

        def probe_match(text: str, topic: Optional[str] = None) -> dict[str, Any]:
            matched = question_bank.match(text, topic_hint=topic)
            ok, reason, margin = _accept_match(matched)
            return {
                "id": matched.entry.id if matched else None,
                "score": round(float(matched.score), 3) if matched else 0.0,
                "mode": matched.mode if matched else None,
                "accepted": ok,
                "drop": reason,
                "margin": round(margin, 3),
            }

        a = probe_match(clause)
        b = probe_match(clause, parent_topic)
        cc = probe_match(resolved)

        # Variant D: real embedder rank on the clause (discriminator kept),
        # soft-filter by parent topic when possible, exclude parent/already.
        d_info: dict[str, Any] = {
            "id": None,
            "score": 0.0,
            "mode": "semantic_cosine",
            "accepted": False,
            "drop": None,
            "surfaced_correct_rank1": False,
            "rank1_id": None,
            "cosine": None,
        }
        if semantic_intent_index.ready and clause.strip():
            hits = semantic_intent_index.top_k(clause, k=15)
            # Soft prefer same topic without erasing out-of-topic gold:
            # stable sort: topic match first, then cosine.
            def sort_key(h):
                same = 0
                if parent_topic and h.profile and h.profile.topic == parent_topic:
                    same = 1
                return (same, h.score)

            ranked = sorted(hits, key=sort_key, reverse=True)
            ranked = [h for h in ranked if h.intent_id not in exclude]
            if ranked:
                top = ranked[0]
                d_info["rank1_id"] = top.intent_id
                d_info["id"] = top.intent_id
                d_info["cosine"] = round(float(top.score), 4)
                d_info["score"] = d_info["cosine"]
                d_info["surfaced_correct_rank1"] = top.intent_id in gold_missing
                # Acceptance via bank match on same id (observe thresholds; no edits)
                bm = question_bank.match(clause, topic_hint=parent_topic)
                # If match landed on excluded parent, try top_matches skip
                tops = question_bank.top_matches(
                    clause, top_k=6, topic_hint=parent_topic
                )
                chosen = None
                for tm in tops:
                    if tm.entry.id not in exclude:
                        chosen = tm
                        break
                if chosen is None and bm is not None and bm.entry.id not in exclude:
                    chosen = bm
                if chosen is not None:
                    ok, reason, margin = _accept_match(chosen)
                    d_info["id"] = chosen.entry.id
                    d_info["score"] = round(float(chosen.score), 3)
                    d_info["mode"] = chosen.mode
                    d_info["accepted"] = ok
                    d_info["drop"] = reason
                    d_info["margin"] = round(margin, 3)
                    # surfaced_correct uses cosine rank1; accepted may differ
                else:
                    d_info["drop"] = "no_match_after_exclude"
            else:
                d_info["drop"] = "empty_after_exclude"
        else:
            d_info["drop"] = "index_not_ready"

        results.append(
            {
                **c,
                "parent_topic": parent_topic,
                "resolved_clause": resolved,
                "A_alone": a,
                "B_topic_hint": b,
                "C_subject_carry": cc,
                "D_embed_exclude_parent": d_info,
                "A_hit": a["id"] in gold_missing if a["id"] else False,
                "B_hit": b["id"] in gold_missing if b["id"] else False,
                "C_hit": cc["id"] in gold_missing if cc["id"] else False,
                "D_hit": (d_info["id"] in gold_missing) if d_info.get("id") else False,
                "A_dup": a["id"] in exclude if a["id"] else False,
                "B_dup": b["id"] in exclude if b["id"] else False,
                "C_dup": cc["id"] in exclude if cc["id"] else False,
                "D_dup": (d_info["id"] in exclude) if d_info.get("id") else False,
            }
        )

    def tally(key: str, hit_key: str, dup_key: str) -> dict[str, Any]:
        acc = sum(1 for r in results if r[key].get("accepted"))
        hits = sum(1 for r in results if r[hit_key] and r[key].get("accepted"))
        dup = sum(1 for r in results if r[key].get("accepted") and r[dup_key])
        wrong = sum(
            1
            for r in results
            if r[key].get("accepted") and not r[hit_key] and not r[dup_key]
        )
        out: dict[str, Any] = {
            "accepted": acc,
            "new_gold_part": hits,
            "duplicate": dup,
            "wrong": wrong,
        }
        if key == "D_embed_exclude_parent":
            out["surfaced_correct_rank1"] = sum(
                1 for r in results if r[key].get("surfaced_correct_rank1")
            )
            out["n"] = len(results)
        return out

    summary: dict[str, Any] = {
        "A_alone": tally("A_alone", "A_hit", "A_dup"),
        "B_topic_hint": tally("B_topic_hint", "B_hit", "B_dup"),
        "C_subject_carry": tally("C_subject_carry", "C_hit", "C_dup"),
        "D_embed_exclude_parent": tally("D_embed_exclude_parent", "D_hit", "D_dup"),
        "n_cases": len(results),
    }
    for k in ("A_alone", "B_topic_hint", "C_subject_carry", "D_embed_exclude_parent"):
        s = summary[k]
        extra = ""
        if k.startswith("D_"):
            extra = f"  surfaced_correct_rank1={s.get('surfaced_correct_rank1', 0)}"
        print(
            f"  L2 {k:24} accepted={s['accepted']:2} new_gold={s['new_gold_part']:2} "
            f"duplicate={s['duplicate']:2} wrong={s['wrong']:2}{extra}",
            flush=True,
        )

    d = summary["D_embed_exclude_parent"]
    surf = int(d.get("surfaced_correct_rank1") or 0)
    n_d = int(d.get("n") or summary["n_cases"] or 1)
    if d["wrong"] > 0:
        d_verdict = "REJECT_WRONG_INTENTS"
    elif surf >= max(2, (n_d + 2) // 3) and d["wrong"] == 0:
        d_verdict = "ADOPT_AS_L2_BASE_CANDIDATE"
    elif surf > 0 and d["accepted"] == 0 and d["wrong"] == 0:
        d_verdict = "SURFACES_GOLD_WEAKLY_ACCEPT_BLOCKED — promising, not yet base"
    elif surf > 0 and d["wrong"] == 0:
        d_verdict = "PARTIAL_SIGNAL"
    else:
        d_verdict = "NO_CLEAR_WIN"
    summary["D_VERDICT"] = d_verdict
    summary["D_NOTE"] = (
        "C often re-matches parent (duplicates). D keeps wrong=0 via exclude+cosine; "
        "adopt only when surfaced_correct_rank1 is meaningful — do not touch accept thresholds yet."
    )
    print(f"  L2 D_VERDICT: {d_verdict}", flush=True)

    return {"summary": summary, "cases": results}


def _write_md(payload: dict) -> str:
    lines: list[str] = []
    A = lines.append
    A("# V4 L1/L2 offline experiments")
    A("")
    A(f"Created: {payload.get('created_at')}")
    A("")
    A(payload.get("note", ""))
    A("")
    if "l1" in payload and "error" not in (payload.get("l1") or {}):
        v = payload["l1"]["VERDICT"]
        A("## L1 VERDICT")
        A("")
        A(f"**{v['VERDICT']}** — {v['next_step']}")
        A("")
        A(f"Buckets: `{v['semantic_rank_buckets']}`")
        A("")
        A("| count | n |")
        A("|---|---|")
        for k, val in (v.get("counts") or {}).items():
            A(f"| {k} | {val} |")
        A("")
        A("### Depth per clip")
        A("")
        A("| id | sem rank | bucket | hyb rank | in hyb |")
        A("|---|---|---|---|---|")
        for d in payload["l1"]["depth"]["per_clip"]:
            A(
                f"| {d['id']} | {d['semantic_rank']} | {d['semantic_bucket']} | "
                f"{d['hybrid_rank']} | {d['gold_in_hybrid_top5']} |"
            )
        A("")
        A("### Variants")
        A("")
        A("```json")
        A(json.dumps(payload["l1"].get("variants"), indent=2))
        A("```")
        A("")
    if "l2" in payload:
        s = payload["l2"]["summary"]
        A("## L2 summary")
        A("")
        A(f"n_cases={s.get('n_cases')} · **D_VERDICT:** {s.get('D_VERDICT')}")
        A("")
        A("| variant | accepted | new_gold | duplicate | wrong | surfaced_correct_rank1 |")
        A("|---|---|---|---|---|---|")
        for k in ("A_alone", "B_topic_hint", "C_subject_carry", "D_embed_exclude_parent"):
            row = s[k]
            A(
                f"| {k} | {row['accepted']} | {row['new_gold_part']} | "
                f"{row['duplicate']} | {row['wrong']} | "
                f"{row.get('surfaced_correct_rank1', '—')} |"
            )
        A("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["l1", "l2"], default=None)
    args = ap.parse_args()
    if not V3.is_file():
        print(f"missing {V3}")
        return 1
    payload: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "measurement only — no threshold, weight, alias or pipeline change; "
            "does not touch _MIN_ANSWER_SCORE / margin rules"
        ),
    }
    if args.only in (None, "l1"):
        print("L1 — candidate generation / hybrid / gates", flush=True)
        payload["l1"] = run_l1()
    if args.only in (None, "l2"):
        print("L2 — trailing-clause variants A/B/C/D", flush=True)
        payload["l2"] = run_l2()
    REPORTS.mkdir(parents=True, exist_ok=True)
    out_json = REPORTS / "V4_L1_L2_EXPERIMENTS.json"
    out_md = REPORTS / "V4_L1_L2_EXPERIMENTS.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(_write_md(payload), encoding="utf-8")
    print(f"\nwrote {out_json}", flush=True)
    print(f"wrote {out_md}", flush=True)
    if payload.get("l1") and "VERDICT" in (payload.get("l1") or {}):
        print("L1_VERDICT=", payload["l1"]["VERDICT"]["VERDICT"], flush=True)
    if payload.get("l2"):
        print("L2_D_VERDICT=", payload["l2"]["summary"].get("D_VERDICT"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
