"""
V5 — re-qualify the original 13 HYBRID/ACTION residuals on the REPAIRED harness.

Measurement only. Does NOT inherit B5 buckets. Fixes the instrument defect:
every forced `question_bank.load(force=True)` is followed by `warm()`, and the
run aborts if `alias_matrix is None` or hybrid top1 semantic is identically 0.

Official provisional baseline (from B7 A_baseline_semantic_restored):
  coverage=0.4878  wrong=4  HC=0

    python scripts/v5_requalify_13_repaired.py
Writes reports/V5_REQUALIFY_13_REPAIRED.{md,json}.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V4 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V4_REPORT.json"
B5 = REPORTS / "V5_B5_RESIDUAL_MATCHING.json"
PACK = ROOT.parent / "frontend" / "public" / "voice-drill" / "final-unseen-holdout-v4"
SCRIPTS = PACK / "scripts.json"

EVIDENCE_THETA = 0.4
HYBRID_POOL_K = 8
SEMANTIC_DEEP_K = 50
PROVISIONAL_BASELINE = {"coverage_by_part": 0.4878, "wrong_intent": 4, "hc_risk": 0}

_INTERROG = re.compile(
    r"\b(what|why|how|when|which|who|whether|where|is|are|do|does|did|can|should|would)\b", re.I)
_IMPER = re.compile(
    r"\b(explain|tell|say|describe|give|point|walk|cover|name|define|summaris|summariz|list)\b", re.I)
_VERBISH = re.compile(
    r"\b(use|used|build|built|work|works|make|choose|pick|handle|stop|prevent|add|need|"
    r"matter|differ|design|halt|reduce|track|monitor)\b", re.I)
_FRAG_SPLIT = re.compile(r",|;|\band\b|\bthen\b|\bplus\b", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.?!])\s+")

_V5_EXTRA_RULES = (
    ("when", re.compile(
        r"(?:^|\b)(?:say |tell me |explain )?when\b|"
        r"\b(?:at what point|under what (?:conditions?|circumstances?))\b|"
        r"\bonce\b.*\b(?:enough|sufficient|needed|required)\b", re.I)),
    ("how", re.compile(
        r"^(?:how you|how we|how they|how one)\b|"
        r"\bhow\s+\w+\s+(?:you|we|they)\b", re.I)),
    ("who", re.compile(r"^(?:who|whom)\b|\bwho (?:is|are|makes|approves|owns|decides)\b", re.I)),
    ("where", re.compile(r"^where\b|\bwhere exactly\b", re.I)),
)


def _f(x, n=4):
    try:
        return round(float(x), n)
    except Exception:
        return None


def clause_has_action(text: str) -> bool:
    return bool(_INTERROG.search(text) or _IMPER.search(text) or _VERBISH.search(text))


def fragments(text: str) -> list[str]:
    return [p.strip(" .;:?") for p in _FRAG_SPLIT.split(text or "") if p.strip(" .;:?")]


def sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENT_SPLIT.split((text or "").strip()) if p.strip(" .?!")]


def word_count(text: str) -> int:
    return len((text or "").split())


def r1_min8w(text: str) -> bool:
    parts = fragments(text)
    if len(parts) < 2 or word_count(text) < 8:
        return False
    return sum(1 for p in parts if len(p.split()) <= 6 and not clause_has_action(p)) >= 2


def split_enumeration(text: str) -> list[str]:
    parts = fragments(text)
    if len(parts) < 2:
        return []
    short_verbless = sum(1 for p in parts if len(p.split()) <= 6 and not clause_has_action(p))
    if short_verbless >= max(2, int(0.5 * len(parts))):
        return [p for p in parts if p.split()]
    return []


def rewarm_bank():
    from app.services.question_bank import question_bank

    question_bank.warm()
    idx = getattr(question_bank, "_index", None)
    am = getattr(idx, "alias_matrix", None) if idx is not None else None
    if am is None:
        raise RuntimeError("alias_matrix is None after warm() — abort (invalid measurement)")
    return am


def install_h():
    from app.services import question_bank as QB

    original = QB.detect_intent

    def patched(normalized: str):
        got = original(normalized)
        if got:
            return got
        for name, pat in _V5_EXTRA_RULES:
            if pat.search(normalized or ""):
                return name
        return None

    QB.detect_intent = patched
    QB.question_bank.load(force=True)
    rewarm_bank()  # CRITICAL — the B5/B6 defect was omitting this

    def restore():
        QB.detect_intent = original
        QB.question_bank.load(force=True)
        rewarm_bank()

    return restore


def evidence_ratio(sub_question: str, transcript: str) -> float:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _content_tokens

    q = set(_content_tokens(normalize_for_matching(sub_question or "")))
    t = set(_content_tokens(normalize_for_matching(transcript or "")))
    if not q:
        return 0.0
    return len(q & t) / len(q)


def detect_action(text: str) -> str | None:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import detect_intent

    return detect_intent(normalize_for_matching(text or ""))


def topic_of(intent_id: str) -> str:
    return (intent_id or "").split(".", 1)[0]


def content_tokens(text: str) -> set[str]:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _content_tokens

    return set(_content_tokens(normalize_for_matching(text or "")))


def path_opens(text: str) -> bool:
    from app.services.compound_question_detector import detect_question_complexity

    return detect_question_complexity(text).question_type != "single" or r1_min8w(text)


def forced_subs(text: str) -> list[str]:
    from app.services.compound_question_detector import (
        ComplexityDetection,
        detect_question_complexity,
    )
    from app.services.compound_question_pipeline import resolve_compound_question

    det = detect_question_complexity(text)
    force = det
    if det is None or det.question_type == "single":
        force = ComplexityDetection(
            "compound", 0.9,
            max(2, int(getattr(det, "request_count_estimate", 1) or 1)),
            ("labeled_compound_pack",),
        )
    res = resolve_compound_question(text, conversation_history=None, detection=force)
    return list(getattr(res, "sub_questions", None) or [])


def working_parts(transcript: str, *, apply_evidence: bool) -> tuple[list[str], list[dict]]:
    audit = []
    kept = []
    for s in forced_subs(transcript):
        ratio = evidence_ratio(s, transcript)
        drop = apply_evidence and ratio < EVIDENCE_THETA
        audit.append({"sub_question": s, "evidence_ratio": _f(ratio),
                      "dropped_by_evidence": drop})
        if drop:
            continue
        for f in (split_enumeration(s) or [s]):
            if apply_evidence and evidence_ratio(f, transcript) < EVIDENCE_THETA:
                audit.append({"sub_question": f, "evidence_ratio": _f(evidence_ratio(f, transcript)),
                              "dropped_by_evidence": True, "via_split": True})
                continue
            kept.append(f)
    return kept, audit


def hybrid_pool(text: str, k: int = HYBRID_POOL_K) -> list[dict]:
    from app.services.question_bank import question_bank

    tops = question_bank.top_matches(text, top_k=k)
    out = []
    for i, m in enumerate(tops):
        out.append({
            "rank": i + 1, "id": m.entry.id, "topic": m.entry.topic,
            "score": _f(m.score), "semantic": _f(m.semantic),
            "lexical": _f(m.lexical), "keyword": _f(m.keyword),
            "mode": m.mode,
            "action_type": detect_action(m.entry.question),
        })
    return out


def semantic_ranks(text: str, gold_id: str, k: int = SEMANTIC_DEEP_K) -> dict:
    from app.services.semantic_intent_index import semantic_intent_index

    if not text.strip() or not semantic_intent_index.ready:
        return {"rank": None, "score": None, "top5": []}
    hits = semantic_intent_index.top_k(text, k=k)
    top5 = [{"rank": i + 1, "id": h.intent_id, "score": _f(h.score)}
            for i, h in enumerate(hits[:5])]
    rank = score = None
    for i, h in enumerate(hits):
        if h.intent_id == gold_id:
            rank, score = i + 1, _f(h.score)
            break
    return {"rank": rank, "score": score, "top5": top5}


def accept_probe(text: str, prefer_id: str | None = None):
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank

    tops = question_bank.top_matches(text, top_k=HYBRID_POOL_K)
    if not tops:
        return {"accepted": False, "reason": "no_match", "top1": None, "margin": 0.0}
    m = tops[0]
    if prefer_id:
        for t in tops:
            if t.entry.id == prefer_id:
                m = t
                break
    ok, reason, margin = _accept_match(m)
    return {
        "accepted": ok, "reason": reason, "top1": tops[0].entry.id,
        "probed_id": m.entry.id, "score": _f(m.score), "margin": _f(margin),
    }


def project_selected(transcript: str) -> list[str]:
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank

    if not path_opens(transcript):
        m = question_bank.match(transcript)
        return [m.entry.id] if m is not None else []
    parts, _ = working_parts(transcript, apply_evidence=True)
    out = []
    for p in parts:
        tops = question_bank.top_matches(p, top_k=6)
        if not tops:
            continue
        ok, _r, _m = _accept_match(tops[0])
        if ok:
            out.append(tops[0].entry.id)
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    if len(uniq) < 2:
        m = question_bank.match(transcript)
        return [m.entry.id] if m is not None else []
    return uniq


def stt_distortion(script: str, asr: str, gold_entry) -> tuple[bool, dict]:
    gq = gold_entry.question if gold_entry else ""
    g_key = {t for t in content_tokens(gq) if len(t) >= 4}
    if gold_entry:
        g_key |= {t for t in content_tokens(gold_entry.id.replace(".", " ")) if len(t) >= 4}
    if not g_key:
        return False, {"lost": [], "script_hits": [], "asr_hits": []}
    s_tok, a_tok = content_tokens(script), content_tokens(asr)
    script_hits, asr_hits = g_key & s_tok, g_key & a_tok
    lost = sorted(script_hits - asr_hits)
    bad = len(script_hits) >= 2 and len(lost) >= 2 and len(asr_hits) < len(script_hits) / 2
    return bad, {"lost": lost, "script_hits": sorted(script_hits), "asr_hits": sorted(asr_hits)}


def gold_reachable(asr: str, gold_entry) -> tuple[bool, str]:
    if gold_entry is None:
        return False, "missing_bank_entry"
    g_tok = {t for t in content_tokens(gold_entry.question) if len(t) >= 4}
    if not g_tok:
        return True, "no_content_tokens_to_check"
    overlap = g_tok & content_tokens(asr)
    if overlap:
        return True, f"overlap={sorted(overlap)[:6]}"
    return False, "no_gold_token_in_utterance"


def assign_bucket(case: dict) -> str:
    """Fresh exclusive assignment — do not inherit B5 labels."""
    if case["status"] == "NOW_HIT":
        return "RESOLVED_UNDER_REPAIRED_BASELINE"
    if case["stt_distortion"]:
        return "STT_DISTORTION"
    # No spoken gold evidence: not a ranking problem. Keep distinct from
    # "gold absent from candidate pool while text carries meaning".
    if not case["reachable"]:
        return "STT_DISTORTION" if case["stt_detail"].get("lost") else "CANDIDATE_GENERATION"
    if case["segmentation_residual"]:
        return "SEGMENTATION_RESIDUAL"
    if case["evidence_rejected"]:
        return "EVIDENCE_REJECTED"
    hy = case["hybrid_gold_rank"]
    sem = case["semantic_gold_rank"]
    if hy is None:
        if sem is None or sem > 25:
            return "CANDIDATE_GENERATION"
        if sem > 5:
            return "SEMANTIC_PROFILE_QUALITY"
        return "HYBRID_RANKING"
    if hy > 1:
        if case["action_granularity"]:
            return "ACTION_GRANULARITY"
        if sem is not None and sem > 5 and case["text_carries_meaning"]:
            return "SEMANTIC_PROFILE_QUALITY"
        return "HYBRID_RANKING"
    if not case["gold_accepted_as_top1"]:
        return "ACCEPTANCE_GATE"
    # top1 + accepted but absent from final projection selection
    return "HYBRID_RANKING"


def load_scripts() -> dict[str, str]:
    return {
        str(r["id"]): str(r.get("transcript") or "")
        for r in json.loads(SCRIPTS.read_text(encoding="utf-8"))
        if not r.get("warmup")
    }


def main() -> int:
    if not V4.is_file() or not B5.is_file():
        print("missing V4 or B5")
        return 1

    os.environ["PYTHONUNBUFFERED"] = "1"
    from app.services.warm_start import warm_system_blocking

    print("warming…", flush=True)
    warm_system_blocking()
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index

    if not semantic_intent_index.ready:
        print("!! semantic_intent_index cold — abort")
        return 2

    restore = install_h()
    try:
        # Instrument self-check: hybrid semantic must be non-zero on a probe.
        probe = hybrid_pool("What is hybrid search?", k=3)
        if not probe or all((p.get("semantic") or 0) == 0 for p in probe):
            print("!! hybrid semantic still zero after warm — abort")
            print("probe:", probe)
            return 3
        print(f"instrument OK — probe top1 semantic={probe[0]['semantic']} "
              f"alias_matrix=present", flush=True)

        b5 = json.loads(B5.read_text(encoding="utf-8"))
        # Identity of the 13 only — ignore old buckets.
        targets = [
            {"clip": c["clip"], "gold": c["gold_intent"],
             "legacy_bucket": c["bucket"], "legacy_fragment": c.get("fragment")}
            for c in b5["missing_parts"]
            if c.get("bucket") in {"HYBRID_RANKING", "ACTION_GRANULARITY"}
        ]
        scripts = load_scripts()
        v4 = json.loads(V4.read_text(encoding="utf-8"))
        by_id = {
            r["sample_id"]: r for r in v4["results"]
            if not str(r.get("notes") or "").startswith("warmup:")
        }

        cases = []
        print(f"re-qualifying {len(targets)} cases…", flush=True)
        for t in targets:
            row = by_id[t["clip"]]
            asr = (row.get("transcript") or "").strip()
            script = (scripts.get(t["clip"]) or "").strip()
            gold_id = t["gold"]
            entry = question_bank.get(gold_id)
            selected = project_selected(asr)
            now_hit = gold_id in selected

            parts_evid, audit_evid = working_parts(asr, apply_evidence=True)
            parts_raw, _audit_raw = working_parts(asr, apply_evidence=False)

            # Best fragment for this gold among evid parts (or ASR).
            candidates = parts_evid if parts_evid else ([asr] if asr else [])
            best_frag, best_pool, best_sem = None, [], {}
            best_key = (10**9, 10**9)
            for p in candidates:
                pool = hybrid_pool(p)
                sem = semantic_ranks(p, gold_id)
                hy_r = next((c["rank"] for c in pool if c["id"] == gold_id), 10**9)
                se_r = sem["rank"] if sem.get("rank") is not None else 10**9
                if (hy_r, se_r) < best_key:
                    best_key = (hy_r, se_r)
                    best_frag, best_pool, best_sem = p, pool, sem
            if best_frag is None:
                best_frag, best_pool = asr, hybrid_pool(asr)
                best_sem = semantic_ranks(asr, gold_id)

            hy_rank = next((c["rank"] for c in best_pool if c["id"] == gold_id), None)
            top1 = best_pool[0] if best_pool else None
            gold_row = next((c for c in best_pool if c["id"] == gold_id), None)

            # Would raw (no-evidence) path accept gold?
            raw_hit = False
            for p in parts_raw:
                tops = question_bank.top_matches(p, top_k=6)
                from app.services.compound_question_pipeline import _accept_match
                if tops and _accept_match(tops[0])[0] and tops[0].entry.id == gold_id:
                    raw_hit = True
                    break
            evid_hit = False
            for p in parts_evid:
                tops = question_bank.top_matches(p, top_k=6)
                from app.services.compound_question_pipeline import _accept_match
                if tops and _accept_match(tops[0])[0] and tops[0].entry.id == gold_id:
                    evid_hit = True
                    break
            evid_rej = raw_hit and not evid_hit

            accept = accept_probe(best_frag or "")
            gold_accept = accept_probe(best_frag or "", prefer_id=gold_id) if hy_rank == 1 else {
                "accepted": False, "reason": "not_top1", "probed_id": gold_id,
            }

            stt_bad, stt_det = stt_distortion(script, asr, entry)
            reachable, reach_why = gold_reachable(asr, entry)

            g_act = detect_action(entry.question) if entry else None
            t_act = top1.get("action_type") if top1 else None
            same_topic = bool(top1 and topic_of(top1["id"]) == topic_of(gold_id))
            # Prefer entry.topic when available
            if top1 and entry:
                same_topic = (top1.get("topic") == entry.topic) or same_topic
            action_gran = bool(
                hy_rank and hy_rank > 1 and same_topic
                and g_act and t_act and g_act != t_act
            )
            g_tok = content_tokens(entry.question if entry else "")
            f_tok = content_tokens(best_frag or "")
            overlap = g_tok & f_tok
            text_carries = len(overlap) >= max(1, min(2, len(g_tok) // 3)) if g_tok else False

            frags, sents = fragments(asr), sentences(asr)
            gold_list = list(row.get("expected_intent_ids") or [])
            seg = len(gold_list) >= 2 and len(frags) <= 1 and len(sents) <= 1

            case = {
                "clip": t["clip"],
                "gold_intent": gold_id,
                "legacy_bucket_ignored": t["legacy_bucket"],
                "status": "NOW_HIT" if now_hit else "STILL_MISSING",
                "path_opened": path_opens(asr),
                "transcript": asr,
                "script": script,
                "fragment": best_frag,
                "selected_intents": selected,
                "reachable": reachable,
                "reachable_why": reach_why,
                "hybrid_pool": best_pool,
                "hybrid_top5": best_pool[:5],
                "hybrid_top1_id": top1["id"] if top1 else None,
                "hybrid_top1_topic": top1.get("topic") if top1 else None,
                "hybrid_top1_action_type": t_act,
                "hybrid_top1_semantic": top1.get("semantic") if top1 else None,
                "hybrid_gold_rank": hy_rank,
                "gold_score": gold_row["score"] if gold_row else None,
                "gold_semantic_in_hybrid": gold_row["semantic"] if gold_row else None,
                "semantic_gold_rank": best_sem.get("rank"),
                "semantic_gold_score": best_sem.get("score"),
                "semantic_top5": best_sem.get("top5"),
                "gold_action_type": g_act,
                "query_action_type": detect_action(best_frag or ""),
                "same_topic_sibling": bool(same_topic and top1 and top1["id"] != gold_id),
                "action_granularity": action_gran,
                "evidence_score_fragment": _f(evidence_ratio(best_frag or "", asr)),
                "evidence_rejected": evid_rej,
                "accept_top1": accept,
                "gold_accepted_as_top1": bool(hy_rank == 1 and gold_accept.get("accepted")),
                "gold_accept_reason": gold_accept.get("reason"),
                "stt_distortion": stt_bad,
                "stt_detail": stt_det,
                "segmentation_residual": seg,
                "text_carries_meaning": text_carries,
                "content_overlap_tokens": sorted(overlap),
            }
            case["bucket"] = assign_bucket(case)
            cases.append(case)
            print(
                f"  {t['clip']} {gold_id}: {case['status']} -> {case['bucket']} "
                f"hy={hy_rank} sem={best_sem.get('rank')} top1={case['hybrid_top1_id']} "
                f"hy_sem={case['hybrid_top1_semantic']}",
                flush=True,
            )
    finally:
        restore()

    still = [c for c in cases if c["status"] == "STILL_MISSING"]
    resolved = [c for c in cases if c["status"] == "NOW_HIT"]
    reachable_still_cases = [c for c in still if c["reachable"]]
    unreachable_still = [c for c in still if not c["reachable"]]
    tally = Counter(c["bucket"] for c in still)
    tally_reachable = Counter(c["bucket"] for c in reachable_still_cases)
    tally_all = Counter(c["bucket"] for c in cases)
    ranking_family = (
        tally_reachable.get("HYBRID_RANKING", 0)
        + tally_reachable.get("ACTION_GRANULARITY", 0)
    )
    profile_family = (
        tally_reachable.get("CANDIDATE_GENERATION", 0)
        + tally_reachable.get("SEMANTIC_PROFILE_QUALITY", 0)
        + tally_reachable.get("SEGMENTATION_RESIDUAL", 0)
    )
    n_reach_still = len(reachable_still_cases) or 1

    # Decision uses REACHABLE still-missing only — unreachable gold has no
    # ranking leverage (contradicts evidence-grounding).
    if ranking_family >= max(1, int(0.35 * n_reach_still)) and ranking_family >= profile_family:
        decision = (
            "REOPEN_RANKING — under repaired harness a real HYBRID/ACTION block "
            "remains among reachable misses; re-open ranking only on this instrument"
        )
        reopen_ranking = True
        close_phase2 = False
    elif profile_family > ranking_family:
        decision = (
            "RANKING_STAYS_CLOSED — reachable mass is profile/candidate/segmentation; "
            "do not reopen ranking"
        )
        reopen_ranking = False
        close_phase2 = False
    else:
        # Little reachable upside toward 0.90 (need +0.41 from 0.4878).
        decision = (
            "PHASE2_NO_IMPLEMENT — reachable upside too small toward 0.90 without "
            "raising wrong; prefer v6 over consuming unseen v5"
        )
        reopen_ranking = False
        close_phase2 = True

    reachable_still = len(reachable_still_cases)
    upside = _f(reachable_still / 41)

    print(f"\nresolved_under_repaired={len(resolved)}/{len(cases)}", flush=True)
    print(f"still_missing={len(still)} (reachable={reachable_still} "
          f"unreachable={len(unreachable_still)})", flush=True)
    print(f"tally_all_still={dict(tally)}", flush=True)
    print(f"tally_reachable_still={dict(tally_reachable)}", flush=True)
    print(f"ranking_family_reachable={ranking_family} "
          f"profile_family_reachable={profile_family} upside≈{upside}", flush=True)
    print(f"DECISION: {decision}", flush=True)

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "V5 re-qualify original 13 on repaired harness",
        "scope": "measurement only; no app/ changes; no inheritance of B5 buckets",
        "provisional_baseline": PROVISIONAL_BASELINE,
        "instrument": {
            "alias_matrix": True,
            "hybrid_semantic_nonzero_probe": True,
            "probe_top1_semantic": probe[0]["semantic"],
        },
        "cases": cases,
        "resolved_count": len(resolved),
        "still_missing_count": len(still),
        "bucket_tally_still_missing": dict(tally),
        "bucket_tally_reachable_still": dict(tally_reachable),
        "bucket_tally_all_13": dict(tally_all),
        "ranking_family_reachable": ranking_family,
        "profile_family_reachable": profile_family,
        "reachable_still": reachable_still,
        "unreachable_still": len(unreachable_still),
        "upside_coverage_if_all_reachable_still_hit": upside,
        "reopen_ranking": reopen_ranking,
        "close_phase2_no_implement": close_phase2,
        "decision": decision,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_REQUALIFY_13_REPAIRED.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        "# V5 — re-qualify the original 13 on repaired harness",
        "",
        f"Created: {payload['created_at']}",
        "",
        "Provisional baseline: "
        f"`cov={PROVISIONAL_BASELINE['coverage_by_part']} "
        f"wrong={PROVISIONAL_BASELINE['wrong_intent']} HC=0`.",
        f"Instrument: `alias_matrix=True`, probe hybrid semantic="
        f"`{probe[0]['semantic']}` (must be > 0).",
        "",
        "B5 buckets were **ignored** — labels below are assigned fresh.",
        "",
        f"Resolved under repaired baseline: **{len(resolved)}/{len(cases)}**",
        f"Still missing: **{len(still)}/{len(cases)}** "
        f"(reachable={reachable_still}, unreachable={len(unreachable_still)})",
        "",
        "## Still-missing bucket tally (all)",
        "",
        "| bucket | count |",
        "|---|---:|",
    ]
    for b, n in tally.most_common():
        md.append(f"| **{b}** | {n} |")
    md += [
        "",
        "## Reachable still-missing only (decision basis)",
        "",
        "| bucket | count | share |",
        "|---|---:|---:|",
    ]
    for b, n in tally_reachable.most_common():
        md.append(f"| **{b}** | {n} | {_f(n / n_reach_still)} |")
    md += [
        "",
        f"Ranking family among reachable (HYBRID+ACTION): **{ranking_family}**",
        f"Profile/seg/candidate among reachable: **{profile_family}**",
        f"Reachable still-missing upside if all hit: **+{upside}** coverage",
        "",
        f"**DECISION: {decision}**",
        "",
        "## Per case",
        "",
        "| clip | gold | status | NEW bucket | legacy (ignored) | hy | sem | top1 | hy_sem | reachable |",
        "|---|---|---|---|---|---:|---:|---|---:|---|",
    ]
    for c in cases:
        md.append(
            f"| {c['clip']} | `{c['gold_intent']}` | {c['status']} | **{c['bucket']}** | "
            f"{c['legacy_bucket_ignored']} | {c['hybrid_gold_rank'] or '—'} | "
            f"{c['semantic_gold_rank'] or '—'} | `{c['hybrid_top1_id']}` | "
            f"{c['hybrid_top1_semantic']} | {c['reachable']} |"
        )
    md += ["", "## Detail", ""]
    for c in cases:
        md += [
            f"### {c['clip']} — `{c['gold_intent']}` → {c['bucket']} ({c['status']})",
            "",
            f"- fragment: `{c['fragment']}`",
            f"- hybrid top5: `{c['hybrid_top5']}`",
            f"- semantic top5: `{c['semantic_top5']}`",
            f"- gold action={c['gold_action_type']} query_action={c['query_action_type']} "
            f"top1_action={c['hybrid_top1_action_type']} sibling={c['same_topic_sibling']}",
            f"- evidence={c['evidence_score_fragment']} rejected={c['evidence_rejected']}",
            f"- accept_top1={c['accept_top1']} gold_as_top1_accepted="
            f"{c['gold_accepted_as_top1']} ({c['gold_accept_reason']})",
            f"- reachable={c['reachable']} ({c['reachable_why']})",
            f"- stt={c['stt_distortion']} lost={c['stt_detail'].get('lost')}",
            "",
        ]
    (REPORTS / "V5_REQUALIFY_13_REPAIRED.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORTS / 'V5_REQUALIFY_13_REPAIRED.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
