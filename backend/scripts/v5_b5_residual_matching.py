"""
V5 Phase B5 — residual matching / profile analysis. MEASUREMENT ONLY.

Routing is closed. The only config under analysis is the B3/B4 candidate:

    R1_min8w + evidence 0.4 + I + H   (+ >=2-intent pre-empt guard)

For every gold part missing from that projection, assign EXACTLY one bucket:

  CANDIDATE_GENERATION   — gold never appears in the hybrid candidate pool
  SEMANTIC_PROFILE_QUALITY — meaning is in the text but gold semantic rank is weak
  HYBRID_RANKING         — gold in pool, another intent outranks it
  ACTION_GRANULARITY     — same topic, wrong action type (e.g. definition vs when)
  EVIDENCE_REJECTED      — a part that would have matched gold was dropped by evidence 0.4
  ACCEPTANCE_GATE        — gold is hybrid top1 but _accept_match rejects it
  STT_DISTORTION         — script carries gold cues the ASR transcript lost
  SEGMENTATION_RESIDUAL  — >1 gold action trapped in one fragment / unopened clause
                           (fuh4_080 is the diagnostic exemplar, not a special rule)

    python scripts/v5_b5_residual_matching.py
Writes reports/V5_B5_RESIDUAL_MATCHING.{md,json}.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V4 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V4_REPORT.json"
PACK = ROOT.parent / "frontend" / "public" / "voice-drill" / "final-unseen-holdout-v4"
SCRIPTS = PACK / "scripts.json"

EVIDENCE_THETA = 0.4
HYBRID_POOL_K = 8
SEMANTIC_DEEP_K = 50

BUCKETS = (
    "STT_DISTORTION",
    "SEGMENTATION_RESIDUAL",
    "EVIDENCE_REJECTED",
    "CANDIDATE_GENERATION",
    "SEMANTIC_PROFILE_QUALITY",
    "ACTION_GRANULARITY",
    "HYBRID_RANKING",
    "ACCEPTANCE_GATE",
)


def _f(x, n=4):
    try:
        return round(float(x), n)
    except Exception:
        return None


# ── shape / candidate helpers (identical to B3/B4) ─────────────────────────
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


def install_v5_detect_intent():
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

    def restore():
        QB.detect_intent = original
        QB.question_bank.load(force=True)

    return restore


def evidence_ratio(sub_question: str, transcript: str) -> float:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _content_tokens

    q = set(_content_tokens(normalize_for_matching(sub_question or "")))
    t = set(_content_tokens(normalize_for_matching(transcript or "")))
    if not q:
        return 0.0
    return len(q & t) / len(q)


def evidence_ok(sub_question: str, transcript: str, theta: float) -> bool:
    return evidence_ratio(sub_question, transcript) >= theta


def topic_of(intent_id: str) -> str:
    return (intent_id or "").split(".", 1)[0]


def load_scripts() -> dict[str, str]:
    raw = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    out = {}
    for row in raw:
        if row.get("warmup"):
            continue
        out[str(row["id"])] = str(row.get("transcript") or "")
    return out


def load_compound() -> list[dict]:
    rep = json.loads(V4.read_text(encoding="utf-8"))
    return [
        r for r in rep["results"]
        if not str(r.get("notes") or "").startswith("warmup:")
        and (r.get("question_type_label") or "") == "compound"
    ]


def forced_resolution(text: str):
    from app.services.compound_question_detector import (
        ComplexityDetection,
        detect_question_complexity,
    )
    from app.services.compound_question_pipeline import resolve_compound_question

    if not (text or "").strip():
        return None
    det = detect_question_complexity(text)
    force = det
    if det is None or det.question_type == "single":
        force = ComplexityDetection(
            "compound", 0.9,
            max(2, int(getattr(det, "request_count_estimate", 1) or 1)),
            ("labeled_compound_pack",),
        )
    return resolve_compound_question(text, conversation_history=None, detection=force)


def path_opens(text: str) -> bool:
    from app.services.compound_question_detector import detect_question_complexity

    det = detect_question_complexity(text)
    return det.question_type != "single" or r1_min8w(text)


def accept_first(text: str):
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank

    tops = question_bank.top_matches(text, top_k=6)
    m = tops[0] if tops else None
    ok, reason, margin = _accept_match(m) if m else (False, "no_match", 0.0)
    return m.entry.id if (m and ok) else None, m, ok, reason, margin


def hybrid_pool(text: str, k: int = HYBRID_POOL_K) -> list[dict]:
    from app.services.question_bank import question_bank

    tops = question_bank.top_matches(text, top_k=k)
    out = []
    for i, m in enumerate(tops):
        out.append({
            "rank": i + 1,
            "id": m.entry.id,
            "topic": m.entry.topic,
            "score": _f(m.score),
            "semantic": _f(m.semantic),
            "lexical": _f(m.lexical),
            "keyword": _f(m.keyword),
            "mode": m.mode,
            "runner_up": m.runner_up,
            "runner_up_score": _f(m.runner_up_score),
            "action_type": getattr(m.entry, "intent", None) or detect_action(m.entry.question),
        })
    return out


def detect_action(text: str) -> str | None:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import detect_intent

    return detect_intent(normalize_for_matching(text or ""))


def semantic_ranks(text: str, gold_id: str, k: int = SEMANTIC_DEEP_K) -> dict:
    from app.services.semantic_intent_index import semantic_intent_index

    if not text.strip() or not semantic_intent_index.ready:
        return {"rank": None, "score": None, "top5": [], "deep_present": False}
    hits = semantic_intent_index.top_k(text, k=k)
    top5 = [{"rank": i + 1, "id": h.intent_id, "score": _f(h.score)}
            for i, h in enumerate(hits[:5])]
    rank = None
    score = None
    for i, h in enumerate(hits):
        if h.intent_id == gold_id:
            rank = i + 1
            score = _f(h.score)
            break
    return {
        "rank": rank,
        "score": score,
        "top5": top5,
        "deep_present": rank is not None,
        "deep_k": k,
    }


def content_tokens(text: str) -> set[str]:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _content_tokens

    return set(_content_tokens(normalize_for_matching(text or "")))


def stt_distortion(script: str, asr: str, gold_entry) -> tuple[bool, dict]:
    """True when script carries gold content the ASR transcript lost."""
    gq = gold_entry.question if gold_entry else ""
    g_tok = content_tokens(gq) | content_tokens(gold_entry.id.replace(".", " ") if gold_entry else "")
    # distinctive-ish: tokens length >= 4 from gold question
    g_key = {t for t in g_tok if len(t) >= 4}
    if not g_key:
        return False, {"gold_keys": [], "lost": [], "script_hits": 0, "asr_hits": 0}
    s_tok = content_tokens(script)
    a_tok = content_tokens(asr)
    script_hits = g_key & s_tok
    asr_hits = g_key & a_tok
    lost = sorted(script_hits - asr_hits)
    # distortion if script retained meaningful gold cues ASR dropped
    bad = len(script_hits) >= 2 and len(lost) >= 2 and len(asr_hits) < len(script_hits) / 2
    return bad, {
        "gold_keys": sorted(g_key),
        "script_hits": sorted(script_hits),
        "asr_hits": sorted(asr_hits),
        "lost": lost,
    }


def working_parts(transcript: str, *, apply_evidence: bool) -> tuple[list[str], list[dict]]:
    """
    Forced decomposition + optional evidence filter + enumeration split (I).
    Returns (query_fragments, audit rows for every raw sub before/after evidence).
    """
    res = forced_resolution(transcript)
    raw_subs = list(getattr(res, "sub_questions", None) or [])
    notes = list(getattr(res, "decomposition_notes", None) or [])
    audit = []
    kept = []
    for s in raw_subs:
        ratio = evidence_ratio(s, transcript)
        drop = apply_evidence and ratio < EVIDENCE_THETA
        audit.append({
            "sub_question": s,
            "evidence_ratio": _f(ratio),
            "dropped_by_evidence": drop,
            "from_facet": any(str(n).startswith("facet:") for n in notes),
        })
        if drop:
            continue
        frags = split_enumeration(s) or [s]
        for f in frags:
            if apply_evidence and not evidence_ok(f, transcript, EVIDENCE_THETA):
                audit.append({
                    "sub_question": f,
                    "evidence_ratio": _f(evidence_ratio(f, transcript)),
                    "dropped_by_evidence": True,
                    "from_facet": False,
                    "via_enumeration_split": True,
                })
                continue
            kept.append(f)
    return kept, audit


def project_selected(transcript: str) -> list[str]:
    """Full candidate projection selection (with >=2-intent guard)."""
    from app.services.question_bank import question_bank

    if not path_opens(transcript):
        m = question_bank.match(transcript)
        return [m.entry.id] if m is not None else []
    parts, _ = working_parts(transcript, apply_evidence=True)
    out = []
    for p in parts:
        got, *_rest = accept_first(p)
        if got:
            out.append(got)
    # dedupe preserve order
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    if len(uniq) < 2:
        m = question_bank.match(transcript)
        return [m.entry.id] if m is not None else []
    return uniq


def best_fragment_for_gold(parts: list[str], gold_id: str) -> tuple[str | None, list[dict], dict]:
    """Pick the fragment where gold ranks best in hybrid (then semantic)."""
    best_text = None
    best_pool: list[dict] = []
    best_sem: dict = {}
    best_key = (10**9, 10**9)  # hybrid rank, semantic rank
    for p in parts:
        pool = hybrid_pool(p)
        sem = semantic_ranks(p, gold_id)
        hy_rank = next((c["rank"] for c in pool if c["id"] == gold_id), 10**9)
        se_rank = sem["rank"] if sem["rank"] is not None else 10**9
        key = (hy_rank, se_rank)
        if key < best_key:
            best_key = key
            best_text = p
            best_pool = pool
            best_sem = sem
    if best_text is None and parts:
        best_text = parts[0]
        best_pool = hybrid_pool(best_text)
        best_sem = semantic_ranks(best_text, gold_id)
    return best_text, best_pool, best_sem


def gold_action_type(gold_id: str, gold_entry) -> str | None:
    if gold_entry is None:
        return None
    # Prefer bank-tagged intent on aliases if any; else detect from question.
    return detect_action(gold_entry.question)


def assign_bucket(case: dict) -> str:
    """Exclusive priority — first match wins."""
    if case["stt_distortion"]:
        return "STT_DISTORTION"
    if case["segmentation_residual"]:
        return "SEGMENTATION_RESIDUAL"
    if case["evidence_rejected"]:
        return "EVIDENCE_REJECTED"
    hy_rank = case["hybrid_gold_rank"]
    sem_rank = case["semantic_gold_rank"]
    top1 = case["hybrid_top1_id"]
    if hy_rank is None:
        # Not in hybrid pool.
        if sem_rank is None or sem_rank > 25:
            return "CANDIDATE_GENERATION"
        if sem_rank > 5:
            return "SEMANTIC_PROFILE_QUALITY"
        # In semantic top5 but not hybrid pool → ranking/surface failure
        return "HYBRID_RANKING"
    if hy_rank > 1:
        if case["action_granularity"]:
            return "ACTION_GRANULARITY"
        # Weak semantic despite being somewhere in hybrid → profile still suspect
        if sem_rank is not None and sem_rank > 5 and case["text_carries_meaning"]:
            return "SEMANTIC_PROFILE_QUALITY"
        return "HYBRID_RANKING"
    # hy_rank == 1
    if not case["accepted"]:
        return "ACCEPTANCE_GATE"
    # Accepted as top1 on a fragment but missing from final selection:
    # usually another fragment / guard / dedupe — treat as segmentation if
    # multiple golds share one fragment, else hybrid competition across parts.
    if case["segmentation_residual"]:
        return "SEGMENTATION_RESIDUAL"
    return "HYBRID_RANKING"


def main() -> int:
    if not V4.is_file():
        print(f"missing {V4}")
        return 1

    from app.services.compound_question_detector import detect_question_complexity
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank
    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()
    from app.services.semantic_intent_index import semantic_intent_index

    warm = bool(semantic_intent_index.ready)
    if not warm:
        print("!! semantic_index_ready=False — abort B5 (needs warm ranks)")
        return 2

    restore = install_v5_detect_intent()
    try:
        scripts = load_scripts()
        compound = load_compound()
        print(f"compound={len(compound)}  semantic_index_ready={warm}")

        missing_cases = []
        clip_summaries = []

        for r in compound:
            cid = r["sample_id"]
            asr = (r.get("transcript") or "").strip()
            script = (scripts.get(cid) or "").strip()
            gold = list(r.get("expected_intent_ids") or [])
            opened = path_opens(asr)
            selected = project_selected(asr)
            hit = [g for g in gold if g in selected]
            miss = [g for g in gold if g not in selected]

            # Parts with and without evidence (for EVIDENCE_REJECTED).
            parts_evid, audit_evid = working_parts(asr, apply_evidence=True)
            parts_raw, audit_raw = working_parts(asr, apply_evidence=False)

            # Which golds would accept_first hit on any raw (no-evidence) part?
            raw_hits = {}
            for g in gold:
                raw_hits[g] = []
                for p in parts_raw:
                    got, m, ok, reason, margin = accept_first(p)
                    if got == g:
                        raw_hits[g].append({
                            "fragment": p,
                            "score": _f(m.score) if m else None,
                            "accepted": ok,
                        })

            evid_hits = {}
            for g in gold:
                evid_hits[g] = []
                for p in parts_evid:
                    got, m, ok, reason, margin = accept_first(p)
                    if got == g:
                        evid_hits[g].append({
                            "fragment": p,
                            "score": _f(m.score) if m else None,
                            "accepted": ok,
                        })

            frags = fragments(asr)
            sents = sentences(asr)
            multi_gold_one_clause = (
                len(gold) >= 2 and len(frags) <= 1 and len(sents) <= 1
            )

            clip_summaries.append({
                "clip": cid,
                "path_opened": opened,
                "detector": detect_question_complexity(asr).question_type,
                "transcript": asr,
                "script": script,
                "gold": gold,
                "selected": selected,
                "hit": hit,
                "miss": miss,
                "parts_with_evidence": parts_evid,
                "parts_without_evidence": parts_raw,
                "fragment_count": len(frags),
                "sentence_count": len(sents),
                "multi_gold_one_clause": multi_gold_one_clause,
            })
            print(f"  {cid}: opened={opened} hit={len(hit)}/{len(gold)} "
                  f"miss={miss}")

            for g in miss:
                entry = question_bank.get(g)
                frag, pool, sem = best_fragment_for_gold(
                    parts_evid if parts_evid else ([asr] if asr else []), g
                )
                # If path closed and no evid parts, still diagnose on whole ASR
                # and on raw parts for evidence comparison.
                if not frag:
                    frag = asr
                    pool = hybrid_pool(frag)
                    sem = semantic_ranks(frag, g)

                hy_rank = next((c["rank"] for c in pool if c["id"] == g), None)
                top1 = pool[0] if pool else None
                top1_id = top1["id"] if top1 else None
                gold_row = next((c for c in pool if c["id"] == g), None)
                gold_score = gold_row["score"] if gold_row else None

                # Acceptance on this fragment's actual top1 / on gold if top1
                tops = question_bank.top_matches(frag or "", top_k=HYBRID_POOL_K)
                top_m = tops[0] if tops else None
                accepted, reject_reason, margin = (
                    _accept_match(top_m) if top_m else (False, "no_match", 0.0)
                )
                gold_is_top1 = bool(top_m and top_m.entry.id == g)
                gold_accepted = False
                gold_reject = None
                if gold_is_top1 and top_m:
                    gold_accepted, gold_reject, margin = _accept_match(top_m)

                stt_bad, stt_detail = stt_distortion(script, asr, entry)

                # Evidence rejected: raw path can land gold, evid path cannot.
                evid_rej = bool(raw_hits.get(g)) and not bool(evid_hits.get(g))
                # Also: a raw sub that is gold-like was dropped by evidence.
                if not evid_rej:
                    for row in audit_raw:
                        if not row.get("dropped_by_evidence"):
                            # check counterpart in evid audit
                            pass
                    for row in audit_evid:
                        if row.get("dropped_by_evidence"):
                            # would this dropped sub have matched gold?
                            sub = row["sub_question"]
                            got, m, ok, reason, _mg = accept_first(sub)
                            if got == g or (m and m.entry.id == g):
                                evid_rej = True
                                break

                g_action = gold_action_type(g, entry)
                top_action = top1.get("action_type") if top1 else None
                same_topic = bool(
                    top1_id and topic_of(top1_id) == topic_of(g)
                )
                action_gran = bool(
                    hy_rank and hy_rank > 1 and same_topic
                    and g_action and top_action and g_action != top_action
                )
                # Sibling = same topic, different id
                sibling = bool(top1_id and same_topic and top1_id != g)

                # Meaning present: content overlap between fragment and gold Q
                g_tok = content_tokens(entry.question if entry else "")
                f_tok = content_tokens(frag or "")
                overlap = g_tok & f_tok
                text_carries = len(overlap) >= max(1, min(2, len(g_tok) // 3)) if g_tok else False

                seg_residual = bool(
                    multi_gold_one_clause
                    or (
                        # this gold shares its best fragment with another gold
                        frag
                        and sum(
                            1 for og in gold
                            if og != g and any(
                                accept_first(frag)[0] == og
                                or (hybrid_pool(frag) and hybrid_pool(frag)[0]["id"] == og)
                                for _ in [0]
                            )
                        ) >= 0
                        and len(gold) >= 2
                        and len(parts_evid) <= 1
                        and len(frags) <= 1
                    )
                )
                # Tighten segmentation: path closed + single clause multi-gold,
                # OR only one working part for >=2 golds.
                seg_residual = bool(
                    (not opened and len(gold) >= 2 and len(frags) <= 1 and len(sents) <= 1)
                    or (opened and len(gold) >= 2 and len(parts_evid) <= 1
                        and len(frags) <= 1 and len(sents) <= 1)
                    or (cid == "fuh4_080")  # exemplar flag only reinforces pattern test
                    and len(gold) >= 2 and len(frags) <= 1
                )
                # Cleaner exclusive segmentation rule:
                seg_residual = (
                    len(gold) >= 2
                    and len(frags) <= 1
                    and len(sents) <= 1
                )

                case = {
                    "clip": cid,
                    "transcript": asr,
                    "script": script,
                    "path_opened": opened,
                    "fragment": frag,
                    "gold_intent": g,
                    "gold_question": entry.question if entry else None,
                    "gold_topic": entry.topic if entry else topic_of(g),
                    "gold_action_type": g_action,
                    "selected_intents": selected,
                    "hybrid_top5": pool[:5],
                    "hybrid_top1_id": top1_id,
                    "hybrid_top1_topic": top1.get("topic") if top1 else None,
                    "hybrid_top1_action_type": top_action,
                    "hybrid_top1_is_sibling_same_topic": sibling,
                    "hybrid_gold_rank": hy_rank,
                    "gold_score": gold_score,
                    "semantic_full_rank": sem,
                    "semantic_gold_rank": sem.get("rank"),
                    "semantic_gold_score": sem.get("score"),
                    "semantic_top5": sem.get("top5"),
                    "evidence_score_fragment": _f(evidence_ratio(frag or "", asr)),
                    "evidence_rejected": evid_rej,
                    "raw_path_gold_hits": raw_hits.get(g) or [],
                    "evid_path_gold_hits": evid_hits.get(g) or [],
                    "accepted": bool(gold_is_top1 and gold_accepted),
                    "reject_reason": gold_reject if gold_is_top1 else (
                        reject_reason if top_m else "no_match"
                    ),
                    "accept_margin": _f(margin),
                    "stt_distortion": stt_bad,
                    "stt_detail": stt_detail,
                    "segmentation_residual": seg_residual,
                    "action_granularity": action_gran,
                    "text_carries_meaning": text_carries,
                    "content_overlap_tokens": sorted(overlap),
                }
                case["bucket"] = assign_bucket(case)
                missing_cases.append(case)
                print(
                    f"    MISS {g}: bucket={case['bucket']} "
                    f"hy_rank={hy_rank} sem_rank={sem.get('rank')} "
                    f"top1={top1_id} evid_rej={evid_rej} seg={seg_residual}"
                )

        tally = Counter(c["bucket"] for c in missing_cases)
        n_miss = len(missing_cases) or 1
        dominant = tally.most_common(1)[0][0] if missing_cases else None
        dominant_n = tally[dominant] if dominant else 0
        dominant_share = _f(dominant_n / n_miss)

        # Next-step recommendation (mechanical).
        if dominant in ("SEMANTIC_PROFILE_QUALITY", "CANDIDATE_GENERATION"):
            next_step = (
                "One experiment: general profile / candidate-generation quality "
                "(not clip-specific). Do not touch routing."
            )
        elif dominant in ("HYBRID_RANKING", "ACTION_GRANULARITY"):
            next_step = (
                "One counterfactual on ranking / action-type discrimination "
                "(measurement only first)."
            )
        elif dominant == "EVIDENCE_REJECTED":
            next_step = (
                "Redesign evidence grounding (structure), do NOT simply lower theta."
            )
        elif dominant == "ACCEPTANCE_GATE":
            next_step = "One counterfactual on _accept_match gates (score/margin)."
        elif dominant == "STT_DISTORTION":
            next_step = "Separate STT robustness track; not an intent-layer change."
        elif dominant == "SEGMENTATION_RESIDUAL":
            next_step = (
                "One structural experiment: multiple requested actions inside one "
                "clause without list separators (general pattern; no fuh4_080 rule)."
            )
        else:
            next_step = "No missing parts — unexpected."

        decision = {
            "missing_gold_parts": len(missing_cases),
            "bucket_tally": dict(tally),
            "dominant_bucket": dominant,
            "dominant_count": dominant_n,
            "dominant_share": dominant_share,
            "clear_dominant": bool(dominant and dominant_share is not None
                                   and dominant_share >= 0.35),
            "next_step": next_step,
            "routing_status": "CLOSED — do not expand unless path_opened=false dominates",
            "path_closed_misses": sum(1 for c in missing_cases if not c["path_opened"]),
        }
        print(f"\n=== B5 DOMINANT: {dominant} ({dominant_n}/{len(missing_cases)} "
              f"= {dominant_share}) ===")
        print(f"  next: {next_step}")

    finally:
        restore()

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "V5 Phase B5 — residual matching/profile analysis",
        "scope": "measurement only; routing closed; no app/ changes",
        "candidate": "R1_min8w + evidence 0.4 + I + H (+ >=2-intent guard)",
        "semantic_index_ready": warm,
        "clip_summaries": clip_summaries,
        "missing_parts": missing_cases,
        "decision": decision,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_B5_RESIDUAL_MATCHING.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        "# V5 Phase B5 — residual matching / profile analysis",
        "",
        f"Created: {payload['created_at']}",
        f"`semantic_index_ready={warm}`",
        "",
        "Measurement only. Routing is **closed**. Candidate under analysis:",
        f"`{payload['candidate']}`",
        "",
        "## Bucket tally (one bucket per missing gold part)",
        "",
        "| bucket | count | share |",
        "|---|---:|---:|",
    ]
    for b, n in tally.most_common():
        md.append(f"| **{b}** | {n} | {_f(n / n_miss)} |")
    for b in BUCKETS:
        if b not in tally:
            md.append(f"| {b} | 0 | 0 |")
    md += [
        "",
        f"**Dominant:** `{dominant}` "
        f"({dominant_n}/{len(missing_cases)} = {dominant_share})"
        + (" — clear" if decision["clear_dominant"] else " — not ≥35%, inspect ties"),
        "",
        f"**Next step:** {next_step}",
        "",
        f"Path-closed misses: {decision['path_closed_misses']}/"
        f"{len(missing_cases)} "
        "(re-open routing only if these dominate — they should not).",
        "",
        "## Per missing gold part",
        "",
        "| clip | gold | bucket | fragment | hy rank | sem rank | top1 | sibling? | evid | reject |",
        "|---|---|---|---|---:|---:|---|---|---:|---|",
    ]
    for c in missing_cases:
        frag_short = (c["fragment"] or "")[:48].replace("|", "/")
        md.append(
            f"| {c['clip']} | `{c['gold_intent']}` | **{c['bucket']}** | "
            f"{frag_short} | {c['hybrid_gold_rank'] or '—'} | "
            f"{c['semantic_gold_rank'] or '—'} | `{c['hybrid_top1_id']}` | "
            f"{c['hybrid_top1_is_sibling_same_topic']} | "
            f"{c['evidence_score_fragment']} | {c['reject_reason'] or '—'} |"
        )

    md += ["", "## Detail blocks", ""]
    for c in missing_cases:
        md += [
            f"### {c['clip']} — `{c['gold_intent']}` → {c['bucket']}",
            "",
            f"- script: `{c['script']}`",
            f"- asr: `{c['transcript']}`",
            f"- path_opened: {c['path_opened']}",
            f"- fragment: `{c['fragment']}`",
            f"- gold Q: `{c['gold_question']}`",
            f"- gold action: `{c['gold_action_type']}` topic=`{c['gold_topic']}`",
            f"- hybrid top5: `{c['hybrid_top5']}`",
            f"- semantic top5: `{c['semantic_top5']}`",
            f"- gold score: {c['gold_score']}  evid: {c['evidence_score_fragment']}",
            f"- top1: `{c['hybrid_top1_id']}` action=`{c['hybrid_top1_action_type']}` "
            f"sibling={c['hybrid_top1_is_sibling_same_topic']}",
            f"- accept: gold_top1_accepted={c['accepted']} reason={c['reject_reason']}",
            f"- stt_distortion={c['stt_distortion']} lost={c['stt_detail'].get('lost')}",
            f"- evidence_rejected={c['evidence_rejected']} "
            f"seg={c['segmentation_residual']} gran={c['action_granularity']}",
            "",
        ]

    (REPORTS / "V5_B5_RESIDUAL_MATCHING.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nwrote {REPORTS / 'V5_B5_RESIDUAL_MATCHING.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
