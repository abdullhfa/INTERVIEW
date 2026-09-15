"""
V5 Phase B6.1 — same-topic sibling action resolver. MEASUREMENT ONLY.

LAST narrow ranking experiment. If this fails the hard gate, close the
ranking/action-rerank path entirely (no more weight/rerank tuning).

Fires ONLY when ALL hold:
  1. query has a clear action type (detect_intent after H, no soft vocab fallback)
  2. hybrid top1 action differs from query action
  3. an alternate in hybrid top-5 shares the SAME topic/family as top1
  4. that alternate's action matches the query action
  5. that alternate is semantically close: sem_rank <= 3 among index hits for the fragment
  6. no topic change (never pick a different topic than top1)

Does NOT touch: thresholds, _accept_match gates, routing, evidence, profiles.

    python scripts/v5_b61_sibling_action_resolver.py
Writes reports/V5_B61_SIBLING_ACTION_RESOLVER.{md,json}.

Hard gate vs A_baseline (R1+evidence0.4+I+H+ge2):
  recovered_target_13 >= 3   (several real recovers from the 13)
  wrong_intent <= 4
  newly_broken_non_compound <= baseline
  hc_risk <= baseline
  coverage_by_part >= baseline   (must not regress)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V4 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V4_REPORT.json"
B5 = REPORTS / "V5_B5_RESIDUAL_MATCHING.json"

EVIDENCE_THETA = 0.4
HC_SCORE = 0.85
MIN_TARGET_RECOVER = 3

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


def _f(x, n=4):
    try:
        return round(float(x), n)
    except Exception:
        return None


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


def detect_action_strict(text: str) -> str | None:
    """Clear action only — detect_intent after H. No soft fallback."""
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import detect_intent

    return detect_intent(normalize_for_matching(text or ""))


def cand_action(entry) -> str | None:
    return detect_action_strict(entry.question or "")


def family_of(intent_id: str, entry=None) -> str:
    if entry is not None and getattr(entry, "topic", None):
        return str(entry.topic)
    return (intent_id or "").split(".", 1)[0]


def target_keys() -> set[tuple[str, str]]:
    d = json.loads(B5.read_text(encoding="utf-8"))
    return {
        (c["clip"], c["gold_intent"])
        for c in d.get("missing_parts", [])
        if c.get("bucket") in {"HYBRID_RANKING", "ACTION_GRANULARITY"}
    }


def load_rows():
    rep = json.loads(V4.read_text(encoding="utf-8"))
    rows = [r for r in rep["results"] if not str(r.get("notes") or "").startswith("warmup:")]
    comp = [r for r in rows if (r.get("question_type_label") or "") == "compound"]
    other = [
        r for r in rows
        if (r.get("question_type_label") or "") != "compound" and r.get("expected_intent_ids")
    ]
    return comp, other


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


def semantic_rank_map(text: str, ids: set[str], k: int = 25) -> dict[str, int]:
    from app.services.semantic_intent_index import semantic_intent_index

    out: dict[str, int] = {}
    if not text.strip() or not semantic_intent_index.ready:
        return out
    for i, h in enumerate(semantic_intent_index.top_k(text, k=k)):
        if h.intent_id in ids and h.intent_id not in out:
            out[h.intent_id] = i + 1
    return out


def pick_baseline(text: str, already: set[str] | None = None):
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank

    tops = question_bank.top_matches(text, top_k=6)
    if not tops:
        return None, 0.0, {"fired": False, "reason": "no_tops"}
    ok, _r, _m = _accept_match(tops[0])
    return (tops[0].entry.id if ok else None), float(tops[0].score), {
        "fired": False, "reason": "baseline", "top1": tops[0].entry.id,
    }


def pick_sibling_action(text: str, already: set[str] | None = None):
    """
    Same-topic sibling action resolver. Returns (id, score, trace).
    """
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import BankMatch, question_bank

    already = already or set()
    tops = question_bank.top_matches(text, top_k=6)
    trace: dict[str, Any] = {
        "fired": False,
        "reason": None,
        "query_action": None,
        "top1": None,
        "chosen": None,
        "alternate": None,
        "sem_rank_alt": None,
    }
    if not tops:
        trace["reason"] = "no_tops"
        return None, 0.0, trace

    top1 = tops[0]
    trace["top1"] = top1.entry.id
    q_act = detect_action_strict(text)
    trace["query_action"] = q_act
    if not q_act:
        ok, _r, _m = _accept_match(top1)
        trace["reason"] = "no_clear_query_action"
        return (top1.entry.id if ok else None), float(top1.score), trace

    top1_act = cand_action(top1.entry)
    if top1_act == q_act:
        ok, _r, _m = _accept_match(top1)
        trace["reason"] = "top1_already_matches_action"
        return (top1.entry.id if ok else None), float(top1.score), trace

    if not top1_act:
        # Still allow swap if top1 has no action but a sibling does match.
        pass
    elif top1_act == q_act:
        pass

    fam = family_of(top1.entry.id, top1.entry)
    pool = [m for m in tops[:5] if m.entry.id not in already]
    ids = {m.entry.id for m in pool}
    sem_ranks = semantic_rank_map(text, ids, k=25)

    # Candidates: same family, action matches query, semantically close (<=3).
    alts = []
    for m in pool:
        if m.entry.id == top1.entry.id:
            continue
        if family_of(m.entry.id, m.entry) != fam:
            continue
        c_act = cand_action(m.entry)
        if c_act != q_act:
            continue
        sr = sem_ranks.get(m.entry.id)
        if sr is None or sr > 3:
            continue
        alts.append((sr, -float(m.score), m))

    if not alts:
        ok, _r, _m = _accept_match(top1)
        trace["reason"] = "no_eligible_same_topic_alt"
        return (top1.entry.id if ok else None), float(top1.score), trace

    alts.sort()
    alt = alts[0][2]
    trace.update({
        "fired": True,
        "reason": "sibling_action_swap",
        "alternate": alt.entry.id,
        "sem_rank_alt": sem_ranks.get(alt.entry.id),
        "top1_action": top1_act,
        "alt_action": cand_action(alt.entry),
        "family": fam,
    })
    runner = top1
    wrapped = BankMatch(
        entry=alt.entry,
        score=alt.score,
        semantic=alt.semantic,
        lexical=alt.lexical,
        keyword=alt.keyword,
        alias=alt.alias,
        mode=alt.mode,
        runner_up=runner.entry.id,
        runner_up_score=runner.score,
    )
    ok, _r, _m = _accept_match(wrapped)
    trace["chosen"] = alt.entry.id if ok else None
    if not ok:
        # Do not weaken accept gate — fall back to top1.
        ok1, _r1, _m1 = _accept_match(top1)
        trace["reason"] = "alt_failed_accept_gate_fallback_top1"
        trace["fired"] = False  # no effective change
        return (top1.entry.id if ok1 else None), float(top1.score), trace
    return alt.entry.id, float(alt.score), trace


def project(transcript: str, picker, collect_traces: bool = False):
    from app.services.question_bank import question_bank

    traces = []
    if not path_opens(transcript):
        m = question_bank.match(transcript)
        if m is None:
            return [], [], traces
        return [m.entry.id], [float(m.score)], traces

    parts = working_parts(transcript)
    ids, scores = [], []
    already: set[str] = set()
    for p in parts:
        got, sc, tr = picker(p, already)
        if collect_traces:
            traces.append({"fragment": p, **tr})
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
            return [], [], traces
        return [m.entry.id], [float(m.score)], traces
    return uniq, uscores, traces


def score_variant(name, picker, comp, other, targets: set[tuple[str, str]], *, traces_on=False):
    hit = wrong = total = hc = 0
    recovered = []
    fire_count = 0
    per_clip = []
    all_traces = []

    for r in comp:
        gold = list(r.get("expected_intent_ids") or [])
        total += len(gold)
        sel, scores, traces = project(
            r.get("transcript") or "", picker, collect_traces=traces_on
        )
        fire_count += sum(1 for t in traces if t.get("fired"))
        if traces_on:
            all_traces.append({"clip": r["sample_id"], "traces": traces})
        got = {s for s in sel if s in gold}
        bad = [s for s in sel if s not in gold]
        hit += len(got)
        wrong += len(bad)
        for s, sc in zip(sel, scores):
            if s not in gold and sc >= HC_SCORE:
                hc += 1
        for g in gold:
            key = (r["sample_id"], g)
            if g in got and key in targets:
                recovered.append({"clip": r["sample_id"], "gold": g})
        per_clip.append({
            "clip": r["sample_id"], "gold": gold, "selected": sel,
            "hit": sorted(got), "wrong": bad,
            "coverage": _f(len(got) / max(1, len(gold))),
        })

    newly_broken = 0
    for r in other:
        tr = r.get("transcript") or ""
        from app.services.compound_question_detector import detect_question_complexity
        if detect_question_complexity(tr).question_type != "single":
            continue
        if not r1_min8w(tr):
            continue
        sel, _sc, _tr = project(tr, picker)
        if len(sel) < 2:
            continue
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
        "recovered_target_13": len(recovered),
        "recovered_target_of": len(targets),
        "recovered_detail": recovered,
        "resolver_fires": fire_count,
        "newly_broken_non_compound": newly_broken,
        "per_clip": per_clip,
        "traces": all_traces if traces_on else [],
    }


def main() -> int:
    if not V4.is_file() or not B5.is_file():
        print("missing V4 or B5 report")
        return 1

    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()
    from app.services.semantic_intent_index import semantic_intent_index

    warm = semantic_intent_index.ready
    if not warm:
        print("!! cold — abort")
        return 2

    restore = install_h_detect_intent()
    try:
        comp, other = load_rows()
        targets = target_keys()
        print(f"compound={len(comp)} targets={len(targets)} semantic_index_ready={warm}")

        # Eligibility probe on the 13 fragments from B5 (diagnostic only).
        b5 = json.loads(B5.read_text(encoding="utf-8"))
        eligible_probe = []
        for c in b5.get("missing_parts", []):
            if c.get("bucket") not in {"HYBRID_RANKING", "ACTION_GRANULARITY"}:
                continue
            frag = c.get("fragment") or ""
            _id, _sc, tr = pick_sibling_action(frag, set())
            eligible_probe.append({
                "clip": c["clip"],
                "gold": c["gold_intent"],
                "bucket": c["bucket"],
                "would_fire": bool(tr.get("fired")),
                "reason": tr.get("reason"),
                "query_action": tr.get("query_action"),
                "top1": tr.get("top1"),
                "alternate": tr.get("alternate"),
                "sem_rank_alt": tr.get("sem_rank_alt"),
            })
            print(
                f"  probe {c['clip']} {c['gold_intent']}: "
                f"fire={tr.get('fired')} reason={tr.get('reason')} "
                f"q_act={tr.get('query_action')} alt={tr.get('alternate')}"
            )

        base = score_variant("A_baseline", pick_baseline, comp, other, targets)
        sib = score_variant(
            "B61_sibling_action", pick_sibling_action, comp, other, targets, traces_on=True
        )
        for r in (base, sib):
            print(
                f"  {r['variant']:22} cov={r['coverage_by_part']} "
                f"hit={r['gold_parts_hit']}/{r['gold_parts']} wrong={r['wrong_intent']} "
                f"hc={r['hc_risk']} target_rec={r['recovered_target_13']}/{r['recovered_target_of']} "
                f"fires={r['resolver_fires']} newly_broken={r['newly_broken_non_compound']}"
            )
    finally:
        restore()

    gate = {
        "recovered_target_ge_3": sib["recovered_target_13"] >= MIN_TARGET_RECOVER,
        "wrong_le_4": sib["wrong_intent"] <= 4,
        "wrong_le_baseline": sib["wrong_intent"] <= base["wrong_intent"],
        "newly_broken_le_baseline": (
            sib["newly_broken_non_compound"] <= base["newly_broken_non_compound"]
        ),
        "hc_le_baseline": sib["hc_risk"] <= base["hc_risk"],
        "coverage_ge_baseline": (
            (sib["coverage_by_part"] or 0) >= (base["coverage_by_part"] or 0)
        ),
    }
    gate["all_pass"] = all(gate.values())
    would_fire_n = sum(1 for p in eligible_probe if p["would_fire"])

    if gate["all_pass"]:
        verdict = (
            f"IMPLEMENT B61_sibling_action — recovered "
            f"{sib['recovered_target_13']}/13 under hard gate"
        )
        close_ranking = False
    else:
        verdict = (
            "CLOSE_RANKING_PATH — B6.1 failed hard gate; stop ranking/action "
            "reranking; reclassify the 13 toward profile/candidate + segmentation"
        )
        close_ranking = True

    print(f"\n=== B6.1 VERDICT: {verdict} ===")
    print(f"  probe would_fire on fragments: {would_fire_n}/13")
    print(f"  gates: {gate}")

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "V5 Phase B6.1 — same-topic sibling action resolver",
        "scope": "measurement only; LAST ranking experiment",
        "semantic_index_ready": warm,
        "eligibility_probe_on_b5_fragments": eligible_probe,
        "baseline": {k: base[k] for k in base if k not in {"per_clip", "traces"}},
        "sibling": {k: sib[k] for k in sib if k != "traces"},
        "sibling_traces": sib.get("traces"),
        "hard_gate": gate,
        "close_ranking_path": close_ranking,
        "verdict": verdict,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_B61_SIBLING_ACTION_RESOLVER.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        "# V5 Phase B6.1 — same-topic sibling action resolver",
        "",
        f"Created: {payload['created_at']}",
        f"`semantic_index_ready={warm}`",
        "",
        "LAST ranking experiment. Measurement only.",
        "",
        "## Eligibility probe (B5 fragments for the 13)",
        "",
        "| clip | gold | would_fire | reason | q_action | alt |",
        "|---|---|---|---|---|---|",
    ]
    for p in eligible_probe:
        md.append(
            f"| {p['clip']} | `{p['gold']}` | {p['would_fire']} | {p['reason']} | "
            f"{p['query_action']} | `{p['alternate']}` |"
        )
    md += [
        "",
        "## Full projection",
        "",
        "| variant | coverage | hit | wrong | hc | target_rec | fires | newly_broken |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| A_baseline | {base['coverage_by_part']} | {base['gold_parts_hit']}/{base['gold_parts']} | "
        f"{base['wrong_intent']} | {base['hc_risk']} | {base['recovered_target_13']}/13 | "
        f"{base['resolver_fires']} | {base['newly_broken_non_compound']} |",
        f"| B61_sibling_action | {sib['coverage_by_part']} | {sib['gold_parts_hit']}/{sib['gold_parts']} | "
        f"{sib['wrong_intent']} | {sib['hc_risk']} | {sib['recovered_target_13']}/13 | "
        f"{sib['resolver_fires']} | {sib['newly_broken_non_compound']} |",
        "",
        f"Recovered detail: {sib['recovered_detail']}",
        "",
        f"Hard gate: `{gate}`",
        "",
        f"**VERDICT: {verdict}**",
        "",
    ]
    (REPORTS / "V5_B61_SIBLING_ACTION_RESOLVER.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORTS / 'V5_B61_SIBLING_ACTION_RESOLVER.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
