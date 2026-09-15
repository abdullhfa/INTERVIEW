"""
V5 Phase B — compound counterfactuals. MEASUREMENT ONLY.

Nothing in app/ is modified. Variants that need different behaviour patch a
symbol inside this process, run, and restore it. No holdout phrase is ever
hard-coded: every rule added here is structural and applies to any utterance.

    python scripts/v5_compound_counterfactuals.py
    python scripts/v5_compound_counterfactuals.py --variants A H I HI

Writes reports/V5_COMPOUND_COUNTERFACTUALS.{md,json}.

WHY THESE VARIANTS
Phase A found `detect_intent()` returns None for 18 of the 32 sub-questions the
v4 compound cohort produced. Inspecting `_INTENT_RULES` shows why:

  * there is NO `when` rule at all
  * `how` is anchored to `^how do|how would|how does|how can|how should|how to|
    how is|how are|how will`, so elliptical `How you chunk oversized documents?`
    misses
  * there is no `who` / `where` rule

`_granularity_penalty` only fires for q_intent in {how, why, compare, definition}.
With q_intent None it never runs — which is exactly how `hard.hybrid_when` loses
to `tech.hybrid_search` on "Say when hybrid search needs it".

Scoring is per GOLD PART, and a part only counts when the matched intent is one
the clip has not already covered — re-matching the parent is a duplicate that
dedupe removes and adds no coverage.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
V4 = REPORTS / "FINAL_UNSEEN_HOLDOUT_V4_REPORT.json"

# ── structural helpers (no holdout text anywhere) ──────────────────────────
_INTERROG = re.compile(
    r"\b(what|why|how|when|which|who|whether|where|is|are|do|does|did|can|should|would)\b", re.I)
_IMPER = re.compile(
    r"\b(explain|tell|say|describe|give|point|walk|cover|name|define|summaris|summariz|list)\b", re.I)
_VERBISH = re.compile(
    r"\b(use|used|build|built|work|works|make|choose|pick|handle|stop|prevent|add|need|"
    r"matter|differ|design|halt|reduce|track|monitor)\b", re.I)
_PRONOUN = re.compile(r"\b(one|it|that|them|those|this|each)\b", re.I)


def clause_has_action(text: str) -> bool:
    return bool(_INTERROG.search(text) or _IMPER.search(text) or _VERBISH.search(text))


def split_enumeration(text: str) -> list[str]:
    """
    Structural enumeration split: 'A, B, and C' where the fragments are short
    noun-ish phrases. Generic — keyed on shape, never on vocabulary.
    """
    parts = [p.strip(" .;:") for p in re.split(r",|\band\b|\bthen\b|;", text) if p.strip(" .;:")]
    if len(parts) < 2:
        return []
    # only treat as an enumeration when most fragments are short and verbless
    short_verbless = sum(1 for p in parts if len(p.split()) <= 6 and not clause_has_action(p))
    if short_verbless >= max(2, int(0.5 * len(parts))):
        return [p for p in parts if p.split()]
    return []


# Variant H: complete the action-type rule set. These are the categories the
# existing set already models, plus the ones it is missing outright.
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
    """Patch detect_intent in-process; returns a restore callable."""
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
    QB.question_bank.load(force=True)          # aliases are tagged at load time

    def restore():
        QB.detect_intent = original
        QB.question_bank.load(force=True)

    return restore


def _subject_of(text: str) -> str:
    t = text.strip().rstrip("?.").strip()
    for pat in (
        r"^(?:which|what)\s+(.+?)\s+(?:have you used|do you use|would you (?:pick|choose))\b",
        r"^(?:tell me about|talk about)\s+(?:your\s+|the\s+)?(.+)$",
        r"^(?:what is|what are|what's)\s+(?:an?\s+|the\s+)?(.+)$",
        r"^(?:explain|describe|define)\s+(?:an?\s+|the\s+)?(.+)$",
        r"^(?:point me to|give me)\s+(?:your\s+|the\s+)?(.+)$",
    ):
        m = re.search(pat, t, re.I)
        if m:
            return m.group(1).strip()
    return t


def _action_word(clause: str) -> str | None:
    for name, pat in _V5_EXTRA_RULES:
        if pat.search(clause):
            return name
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import detect_intent
    return detect_intent(normalize_for_matching(clause))


_ACTION_PREFIX = {"when": "When", "how": "How", "why": "Why", "who": "Who",
                  "where": "Where", "compare": "What is the difference in",
                  "definition": "What is", "describe": "Describe",
                  "experience": "Have you worked on"}


def _env_snapshot() -> dict:
    """Recorded in every report from now on — Phase B shipped without it, which
    is why the warm/cold state of that run could not be audited afterwards."""
    import os

    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index

    idx = getattr(question_bank, "_index", None)
    am = getattr(idx, "alias_matrix", None) if idx is not None else None
    snap = {
        "semantic_index_ready": bool(getattr(semantic_intent_index, "ready", False)),
        "alias_matrix_present": am is not None,
        "bank_entries": len(getattr(idx, "entries", []) or []) if idx is not None else 0,
        "bank_generation": int(getattr(question_bank, "generation", -1) or -1),
        "env": {k: os.getenv(k) for k in
                ("SEMANTIC_BLOB_PROXY", "QB_FAST_LEXICAL", "INTENT_SEMANTIC_MODEL",
                 "SEMANTIC_INTENT_RECOVERY")},
    }
    try:
        from app.services.question_bank import embed_stats
        snap["embed_stats"] = dict(embed_stats() or {})
    except Exception:
        snap["embed_stats"] = None
    try:
        from app.services.semantic_intent_recovery import rerank_stats
        snap["rerank_stats"] = dict(rerank_stats() or {})
    except Exception:
        snap["rerank_stats"] = None
    return snap


# ── the cases ──────────────────────────────────────────────────────────────
def load_cases() -> list[dict]:
    rep = json.loads(V4.read_text(encoding="utf-8"))
    rows = [r for r in rep["results"] if not str(r.get("notes") or "").startswith("warmup:")]
    return [r for r in rows if (r.get("question_type_label") or "") == "compound"]


def score_variant(name: str, cases: list[dict], resolver) -> dict:
    """resolver(clip_row) -> list of selected intent ids (in order)."""
    from app.services.question_bank import question_bank

    hit = wrong = dup = parent_rematch = hc = 0
    total_gold = 0
    per_clip = []
    t0 = time.perf_counter()
    for r in cases:
        gold = list(r.get("expected_intent_ids") or [])
        total_gold += len(gold)
        sel = resolver(r)
        seen, uniq = set(), []
        for s in sel:
            if s in seen:
                dup += 1
                continue
            seen.add(s)
            uniq.append(s)
        got = [s for s in uniq if s in gold]
        bad = [s for s in uniq if s not in gold]
        hit += len(set(got))
        wrong += len(bad)
        per_clip.append({"clip": r["sample_id"], "gold": gold, "selected": uniq,
                         "hit": sorted(set(got)), "wrong": bad,
                         "coverage": round(len(set(got)) / max(1, len(gold)), 4)})
    ms = (time.perf_counter() - t0) * 1000
    return {"variant": name, "gold_parts": total_gold, "gold_parts_hit": hit,
            "coverage_by_part": round(hit / max(1, total_gold), 4),
            "coverage_mean_of_clips": round(
                sum(c["coverage"] for c in per_clip) / max(1, len(per_clip)), 4),
            "wrong_intent": wrong, "duplicates": dup, "parent_rematch": parent_rematch,
            "hc_risk": hc, "latency_ms_total": round(ms, 1),
            "latency_ms_per_clip": round(ms / max(1, len(per_clip)), 2),
            "per_clip": per_clip}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="*", default=None)
    ap.add_argument(
        "--parts",
        choices=("live", "recorded"),
        default="live",
        help="source of the sub-questions every variant starts from. 'live' "
             "recomputes them with the same forced detection production uses; "
             "'recorded' replays the v4 trace. Both are fair as long as ALL "
             "variants use the same one — that was the Phase B bug.",
    )
    args = ap.parse_args()
    if not V4.is_file():
        print(f"missing {V4}")
        return 1

    from app.services.compound_question_pipeline import _accept_match, resolve_compound_question
    from app.services.question_bank import question_bank
    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()
    from app.services.semantic_intent_index import semantic_intent_index

    warm = bool(semantic_intent_index.ready)
    if not warm:
        print("!! SEMANTIC INDEX COLD — every variant, including the baseline, is")
        print("   evaluated without cosine scores. The ORDERING between variants is")
        print("   still meaningful (they share conditions) but the absolute coverage")
        print("   numbers are a lower bound and must not be compared with the warm")
        print("   production run. Fix the embedder before deciding anything.")
    cases = load_cases()
    print(f"compound clips: {len(cases)}  semantic_index_ready={warm}")

    # ---- shared starting condition (Phase B2 fix) ------------------------
    # Phase B compared variant A, which recomputed everything from the raw
    # transcript with NO detection, against variants B-I, which were handed the
    # RECORDED sub-questions. The recorded sub-questions are the output of the
    # forced detection that interview_e2e_loopback applies to labeled compound
    # packs. A therefore started from nothing on the 10 of 15 clips whose bare
    # detector says "single", and the resulting baseline was meaningless.
    # Every variant now starts from ONE declared source.
    def prod_parity_resolution(r):
        """Exactly what interview_e2e_loopback.run_clip does for a labeled pack."""
        from app.services.compound_question_detector import (
            ComplexityDetection,
            detect_question_complexity,
        )

        text = r.get("transcript") or ""
        if not text.strip():
            return None
        det = detect_question_complexity(text)
        force_det = det
        if det is None or det.question_type == "single":
            force_det = ComplexityDetection(
                "compound",
                0.9,
                max(2, int(getattr(det, "request_count_estimate", 1) or 1)),
                ("labeled_compound_pack",),
            )
        return resolve_compound_question(
            text, conversation_history=None, detection=force_det
        )

    _live_cache: dict = {}

    def live_res(r):
        key = r["sample_id"]
        if key not in _live_cache:
            _live_cache[key] = prod_parity_resolution(r)
        return _live_cache[key]

    PARTS_SOURCE = args.parts

    def parts_of(r):
        if PARTS_SOURCE == "recorded":
            return list((r.get("compound_trace") or {}).get("sub_questions") or [])
        res = live_res(r)
        return list(getattr(res, "sub_questions", None) or [])

    def _cand_map(r):
        if PARTS_SOURCE == "recorded":
            cands = (r.get("compound_trace") or {}).get("candidate_intents") or []
        else:
            cands = getattr(live_res(r), "candidate_intents", None) or []
        return {c.get("sub_question"): c.get("intent_id") for c in cands}

    def parent_id_for(r, idx):
        subs = parts_of(r)
        return _cand_map(r).get(subs[idx - 1]) if idx > 0 else None

    def accept_first(text, exclude=None, topic=None):
        tops = question_bank.top_matches(text, top_k=6, topic_hint=topic)
        m = next((t for t in tops if exclude is None or t.entry.id != exclude), None)
        ok, _reason, _margin = _accept_match(m)
        return m.entry.id if (m and ok) else None

    # ---- resolvers -------------------------------------------------------
    def A(r):
        """
        Baseline recomputed LIVE **under production parity**.

        Phase B called resolve_compound_question(transcript) with no detection.
        interview_e2e_loopback forces ComplexityDetection("compound", 0.9, ...)
        for labeled compound packs, so the Phase B baseline skipped the compound
        path entirely on 10 of 15 clips. See V5_MEASUREMENT_PARITY.
        """
        res = live_res(r)
        return list(getattr(res, "selected_intents", None) or [])

    def A_recorded(r):
        """The warm production result, kept only as a reference row."""
        return list((r.get("compound_trace") or {}).get("selected_intents") or [])

    def B(r):
        return [x for x in (accept_first(s) for s in parts_of(r)) if x]

    def C(r):
        out, subs = [], parts_of(r)
        for i, s in enumerate(subs):
            pid = parent_id_for(r, i)
            pe = question_bank.get(pid) if pid else None
            subj = _subject_of(pe.question) if pe else ""
            txt = _PRONOUN.sub(subj, s, count=1) if (subj and i > 0) else s
            got = accept_first(txt)
            if got:
                out.append(got)
        return out

    def D(r):
        out, subs = [], parts_of(r)
        for i, s in enumerate(subs):
            pid = parent_id_for(r, i)
            pe = question_bank.get(pid) if pid else None
            subj = _subject_of(pe.question) if pe else ""
            txt = f"{s.rstrip('?.').strip()} — {subj}?" if (subj and i > 0) else s
            got = accept_first(txt, exclude=pid if i > 0 else None)
            if got:
                out.append(got)
        return out

    def E(r):
        out, subs = [], parts_of(r)
        for i, s in enumerate(subs):
            pid = parent_id_for(r, i)
            pe = question_bank.get(pid) if pid else None
            ctx = f"{pe.topic}" if pe else ""
            got = accept_first(s, exclude=pid if i > 0 else None,
                               topic=ctx or None)
            if got:
                out.append(got)
        return out

    def F(r):
        out = []
        for s in parts_of(r):
            got = accept_first(s)
            if got:
                out.append(got)
        return out

    def G(r):
        """Rewrite each part as a standalone short question using its own action."""
        out = []
        for s in parts_of(r):
            act = _action_word(s)
            txt = s if clause_has_action(s) and act else s
            if act and not re.match(rf"^\s*{_ACTION_PREFIX.get(act,'')}", s, re.I):
                txt = f"{_ACTION_PREFIX.get(act, 'What about')} {s.rstrip('?.').strip()}?"
            got = accept_first(txt)
            if got:
                out.append(got)
        return out

    def I_split(r):
        """Enumeration splitting only."""
        out = []
        for s in parts_of(r):
            frags = split_enumeration(s) or [s]
            for f in frags:
                got = accept_first(f)
                if got:
                    out.append(got)
        return out

    plan = [("A_current_live", A), ("A_recorded_warm_reference", A_recorded), ("B_clause_alone", B), ("C_clause_plus_subject", C),
            ("D_discriminator_plus_subject_excl_parent", D), ("E_compact_parent_context", E),
            ("F_independent_no_carry", F), ("G_standalone_rewrite", G),
            ("I_enumeration_split", I_split)]
    if args.variants:
        want = {v.upper() for v in args.variants}
        plan = [(n, f) for n, f in plan if n.split("_")[0].upper() in want]

    results = []
    for name, fn in plan:
        res = score_variant(name, cases, fn)
        results.append(res)
        print(f"  {name:42} cov_part={res['coverage_by_part']:.4f} hit={res['gold_parts_hit']:2}/"
              f"{res['gold_parts']} wrong={res['wrong_intent']:2} dup={res['duplicates']:2} "
              f"{res['latency_ms_per_clip']:.1f} ms/clip")

    # H and H+I need detect_intent patched, so they run in their own block.
    for label, fn in (("H_action_type_completion", F), ("HI_action_plus_enumeration", I_split)):
        restore = install_v5_detect_intent()
        try:
            res = score_variant(label, cases, fn)
        finally:
            restore()
        results.append(res)
        print(f"  {label:42} cov_part={res['coverage_by_part']:.4f} hit={res['gold_parts_hit']:2}/"
              f"{res['gold_parts']} wrong={res['wrong_intent']:2} dup={res['duplicates']:2} "
              f"{res['latency_ms_per_clip']:.1f} ms/clip")

    base = next((r for r in results if r["variant"] == "A_current_live"), results[0])
    # A runs the FULL pipeline (dedupe, harvest, facet merge); B-I run a plain
    # per-part accept_first over the shared parts. They are therefore not the
    # same amount of machinery. F_independent_no_carry is the null member of the
    # B-I family — the honest within-family baseline. Report both.
    fam = next((r for r in results if r["variant"] == "F_independent_no_carry"), None)
    fam_winners = []
    if fam is not None:
        fam_winners = sorted(
            [r for r in results
             if r["variant"] not in {"A_current_live", "A_recorded_warm_reference",
                                     "F_independent_no_carry"}
             and r["coverage_by_part"] > fam["coverage_by_part"]
             and r["wrong_intent"] <= fam["wrong_intent"]],
            key=lambda r: (-r["coverage_by_part"], r["wrong_intent"]))
    winners = [r for r in results
               if r["variant"] not in {"A_current_live", "A_recorded_warm_reference"}
               and r["coverage_by_part"] > base["coverage_by_part"]
               and r["wrong_intent"] <= base["wrong_intent"]]
    winners.sort(key=lambda r: (-r["coverage_by_part"], r["wrong_intent"]))
    print(f"\n  baseline A coverage {base['coverage_by_part']:.4f}, wrong {base['wrong_intent']}")
    print(f"  variants that BEAT it without raising wrong_intent: "
          f"{[w['variant'] for w in winners] or 'none'}")

    payload = {"created_at": datetime.now(timezone.utc).isoformat(),
               "phase": "V5 Phase B — compound counterfactuals (measurement only)",
               "scope": "telegraphic compound IN SCOPE; coverage gate stays >= 0.90",
               "guard": f"wrong_intent must not exceed baseline ({base['wrong_intent']})",
               "parts_source": PARTS_SOURCE,
               "baseline_definition": ("A_current_live = production-parity forced "
                                       "detection, identical starting condition to "
                                       "every other variant"),
               "supersedes": ("the Phase B run, whose A_current_live baseline "
                              "(coverage 0.1707 / wrong_intent 4) is INVALID — see "
                              "V5_MEASUREMENT_PARITY"),
               "environment": _env_snapshot(),
               "semantic_index_ready": warm,
               "validity": ("warm — absolute numbers are comparable with production"
                            if warm else
                            "COLD — ordering only; absolute coverage is a lower bound"),
               "baseline": base["variant"], "results": results,
               "winners": [w["variant"] for w in winners],
               "within_family_baseline": (fam["variant"] if fam else None),
               "within_family_winners": [w["variant"] for w in fam_winners],
               "machinery_caveat": ("A runs the full compound pipeline; B-I run a "
                                    "per-part accept_first over the shared parts. "
                                    "Compare B-I against F_independent_no_carry."),
               "decision_status": ("PROVISIONAL — warm rerun required before any "
                                   "variant may be called a winner")}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_COMPOUND_COUNTERFACTUALS.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# V5 Phase B — compound counterfactuals", "",
          f"Created: {payload['created_at']}", "",
          "Measurement only. Telegraphic compound is in scope; the 0.90 gate is unchanged.",
          f"Starting condition shared by every variant: `--parts {PARTS_SOURCE}` "
          f"with production-parity forced detection.", "",
          "> Supersedes the Phase B run. That run's `A_current_live` baseline "
          "(0.1707 / wrong_intent 4) is **invalid**: A skipped the compound path "
          "on 10 of 15 clips while B-I were handed the forced decomposition. "
          "See `V5_MEASUREMENT_PARITY`.", "",
          f"Guard: `wrong_intent` must not exceed the baseline ({base['wrong_intent']}).", "",
          ("" if warm else
           "> **Semantic index was COLD for this run.** Variant ordering is valid "
           "(all variants shared conditions) but absolute coverage is a lower bound "
           "and is not comparable with the warm production number.\n"),
          "| variant | coverage (by part) | hit | wrong | dup | ms/clip |",
          "|---|---:|---:|---:|---:|---:|"]
    for r in results:
        md.append(f"| {r['variant']} | {r['coverage_by_part']:.4f} | "
                  f"{r['gold_parts_hit']}/{r['gold_parts']} | {r['wrong_intent']} | "
                  f"{r['duplicates']} | {r['latency_ms_per_clip']:.1f} |")
    md += ["", f"**Beat baseline A (full pipeline) without raising wrong_intent:** "
               f"{', '.join(w['variant'] for w in winners) or 'none'}",
           f"**Beat the within-family null F (per-part matcher) without raising "
           f"wrong_intent:** {', '.join(w['variant'] for w in fam_winners) or 'none'}",
           "", "A runs the full pipeline; B-I run a per-part matcher over the shared "
           "parts. The F comparison is the like-for-like one.",
           "", "**Status: PROVISIONAL.** No variant may be called a winner until this "
           "table is reproduced with `semantic_index_ready=True`.", ""]
    (REPORTS / "V5_COMPOUND_COUNTERFACTUALS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nwrote {REPORTS/'V5_COMPOUND_COUNTERFACTUALS.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
