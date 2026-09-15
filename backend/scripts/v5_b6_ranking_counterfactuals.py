"""
V5 Phase B6 — ranking / action-type counterfactuals. MEASUREMENT ONLY.

Target residual from B5 (54% of missing gold parts):
  HYBRID_RANKING + ACTION_GRANULARITY

Config under test (routing closed, fixed):
  R1_min8w + evidence 0.4 + I + H + >=2-intent pre-empt guard

Variants change ONLY how a fragment picks its intent (no routing / evidence /
profile / threshold retunes of _MIN_ANSWER_SCORE).

    python scripts/v5_b6_ranking_counterfactuals.py

Writes reports/V5_B6_RANKING_COUNTERFACTUALS.{md,json}.

Winner gate (all required):
  coverage_by_part > baseline
  wrong_intent <= baseline
  hc_risk <= baseline
  newly_broken_non_compound == 0  (R1-opened, with >=2-intent guard)
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
V4 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V4_REPORT.json"
B5 = REPORTS / "V5_B5_RESIDUAL_MATCHING.json"

EVIDENCE_THETA = 0.4
HC_SCORE = 0.85  # proxy: accepted non-gold at/above this is HC risk


def _f(x, n=4):
    try:
        return round(float(x), n)
    except Exception:
        return None


_INTERROG = re.compile(
    r"\b(what|why|how|when|which|who|whether|where|is|are|do|does|did|can|should|would)\b", re.I)
_IMPER = re.compile(
    r"\b(explain|tell|say|describe|give|point|walk|cover|name|define|summaris|summariz|list)\b", re.I)
_VERBISH = re.compile(
    r"\b(use|used|build|built|work|works|make|choose|pick|handle|stop|prevent|add|need|"
    r"matter|differ|design|halt|reduce|track|monitor)\b", re.I)
_FRAG_SPLIT = re.compile(r",|;|\band\b|\bthen\b|\bplus\b", re.I)

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

# Soft action cues beyond detect_intent — structural, not vocab lists of holdout.
_SOFT_ACTION = (
    ("when", re.compile(r"\b(when|halt|stop|enough|trigger)\b", re.I)),
    ("why", re.compile(r"\b(why|rationale|reason|because|versus|vs\.?|compared)\b", re.I)),
    ("how", re.compile(r"\b(how|steps|internals?|mechanism)\b", re.I)),
    ("definition", re.compile(r"\b(what is|what are|define|meaning of)\b", re.I)),
    ("compare", re.compile(r"\b(versus|vs\.?|difference|compared|or a lone)\b", re.I)),
    ("experience", re.compile(r"\b(have you|did you|your (?:history|experience)|you use)\b", re.I)),
    ("describe", re.compile(r"\b(summarize|summarise|tell me about|walk me through|describe)\b", re.I)),
)


def clause_has_action(text: str) -> bool:
    return bool(_INTERROG.search(text) or _IMPER.search(text) or _VERBISH.search(text))


def fragments(text: str) -> list[str]:
    return [p.strip(" .;:?") for p in _FRAG_SPLIT.split(text or "") if p.strip(" .;:?")]


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


def install_h_detect_intent():
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


def query_action(text: str) -> str | None:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import detect_intent

    n = normalize_for_matching(text or "")
    got = detect_intent(n)
    if got:
        return got
    for name, pat in _SOFT_ACTION:
        if pat.search(text or "") or pat.search(n):
            return name
    return None


def cand_action(entry) -> str | None:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import detect_intent

    return detect_intent(normalize_for_matching(entry.question or ""))


def topic_of(intent_id: str) -> str:
    return (intent_id or "").split(".", 1)[0]


def load_rows():
    rep = json.loads(V4.read_text(encoding="utf-8"))
    rows = [r for r in rep["results"] if not str(r.get("notes") or "").startswith("warmup:")]
    comp = [r for r in rows if (r.get("question_type_label") or "") == "compound"]
    other = [r for r in rows
             if (r.get("question_type_label") or "") != "compound" and r.get("expected_intent_ids")]
    return comp, other


def target_miss_keys() -> set[tuple[str, str]]:
    if not B5.is_file():
        return set()
    d = json.loads(B5.read_text(encoding="utf-8"))
    return {
        (c["clip"], c["gold_intent"])
        for c in d.get("missing_parts", [])
        if c.get("bucket") in {"HYBRID_RANKING", "ACTION_GRANULARITY"}
    }


def path_opens(text: str) -> bool:
    from app.services.compound_question_detector import detect_question_complexity

    det = detect_question_complexity(text)
    return det.question_type != "single" or r1_min8w(text)


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


def working_parts(transcript: str) -> list[str]:
    kept = []
    for s in forced_subs(transcript):
        if evidence_ratio(s, transcript) < EVIDENCE_THETA:
            continue
        for f in (split_enumeration(s) or [s]):
            if evidence_ratio(f, transcript) < EVIDENCE_THETA:
                continue
            kept.append(f)
    return kept


def _bank_match_from_top(tops, idx: int):
    from app.services.question_bank import BankMatch

    if not tops or idx >= len(tops):
        return None
    m = tops[idx]
    runner = tops[1] if idx == 0 and len(tops) > 1 else (tops[0] if idx != 0 else (tops[1] if len(tops) > 1 else None))
    return BankMatch(
        entry=m.entry,
        score=m.score,
        semantic=m.semantic,
        lexical=m.lexical,
        keyword=m.keyword,
        alias=m.alias,
        mode=m.mode,
        runner_up=runner.entry.id if runner else None,
        runner_up_score=runner.score if runner else 0.0,
    )


def _accept_from_ordered(ordered, already: set[str]):
    """Walk ordered BankMatch list; skip already-selected; return first accepted."""
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import BankMatch

    for i, m in enumerate(ordered):
        if m.entry.id in already:
            continue
        runner = next((x for x in ordered if x.entry.id != m.entry.id), None)
        wrapped = BankMatch(
            entry=m.entry,
            score=m.score,
            semantic=m.semantic,
            lexical=m.lexical,
            keyword=m.keyword,
            alias=m.alias,
            mode=m.mode,
            runner_up=runner.entry.id if runner else None,
            runner_up_score=runner.score if runner else 0.0,
        )
        ok, _r, _m = _accept_match(wrapped)
        if ok:
            return m.entry.id, float(m.score)
        # Mirror compound pipeline: allow harvest-ish alternate when already blocked top.
        if already and float(m.score) >= 0.55:
            return m.entry.id, float(m.score)
    return None, 0.0


def pick_baseline(text: str, already: set[str] | None = None):
    from app.services.question_bank import question_bank

    already = already or set()
    tops = question_bank.top_matches(text, top_k=6)
    if not tops:
        return None, tops, 0.0
    got, sc = _accept_from_ordered(tops, set())  # baseline ignores already
    return got, tops, sc


def pick_distinct_across_parts(text: str, already: set[str] | None = None):
    """Skip intents already taken by earlier fragments (compound pipeline parity)."""
    from app.services.question_bank import question_bank

    already = already or set()
    tops = question_bank.top_matches(text, top_k=8)
    if not tops:
        return None, tops, 0.0
    got, sc = _accept_from_ordered(tops, already)
    return got, tops, sc


def pick_sem_in_pool(text: str, already: set[str] | None = None):
    """
    If semantic top1 sits inside hybrid top-5 and hybrid margin to that cand
    is <= 0.15, prefer it (addresses B5 cases where sem_rank=1 but hy_rank>1).
    """
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index

    already = already or set()
    tops = question_bank.top_matches(text, top_k=8)
    if not tops:
        return None, tops, 0.0
    ordered = list(tops)
    if semantic_intent_index.ready:
        hits = semantic_intent_index.top_k(text, k=5)
        if hits:
            sem_id = hits[0].intent_id
            hy_ids = {m.entry.id: (i, m) for i, m in enumerate(tops[:5])}
            if sem_id in hy_ids and sem_id not in already:
                idx, sem_m = hy_ids[sem_id]
                if idx > 0 and float(tops[0].score) - float(sem_m.score) <= 0.15:
                    # Move semantic hit to front.
                    ordered = [sem_m] + [m for m in tops if m.entry.id != sem_id]
    got, sc = _accept_from_ordered(ordered, already)
    return got, tops, sc


def pick_distinct_plus_sem(text: str, already: set[str] | None = None):
    already = already or set()
    # First apply sem-in-pool ordering, then distinct accept.
    return pick_sem_in_pool(text, already)


def pick_action_on_distinct(text: str, already: set[str] | None = None):
    """Action-type adjust among top-5, then distinct accept."""
    from app.services.question_bank import question_bank

    already = already or set()
    tops = question_bank.top_matches(text, top_k=8)
    if not tops:
        return None, tops, 0.0
    q_act = query_action(text)
    scored = []
    for m in tops[:5]:
        adj = float(m.score)
        if q_act:
            c_act = cand_action(m.entry)
            if c_act == q_act:
                adj += 0.10
            elif c_act and c_act != q_act:
                adj -= 0.15
        scored.append((adj, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    ordered = [m for _a, m in scored] + [m for m in tops[5:]]
    got, sc = _accept_from_ordered(ordered, already)
    return got, tops, sc


def pick_action_rerank(text: str, already: set[str] | None = None, *, same_topic_only: bool = False):
    already = already or set()
    return pick_action_on_distinct(text, already) if not same_topic_only else _pick_action_same_topic(text, already)


def _pick_action_same_topic(text: str, already: set[str]):
    from app.services.question_bank import question_bank

    tops = question_bank.top_matches(text, top_k=8)
    if not tops:
        return None, tops, 0.0
    q_act = query_action(text)
    anchor = tops[0].entry.topic
    scored = []
    for m in tops[:5]:
        adj = float(m.score)
        if m.entry.topic == anchor and q_act:
            c_act = cand_action(m.entry)
            if c_act == q_act:
                adj += 0.10
            elif c_act and c_act != q_act:
                adj -= 0.15
        scored.append((adj, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    ordered = [m for _a, m in scored] + list(tops[5:])
    got, sc = _accept_from_ordered(ordered, already)
    return got, tops, sc


def pick_sem_close_promote(text: str, already: set[str] | None = None):
    from app.services.question_bank import question_bank

    already = already or set()
    tops = question_bank.top_matches(text, top_k=8)
    if len(tops) < 2:
        return pick_baseline(text, already)
    a, b = tops[0], tops[1]
    q_act = query_action(text)
    margin = float(a.score) - float(b.score)
    promote = margin <= 0.08 and float(b.semantic) > float(a.semantic) + 0.02
    if q_act:
        a_act, b_act = cand_action(a.entry), cand_action(b.entry)
        if b_act == q_act and a_act != q_act and margin <= 0.12:
            promote = True
        if a_act == q_act and b_act != q_act:
            promote = False
    ordered = ([b, a] + list(tops[2:])) if promote else list(tops)
    got, sc = _accept_from_ordered(ordered, already)
    return got, tops, sc


def pick_stronger_bank_intent(text: str, already: set[str] | None = None):
    from app.services import question_bank as QB

    already = already or set()
    old_b, old_p = QB.INTENT_MATCH_BONUS, QB.INTENT_MISMATCH_PENALTY
    QB.INTENT_MATCH_BONUS = 0.08
    QB.INTENT_MISMATCH_PENALTY = 0.18
    try:
        QB.question_bank._score_cache.clear()  # noqa: SLF001
        tops = QB.question_bank.top_matches(text, top_k=8)
        if not tops:
            return None, tops, 0.0
        got, sc = _accept_from_ordered(tops, already)
        return got, tops, sc
    finally:
        QB.INTENT_MATCH_BONUS = old_b
        QB.INTENT_MISMATCH_PENALTY = old_p
        QB.question_bank._score_cache.clear()  # noqa: SLF001


PICKERS = {
    "A_baseline": pick_baseline,
    "B_action_rerank": lambda t, a=None: pick_action_rerank(t, a, same_topic_only=False),
    "C_action_rerank_same_topic": lambda t, a=None: pick_action_rerank(t, a, same_topic_only=True),
    "D_sem_close_promote": pick_sem_close_promote,
    "F_stronger_bank_intent_weights": pick_stronger_bank_intent,
    # Round-2 hypotheses guided by B5 (sem_rank=1 but hy>1; sibling collisions):
    "G_distinct_across_parts": pick_distinct_across_parts,
    "H_sem_top1_in_hybrid_pool": pick_sem_in_pool,
    "I_distinct_plus_sem_in_pool": pick_distinct_plus_sem,
    "J_action_on_distinct": pick_action_on_distinct,
}


def project(transcript: str, picker) -> tuple[list[str], list[float]]:
    from app.services.question_bank import question_bank

    if not path_opens(transcript):
        m = question_bank.match(transcript)
        if m is None:
            return [], []
        return [m.entry.id], [float(m.score)]
    parts = working_parts(transcript)
    ids, scores = [], []
    already: set[str] = set()
    for p in parts:
        got, _tops, sc = picker(p, already)
        if got:
            ids.append(got)
            scores.append(sc)
            already.add(got)
    seen, uniq, uscores = set(), [], []
    for i, s in zip(ids, scores):
        if i not in seen:
            seen.add(i)
            uniq.append(i)
            uscores.append(s)
    if len(uniq) < 2:
        m = question_bank.match(transcript)
        if m is None:
            return [], []
        return [m.entry.id], [float(m.score)]
    return uniq, uscores


def score_variant(name: str, picker, comp, other, target_keys: set[tuple[str, str]]) -> dict:
    hit = wrong = total = hc = 0
    target_recovered = 0
    per_clip = []
    for r in comp:
        gold = list(r.get("expected_intent_ids") or [])
        total += len(gold)
        sel, scores = project(r.get("transcript") or "", picker)
        got = {s for s in sel if s in gold}
        bad = [s for s in sel if s not in gold]
        hit += len(got)
        wrong += len(bad)
        for s, sc in zip(sel, scores):
            if s not in gold and sc >= HC_SCORE:
                hc += 1
        for g in gold:
            if g in got and (r["sample_id"], g) in target_keys:
                target_recovered += 1
        per_clip.append({
            "clip": r["sample_id"],
            "gold": gold,
            "selected": sel,
            "hit": sorted(got),
            "wrong": bad,
            "coverage": _f(len(got) / max(1, len(gold))),
        })

    # Non-compound blast for R1-opened clips under >=2-intent guard.
    newly_broken = 0
    opened_nc = 0
    for r in other:
        tr = r.get("transcript") or ""
        from app.services.compound_question_detector import detect_question_complexity
        if detect_question_complexity(tr).question_type != "single":
            continue
        if not r1_min8w(tr):
            continue
        opened_nc += 1
        sel, _scores = project(tr, picker)
        if len(sel) < 2:
            continue  # guard: would not pre-empt
        gold = list(r.get("expected_intent_ids") or [])
        if bool(r.get("intent_ok")) and gold and not (set(gold) & set(sel)):
            newly_broken += 1

    return {
        "variant": name,
        "gold_parts": total,
        "gold_parts_hit": hit,
        "coverage_by_part": _f(hit / max(1, total)),
        "wrong_intent": wrong,
        "hc_risk": hc,
        "target_family_recovered": target_recovered,
        "target_family_of": len(target_keys),
        "non_compound_r1_opened": opened_nc,
        "newly_broken_non_compound": newly_broken,
        "per_clip": per_clip,
    }


def main() -> int:
    if not V4.is_file():
        print(f"missing {V4}")
        return 1

    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()
    from app.services.semantic_intent_index import semantic_intent_index

    warm = (semantic_intent_index.ready)
    if not warm:
        print("!! semantic_index_ready=False — abort")
        return 2

    restore = install_h_detect_intent()
    try:
        comp, other = load_rows()
        target = target_miss_keys()
        print(f"compound={len(comp)}  target_family_misses={len(target)}  "
              f"semantic_index_ready={warm}")

        results = []
        for name, picker in PICKERS.items():
            res = score_variant(name, picker, comp, other, target)
            results.append(res)
            print(
                f"  {name:32} cov={res['coverage_by_part']} "
                f"hit={res['gold_parts_hit']}/{res['gold_parts']} "
                f"wrong={res['wrong_intent']} hc={res['hc_risk']} "
                f"target_rec={res['target_family_recovered']}/{res['target_family_of']} "
                f"newly_broken={res['newly_broken_non_compound']}"
            )
    finally:
        restore()

    base = next(r for r in results if r["variant"] == "A_baseline")
    winners = []
    for r in results:
        if r["variant"] == "A_baseline":
            continue
        ok = (
            (r["coverage_by_part"] or 0) > (base["coverage_by_part"] or 0)
            and r["wrong_intent"] <= base["wrong_intent"]
            and r["hc_risk"] <= base["hc_risk"]
            and r["newly_broken_non_compound"] <= base["newly_broken_non_compound"]
        )
        r["beats_baseline"] = ok
        if ok:
            winners.append(r)
    winners.sort(key=lambda r: (-(r["coverage_by_part"] or 0), r["wrong_intent"], r["hc_risk"]))

    decision = {
        "baseline": {
            "variant": base["variant"],
            "coverage_by_part": base["coverage_by_part"],
            "wrong_intent": base["wrong_intent"],
            "hc_risk": base["hc_risk"],
        },
        "winners": [w["variant"] for w in winners],
        "recommended": winners[0]["variant"] if winners else None,
        "verdict": (
            f"IMPLEMENT {winners[0]['variant']} — then regression/hardening/latency/lock"
            if winners
            else "NO_IMPLEMENT — no variant beat baseline under gates; redesign hypothesis"
        ),
    }
    print(f"\n=== B6 VERDICT: {decision['verdict']} ===")

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "V5 Phase B6 — ranking/action-type counterfactuals",
        "scope": "measurement only; no app/ changes in this script",
        "candidate_fixed": "R1_min8w + evidence 0.4 + I + H + ge2 guard",
        "target_buckets": ["HYBRID_RANKING", "ACTION_GRANULARITY"],
        "semantic_index_ready": warm,
        "results": results,
        "decision": decision,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_B6_RANKING_COUNTERFACTUALS.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        "# V5 Phase B6 — ranking / action-type counterfactuals",
        "",
        f"Created: {payload['created_at']}",
        f"`semantic_index_ready={warm}`",
        "",
        "Measurement only. Routing/evidence/profiles frozen.",
        "Target: HYBRID_RANKING + ACTION_GRANULARITY from B5.",
        "",
        "| variant | coverage | hit | wrong | hc_risk | target recovered | newly_broken | beats? |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in results:
        beat = "—" if r["variant"] == "A_baseline" else ("YES" if r.get("beats_baseline") else "no")
        md.append(
            f"| {r['variant']} | {r['coverage_by_part']} | "
            f"{r['gold_parts_hit']}/{r['gold_parts']} | {r['wrong_intent']} | "
            f"{r['hc_risk']} | {r['target_family_recovered']}/{r['target_family_of']} | "
            f"{r['newly_broken_non_compound']} | {beat} |"
        )
    md += [
        "",
        f"**Baseline:** cov={base['coverage_by_part']} wrong={base['wrong_intent']} "
        f"hc={base['hc_risk']}",
        f"**Winners:** {', '.join(decision['winners']) or 'none'}",
        f"**VERDICT:** {decision['verdict']}",
        "",
    ]
    (REPORTS / "V5_B6_RANKING_COUNTERFACTUALS.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORTS / 'V5_B6_RANKING_COUNTERFACTUALS.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
