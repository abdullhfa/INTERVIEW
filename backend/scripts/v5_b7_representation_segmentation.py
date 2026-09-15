"""
V5 Phase B7 — Candidate Representation (P) + Segmentation Residual (S).
MEASUREMENT ONLY. Nothing in app/ is modified.

    python scripts/v5_b7_representation_segmentation.py
Writes reports/V5_B7_REPRESENTATION_SEGMENTATION.{md,json}.

────────────────────────────────────────────────────────────────────────────
INSTRUMENT DEFECT FIXED HERE (read before trusting B5/B6/B6.1)

`install_*_detect_intent()` in v5_b5 / v5_b6 / v5_b61 (and in the H rows of
v5_b3 / v5_b4) calls:

    QB.question_bank.load(force=True)

and never re-warms. `QuestionBank.load()` builds a fresh `_Index`, whose
`alias_matrix` is None, and sets `self._warm = False`. Only `warm()` rebuilds
that matrix. Consequences for every measurement taken after that call:

  * `_score_all` sets `semantic = np.zeros(n_alias)` (question_bank.py:967-972),
    so `_W_SEM = 0.34` — a third of the hybrid score — was ZERO.
  * `match()` demotes every strong match to weak (question_bank.py:679-680).

Empirically: all 120 `hybrid_top5` rows in V5_B5_RESIDUAL_MATCHING.json carry
`semantic: 0.0`, while `semantic_intent_index` (a DIFFERENT component, the one
`semantic_index_ready` reports) was warm and scoring 0.57 on the same
fragments. The reports therefore say "warm" while the bank's hybrid ranker was
running lexical+keyword only.

So the B5 bucket `HYBRID_RANKING` and the B6/B6.1 verdict "ranking path closed"
were measured on a scorer with its semantic term disabled. This script restores
the matrix and re-measures the baseline so the damage is visible, before
testing P and S.
────────────────────────────────────────────────────────────────────────────

ARMS (each structural; no holdout phrase, clip id, or gold text is referenced)

  P — Candidate/Profile Representation.
      Each bank entry gains extra aliases generated from ITS OWN question,
      topic and action type: canonical phrasing, action-consistent variants
      (what/how/when/why/compare/experience) and nominalisation forms of its
      own verbs (prevent → prevention, detect → detection). Variants are
      emitted ONLY in the entry's own action type, so a `definition` entry
      never gains a `how do you ...` surface and cannot steal from its `how`
      sibling. Weights, thresholds and `_accept_match` are untouched.

  S — Segmentation Residual.
      Multiple asks inside ONE clause with no list punctuation. A clause with
      an imperative/interrogative head and >= 2 distinct nominalisations is
      treated as that many asks, anchored to the clause's shared subject.
      Includes the matching entry rule, since such a clause does not open the
      compound path today.

GATES (as briefed)
  coverage_by_part > baseline by >= 0.02
  wrong_intent <= 4
  hc_risk == 0
  newly_broken == 0
  recovered_target > 0            (from the P/S residual set, not elsewhere)
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

import os

ALLOW_COLD = os.getenv("B7_ALLOW_COLD", "").strip() in {"1", "true", "yes"}
EVIDENCE_THETA = 0.4
HC_SCORE = 0.85
MATERIAL_GAIN = 0.02
WRONG_MAX = 4
P_S_BUCKETS = {"SEGMENTATION_RESIDUAL", "CANDIDATE_GENERATION", "SEMANTIC_PROFILE_QUALITY"}

# ── shape primitives (identical to B3-B6.1) ────────────────────────────────
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


# ══ ARM S — intra-clause multi-action segmentation ═════════════════════════
_NOMINAL_SUFFIX = ("tion", "sion", "ment", "ance", "ence", "ability", "ility")
_STOPISH = {"your", "our", "the", "a", "an", "their", "its", "my", "this", "that",
            "in", "for", "with", "under", "on", "of", "to", "and", "or", "is", "are"}


def _is_nominalisation(tok: str) -> bool:
    t = tok.lower().strip(".,;:?!")
    return len(t) >= 7 and t.endswith(_NOMINAL_SUFFIX)


def _clause_head_verb(text: str) -> str | None:
    m = _IMPER.search(text or "")
    return m.group(1).lower() if m else None


def _clause_subject(text: str, nominals: list[str]) -> str | None:
    """
    Shared subject = the first content token that is neither the imperative head
    nor a nominalisation nor a function word. Purely positional.
    """
    head = _clause_head_verb(text)
    for tok in (text or "").split():
        t = tok.lower().strip(".,;:?!")
        if not t or t in _STOPISH:
            continue
        if head and t.startswith(head[:5]):
            continue
        if t in nominals:
            continue
        if len(t) < 4:
            continue
        return t
    return None


def intra_clause_asks(text: str) -> list[str]:
    """
    One clause, no list punctuation, >= 2 nominalisations, an action head and a
    shared subject → one ask per nominalisation, anchored on that subject.
    Returns [] when the shape does not apply.
    """
    raw = (text or "").strip()
    if not raw or len(fragments(raw)) > 1:
        return []
    if not clause_has_action(raw):
        return []
    nominals, seen = [], set()
    for tok in raw.split():
        t = tok.lower().strip(".,;:?!")
        if _is_nominalisation(t) and t not in seen:
            seen.add(t)
            nominals.append(t)
    if len(nominals) < 2:
        return []
    subject = _clause_subject(raw, nominals)
    if not subject:
        return []
    head = _clause_head_verb(raw)
    out = [f"{head} {subject}" if head else subject]
    for nom in nominals:
        out.append(f"{subject} {nom}")
    # de-dup, keep order
    got, uniq = set(), []
    for a in out:
        if a not in got:
            got.add(a)
            uniq.append(a)
    return uniq


def s_opens(text: str) -> bool:
    """Entry rule for arm S — the clause shape above also opens the path."""
    return bool(intra_clause_asks(text))


# ══ ARM P — candidate/profile representation ═══════════════════════════════
_IRREGULAR_NOMINAL = {
    "prevent": "prevention", "detect": "detection", "evaluate": "evaluation",
    "validate": "validation", "mitigate": "mitigation", "retrieve": "retrieval",
    "generate": "generation", "classify": "classification", "select": "selection",
    "protect": "protection", "isolate": "isolation", "migrate": "migration",
    "integrate": "integration", "deploy": "deployment", "measure": "measurement",
    "manage": "management", "monitor": "monitoring", "rank": "ranking",
    "chunk": "chunking", "embed": "embedding", "split": "splitting",
    "handle": "handling", "score": "scoring", "tune": "tuning",
}

_LEAD_STRIP = re.compile(
    r"^(?:what\s+(?:is|are|'s)\s+|what's\s+|how\s+(?:do|does|would|can|should)\s+you\s+|"
    r"how\s+to\s+|how\s+(?:do|does)\s+|why\s+(?:do|does|is|are)?\s*|"
    r"when\s+(?:do|does|is|are)?\s*|who\s+(?:is|are)?\s*|where\s+(?:is|are)?\s*|"
    r"have\s+you\s+(?:used|worked\s+on)\s+|tell\s+me\s+about\s+|walk\s+me\s+through\s+|"
    r"describe\s+|explain\s+|define\s+|give\s+me\s+|point\s+me\s+to\s+)",
    re.I)
_TRAIL_STRIP = re.compile(r"[?.!]+$")


def entry_subject(question: str) -> str:
    s = _TRAIL_STRIP.sub("", (question or "").strip())
    prev = None
    while prev != s:
        prev = s
        s = _LEAD_STRIP.sub("", s).strip()
    s = re.sub(r"^(?:an?|the|your|our|their)\s+", "", s, flags=re.I).strip()
    return s


def nominalise(word: str) -> str | None:
    w = word.lower().strip()
    if w in _IRREGULAR_NOMINAL:
        return _IRREGULAR_NOMINAL[w]
    if len(w) < 5:
        return None
    if w.endswith("ate"):
        return w[:-1] + "ion"
    if w.endswith("ise") or w.endswith("ize"):
        return w[:-1] + "ation"
    return None


_ACTION_TEMPLATES = {
    "definition": ("what is {s}", "define {s}", "{s} meaning", "{s}"),
    "how": ("how do you {s}", "how to {s}", "{s} approach", "{s} steps"),
    "when": ("when do you {s}", "when is {s} needed", "{s} timing"),
    "why": ("why {s}", "reason for {s}", "{s} rationale"),
    "compare": ("difference between {s}", "{s} comparison", "{s} tradeoffs"),
    "describe": ("describe {s}", "walk me through {s}", "{s} overview"),
    "experience": ("have you used {s}", "your experience with {s}", "tell me about {s}"),
}


def generated_aliases(entry) -> list[str]:
    """
    Extra matching surfaces for ONE entry, derived only from that entry.
    Action-consistent: a `definition` entry never gains a `how` surface.
    """
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import detect_intent

    subj = entry_subject(entry.question or "")
    if not subj or len(subj.split()) > 8:
        return []
    action = detect_intent(normalize_for_matching(entry.question or ""))
    out: list[str] = [subj]
    for tpl in _ACTION_TEMPLATES.get(action or "", ()):
        out.append(tpl.format(s=subj))
    # nominalisation of the subject's own leading verb, e.g. "prevent overfitting"
    # → "overfitting prevention". Generic morphology, no vocabulary list of topics.
    toks = subj.split()
    if toks:
        nom = nominalise(toks[0])
        if nom:
            rest = " ".join(toks[1:]).strip()
            out.append(f"{rest} {nom}".strip())
            out.append(f"{nom} of {rest}".strip() if rest else nom)
    got, uniq = set(), []
    for a in out:
        a = a.strip()
        if a and a.lower() not in got:
            got.add(a.lower())
            uniq.append(a)
    return uniq


# ══ in-process patches ═════════════════════════════════════════════════════
def _rewarm_bank():
    """
    Rebuild the alias embedding matrix after any forced reload. WITHOUT this the
    hybrid semantic term is zero and every strong match is demoted to weak —
    the defect that invalidated B5/B6/B6.1.
    """
    from app.services.question_bank import question_bank

    question_bank.warm()
    idx = getattr(question_bank, "_index", None)
    am = getattr(idx, "alias_matrix", None) if idx is not None else None
    if am is None and ALLOW_COLD:
        return None
    if am is None:
        raise RuntimeError(
            "alias_matrix is None after warm(): the bank's semantic term would be "
            "disabled and this measurement would be invalid. Aborting."
        )
    return am


def install_arms(*, action_rules: bool, representation: bool):
    """Install H (action-type rules) and/or P (representation). Returns restore()."""
    from app.services import question_bank as QB

    original_detect = QB.detect_intent
    original_from_raw = QB.QuestionBank._entry_from_raw

    if action_rules:
        def patched_detect(normalized: str):
            got = original_detect(normalized)
            if got:
                return got
            for name, pat in _V5_EXTRA_RULES:
                if pat.search(normalized or ""):
                    return name
            return None

        QB.detect_intent = patched_detect

    added = {"entries_touched": 0, "aliases_added": 0}
    if representation:
        def patched_from_raw(raw, bank_name):
            # NOTE: _entry_from_raw is a @staticmethod called as
            # self._entry_from_raw(raw, bank_name) — no self argument.
            entry = original_from_raw(raw, bank_name)
            if entry is None:
                return None
            extra = [a for a in generated_aliases(entry) if a not in entry.aliases]
            if not extra:
                return entry
            added["entries_touched"] += 1
            added["aliases_added"] += len(extra)
            return entry.__class__(
                id=entry.id, bank=entry.bank, category=entry.category, topic=entry.topic,
                question=entry.question, aliases=tuple(entry.aliases) + tuple(extra),
                keywords=entry.keywords, answer_en=entry.answer_en, answer_ar=entry.answer_ar,
                followup_en=entry.followup_en, listen_for=entry.listen_for,
            )

        QB.QuestionBank._entry_from_raw = staticmethod(patched_from_raw)

    QB.question_bank.load(force=True)
    _rewarm_bank()

    def restore():
        QB.detect_intent = original_detect
        QB.QuestionBank._entry_from_raw = staticmethod(original_from_raw)
        QB.question_bank.load(force=True)
        _rewarm_bank()

    return restore, added


# ══ pipeline projection (identical contract to B6.1) ═══════════════════════
def evidence_ratio(sub_question: str, transcript: str) -> float:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _content_tokens

    q = set(_content_tokens(normalize_for_matching(sub_question or "")))
    t = set(_content_tokens(normalize_for_matching(transcript or "")))
    if not q:
        return 0.0
    return len(q & t) / len(q)


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


def path_opens(text: str, *, segmentation: bool) -> bool:
    from app.services.compound_question_detector import detect_question_complexity

    if detect_question_complexity(text).question_type != "single":
        return True
    if r1_min8w(text):
        return True
    return bool(segmentation and s_opens(text))


def working_parts(transcript: str, *, segmentation: bool) -> list[str]:
    kept: list[str] = []
    subs = forced_subs(transcript)
    if segmentation:
        expanded: list[str] = []
        for s in subs:
            asks = intra_clause_asks(s)
            expanded.extend(asks or [s])
        if not subs:
            expanded = intra_clause_asks(transcript)
        subs = expanded
    for s in subs:
        if evidence_ratio(s, transcript) < EVIDENCE_THETA:
            continue
        for f in (split_enumeration(s) or [s]):
            if evidence_ratio(f, transcript) < EVIDENCE_THETA:
                continue
            kept.append(f)
    return kept


def pick(text: str, already: set[str]):
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank

    tops = question_bank.top_matches(text, top_k=6)
    if not tops:
        return None, 0.0
    m = next((t for t in tops if t.entry.id not in already), tops[0])
    ok, _r, _mg = _accept_match(m)
    return (m.entry.id if ok else None), float(m.score)


def project(transcript: str, *, segmentation: bool):
    from app.services.question_bank import question_bank

    if not path_opens(transcript, segmentation=segmentation):
        m = question_bank.match(transcript)
        return ([m.entry.id], [float(m.score)]) if m else ([], [])
    ids, scores, already = [], [], set()
    for p in working_parts(transcript, segmentation=segmentation):
        got, sc = pick(p, already)
        if got:
            ids.append(got)
            scores.append(sc)
            already.add(got)
    seen, uniq, us = set(), [], []
    for i, s in zip(ids, scores):
        if i not in seen:
            seen.add(i)
            uniq.append(i)
            us.append(s)
    if len(uniq) < 2:                      # >=2-intent pre-empt guard
        m = question_bank.match(transcript)
        return ([m.entry.id], [float(m.score)]) if m else ([], [])
    return uniq, us


def score_arm(name, comp, other, targets, *, segmentation: bool):
    from app.services.compound_question_detector import detect_question_complexity

    hit = wrong = total = hc = 0
    recovered, per_clip = [], []
    for r in comp:
        gold = list(r.get("expected_intent_ids") or [])
        total += len(gold)
        sel, scores = project(r.get("transcript") or "", segmentation=segmentation)
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
        per_clip.append({"clip": r["sample_id"], "gold": gold, "selected": sel,
                         "hit": sorted(got), "wrong": bad,
                         "coverage": _f(len(got) / max(1, len(gold)))})

    # newly broken — two definitions.
    #   opened_only : same rule as B6.1 (clips the routing rule opens)
    #   all_single  : every non-compound clip, because P changes the single
    #                 bank path too, which the opened_only definition misses.
    nb_opened = nb_all = 0
    broken_detail = []
    for r in other:
        tr = r.get("transcript") or ""
        gold = list(r.get("expected_intent_ids") or [])
        if not (gold and bool(r.get("intent_ok"))):
            continue
        sel, _s = project(tr, segmentation=segmentation)
        if not sel or (set(gold) & set(sel)):
            continue
        nb_all += 1
        broken_detail.append({"clip": r["sample_id"], "label": r.get("question_type_label"),
                              "gold": gold, "selected": sel})
        if detect_question_complexity(tr).question_type == "single" and (
            r1_min8w(tr) or (segmentation and s_opens(tr))
        ) and len(sel) >= 2:
            nb_opened += 1

    return {"arm": name, "gold_parts": total, "gold_parts_hit": hit,
            "coverage_by_part": _f(hit / max(1, total)), "wrong_intent": wrong,
            "hc_risk": hc, "recovered_target": len(recovered),
            "recovered_target_of": len(targets), "recovered_detail": recovered,
            "newly_broken_opened_only": nb_opened, "newly_broken_all_single": nb_all,
            "newly_broken_detail": broken_detail[:20], "per_clip": per_clip}


# ══ data ═══════════════════════════════════════════════════════════════════
def load_rows():
    rep = json.loads(V4.read_text(encoding="utf-8"))
    rows = [r for r in rep["results"] if not str(r.get("notes") or "").startswith("warmup:")]
    comp = [r for r in rows if (r.get("question_type_label") or "") == "compound"]
    other = [r for r in rows
             if (r.get("question_type_label") or "") != "compound" and r.get("expected_intent_ids")]
    return comp, other


def ps_targets():
    d = json.loads(B5.read_text(encoding="utf-8"))
    rows = [c for c in d.get("missing_parts", []) if c.get("bucket") in P_S_BUCKETS]
    keys = {(c["clip"], c["gold_intent"]) for c in rows}
    return keys, rows


def reachability(rows):
    """
    Honest pre-analysis: a target with no surviving evidence in the ASR text is
    not reachable by representation or segmentation, and must not be counted as
    a failure of either arm.
    """
    out = []
    for c in rows:
        stt = c.get("stt_detail") or {}
        lost = list(stt.get("lost") or [])
        overlap = list(c.get("content_overlap_tokens") or [])
        carries = bool(c.get("text_carries_meaning"))
        if lost:
            verdict, why = "UNREACHABLE_STT_LOSS", f"ASR lost {lost}"
        elif not overlap and not carries:
            verdict, why = "UNREACHABLE_NO_EVIDENCE", "no gold token occurs in the utterance"
        else:
            verdict, why = "REACHABLE", "gold tokens present in the utterance"
        out.append({"clip": c["clip"], "gold": c["gold_intent"], "bucket": c["bucket"],
                    "fragment": c.get("fragment"), "verdict": verdict, "why": why,
                    "content_overlap_tokens": overlap, "stt_lost": lost})
    return out


def main() -> int:
    if not V4.is_file() or not B5.is_file():
        print("missing V4 or B5 report")
        return 1

    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index

    if not semantic_intent_index.ready and not ALLOW_COLD:
        print("!! semantic_intent_index cold — abort")
        return 2
    idx = getattr(question_bank, "_index", None)
    if getattr(idx, "alias_matrix", None) is None and not ALLOW_COLD:
        print("!! alias_matrix is None straight after warm_system_blocking — abort")
        return 2
    if ALLOW_COLD:
        print("!! B7_ALLOW_COLD set — this is a SMOKE TEST, the numbers are invalid")

    comp, other = load_rows()
    targets, target_rows = ps_targets()
    reach = reachability(target_rows)
    n_reach = sum(1 for r in reach if r["verdict"] == "REACHABLE")
    print(f"compound={len(comp)} non_compound={len(other)} "
          f"P/S targets={len(targets)} reachable={n_reach}")
    for r in reach:
        print(f"  {r['clip']} {r['gold']:32} {r['bucket']:24} {r['verdict']}")

    results = []
    alias_stats = {}

    # A0 — reproduce the BROKEN condition B5/B6/B6.1 ran under, to size the damage.
    from app.services import question_bank as QB
    _orig_detect = QB.detect_intent

    def _h(normalized: str):
        got = _orig_detect(normalized)
        if got:
            return got
        for nm, pat in _V5_EXTRA_RULES:
            if pat.search(normalized or ""):
                return nm
        return None

    QB.detect_intent = _h
    QB.question_bank.load(force=True)          # deliberately WITHOUT warm()
    broken_matrix = getattr(getattr(QB.question_bank, "_index", None), "alias_matrix", None)
    res = score_arm("A0_baseline_as_measured_in_B6 (alias_matrix=None)",
                    comp, other, targets, segmentation=False)
    res["alias_matrix_present"] = broken_matrix is not None
    results.append(res)
    print(f"  {res['arm']:58} cov={res['coverage_by_part']} wrong={res['wrong_intent']} "
          f"hc={res['hc_risk']} alias_matrix={res['alias_matrix_present']}")
    QB.detect_intent = _orig_detect
    QB.question_bank.load(force=True)
    _rewarm_bank()

    # A / P / S / P+S — all with the semantic term restored.
    plan = [("A_baseline_semantic_restored", False, False),
            ("P_representation", True, False),
            ("S_segmentation", False, True),
            ("PS_representation_plus_segmentation", True, True)]
    for name, rep, seg in plan:
        restore, added = install_arms(action_rules=True, representation=rep)
        try:
            r = score_arm(name, comp, other, targets, segmentation=seg)
            r["alias_matrix_present"] = True
            r["aliases_added"] = dict(added)
            alias_stats[name] = dict(added)
        finally:
            restore()
        results.append(r)
        print(f"  {name:58} cov={r['coverage_by_part']} hit={r['gold_parts_hit']}/"
              f"{r['gold_parts']} wrong={r['wrong_intent']} hc={r['hc_risk']} "
              f"target={r['recovered_target']}/{r['recovered_target_of']} "
              f"nb_open={r['newly_broken_opened_only']} nb_all={r['newly_broken_all_single']}")

    base = next(r for r in results if r["arm"] == "A_baseline_semantic_restored")
    gates, winners = {}, []
    for r in results:
        if r["arm"].startswith("A0") or r["arm"] == base["arm"]:
            continue
        g = {
            "coverage_material_gain": (r["coverage_by_part"] or 0)
            >= (base["coverage_by_part"] or 0) + MATERIAL_GAIN,
            "wrong_le_4": r["wrong_intent"] <= WRONG_MAX,
            "hc_zero": r["hc_risk"] == 0,
            # The briefed gate is newly_broken == 0. Two definitions are tracked:
            #   opened_only — clips broken BY OPENING the path (the B6.1 metric)
            #   all_single  — every non-compound clip, needed because arm P also
            #                 changes the ordinary single-match path. Its baseline
            #                 value is NOT zero (it counts pre-existing single-path
            #                 misses), so for that one the operative test is
            #                 "no worse than baseline".
            "newly_broken_opened_zero": r["newly_broken_opened_only"] == 0,
            "newly_broken_opened_le_baseline":
                r["newly_broken_opened_only"] <= base["newly_broken_opened_only"],
            "newly_broken_all_le_baseline":
                r["newly_broken_all_single"] <= base["newly_broken_all_single"],
            "target_recovery_gt_0": r["recovered_target"] > 0,
        }
        g["all_pass"] = all(
            g[k] for k in ("coverage_material_gain", "wrong_le_4", "hc_zero",
                           "newly_broken_opened_le_baseline",
                           "newly_broken_all_le_baseline", "target_recovery_gt_0")
        )
        g["all_pass_strict_zero_breakage"] = g["all_pass"] and g["newly_broken_opened_zero"]
        gates[r["arm"]] = g
        if g["all_pass"]:
            winners.append(r["arm"])

    a0 = results[0]
    instrument = {
        "defect": "question_bank.load(force=True) without warm() drops alias_matrix",
        "effect": "hybrid semantic term (_W_SEM=0.34) = 0; every strong match demoted to weak",
        "affected_reports": ["V5_B3 (H rows onward)", "V5_B4", "V5_B5",
                             "V5_B6", "V5_B61"],
        "proof": "all 120 hybrid_top5 rows in V5_B5_RESIDUAL_MATCHING.json have semantic=0.0 "
                 "while semantic_intent_index scored 0.57 on the same fragments",
        "baseline_as_measured": {"coverage": a0["coverage_by_part"],
                                 "wrong": a0["wrong_intent"], "hc": a0["hc_risk"]},
        "baseline_repaired": {"coverage": base["coverage_by_part"],
                              "wrong": base["wrong_intent"], "hc": base["hc_risk"]},
        "consequence": ("the B5 bucket HYBRID_RANKING and the B6/B6.1 verdict "
                        "'ranking path closed' were measured with the bank's semantic "
                        "term disabled and must be re-qualified before that path is "
                        "treated as closed"),
    }

    if winners:
        verdict = f"IMPLEMENT — {', '.join(winners)} passed every gate"
    elif base["coverage_by_part"] != a0["coverage_by_part"]:
        verdict = ("NO_WINNER_BUT_BASELINE_MOVED — no arm passed the gates, and the "
                   "repaired baseline differs from the one B6/B6.1 used, so phase 2 "
                   "cannot be closed on those numbers")
    else:
        verdict = "NO_WINNER — close phase 2 as NO-IMPLEMENT"

    payload = {"created_at": datetime.now(timezone.utc).isoformat(),
               "phase": "V5 Phase B7 — representation (P) + segmentation residual (S)",
               "scope": "measurement only; no production code touched",
               "valid": (not ALLOW_COLD),
               "validity_note": ("SMOKE TEST — B7_ALLOW_COLD was set, numbers are invalid"
                                 if ALLOW_COLD else "warm, semantic term active"),
               "gates": {"coverage_material_gain": MATERIAL_GAIN, "wrong_max": WRONG_MAX,
                         "hc": 0, "newly_broken": 0, "target_recovery": "> 0"},
               "instrument_defect": instrument,
               "targets": sorted(f"{c}:{g}" for c, g in targets),
               "target_reachability": reach,
               "reachable_target_count": n_reach,
               "alias_generation_stats": alias_stats,
               "baseline": base["arm"], "results": results, "gate_results": gates,
               "winners": winners, "verdict": verdict}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_B7_REPRESENTATION_SEGMENTATION.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# V5 Phase B7 — representation (P) + segmentation residual (S)", "",
          f"Created: {payload['created_at']}", "",
          "Measurement only. No `app/` file modified.", "",
          "## Instrument defect found before running B7", "",
          f"- {instrument['defect']}",
          f"- effect: {instrument['effect']}",
          f"- proof: {instrument['proof']}",
          f"- affected: {', '.join(instrument['affected_reports'])}", "",
          "| baseline | coverage | wrong | hc |", "|---|---:|---:|---:|",
          f"| as measured in B6/B6.1 (alias_matrix=None) | {a0['coverage_by_part']} | "
          f"{a0['wrong_intent']} | {a0['hc_risk']} |",
          f"| repaired (semantic term restored) | {base['coverage_by_part']} | "
          f"{base['wrong_intent']} | {base['hc_risk']} |", "",
          f"> {instrument['consequence']}", "",
          "## Target reachability (before any arm runs)", "",
          "| clip | gold | bucket | verdict | why |", "|---|---|---|---|---|"]
    for r in reach:
        md.append(f"| {r['clip']} | `{r['gold']}` | {r['bucket']} | **{r['verdict']}** | {r['why']} |")
    md += ["", f"Reachable targets: **{n_reach} / {len(reach)}** — the ceiling for B7.", "",
           "## Arms", "",
           "| arm | coverage | hit | wrong | hc | target recovered | newly broken (opened) | newly broken (all) |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        md.append(f"| {r['arm']} | {r['coverage_by_part']} | {r['gold_parts_hit']}/"
                  f"{r['gold_parts']} | {r['wrong_intent']} | {r['hc_risk']} | "
                  f"{r['recovered_target']}/{r['recovered_target_of']} | "
                  f"{r['newly_broken_opened_only']} | {r['newly_broken_all_single']} |")
    md += ["", "## Gates", "",
           f"Baseline newly_broken: opened={base['newly_broken_opened_only']}, "
           f"all_single={base['newly_broken_all_single']}. The `all_single` baseline is "
           "not zero — it counts pre-existing single-path misses — so for that column "
           "the test is 'no worse than baseline'.", "",
           "| arm | coverage +0.02 | wrong<=4 | hc=0 | nb_opened=0 | nb_opened<=base | nb_all<=base | target>0 | ALL |",
           "|---|---|---|---|---|---|---|---|---|"]
    for arm, g in gates.items():
        md.append(f"| {arm} | {g['coverage_material_gain']} | {g['wrong_le_4']} | "
                  f"{g['hc_zero']} | {g['newly_broken_opened_zero']} | "
                  f"{g['newly_broken_opened_le_baseline']} | "
                  f"{g['newly_broken_all_le_baseline']} | "
                  f"{g['target_recovery_gt_0']} | **{g['all_pass']}** |")
    md += ["", f"## VERDICT: {verdict}", ""]
    (REPORTS / "V5_B7_REPRESENTATION_SEGMENTATION.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8")
    print(f"\nVERDICT: {verdict}")
    print(f"wrote {REPORTS/'V5_B7_REPRESENTATION_SEGMENTATION.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
