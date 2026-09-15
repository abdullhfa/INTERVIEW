"""
V5 Phase B4 — residual routing (measurement only).

No app/ changes. Does not invent clip-specific rules. Does not retune ranking
or thresholds. Goal: decide whether expanding routing past R1_min8w (via
guarded R5) is worth a Phase D candidate, or whether the residual gap is now
matching/profile rather than entry.

Order (locked):
  1. R1_min8w is FIXED — already safe and evidenced in B3 warm.
  2. Measure R5 ONLY under the >=2-intent pre-empt guard.
  3. Measure R1 + guarded R5 as one path.
  4. Diagnose fuh4_080 for the missing STRUCTURAL pattern only (no special rule).
  5. Keep evidence grounding; report its trade-off explicitly.

Phase D gate (all must hold for the combo vs B3 candidate):
  - coverage clearly above R1_min8w + evidence 0.4 + I + H projection
  - wrong_intent <= 4
  - newly_broken == 0 (with the >=2-intent guard enforced)

    python scripts/v5_b4_routing_residual.py
Writes reports/V5_B4_ROUTING_RESIDUAL.{md,json}.
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

# B3 warm production-projection candidate — the bar B4 must beat.
B3_CANDIDATE = {
    "label": "R1_min8w + evidence 0.4 + I + H",
    "coverage_by_part": 0.4146,
    "wrong_intent": 4,
}


def _f(x, n=4):
    try:
        return round(float(x), n)
    except Exception:
        return None


def _num(x: Any, default: float = 0.0) -> float:
    """Coerce heterogeneous report values to float for arithmetic."""
    v = _f(x)
    return float(v) if v is not None else default


def _inum(x: Any, default: int = 0) -> int:
    """Coerce heterogeneous report values to int for arithmetic."""
    try:
        if x is None or isinstance(x, bool):
            return default
        return int(x)
    except (TypeError, ValueError):
        return default


# ── shape primitives (identical to B3) ─────────────────────────────────────
_INTERROG = re.compile(
    r"\b(what|why|how|when|which|who|whether|where|is|are|do|does|did|can|should|would)\b", re.I)
_IMPER = re.compile(
    r"\b(explain|tell|say|describe|give|point|walk|cover|name|define|summaris|summariz|list)\b", re.I)
_VERBISH = re.compile(
    r"\b(use|used|build|built|work|works|make|choose|pick|handle|stop|prevent|add|need|"
    r"matter|differ|design|halt|reduce|track|monitor)\b", re.I)
_WH_HEAD = re.compile(
    r"^\s*(what|why|how|when|which|who|where|say|tell|point|name|give|explain|describe)\b", re.I)
_FRAG_SPLIT = re.compile(r",|;|\band\b|\bthen\b|\bplus\b", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.?!])\s+")


def clause_has_action(text: str) -> bool:
    return bool(_INTERROG.search(text) or _IMPER.search(text) or _VERBISH.search(text))


def fragments(text: str) -> list[str]:
    return [p.strip(" .;:?") for p in _FRAG_SPLIT.split(text or "") if p.strip(" .;:?")]


def sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENT_SPLIT.split((text or "").strip()) if p.strip(" .?!")]


def word_count(text: str) -> int:
    return len((text or "").split())


def split_enumeration(text: str) -> list[str]:
    parts = fragments(text)
    if len(parts) < 2:
        return []
    short_verbless = sum(1 for p in parts if len(p.split()) <= 6 and not clause_has_action(p))
    if short_verbless >= max(2, int(0.5 * len(parts))):
        return [p for p in parts if p.split()]
    return []


def r1_verbless_series(text: str) -> bool:
    parts = fragments(text)
    if len(parts) < 2:
        return False
    return sum(1 for p in parts if len(p.split()) <= 6 and not clause_has_action(p)) >= 2


def r5_multi_sentence_request(text: str) -> bool:
    sents = sentences(text)
    if len(sents) < 2:
        return False
    return any(_WH_HEAD.match(s) or clause_has_action(s) for s in sents[1:])


def r1_min8w(text: str) -> bool:
    return r1_verbless_series(text) and word_count(text) >= 8


def r5_min8w(text: str) -> bool:
    return r5_multi_sentence_request(text) and word_count(text) >= 8


def r1_or_r5_min8w(text: str) -> bool:
    return (r1_verbless_series(text) or r5_multi_sentence_request(text)) and word_count(text) >= 8


# Only the residual-routing family under test. R1 is fixed; R5 is the question.
ROUTING = {
    "detector_only": lambda _t: False,
    "R1_min8w": r1_min8w,
    "R5_min8w": r5_min8w,
    "R1_or_R5_min8w": r1_or_r5_min8w,
}


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


def evidence_ratio(sub_question: str, transcript: str) -> float:
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _content_tokens

    q = set(_content_tokens(normalize_for_matching(sub_question or "")))
    t = set(_content_tokens(normalize_for_matching(transcript or "")))
    if not q:
        return 0.0
    return len(q & t) / len(q)


def evidence_ok(sub_question: str, transcript: str, theta: float | None) -> bool:
    if theta is None:
        return True
    return evidence_ratio(sub_question, transcript) >= theta


def load_rows() -> tuple[list[dict], list[dict]]:
    rep = json.loads(V4.read_text(encoding="utf-8"))
    rows = [r for r in rep["results"] if not str(r.get("notes") or "").startswith("warmup:")]
    comp = [r for r in rows if (r.get("question_type_label") or "") == "compound"]
    other = [r for r in rows
             if (r.get("question_type_label") or "") != "compound" and r.get("expected_intent_ids")]
    return comp, other


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


def accept_first(text: str):
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank

    tops = question_bank.top_matches(text, top_k=6)
    m = tops[0] if tops else None
    ok, _reason, _margin = _accept_match(m) if m else (False, "", 0.0)
    return m.entry.id if (m and ok) else None


def score(rows: list[dict], picker) -> dict:
    hit = wrong = total = 0
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
        per_clip.append({
            "clip": r["sample_id"], "gold": gold, "selected": uniq,
            "hit": got, "wrong": bad,
            "coverage": _f(len(got) / max(1, len(gold))),
        })
    return {
        "gold_parts": total,
        "gold_parts_hit": hit,
        "coverage_by_part": _f(hit / max(1, total)),
        "wrong_intent": wrong,
        "per_clip": per_clip,
    }


def diagnose_080(row: dict | None) -> dict:
    """Structural autopsy only — never proposes a clip-id rule."""
    if row is None:
        return {"clip": "fuh4_080", "error": "clip not found in v4 compound cohort"}
    from app.services.compound_question_detector import detect_question_complexity

    tr = row.get("transcript") or ""
    det = detect_question_complexity(tr)
    frags = fragments(tr)
    sents = sentences(tr)
    return {
        "clip": "fuh4_080",
        "purpose": "diagnose the missing STRUCTURAL pattern; do not write a special rule",
        "transcript": tr,
        "detector_type": getattr(det, "question_type", None),
        "detector_signals": list(getattr(det, "signals", []) or []),
        "word_count": word_count(tr),
        "fragment_split_on_comma_and_then": frags,
        "fragment_count": len(frags),
        "sentence_split_on_period": sents,
        "sentence_count": len(sents),
        "whole_has_action_cue": clause_has_action(tr),
        "per_fragment_action_cue": [
            {"fragment": f, "has_action_cue": clause_has_action(f), "words": len(f.split())}
            for f in frags
        ],
        "per_sentence_action_or_wh": [
            {
                "sentence": s,
                "wh_or_request_head": bool(_WH_HEAD.match(s)),
                "has_action_cue": clause_has_action(s),
                "words": len(s.split()),
            }
            for s in sents
        ],
        "R1_min8w": r1_min8w(tr),
        "R5_min8w": r5_min8w(tr),
        "R1_or_R5_min8w": r1_or_r5_min8w(tr),
        "why_R1_misses": (
            "needs >=2 short verbless fragments under comma/and/then split"
            if len(frags) < 2
            else "fragments exist but short-verbless count < 2"
            if sum(1 for p in frags if len(p.split()) <= 6 and not clause_has_action(p)) < 2
            else "word floor"
            if word_count(tr) < 8
            else "unexpected — R1 should fire"
        ),
        "why_R5_misses": (
            "needs >=2 sentences under [.?!] split"
            if len(sents) < 2
            else "non-first sentence has neither WH/request head nor action cue"
            if not any(_WH_HEAD.match(s) or clause_has_action(s) for s in sents[1:])
            else "word floor"
            if word_count(tr) < 8
            else "unexpected — R5 should fire"
        ),
        "structural_hypothesis": (
            "Likely a single orthographic sentence / single detector fragment that packs "
            "two asks without a comma/and/then OR a sentence boundary the current R5 sees. "
            "Missing family is probably 'juxtaposed asks without list punctuation' "
            "(e.g. colon, em-dash, bare apposition, or soft conjunction the splitter ignores), "
            "not a vocabulary gap."
        ),
    }


def main() -> int:
    if not V4.is_file():
        print(f"missing {V4}")
        return 1

    from app.services.compound_question_detector import detect_question_complexity
    from app.services.question_bank import question_bank
    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()
    from app.services.semantic_intent_index import semantic_intent_index

    warm = semantic_intent_index.ready
    comp, other = load_rows()
    print(f"compound={len(comp)}  non_compound_with_gold={len(other)}  "
          f"semantic_index_ready={warm}")

    blocked = []
    for r in comp:
        tr = r.get("transcript") or ""
        det = detect_question_complexity(tr)
        if det.question_type != "single":
            continue
        blocked.append(r)
    blocked_ids = {r["sample_id"] for r in blocked}
    print(f"blocked (detector=single): {len(blocked)}")

    # ── Step 1–3: routing family under the >=2-intent guard ───────────────
    routing_rows = []
    for name, fn in ROUTING.items():
        recovered = [
            r["sample_id"] for r in blocked if fn(r.get("transcript") or "")
        ]
        opened_nc = [
            r["sample_id"] for r in other
            if detect_question_complexity(r.get("transcript") or "").question_type == "single"
            and fn(r.get("transcript") or "")
        ]
        # Blast with the guard ALWAYS treated as the shipping rule.
        newly_broken = 0
        newly_broken_unguarded = 0
        preempted = 0
        details = []
        for r in other:
            if r["sample_id"] not in opened_nc:
                continue
            res = forced_resolution(r.get("transcript") or "")
            if res is None or not res.used_compound_path or not (res.answer_en or ""):
                continue
            sel = list(res.selected_intents or [])
            gold = list(r.get("expected_intent_ids") or [])
            if not sel:
                continue
            multi = len(sel) >= 2
            preempted += 1
            gold_lost = not (set(gold) & set(sel)) and set(sel) != set(gold)
            # tighter: gold absent from selection
            gold_absent = bool(gold) and not (set(gold) & set(sel))
            was_ok = bool(r.get("intent_ok"))
            if gold_absent and was_ok:
                newly_broken_unguarded += 1
                if multi:
                    newly_broken += 1
            details.append({
                "clip": r["sample_id"],
                "label": r.get("question_type_label"),
                "selected_count": len(sel),
                "gold": gold,
                "selected": sel,
                "gold_absent": gold_absent,
                "was_intent_ok_in_v4": was_ok,
                "blocked_by_multi_intent_guard": not multi,
            })
        still_blocked = sorted(blocked_ids - set(recovered))
        row = {
            "routing": name,
            "telegraphic_recovered": len(recovered),
            "telegraphic_recovered_of": len(blocked),
            "telegraphic_clips": recovered,
            "still_blocked_clips": still_blocked,
            "non_compound_opened": len(opened_nc),
            "non_compound_of": len(other),
            "non_compound_clips": opened_nc,
            "preempted": preempted,
            "newly_broken_unguarded": newly_broken_unguarded,
            "newly_broken_with_ge2_intent_guard": newly_broken,
            "blast_details": details,
        }
        routing_rows.append(row)
        print(
            f"  {name:18} recovered {len(recovered):2}/{len(blocked)}  "
            f"opens_nc {len(opened_nc):3}/{len(other)}  "
            f"newly_broken_unguarded={newly_broken_unguarded}  "
            f"newly_broken_GUARDED={newly_broken}  "
            f"still_out={still_blocked}"
        )

    # ── Step 4: fuh4_080 structural diagnosis only ────────────────────────
    row_080 = next((r for r in comp if r.get("sample_id") == "fuh4_080"), None)
    diag_080 = diagnose_080(row_080)
    print("\n--- fuh4_080 structural diagnosis ---")
    print(f"  transcript: {diag_080.get('transcript')!r}")
    print(f"  frags={diag_080.get('fragment_count')} sents={diag_080.get('sentence_count')} "
          f"R1={diag_080.get('R1_min8w')} R5={diag_080.get('R5_min8w')}")
    print(f"  why_R1: {diag_080.get('why_R1_misses')}")
    print(f"  why_R5: {diag_080.get('why_R5_misses')}")

    # ── Step 5: evidence trade-off (forced path) + production projections ─
    def parts_for(r, theta: float | None):
        tr = r.get("transcript") or ""
        res = forced_resolution(tr)
        subs = list(getattr(res, "sub_questions", None) or [])
        return [s for s in subs if evidence_ok(s, tr, theta)]

    def make_forced_picker(*, theta, split, action_rules):
        def picker(r):
            out = []
            tr = r.get("transcript") or ""
            for s in parts_for(r, theta):
                frags = (split_enumeration(s) or [s]) if split else [s]
                for frag in frags:
                    if not evidence_ok(frag, tr, theta):
                        continue
                    got = accept_first(frag)
                    if got:
                        out.append(got)
            return out

        return picker

    def single_path_intent(r):
        m = question_bank.match(r.get("transcript") or "")
        return [m.entry.id] if m is not None else []

    def make_proj_picker(*, route_fn, theta, split):
        """Production projection: rule opens path; >=2 intents or fall back to single."""
        def picker(r):
            tr = r.get("transcript") or ""
            opened = (
                detect_question_complexity(tr).question_type != "single" or route_fn(tr)
            )
            if not opened:
                return single_path_intent(r)
            out = []
            for sub in parts_for(r, theta):
                frags = (split_enumeration(sub) or [sub]) if split else [sub]
                for frag in frags:
                    if not evidence_ok(frag, tr, theta):
                        continue
                    got = accept_first(frag)
                    if got:
                        out.append(got)
            return out if len(out) >= 2 else single_path_intent(r)

        return picker

    evidence_tradeoff = []
    for theta, split, action in (
        (None, False, False),
        (None, True, True),
        (0.4, True, True),
        (0.4, False, False),
    ):
        restore = install_v5_detect_intent() if action else None
        try:
            res = score(comp, make_forced_picker(theta=theta, split=split, action_rules=action))
        finally:
            if restore:
                restore()
        label = (
            f"forced | evidence={'off' if theta is None else theta} | "
            f"split={'I' if split else '-'} | action={'H' if action else '-'}"
        )
        evidence_tradeoff.append({
            "config": label, "theta": theta, "split": split, "action": action,
            "path": "forced_all_15",
            "coverage_by_part": res["coverage_by_part"],
            "gold_parts_hit": res["gold_parts_hit"],
            "gold_parts": res["gold_parts"],
            "wrong_intent": res["wrong_intent"],
        })
        print(f"  {label:70} cov={res['coverage_by_part']} "
              f"hit={res['gold_parts_hit']}/{res['gold_parts']} wrong={res['wrong_intent']}")

    # Delta callout the user asked for.
    off_ih = next(e for e in evidence_tradeoff if e["theta"] is None and e["split"] and e["action"])
    on_ih = next(e for e in evidence_tradeoff if e["theta"] == 0.4 and e["split"] and e["action"])
    evidence_delta = {
        "from": off_ih["config"],
        "to": on_ih["config"],
        "coverage_delta": _f(_num(on_ih.get("coverage_by_part")) - _num(off_ih.get("coverage_by_part"))),
        "wrong_delta": _inum(on_ih.get("wrong_intent")) - _inum(off_ih.get("wrong_intent")),
        "note": "evidence 0.4 on forced path: halves/cuts wrong at a coverage cost",
    }
    print(f"\n  EVIDENCE TRADE-OFF (forced I+H): "
          f"cov {off_ih['coverage_by_part']} -> {on_ih['coverage_by_part']} "
          f"(delta {evidence_delta['coverage_delta']}); "
          f"wrong {off_ih['wrong_intent']} -> {on_ih['wrong_intent']} "
          f"(delta {evidence_delta['wrong_delta']})")

    projections = []
    for route_name, route_fn in ROUTING.items():
        for theta, split, action in (
            (None, False, False),
            (None, True, True),
            (0.4, True, True),
        ):
            restore = install_v5_detect_intent() if action else None
            try:
                res = score(
                    comp,
                    make_proj_picker(route_fn=route_fn, theta=theta, split=split),
                )
            finally:
                if restore:
                    restore()
            # Recovered under this routing (entry only; independent of I/H).
            recovered_n = next(
                r["telegraphic_recovered"] for r in routing_rows if r["routing"] == route_name
            )
            newly_broken = next(
                r["newly_broken_with_ge2_intent_guard"]
                for r in routing_rows if r["routing"] == route_name
            )
            opened_nc = next(
                r["non_compound_opened"] for r in routing_rows if r["routing"] == route_name
            )
            label = (
                f"PROJ {route_name} | evidence={'off' if theta is None else theta} | "
                f"split={'I' if split else '-'} | action={'H' if action else '-'} | "
                f"guard=ge2"
            )
            row = {
                "config": label,
                "routing": route_name,
                "theta": theta,
                "split": split,
                "action": action,
                "telegraphic_recovered": recovered_n,
                "telegraphic_of": len(blocked),
                "non_compound_opened": opened_nc,
                "newly_broken_with_ge2_intent_guard": newly_broken,
                "coverage_by_part": res["coverage_by_part"],
                "gold_parts_hit": res["gold_parts_hit"],
                "gold_parts": res["gold_parts"],
                "wrong_intent": res["wrong_intent"],
                "per_clip": res["per_clip"],
            }
            projections.append(row)
            print(
                f"  {label:78} cov={res['coverage_by_part']} "
                f"hit={res['gold_parts_hit']}/{res['gold_parts']} "
                f"wrong={res['wrong_intent']} recovered={recovered_n}/{len(blocked)} "
                f"newly_broken={newly_broken}"
            )

    # ── Decision ──────────────────────────────────────────────────────────
    b3 = next(
        p for p in projections
        if p["routing"] == "R1_min8w" and p["theta"] == 0.4 and p["split"] and p["action"]
    )
    combo = next(
        p for p in projections
        if p["routing"] == "R1_or_R5_min8w" and p["theta"] == 0.4 and p["split"] and p["action"]
    )
    cov_gain = _f(_num(combo.get("coverage_by_part")) - _num(b3.get("coverage_by_part")))
    material = (cov_gain or 0) >= 0.02  # ~+1 gold part on 41; tangible, not noise
    phase_d = (
        material
        and _inum(combo.get("wrong_intent")) <= 4
        and _inum(combo.get("newly_broken_with_ge2_intent_guard")) == 0
    )
    decision = {
        "b3_candidate_measured_here": {
            "config": b3["config"],
            "coverage_by_part": b3["coverage_by_part"],
            "wrong_intent": b3["wrong_intent"],
            "newly_broken": b3["newly_broken_with_ge2_intent_guard"],
            "telegraphic_recovered": b3["telegraphic_recovered"],
        },
        "b4_combo_r1_guarded_r5": {
            "config": combo["config"],
            "coverage_by_part": combo["coverage_by_part"],
            "wrong_intent": combo["wrong_intent"],
            "newly_broken": combo["newly_broken_with_ge2_intent_guard"],
            "telegraphic_recovered": combo["telegraphic_recovered"],
            "coverage_gain_vs_b3": cov_gain,
        },
        "phase_d_gate": {
            "material_coverage_gain_ge_0.02": material,
            "wrong_le_4": combo["wrong_intent"] <= 4,
            "newly_broken_eq_0": combo["newly_broken_with_ge2_intent_guard"] == 0,
            "all_pass": phase_d,
        },
        "verdict": (
            "PHASE_D_CANDIDATE — R1 + guarded R5 + evidence + I/H clears the B4 gate"
            if phase_d
            else "STOP_EXPANDING_ROUTING — residual is matching/profile, not entry; "
                 "do not add more shape rules before analysing remaining misses"
        ),
    }
    print(f"\n=== B4 VERDICT: {decision['verdict']} ===")
    print(f"  B3 bar:  cov={b3['coverage_by_part']} wrong={b3['wrong_intent']} "
          f"recovered={b3['telegraphic_recovered']}")
    print(f"  B4 combo: cov={combo['coverage_by_part']} wrong={combo['wrong_intent']} "
          f"recovered={combo['telegraphic_recovered']} gain={cov_gain}")

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "V5 Phase B4 — residual routing (measurement only)",
        "scope": "no app/ changes; no ranking/threshold retune; no clip-specific rules",
        "semantic_index_ready": warm,
        "validity": "warm" if warm else "COLD — ordering only",
        "b3_reference_candidate": B3_CANDIDATE,
        "blocked_count": len(blocked),
        "routing_family": routing_rows,
        "fuh4_080_structural_diagnosis": diag_080,
        "evidence_tradeoff_forced": evidence_tradeoff,
        "evidence_delta_forced_ih": evidence_delta,
        "production_projections": projections,
        "decision": decision,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_B4_ROUTING_RESIDUAL.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        "# V5 Phase B4 — residual routing",
        "",
        f"Created: {payload['created_at']}",
        f"`semantic_index_ready={warm}` — {payload['validity']}",
        "",
        "Measurement only. No `app/` file modified. No ranking/threshold changes.",
        "R1_min8w is fixed. Question under test: does guarded R5 buy enough entry?",
        "",
        "## Routing family (guard = ≥2 accepted intents before pre-empt)",
        "",
        "| routing | telegraphic recovered | still blocked | opens non-compound | newly_broken unguarded | newly_broken GUARDED |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for r in routing_rows:
        md.append(
            f"| {r['routing']} | {r['telegraphic_recovered']}/{r['telegraphic_recovered_of']} | "
            f"{', '.join(r['still_blocked_clips']) or '—'} | "
            f"{r['non_compound_opened']}/{r['non_compound_of']} | "
            f"{r['newly_broken_unguarded']} | "
            f"**{r['newly_broken_with_ge2_intent_guard']}** |"
        )

    md += [
        "",
        "## fuh4_080 — structural diagnosis only (no special rule)",
        "",
        f"- transcript: `{diag_080.get('transcript')}`",
        f"- fragments (comma/and/then): {diag_080.get('fragment_count')} → "
        f"`{diag_080.get('fragment_split_on_comma_and_then')}`",
        f"- sentences ([.?!]): {diag_080.get('sentence_count')} → "
        f"`{diag_080.get('sentence_split_on_period')}`",
        f"- R1_min8w={diag_080.get('R1_min8w')} — {diag_080.get('why_R1_misses')}",
        f"- R5_min8w={diag_080.get('R5_min8w')} — {diag_080.get('why_R5_misses')}",
        f"- hypothesis: {diag_080.get('structural_hypothesis')}",
        "",
        "## Evidence trade-off (forced path on all 15)",
        "",
        "| config | coverage | hit | wrong |",
        "|---|---:|---:|---:|",
    ]
    for e in evidence_tradeoff:
        md.append(
            f"| {e['config']} | {e['coverage_by_part']} | "
            f"{e['gold_parts_hit']}/{e['gold_parts']} | {e['wrong_intent']} |"
        )
    md += [
        "",
        f"**Forced I+H delta with evidence 0.4:** coverage "
        f"{off_ih['coverage_by_part']} → {on_ih['coverage_by_part']} "
        f"({evidence_delta['coverage_delta']}); wrong "
        f"{off_ih['wrong_intent']} → {on_ih['wrong_intent']} "
        f"({evidence_delta['wrong_delta']:+d}).",
        "",
        "## Production projection (entry rule + ≥2-intent guard + optional evidence/I/H)",
        "",
        "| config | recovered | opens NC | newly_broken | coverage | hit | wrong |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for p in projections:
        md.append(
            f"| {p['config']} | {p['telegraphic_recovered']}/{p['telegraphic_of']} | "
            f"{p['non_compound_opened']} | {p['newly_broken_with_ge2_intent_guard']} | "
            f"{p['coverage_by_part']} | {p['gold_parts_hit']}/{p['gold_parts']} | "
            f"{p['wrong_intent']} |"
        )
    md += [
        "",
        "## Decision",
        "",
        f"- B3 bar (re-measured): cov={b3['coverage_by_part']} wrong={b3['wrong_intent']} "
        f"recovered={b3['telegraphic_recovered']}/{len(blocked)}",
        f"- B4 combo R1+guarded R5+evidence0.4+I/H: cov={combo['coverage_by_part']} "
        f"wrong={combo['wrong_intent']} recovered={combo['telegraphic_recovered']}/{len(blocked)} "
        f"gain={cov_gain}",
        f"- Gate: material_gain≥0.02={material}; wrong≤4="
        f"{combo['wrong_intent'] <= 4}; newly_broken=0="
        f"{combo['newly_broken_with_ge2_intent_guard'] == 0}",
        "",
        f"**VERDICT: {decision['verdict']}**",
        "",
    ]
    (REPORTS / "V5_B4_ROUTING_RESIDUAL.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nwrote {REPORTS / 'V5_B4_ROUTING_RESIDUAL.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
