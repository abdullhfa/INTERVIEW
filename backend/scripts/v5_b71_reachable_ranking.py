"""
V5 Phase B7.1 — repaired-harness reachable ranking counterfactual.
MEASUREMENT ONLY. No app/ changes.

Scope: ONLY the 6 reachable misses from V5_REQUALIFY_13_REPAIRED
  (5 ACTION_GRANULARITY + 1 HYBRID_RANKING). Not the full 13, not system-wide.

Provisional baseline (B7 A_baseline_semantic_restored):
  coverage=0.4878  wrong=4  HC=0

Instrument: every load(force=True) is followed by warm(); abort if
alias_matrix is None or hybrid probe semantic is 0.

Discriminators tested: SAME-TOPIC / SAME-FAMILY action only.
No general rerank, no routing/evidence/profile/threshold changes.

    python scripts/v5_b71_reachable_ranking.py
Writes reports/V5_B71_REACHABLE_RANKING.{md,json}.

Hard gate vs repaired baseline:
  target_recovered > 0   (prefer several of the 6)
  wrong_intent <= 4
  hc_risk == 0
  newly_broken_opened_only == 0
  coverage_by_part >= baseline
  alias_matrix present throughout
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V4 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V4_REPORT.json"
REQUAL = REPORTS / "V5_REQUALIFY_13_REPAIRED.json"

EVIDENCE_THETA = 0.4
HC_SCORE = 0.85
BASELINE = {"coverage_by_part": 0.4878, "wrong_intent": 4, "hc_risk": 0}

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

# Query-side structural cues only (not bank aliases). Narrow action lexicon.
_QUERY_ACTION_CUES = (
    ("when", re.compile(r"\b(when|halt|stop once|at what point)\b", re.I)),
    ("why", re.compile(r"\b(why|rationale|reason|because)\b", re.I)),
    ("how", re.compile(r"\b(how|steps|internals?|evaluate how)\b", re.I)),
    ("definition", re.compile(r"\b(what is|what are|define|meaning of)\b", re.I)),
    ("compare", re.compile(r"\b(versus|vs\.?|difference|compared|rather than)\b", re.I)),
    ("describe", re.compile(r"\b(summarize|summarise|summarize|tell me about|describe|walk me through)\b", re.I)),
    ("experience", re.compile(r"\b(have you|did you|your (?:history|experience))\b", re.I)),
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


def rewarm_bank():
    from app.services.question_bank import question_bank

    question_bank.warm()
    idx = getattr(question_bank, "_index", None)
    am = getattr(idx, "alias_matrix", None) if idx is not None else None
    if am is None:
        raise RuntimeError("alias_matrix is None after warm() — abort")
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
    rewarm_bank()

    def restore():
        QB.detect_intent = original
        QB.question_bank.load(force=True)
        rewarm_bank()

    return restore


def evidence_ratio(sub: str, transcript: str) -> float:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _content_tokens

    q = set(_content_tokens(normalize_for_matching(sub or "")))
    t = set(_content_tokens(normalize_for_matching(transcript or "")))
    if not q:
        return 0.0
    return len(q & t) / len(q)


def detect_action_strict(text: str) -> str | None:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import detect_intent

    return detect_intent(normalize_for_matching(text or ""))


def detect_action_query(text: str, *, soft: bool) -> str | None:
    got = detect_action_strict(text)
    if got or not soft:
        return got
    for name, pat in _QUERY_ACTION_CUES:
        if pat.search(text or ""):
            return name
    return None


def cand_action(entry) -> str | None:
    return detect_action_strict(entry.question or "")


def family_of(intent_id: str, entry=None) -> str:
    if entry is not None and getattr(entry, "topic", None):
        return str(entry.topic)
    return (intent_id or "").split(".", 1)[0]


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


def sem_rank_map(text: str, ids: set[str], k: int = 25) -> dict[str, int]:
    from app.services.semantic_intent_index import semantic_intent_index

    out: dict[str, int] = {}
    if not text.strip() or not semantic_intent_index.ready:
        return out
    for i, h in enumerate(semantic_intent_index.top_k(text, k=k)):
        if h.intent_id in ids and h.intent_id not in out:
            out[h.intent_id] = i + 1
    return out


def _accept_ordered(ordered, already: set[str]):
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import BankMatch

    for m in ordered:
        if m.entry.id in already:
            continue
        runner = next((x for x in ordered if x.entry.id != m.entry.id), None)
        wrapped = BankMatch(
            entry=m.entry, score=m.score, semantic=m.semantic, lexical=m.lexical,
            keyword=m.keyword, alias=m.alias, mode=m.mode,
            runner_up=runner.entry.id if runner else None,
            runner_up_score=runner.score if runner else 0.0,
        )
        ok, _r, _m = _accept_match(wrapped)
        if ok:
            return m.entry.id, float(m.score), {"fired": False, "reason": "accepted"}
    return None, 0.0, {"fired": False, "reason": "none_accepted"}


def pick_baseline(text: str, already: set[str] | None = None):
    from app.services.question_bank import question_bank

    already = already or set()
    tops = question_bank.top_matches(text, top_k=8)
    if not tops:
        return None, 0.0, {"fired": False, "reason": "no_tops"}
    # True baseline ignores already (matches B7 projection).
    return _accept_ordered(tops, set())


def pick_sibling_strict(text: str, already: set[str] | None = None):
    """B6.1 logic on repaired harness: strict query action, same family, sem<=3."""
    return _sibling_action(text, already or set(), soft_query=False, sem_max=3)


def pick_sibling_soft_query(text: str, already: set[str] | None = None):
    """Same as strict, but query action may use structural cues (rationale->why)."""
    return _sibling_action(text, already or set(), soft_query=True, sem_max=3)


def pick_same_topic_action_rerank(text: str, already: set[str] | None = None):
    """
    Among hybrid top-5 sharing top1's topic/family and sem_rank<=3:
    +0.12 if cand action matches query, -0.10 if clear mismatch; then accept.
    """
    from app.services.question_bank import question_bank

    already = already or set()
    tops = question_bank.top_matches(text, top_k=8)
    if not tops:
        return None, 0.0, {"fired": False, "reason": "no_tops"}
    q_act = detect_action_query(text, soft=True)
    fam = family_of(tops[0].entry.id, tops[0].entry)
    ranks = sem_rank_map(text, {m.entry.id for m in tops[:5]})
    scored = []
    fired = False
    for m in tops[:5]:
        adj = float(m.score)
        same = family_of(m.entry.id, m.entry) == fam
        sr = ranks.get(m.entry.id)
        if q_act and same and sr is not None and sr <= 3:
            c_act = cand_action(m.entry)
            if c_act == q_act:
                adj += 0.12
                fired = True
            elif c_act and c_act != q_act:
                adj -= 0.10
                fired = True
        scored.append((adj, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    ordered = [m for _a, m in scored] + list(tops[5:])
    got, sc, tr = _accept_ordered(ordered, already)
    tr.update({"fired": fired and got is not None and got != tops[0].entry.id,
               "reason": "same_topic_action_rerank", "query_action": q_act,
               "top1": tops[0].entry.id, "chosen": got})
    return got, sc, tr


def _sibling_action(text: str, already: set[str], *, soft_query: bool, sem_max: int):
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import BankMatch, question_bank

    tops = question_bank.top_matches(text, top_k=8)
    trace = {"fired": False, "reason": None, "query_action": None,
             "top1": None, "alternate": None, "sem_rank_alt": None}
    if not tops:
        trace["reason"] = "no_tops"
        return None, 0.0, trace
    top1 = tops[0]
    trace["top1"] = top1.entry.id
    q_act = detect_action_query(text, soft=soft_query)
    trace["query_action"] = q_act
    if not q_act:
        got, sc, tr = _accept_ordered(tops, already)
        trace["reason"] = "no_clear_query_action"
        return got, sc, trace

    top1_act = cand_action(top1.entry)
    if top1_act == q_act:
        got, sc, tr = _accept_ordered(tops, already)
        trace["reason"] = "top1_already_matches_action"
        return got, sc, trace

    fam = family_of(top1.entry.id, top1.entry)
    pool = [m for m in tops[:5] if m.entry.id not in already]
    ranks = sem_rank_map(text, {m.entry.id for m in pool})
    alts = []
    for m in pool:
        if m.entry.id == top1.entry.id:
            continue
        if family_of(m.entry.id, m.entry) != fam:
            continue
        if cand_action(m.entry) != q_act:
            continue
        sr = ranks.get(m.entry.id)
        if sr is None or sr > sem_max:
            continue
        alts.append((sr, -float(m.score), m))
    if not alts:
        got, sc, tr = _accept_ordered(tops, already)
        trace["reason"] = "no_eligible_same_topic_alt"
        return got, sc, trace
    alts.sort()
    alt = alts[0][2]
    trace.update({
        "fired": True, "reason": "sibling_action_swap", "alternate": alt.entry.id,
        "sem_rank_alt": ranks.get(alt.entry.id),
    })
    wrapped = BankMatch(
        entry=alt.entry, score=alt.score, semantic=alt.semantic, lexical=alt.lexical,
        keyword=alt.keyword, alias=alt.alias, mode=alt.mode,
        runner_up=top1.entry.id, runner_up_score=top1.score,
    )
    ok, _r, _m = _accept_match(wrapped)
    if not ok:
        got, sc, tr = _accept_ordered(tops, already)
        trace["fired"] = False
        trace["reason"] = "alt_failed_accept_gate"
        return got, sc, trace
    return alt.entry.id, float(alt.score), trace


PICKERS = {
    "A_baseline": pick_baseline,
    "B_sibling_strict": pick_sibling_strict,
    "C_sibling_soft_query": pick_sibling_soft_query,
    "D_same_topic_action_rerank": pick_same_topic_action_rerank,
}


def load_targets() -> set[tuple[str, str]]:
    d = json.loads(REQUAL.read_text(encoding="utf-8"))
    return {
        (c["clip"], c["gold_intent"])
        for c in d["cases"]
        if c["status"] == "STILL_MISSING"
        and c["reachable"]
        and c["bucket"] in {"ACTION_GRANULARITY", "HYBRID_RANKING"}
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


def project(transcript: str, picker):
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
        got, sc, _tr = picker(p, already)
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


def score_variant(name, picker, comp, other, targets: set[tuple[str, str]]):
    hit = wrong = total = hc = 0
    recovered = []
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
            if g in got and (r["sample_id"], g) in targets:
                recovered.append({"clip": r["sample_id"], "gold": g})
        per_clip.append({
            "clip": r["sample_id"], "gold": gold, "selected": sel,
            "hit": sorted(got), "wrong": bad,
            "coverage": _f(len(got) / max(1, len(gold))),
        })

    newly_broken = 0
    from app.services.compound_question_detector import detect_question_complexity
    for r in other:
        tr = r.get("transcript") or ""
        if detect_question_complexity(tr).question_type != "single":
            continue
        if not r1_min8w(tr):
            continue
        sel, _sc = project(tr, picker)
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
        "target_recovered": len(recovered),
        "target_of": len(targets),
        "recovered_detail": recovered,
        "newly_broken_opened_only": newly_broken,
        "per_clip": per_clip,
    }


def main() -> int:
    if not V4.is_file() or not REQUAL.is_file():
        print("missing V4 or V5_REQUALIFY_13_REPAIRED")
        return 1

    os.environ["PYTHONUNBUFFERED"] = "1"
    from app.services.warm_start import warm_system_blocking

    print("warming...", flush=True)
    warm_system_blocking()
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index

    if not semantic_intent_index.ready:
        print("!! semantic_intent_index cold — abort")
        return 2

    restore = install_h()
    try:
        tops = question_bank.top_matches("What is hybrid search?", top_k=3)
        if not tops or float(tops[0].semantic) == 0.0:
            print("!! hybrid semantic still 0 — abort")
            return 3
        print(f"instrument OK alias_matrix=True probe_sem={_f(tops[0].semantic)}", flush=True)

        targets = load_targets()
        print(f"reachable ranking targets: {len(targets)}", flush=True)
        for c, g in sorted(targets):
            print(f"  {c} {g}", flush=True)

        # Fragment-level eligibility probe for each target.
        requal = json.loads(REQUAL.read_text(encoding="utf-8"))
        probes = []
        for c in requal["cases"]:
            if (c["clip"], c["gold_intent"]) not in targets:
                continue
            frag = c.get("fragment") or ""
            for label, picker in (
                ("B_sibling_strict", pick_sibling_strict),
                ("C_sibling_soft_query", pick_sibling_soft_query),
                ("D_same_topic_action_rerank", pick_same_topic_action_rerank),
            ):
                _id, _sc, tr = picker(frag, set())
                probes.append({
                    "clip": c["clip"], "gold": c["gold_intent"], "variant": label,
                    "fragment": frag, "would_pick": _id,
                    "would_hit_gold": _id == c["gold_intent"],
                    "trace": tr,
                })
                print(
                    f"  probe {label} {c['clip']} {c['gold_intent']}: "
                    f"pick={_id} hit={_id == c['gold_intent']} "
                    f"fired={tr.get('fired')} reason={tr.get('reason')}",
                    flush=True,
                )

        comp, other = load_rows()
        results = []
        for name, picker in PICKERS.items():
            res = score_variant(name, picker, comp, other, targets)
            results.append(res)
            print(
                f"  {name:32} cov={res['coverage_by_part']} "
                f"hit={res['gold_parts_hit']}/{res['gold_parts']} "
                f"wrong={res['wrong_intent']} hc={res['hc_risk']} "
                f"target={res['target_recovered']}/{res['target_of']} "
                f"nb={res['newly_broken_opened_only']} "
                f"detail={res['recovered_detail']}",
                flush=True,
            )
    finally:
        restore()

    base = next(r for r in results if r["variant"] == "A_baseline")
    # Sanity: baseline should be near provisional 0.4878
    winners = []
    gates = {}
    for r in results:
        if r["variant"] == "A_baseline":
            continue
        g = {
            "target_gt_0": r["target_recovered"] > 0,
            "wrong_le_4": r["wrong_intent"] <= 4,
            "hc_zero": r["hc_risk"] == 0,
            "newly_broken_zero": r["newly_broken_opened_only"] == 0,
            "coverage_ge_baseline": (r["coverage_by_part"] or 0) >= (base["coverage_by_part"] or 0),
        }
        g["all_pass"] = all(g.values())
        gates[r["variant"]] = g
        if g["all_pass"]:
            winners.append(r)

    winners.sort(key=lambda r: (-r["target_recovered"], -(r["coverage_by_part"] or 0),
                                r["wrong_intent"]))
    if winners:
        verdict = (
            f"IMPLEMENT {winners[0]['variant']} — recovered "
            f"{winners[0]['target_recovered']}/6 under hard gate; then recompute full residual"
        )
        close_ranking = False
    else:
        verdict = (
            "CLOSE_RANKING_WITH_CONFIDENCE — B7.1 failed on repaired harness; "
            "same-topic action discriminators have no safe leverage on the 6 reachable misses"
        )
        close_ranking = True

    print(f"\n=== B7.1 VERDICT: {verdict} ===", flush=True)

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "V5 Phase B7.1 — repaired-harness reachable ranking counterfactual",
        "scope": "measurement only; 6 reachable misses only; same-topic action discriminators",
        "provisional_baseline": BASELINE,
        "measured_baseline": {
            "coverage_by_part": base["coverage_by_part"],
            "wrong_intent": base["wrong_intent"],
            "hc_risk": base["hc_risk"],
        },
        "targets": sorted(f"{c}:{g}" for c, g in targets),
        "fragment_probes": probes,
        "results": results,
        "gates": gates,
        "winners": [w["variant"] for w in winners],
        "close_ranking": close_ranking,
        "verdict": verdict,
        "note": "Even 6/6 recoveries add only ~+0.146 coverage (~0.63); not a path to 0.90 alone.",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_B71_REACHABLE_RANKING.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        "# V5 Phase B7.1 — repaired-harness reachable ranking",
        "",
        f"Created: {payload['created_at']}",
        "",
        "Measurement only. Targets = 6 reachable HYBRID/ACTION misses.",
        f"Provisional baseline: `{BASELINE}`.",
        f"Measured A_baseline: cov={base['coverage_by_part']} wrong={base['wrong_intent']} hc={base['hc_risk']}.",
        "",
        "## Fragment probes",
        "",
        "| variant | clip | gold | would_pick | hit_gold | fired | reason |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in probes:
        md.append(
            f"| {p['variant']} | {p['clip']} | `{p['gold']}` | `{p['would_pick']}` | "
            f"{p['would_hit_gold']} | {p['trace'].get('fired')} | {p['trace'].get('reason')} |"
        )
    md += [
        "",
        "## Full projection",
        "",
        "| variant | coverage | hit | wrong | hc | target | newly_broken | pass? |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in results:
        if r["variant"] == "A_baseline":
            beat = "—"
        else:
            beat = "YES" if gates[r["variant"]]["all_pass"] else "no"
        md.append(
            f"| {r['variant']} | {r['coverage_by_part']} | "
            f"{r['gold_parts_hit']}/{r['gold_parts']} | {r['wrong_intent']} | "
            f"{r['hc_risk']} | {r['target_recovered']}/{r['target_of']} | "
            f"{r['newly_broken_opened_only']} | {beat} |"
        )
    md += [
        "",
        f"Recovered details: "
        + "; ".join(
            f"{r['variant']}={r['recovered_detail']}" for r in results if r["variant"] != "A_baseline"
        ),
        "",
        f"**VERDICT: {verdict}**",
        "",
        payload["note"],
        "",
    ]
    (REPORTS / "V5_B71_REACHABLE_RANKING.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORTS / 'V5_B71_REACHABLE_RANKING.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
