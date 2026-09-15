"""
V5 Phase B3 — routing entry + evidence-grounded acceptance. MEASUREMENT ONLY.

Nothing in app/ is modified. Every rule tested here is structural (shape of the
utterance), never a vocabulary list and never a holdout phrase or clip id.

Order, as agreed:

  1. WHY the 10 telegraphic clips never enter the compound path, and what opening
     it costs on the 105 non-compound clips (the blast radius that matters, since
     answer_generator.py:351-360 lets a compound answer PRE-EMPT a strong single
     bank answer).
  2. Evidence-grounded acceptance: a generated sub-question is accepted only when
     it has evidence in the spoken transcript.
  3. I / HI re-measured ON TOP of 1 and 2, not alone.

Guards (reported, never silently passed):
     compound cohort wrong_intent <= 12
     non-compound clips newly broken by opening routing == 0

    python scripts/v5_b3_routing_and_evidence.py
Writes reports/V5_B3_ROUTING_AND_EVIDENCE.{md,json}.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V4 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V4_REPORT.json"


def _f(x, n=4):
    try:
        return round(float(x), n)
    except Exception:
        return None


# ── shape primitives (shared with the Phase B script, kept identical) ───────
_INTERROG = re.compile(
    r"\b(what|why|how|when|which|who|whether|where|is|are|do|does|did|can|should|would)\b", re.I)
_IMPER = re.compile(
    r"\b(explain|tell|say|describe|give|point|walk|cover|name|define|summaris|summariz|list)\b", re.I)
_VERBISH = re.compile(
    r"\b(use|used|build|built|work|works|make|choose|pick|handle|stop|prevent|add|need|"
    r"matter|differ|design|halt|reduce|track|monitor)\b", re.I)
_WH_HEAD = re.compile(
    r"^\s*(what|why|how|when|which|who|where|say|tell|point|name|give|explain|describe)\b", re.I)
_DET_HEAD = re.compile(r"^\s*(your|our|the|a|an|their|its|my)\b", re.I)
_FRAG_SPLIT = re.compile(r",|;|\band\b|\bthen\b|\bplus\b", re.I)


def clause_has_action(text: str) -> bool:
    return bool(_INTERROG.search(text) or _IMPER.search(text) or _VERBISH.search(text))


def fragments(text: str) -> list[str]:
    return [p.strip(" .;:?") for p in _FRAG_SPLIT.split(text or "") if p.strip(" .;:?")]


def split_enumeration(text: str) -> list[str]:
    parts = fragments(text)
    if len(parts) < 2:
        return []
    short_verbless = sum(1 for p in parts if len(p.split()) <= 6 and not clause_has_action(p))
    if short_verbless >= max(2, int(0.5 * len(parts))):
        return [p for p in parts if p.split()]
    return []


# ── candidate ROUTING rules (step 1) ───────────────────────────────────────
def r1_verbless_series(text: str) -> bool:
    """>=2 fragments, at least 2 of them short and carrying no action cue."""
    parts = fragments(text)
    if len(parts) < 2:
        return False
    return sum(1 for p in parts if len(p.split()) <= 6 and not clause_has_action(p)) >= 2


def r2_trailing_request_fragment(text: str) -> bool:
    """A non-first fragment opens with a WH word or a request verb."""
    parts = fragments(text)
    return len(parts) >= 2 and any(_WH_HEAD.match(p) for p in parts[1:])


def r3_no_finite_verb_series(text: str) -> bool:
    """Whole utterance carries no action cue at all, yet lists >=2 fragments."""
    parts = fragments(text)
    return len(parts) >= 2 and not clause_has_action(text or "")


def r4_determiner_series(text: str) -> bool:
    """>=2 fragments each opening with a determiner/possessive."""
    parts = fragments(text)
    return len(parts) >= 2 and sum(1 for p in parts if _DET_HEAD.match(p)) >= 2


_SENT_SPLIT = re.compile(r"(?<=[.?!])\s+")


def sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENT_SPLIT.split((text or "").strip()) if p.strip(" .?!")]


def word_count(text: str) -> int:
    return len((text or "").split())


def r5_multi_sentence_request(text: str) -> bool:
    """
    >=2 sentences where a non-first sentence is itself a request. The existing
    detector only ever splits on ',', ';', 'and', 'then' — a full stop between
    two asks is invisible to it.
    """
    sents = sentences(text)
    if len(sents) < 2:
        return False
    return any(_WH_HEAD.match(s) or clause_has_action(s) for s in sents[1:])


def _min_words(fn, n: int):
    return lambda t: fn(t) and word_count(t) >= n


ROUTING_RULES = {
    "R1_verbless_series": r1_verbless_series,
    "R2_trailing_request_fragment": r2_trailing_request_fragment,
    "R3_no_finite_verb_series": r3_no_finite_verb_series,
    "R4_determiner_series": r4_determiner_series,
    "R1_or_R2": lambda t: r1_verbless_series(t) or r2_trailing_request_fragment(t),
    "R1_and_R2": lambda t: r1_verbless_series(t) and r2_trailing_request_fragment(t),
    "R1_or_R4": lambda t: r1_verbless_series(t) or r4_determiner_series(t),
    "R1_or_R2_or_R4": lambda t: (
        r1_verbless_series(t) or r2_trailing_request_fragment(t) or r4_determiner_series(t)
    ),
    # Length floor: the false positives found in the first pass are all very
    # short single asks ("Notice, if we hire you?"). A word floor is structural.
    "R1_min8w": _min_words(r1_verbless_series, 8),
    "R5_multi_sentence_request": r5_multi_sentence_request,
    "R5_min8w": _min_words(r5_multi_sentence_request, 8),
    "R1_or_R5_min8w": _min_words(
        lambda t: r1_verbless_series(t) or r5_multi_sentence_request(t), 8),
    "R1_or_R4_or_R5_min8w": _min_words(
        lambda t: (r1_verbless_series(t) or r4_determiner_series(t)
                   or r5_multi_sentence_request(t)), 8),
    "R1_or_R5_min10w": _min_words(
        lambda t: r1_verbless_series(t) or r5_multi_sentence_request(t), 10),
}


# ── evidence gate (step 2) ─────────────────────────────────────────────────
def evidence_ratio(sub_question: str, transcript: str) -> tuple[float, int, int]:
    """
    Share of the generated sub-question's CONTENT tokens that actually occur in
    the spoken transcript. Uses the production tokenizer and stopword list, so
    interrogative scaffolding ("what is ...") is not counted as evidence.
    """
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _content_tokens

    q = set(_content_tokens(normalize_for_matching(sub_question or "")))
    t = set(_content_tokens(normalize_for_matching(transcript or "")))
    if not q:
        return 0.0, 0, 0
    shared = q & t
    return len(shared) / len(q), len(shared), len(q)


def has_anchor(sub_question: str, transcript: str, min_len: int = 5) -> bool:
    """At least one shared content token long enough to carry meaning."""
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _content_tokens

    q = set(_content_tokens(normalize_for_matching(sub_question or "")))
    t = set(_content_tokens(normalize_for_matching(transcript or "")))
    return any(len(tok) >= min_len for tok in (q & t))


def evidence_ok(sub_question: str, transcript: str, theta: float, need_anchor: bool) -> bool:
    ratio, _, _ = evidence_ratio(sub_question, transcript)
    if ratio < theta:
        return False
    return has_anchor(sub_question, transcript) if need_anchor else True


# ── H (action-type completion) and I (enumeration split), unchanged ─────────
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


# ── data ───────────────────────────────────────────────────────────────────
def load_rows() -> tuple[list[dict], list[dict]]:
    rep = json.loads(V4.read_text(encoding="utf-8"))
    rows = [r for r in rep["results"] if not str(r.get("notes") or "").startswith("warmup:")]
    comp = [r for r in rows if (r.get("question_type_label") or "") == "compound"]
    other = [r for r in rows
             if (r.get("question_type_label") or "") != "compound" and r.get("expected_intent_ids")]
    return comp, other


def forced_resolution(text: str):
    """Exactly the interview_e2e_loopback labeled-pack call."""
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


def accept_first(text, exclude=None, topic=None):
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank

    tops = question_bank.top_matches(text, top_k=6, topic_hint=topic)
    m = next((t for t in tops if exclude is None or t.entry.id != exclude), None)
    ok, _reason, _margin = _accept_match(m)
    return m.entry.id if (m and ok) else None


def score(rows: list[dict], picker) -> dict:
    hit = wrong = 0
    total = 0
    per_clip = []
    for r in rows:
        gold = list(r.get("expected_intent_ids") or [])
        total += len(gold)
        seen, uniq = set(), []
        for s in picker(r):
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        got = sorted({s for s in uniq if s in gold})
        bad = [s for s in uniq if s not in gold]
        hit += len(got)
        wrong += len(bad)
        per_clip.append({"clip": r["sample_id"], "gold": gold, "selected": uniq,
                         "hit": got, "wrong": bad,
                         "coverage": _f(len(got) / max(1, len(gold)))})
    return {"gold_parts": total, "gold_parts_hit": hit,
            "coverage_by_part": _f(hit / max(1, total)),
            "wrong_intent": wrong, "per_clip": per_clip}


# ── main ───────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theta", nargs="*", type=float, default=[0.3, 0.4, 0.5, 0.6])
    args = ap.parse_args()
    if not V4.is_file():
        print(f"missing {V4}")
        return 1

    from app.services.compound_question_detector import detect_question_complexity
    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index

    warm = bool(semantic_intent_index.ready)
    comp, other = load_rows()
    print(f"compound={len(comp)}  non_compound_with_gold={len(other)}  "
          f"semantic_index_ready={warm}")

    # ---------- STEP 1a: why are they blocked? --------------------------
    blocked = []
    for r in comp:
        tr = r.get("transcript") or ""
        det = detect_question_complexity(tr)
        if det.question_type != "single":
            continue
        blocked.append({
            "clip": r["sample_id"],
            "transcript": tr,
            "terminal_branch": ("no_multi_request_signal"
                                if "no_multi_request_signal" in det.signals
                                else "weak_signal_or_single_request"),
            "signals_fired": list(det.signals),
            "fragments": fragments(tr),
            "fragment_count": len(fragments(tr)),
            "whole_utterance_has_action_cue": clause_has_action(tr),
            "fragments_without_action_cue": [p for p in fragments(tr) if not clause_has_action(p)],
            "sentences": sentences(tr),
            "word_count": word_count(tr),
            "rules_that_would_open": [k for k, fn in ROUTING_RULES.items() if fn(tr)],
        })
    print(f"blocked compound clips: {len(blocked)}")

    # ---------- STEP 1b: recall vs false-positive for each rule ----------
    rule_table = []
    for name, fn in ROUTING_RULES.items():
        opened_comp = [r["sample_id"] for r in comp
                       if detect_question_complexity(r.get("transcript") or "").question_type
                       == "single" and fn(r.get("transcript") or "")]
        # a non-compound clip is "newly opened" only if the detector does not
        # already route it — otherwise the rule changes nothing there.
        opened_other = [r["sample_id"] for r in other
                        if detect_question_complexity(r.get("transcript") or "").question_type
                        == "single" and fn(r.get("transcript") or "")]
        rule_table.append({
            "rule": name,
            "compound_recovered": len(opened_comp),
            "compound_recovered_of": len(blocked),
            "compound_clips": opened_comp,
            "non_compound_newly_opened": len(opened_other),
            "non_compound_of": len(other),
            "non_compound_clips": opened_other,
        })
        print(f"  {name:32} recovers {len(opened_comp):2}/{len(blocked)}  "
              f"opens {len(opened_other):3}/{len(other)} non-compound")

    # ---------- STEP 1c: blast radius on the newly opened non-compound ----
    # answer_generator.py:351-360 returns the compound answer BEFORE the strong
    # single bank answer, so a newly opened clip whose compound path produces an
    # answer replaces a result that was already correct.
    blast = {}
    for entry in rule_table:
        name = entry["rule"]
        damage = {"preempted": 0, "preempt_keeps_gold_alone": 0,
                  "preempt_keeps_gold_plus_extra": 0, "preempt_loses_gold": 0,
                  "newly_broken": 0,
                  # G2: let a compound answer pre-empt the single bank answer ONLY
                  # when it actually produced >= 2 accepted intents. A one-intent
                  # "compound" answer is a re-match of the same utterance through a
                  # different matcher, which is how a correct single answer gets
                  # replaced by a wrong one.
                  "newly_broken_with_multi_intent_guard": 0,
                  "preempted_with_multi_intent_guard": 0,
                  "details": []}
        for r in other:
            if r["sample_id"] not in entry["non_compound_clips"]:
                continue
            res = forced_resolution(r.get("transcript") or "")
            if res is None or not res.used_compound_path or not (res.answer_en or ""):
                continue
            sel = list(res.selected_intents or [])
            gold = list(r.get("expected_intent_ids") or [])
            damage["preempted"] += 1
            multi = len(sel) >= 2
            if multi:
                damage["preempted_with_multi_intent_guard"] += 1
            was_ok = bool(r.get("intent_ok"))
            if not sel:
                continue
            if set(sel) == set(gold):
                damage["preempt_keeps_gold_alone"] += 1
                verdict = "same"
            elif set(gold) & set(sel):
                damage["preempt_keeps_gold_plus_extra"] += 1
                verdict = "gold_plus_extra"
            else:
                damage["preempt_loses_gold"] += 1
                verdict = "gold_lost"
                if was_ok:
                    damage["newly_broken"] += 1
                    if multi:
                        damage["newly_broken_with_multi_intent_guard"] += 1
            damage["details"].append({
                "clip": r["sample_id"], "label": r.get("question_type_label"),
                "transcript": r.get("transcript"), "gold": gold, "compound_selected": sel,
                "verdict": verdict, "was_intent_ok_in_v4": was_ok,
                "selected_count": len(sel), "blocked_by_multi_intent_guard": not multi,
                "sub_questions": list(res.sub_questions or []),
            })
        blast[name] = damage
        if entry["non_compound_newly_opened"]:
            print(f"  blast {name:32} preempted={damage['preempted']:3} "
                  f"lose_gold={damage['preempt_loses_gold']:3} "
                  f"NEWLY_BROKEN={damage['newly_broken']:3} "
                  f"(with >=2-intent guard: {damage['newly_broken_with_multi_intent_guard']})")

    # ---------- STEP 2: evidence gate on the compound cohort -------------
    evidence_rows = []
    parts_audit = []
    for r in comp:
        tr = r.get("transcript") or ""
        res = forced_resolution(tr)
        subs = list(getattr(res, "sub_questions", None) or [])
        notes = list(getattr(res, "decomposition_notes", None) or [])
        for s in subs:
            ratio, shared, need = evidence_ratio(s, tr)
            parts_audit.append({
                "clip": r["sample_id"], "sub_question": s,
                "evidence_ratio": _f(ratio), "shared_tokens": shared,
                "sub_question_content_tokens": need,
                "has_anchor": has_anchor(s, tr),
                "from_facet": any(n.startswith("facet:") for n in notes),
                "decomposition_notes": notes,
            })
    facet_parts = [p for p in parts_audit if p["from_facet"]]
    print(f"\nsub-questions audited: {len(parts_audit)} "
          f"(facet-derived: {len(facet_parts)})")
    for th in args.theta:
        drop = [p for p in parts_audit if p["evidence_ratio"] < th]
        evidence_rows.append({
            "theta": th,
            "parts_total": len(parts_audit),
            "parts_dropped": len(drop),
            "parts_dropped_facet_derived": sum(1 for p in drop if p["from_facet"]),
            "dropped": [{"clip": p["clip"], "sub_question": p["sub_question"],
                         "evidence_ratio": p["evidence_ratio"]} for p in drop],
        })
        print(f"  theta={th}: drops {len(drop)}/{len(parts_audit)} parts "
              f"({sum(1 for p in drop if p['from_facet'])} facet-derived)")

    # ---------- STEP 3: combined matrix ----------------------------------
    def parts_for(r, *, theta, need_anchor):
        tr = r.get("transcript") or ""
        res = forced_resolution(tr)
        subs = list(getattr(res, "sub_questions", None) or [])
        if theta is None:
            return subs
        return [s for s in subs if evidence_ok(s, tr, theta, need_anchor)]

    def make_picker(*, theta, need_anchor, split):
        def picker(r):
            out = []
            for s in parts_for(r, theta=theta, need_anchor=need_anchor):
                frags = (split_enumeration(s) or [s]) if split else [s]
                for frag in frags:
                    if theta is not None and not evidence_ok(
                        frag, r.get("transcript") or "", theta, need_anchor
                    ):
                        continue
                    got = accept_first(frag)
                    if got:
                        out.append(got)
            return out

        return picker

    matrix = []
    combos = []
    for theta in [None] + list(args.theta):
        for need_anchor in ([False] if theta is None else [False, True]):
            for split in (False, True):
                for action_rules in (False, True):
                    combos.append((theta, need_anchor, split, action_rules))
    for theta, need_anchor, split, action_rules in combos:
        restore = install_v5_detect_intent() if action_rules else None
        try:
            res = score(comp, make_picker(theta=theta, need_anchor=need_anchor, split=split))
        finally:
            if restore:
                restore()
        label = (
            f"evidence={'off' if theta is None else theta}"
            f"{'+anchor' if need_anchor else ''}"
            f" | split={'I' if split else '-'}"
            f" | action_rules={'H' if action_rules else '-'}"
        )
        row = {"config": label, "theta": theta, "anchor": need_anchor,
               "enumeration_split": split, "action_type_rules": action_rules,
               "coverage_by_part": res["coverage_by_part"],
               "gold_parts_hit": res["gold_parts_hit"], "gold_parts": res["gold_parts"],
               "wrong_intent": res["wrong_intent"],
               "guard_wrong_le_12": res["wrong_intent"] <= 12,
               "per_clip": res["per_clip"]}
        matrix.append(row)
        print(f"  {label:56} cov={row['coverage_by_part']} "
              f"hit={row['gold_parts_hit']}/{row['gold_parts']} "
              f"wrong={row['wrong_intent']}")

    # ---------- STEP 4: realistic projection -----------------------------
    # Step 3 forces the compound path on all 15 clips, i.e. it assumes routing is
    # solved. In production a clip only enters the path when the detector (or a
    # new routing rule) opens it. This is the number that would actually ship.
    from app.services.question_bank import question_bank as _qb

    def single_path_intent(r):
        m = _qb.match(r.get("transcript") or "")
        return [m.entry.id] if m is not None else []

    projection = []
    for rule_name in ("R1_min8w", "R1_or_R5_min8w", None):
        fn = ROUTING_RULES[rule_name] if rule_name else (lambda t: False)
        for theta, split, action_rules in (
            (None, False, False), (None, True, True), (0.4, True, True), (0.4, False, False)
        ):
            restore = install_v5_detect_intent() if action_rules else None
            try:
                def picker(r, _fn=fn, _th=theta, _sp=split):
                    tr = r.get("transcript") or ""
                    opened = (
                        detect_question_complexity(tr).question_type != "single" or _fn(tr)
                    )
                    if not opened:
                        return single_path_intent(r)
                    out = []
                    for sub in parts_for(r, theta=_th, need_anchor=False):
                        frags = (split_enumeration(sub) or [sub]) if _sp else [sub]
                        for frag in frags:
                            if _th is not None and not evidence_ok(frag, tr, _th, False):
                                continue
                            got = accept_first(frag)
                            if got:
                                out.append(got)
                    # >=2-intent pre-empt guard: fall back to the single answer
                    return out if len(out) >= 2 else single_path_intent(r)

                res = score(comp, picker)
            finally:
                if restore:
                    restore()
            label = (f"routing={rule_name or 'detector_only'} | "
                     f"evidence={'off' if theta is None else theta} | "
                     f"split={'I' if split else '-'} | action={'H' if action_rules else '-'}")
            projection.append({"config": label, "routing_rule": rule_name,
                               "theta": theta, "split": split,
                               "action_rules": action_rules,
                               "coverage_by_part": res["coverage_by_part"],
                               "gold_parts_hit": res["gold_parts_hit"],
                               "gold_parts": res["gold_parts"],
                               "wrong_intent": res["wrong_intent"],
                               "guard_wrong_le_12": res["wrong_intent"] <= 12,
                               "per_clip": res["per_clip"]})
            print(f"  PROJ {label:74} cov={res['coverage_by_part']} "
                  f"hit={res['gold_parts_hit']}/{res['gold_parts']} wrong={res['wrong_intent']}")

    best = sorted(
        [m for m in matrix if m["guard_wrong_le_12"]],
        key=lambda m: (-(m["coverage_by_part"] or 0), m["wrong_intent"]),
    )[:5]
    safe_rules = [e["rule"] for e in rule_table
                  if blast[e["rule"]]["newly_broken"] == 0 and e["compound_recovered"] > 0]
    safe_rules_with_guard = [
        e["rule"] for e in rule_table
        if blast[e["rule"]]["newly_broken_with_multi_intent_guard"] == 0
        and e["compound_recovered"] > 0]

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "V5 Phase B3 — routing entry + evidence-grounded acceptance",
        "scope": "measurement only; no production code touched",
        "semantic_index_ready": warm,
        "validity": ("warm" if warm else
                     "COLD — ordering only; absolute coverage is a lower bound"),
        "guards": {"compound_wrong_intent_max": 12,
                   "non_compound_newly_broken_max": 0},
        "step1_blocked_clips": blocked,
        "step1_rule_table": rule_table,
        "step1_blast_radius": blast,
        "step1_rules_with_zero_new_breakage": safe_rules,
        "step1_rules_with_zero_new_breakage_under_multi_intent_guard": safe_rules_with_guard,
        "step2_parts_audit": parts_audit,
        "step2_evidence_sweep": evidence_rows,
        "step3_matrix": matrix,
        "step3_best_under_guard": [b["config"] for b in best],
        "step4_realistic_projection": projection,
        "step4_note": ("step 3 assumes routing is solved; step 4 opens the path only "
                       "when the rule fires and applies the >=2-intent pre-empt guard, "
                       "falling back to the single bank answer otherwise"),
        "decision_status": "PROVISIONAL — warm rerun required before any adoption",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_B3_ROUTING_AND_EVIDENCE.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# V5 Phase B3 — routing entry + evidence-grounded acceptance", "",
          f"Created: {payload['created_at']}",
          f"`semantic_index_ready={warm}` — {payload['validity']}", "",
          "Measurement only. No `app/` file was modified.", "",
          "## Step 1 — why telegraphic compound never enters the path", "",
          f"{len(blocked)} of {len(comp)} compound clips are classified SINGLE by "
          "`detect_question_complexity`, so `compound_question_pipeline.py:230` returns "
          "with `used_compound_path=False`.", "",
          "| clip | terminal branch | fragments | action cue in utterance | rules that would open |",
          "|---|---|---:|---|---|"]
    for b in blocked:
        md.append(f"| {b['clip']} | {b['terminal_branch']} | {b['fragment_count']} | "
                  f"{b['whole_utterance_has_action_cue']} | "
                  f"{', '.join(b['rules_that_would_open']) or '—'} |")
    md += ["", "### Recall vs false-positive for each candidate routing rule", "",
           "| rule | recovers (of blocked) | opens non-compound | pre-empted | loses gold | **newly broken** | newly broken with >=2-intent guard |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for e in rule_table:
        d = blast[e["rule"]]
        md.append(f"| {e['rule']} | {e['compound_recovered']}/{e['compound_recovered_of']} | "
                  f"{e['non_compound_newly_opened']}/{e['non_compound_of']} | "
                  f"{d['preempted']} | {d['preempt_loses_gold']} | **{d['newly_broken']}** | "
                  f"{d['newly_broken_with_multi_intent_guard']} |")
    md += ["",
           "`newly broken` = a non-compound clip that v4 answered with the correct "
           "intent and that the opened compound path would answer with the gold intent "
           "absent. `answer_generator.py:351-360` returns the compound answer *before* "
           "the strong single bank answer, so these are real regressions, at compound "
           "confidence 0.88-0.94 — i.e. high-confidence wrong.", "",
           f"Rules that recover something and break nothing: "
           f"**{', '.join(safe_rules) or 'none'}**",
           f"Same, once a compound answer may only pre-empt when it produced >=2 "
           f"accepted intents: **{', '.join(safe_rules_with_guard) or 'none'}**", "",
           "## Step 2 — evidence-grounded acceptance", "",
           f"{len(parts_audit)} sub-questions audited, {len(facet_parts)} of them "
           "facet-derived (`_FACETS` emits up to 3 canonical questions per matched "
           "key, which is where fabricated asks come from).", "",
           "| theta | parts dropped | of which facet-derived |", "|---:|---:|---:|"]
    for e in evidence_rows:
        md.append(f"| {e['theta']} | {e['parts_dropped']}/{e['parts_total']} | "
                  f"{e['parts_dropped_facet_derived']} |")
    md += ["", "## Step 3 — I / HI measured on top of routing + evidence", "",
           "| config | coverage | hit | wrong | guard wrong<=12 |",
           "|---|---:|---:|---:|---|"]
    for m in matrix:
        md.append(f"| {m['config']} | {m['coverage_by_part']} | "
                  f"{m['gold_parts_hit']}/{m['gold_parts']} | {m['wrong_intent']} | "
                  f"{'ok' if m['guard_wrong_le_12'] else 'FAIL'} |")
    md += ["", f"Best under guard: {', '.join(payload['step3_best_under_guard']) or 'none'}",
           "", "Step 3 assumes routing is solved (every clip forced into the path).", "",
           "## Step 4 — realistic projection (routing rule + >=2-intent pre-empt guard)", "",
           "| config | coverage | hit | wrong |", "|---|---:|---:|---:|"]
    for pr in projection:
        md.append(f"| {pr['config']} | {pr['coverage_by_part']} | "
                  f"{pr['gold_parts_hit']}/{pr['gold_parts']} | {pr['wrong_intent']} |")
    md += ["",
           "", "**Status: PROVISIONAL.** No configuration may be adopted until this "
           "table is reproduced with `semantic_index_ready=True` and the routing rule "
           "shows zero newly broken non-compound clips.", ""]
    (REPORTS / "V5_B3_ROUTING_AND_EVIDENCE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nwrote {REPORTS/'V5_B3_ROUTING_AND_EVIDENCE.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
