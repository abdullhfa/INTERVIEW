"""
V5 Phase B2 — MEASUREMENT PARITY. MEASUREMENT ONLY. NO PRODUCTION CODE CHANGES.

Question this script answers, and nothing else:

    Why does `A_current_live` (0.1707) not reproduce `A_recorded_warm_reference`
    (0.3659) on the same 15 compound clips, even though semantic_index_ready=True?

It compares, per clip and per fragment:
    detection -> decomposition -> candidate pool -> cosine/lexical components
    -> accept decision -> selected intents
against what the v4 run actually recorded, and reports the FIRST stage where
the two diverge.

Three live re-runs are scored side by side:
    live_bare          resolve_compound_question(transcript)                      <- what variant A did
    live_prod_parity   the exact forced-detection path in interview_e2e_loopback  <- what v4 actually ran
    recorded           the v4 trace itself                                        <- ground truth

    python scripts/v5_measurement_parity.py
Writes reports/V5_MEASUREMENT_PARITY.{md,json}.
"""

from __future__ import annotations

import json
import os
import sys
import time
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


def load_cases() -> list[dict]:
    rep = json.loads(V4.read_text(encoding="utf-8"))
    rows = [r for r in rep["results"] if not str(r.get("notes") or "").startswith("warmup:")]
    return [r for r in rows if (r.get("question_type_label") or "") == "compound"]


def env_snapshot() -> dict:
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_index import semantic_intent_index

    qb = question_bank
    idx = getattr(qb, "_index", None)
    alias_matrix = getattr(idx, "alias_matrix", None) if idx is not None else None
    snap = {
        "semantic_index_ready": bool(getattr(semantic_intent_index, "ready", False)),
        "alias_matrix_present": alias_matrix is not None,
        "alias_matrix_rows": int(getattr(alias_matrix, "shape", (0,))[0]) if alias_matrix is not None else 0,
        "bank_entries": len(getattr(idx, "entries", []) or []) if idx is not None else 0,
        "bank_generation": int(getattr(qb, "generation", -1) or -1),
        "env": {
            k: os.getenv(k)
            for k in (
                "SEMANTIC_BLOB_PROXY",
                "QB_FAST_LEXICAL",
                "E2E_WARM_TIMEOUT_S",
                "INTENT_SEMANTIC_MODEL",
                "SEMANTIC_INTENT_RECOVERY",
            )
        },
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


def detection_dict(d) -> dict:
    if d is None:
        return {"question_type": None}
    return {
        "question_type": d.question_type,
        "confidence": _f(d.confidence),
        "request_count_estimate": int(d.request_count_estimate),
        "signals": list(d.signals),
    }


def resolution_dict(res) -> dict:
    if res is None:
        return {}
    return {
        "question_type": res.question_type,
        "compound_confidence": _f(res.compound_confidence),
        "request_count_estimate": int(res.request_count_estimate or 0),
        "used_compound_path": bool(res.used_compound_path),
        "detection_signals": list(res.detection_signals or []),
        "sub_questions": list(res.sub_questions or []),
        "decomposition_notes": list(res.decomposition_notes or []),
        "selected_intents": list(res.selected_intents or []),
        "dropped_intents": list(res.dropped_intents or []),
        "duplicate_intents": list(res.duplicate_intents or []),
        "unknown_parts": list(res.unknown_parts or []),
        "candidate_intents": [
            {
                "sub_question": c.get("sub_question"),
                "intent_id": c.get("intent_id"),
                "score": _f(c.get("score")),
                "mode": c.get("mode"),
                "runner_up": c.get("runner_up"),
                "margin": _f(c.get("margin")),
                "accepted": c.get("accepted"),
                "drop_reason": c.get("drop_reason"),
                "fast_lexical": c.get("fast_lexical"),
                "semantic_triggered": c.get("semantic_triggered"),
            }
            for c in (res.candidate_intents or [])
        ],
        "final_coverage": _f(res.final_coverage),
        "failure_code": getattr(res, "failure_code", None),
    }


def run_live(transcript: str, *, labeled_compound: bool) -> dict:
    """Reproduce interview_e2e_loopback.run_clip's compound call exactly."""
    from app.services.compound_question_detector import (
        ComplexityDetection,
        detect_question_complexity,
    )
    from app.services.compound_question_pipeline import resolve_compound_question

    detection = detect_question_complexity(transcript) if transcript.strip() else None
    forced = False
    force_det = detection
    if labeled_compound and (detection is None or detection.question_type == "single"):
        force_det = ComplexityDetection(
            "compound",
            0.9,
            max(2, int(getattr(detection, "request_count_estimate", 1) or 1)),
            ("labeled_compound_pack",),
        )
        forced = True
    res = None
    if transcript.strip() and (
        labeled_compound or (detection is not None and detection.question_type != "single")
    ):
        res = resolve_compound_question(
            transcript, conversation_history=None, detection=force_det
        )
    return {
        "detector_says": detection_dict(detection),
        "detection_forced": forced,
        "detection_used": detection_dict(force_det),
        "resolution": resolution_dict(res),
    }


def candidate_pool(text: str, top_k: int = 6) -> list[dict]:
    """Full component breakdown for one fragment — the 'cosine scores' evidence."""
    from app.services.compound_question_pipeline import _accept_match
    from app.services.question_bank import question_bank

    out = []
    for m in question_bank.top_matches(text, top_k=top_k):
        ok, reason, margin = _accept_match(m)
        out.append(
            {
                "intent_id": m.entry.id,
                "score": _f(m.score),
                "semantic": _f(m.semantic),
                "lexical": _f(m.lexical),
                "keyword": _f(m.keyword),
                "mode": m.mode,
                "alias": m.alias,
                "runner_up": m.runner_up,
                "runner_up_score": _f(m.runner_up_score),
                "accept": bool(ok),
                "drop_reason": reason,
                "margin": _f(margin),
            }
        )
    return out


def score_selection(cases: list[dict], picker) -> dict:
    hit = wrong = 0
    total = 0
    per_clip = []
    for r in cases:
        gold = list(r.get("expected_intent_ids") or [])
        total += len(gold)
        sel, seen, uniq = picker(r), set(), []
        for s in sel:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        got = sorted({s for s in uniq if s in gold})
        bad = [s for s in uniq if s not in gold]
        hit += len(got)
        wrong += len(bad)
        per_clip.append(
            {
                "clip": r["sample_id"],
                "gold": gold,
                "selected": uniq,
                "hit": got,
                "wrong": bad,
                "coverage": _f(len(got) / max(1, len(gold))),
            }
        )
    return {
        "gold_parts": total,
        "gold_parts_hit": hit,
        "coverage_by_part": _f(hit / max(1, total)),
        "wrong_intent": wrong,
        "per_clip": per_clip,
    }


DIVERGENCE_ORDER = [
    "DETECTION",
    "DECOMPOSITION",
    "CANDIDATE_POOL",
    "ACCEPT_DECISION",
    "SELECTION",
    "NONE",
]


def first_divergence(rec: dict, live: dict, *, use_forced: bool = False) -> tuple[str, str]:
    """
    use_forced=False -> compare against what the bare detector concluded
                        (this is the stage that broke variant A).
    use_forced=True  -> compare against the detection actually fed to the
                        pipeline, i.e. after the labeled-pack force. Any
                        divergence reported then is a REAL runtime difference,
                        not a harness artefact.
    """
    lres = live.get("resolution") or {}
    rec_type = rec.get("question_type")
    key = "detection_used" if use_forced else "detector_says"
    live_type = (live.get(key) or {}).get("question_type")
    if rec_type != live_type:
        return "DETECTION", f"recorded={rec_type} live_detector={live_type}"
    rec_subs = list(rec.get("sub_questions") or [])
    live_subs = list(lres.get("sub_questions") or [])
    if rec_subs != live_subs:
        return "DECOMPOSITION", f"recorded={rec_subs} live={live_subs}"
    rec_c = {c.get("sub_question"): c for c in (rec.get("candidate_intents") or [])}
    live_c = {c.get("sub_question"): c for c in (lres.get("candidate_intents") or [])}
    for sub in rec_subs:
        rc, lc = rec_c.get(sub), live_c.get(sub)
        if (rc is None) != (lc is None):
            return "CANDIDATE_POOL", f"{sub!r}: recorded={bool(rc)} live={bool(lc)}"
        if rc is None:
            continue
        if rc.get("intent_id") != lc.get("intent_id"):
            return (
                "CANDIDATE_POOL",
                f"{sub!r}: recorded={rc.get('intent_id')}@{_f(rc.get('score'))} "
                f"live={lc.get('intent_id')}@{_f(lc.get('score'))}",
            )
        if bool(rc.get("accepted")) != bool(lc.get("accepted")):
            return (
                "ACCEPT_DECISION",
                f"{sub!r}: recorded_accept={rc.get('accepted')} live_accept={lc.get('accepted')} "
                f"live_reason={lc.get('drop_reason')}",
            )
    if list(rec.get("selected_intents") or []) != list(lres.get("selected_intents") or []):
        return (
            "SELECTION",
            f"recorded={rec.get('selected_intents')} live={lres.get('selected_intents')}",
        )
    return "NONE", ""


def main() -> int:
    if not V4.is_file():
        print(f"missing {V4}")
        return 1

    from app.services.warm_start import warm_system_blocking

    t0 = time.perf_counter()
    warm_system_blocking()
    env = env_snapshot()
    warm_ms = (time.perf_counter() - t0) * 1000
    print(f"warm in {warm_ms:.0f}ms  semantic_index_ready={env['semantic_index_ready']} "
          f"alias_matrix={env['alias_matrix_present']}")

    cases = load_cases()
    print(f"compound clips: {len(cases)}")

    clips = []
    for r in cases:
        tr = r.get("transcript") or ""
        rec = dict(r.get("compound_trace") or {})
        bare = run_live(tr, labeled_compound=False)
        prod = run_live(tr, labeled_compound=True)
        stage_bare, detail_bare = first_divergence(rec, bare)
        stage_prod, detail_prod = first_divergence(rec, prod, use_forced=True)
        pools = {}
        for sub in list(rec.get("sub_questions") or []):
            pools[sub] = candidate_pool(sub)
        clips.append(
            {
                "clip": r["sample_id"],
                "transcript": tr,
                "gold": list(r.get("expected_intent_ids") or []),
                "recorded": {
                    "question_type": rec.get("question_type"),
                    "compound_confidence": _f(rec.get("compound_confidence")),
                    "request_count_estimate": rec.get("request_count_estimate"),
                    "detection_signals": list(rec.get("detection_signals") or []),
                    "used_compound_path": rec.get("used_compound_path"),
                    "sub_questions": list(rec.get("sub_questions") or []),
                    "decomposition_notes": list(rec.get("decomposition_notes") or []),
                    "candidate_intents": rec.get("candidate_intents") or [],
                    "selected_intents": list(rec.get("selected_intents") or []),
                    "dropped_intents": list(rec.get("dropped_intents") or []),
                    "unknown_parts": list(rec.get("unknown_parts") or []),
                    "final_coverage": _f(rec.get("final_coverage")),
                    "failure_code": rec.get("failure_code"),
                },
                "live_bare": bare,
                "live_prod_parity": prod,
                "first_divergence_bare": {"stage": stage_bare, "detail": detail_bare},
                "first_divergence_prod": {"stage": stage_prod, "detail": detail_prod},
                "live_candidate_pool_by_recorded_fragment": pools,
            }
        )

    by_clip = {c["clip"]: c for c in clips}
    scores = {
        "recorded": score_selection(
            cases, lambda r: list((r.get("compound_trace") or {}).get("selected_intents") or [])
        ),
        "live_bare": score_selection(
            cases,
            lambda r: list(
                ((by_clip[r["sample_id"]]["live_bare"].get("resolution") or {}).get("selected_intents"))
                or []
            ),
        ),
        "live_prod_parity": score_selection(
            cases,
            lambda r: list(
                (
                    (by_clip[r["sample_id"]]["live_prod_parity"].get("resolution") or {}).get(
                        "selected_intents"
                    )
                )
                or []
            ),
        ),
    }

    def tally(key):
        out = {}
        for c in clips:
            out[c[key]["stage"]] = out.get(c[key]["stage"], 0) + 1
        return {k: out.get(k, 0) for k in DIVERGENCE_ORDER if out.get(k)}

    stage_bare_tally = tally("first_divergence_bare")
    stage_prod_tally = tally("first_divergence_prod")

    prod_matches_recorded = sum(
        1 for c in clips if c["first_divergence_prod"]["stage"] == "NONE"
    )
    cov_rec = scores["recorded"]["coverage_by_part"]
    cov_bare = scores["live_bare"]["coverage_by_part"]
    cov_prod = scores["live_prod_parity"]["coverage_by_part"]

    # --- verdict -------------------------------------------------------
    # Two independent questions, answered separately:
    #   1. what caused the 0.1707 vs 0.3659 coverage gap?
    #   2. is there any residual live-vs-recorded difference left after that?
    gap_total = (cov_rec or 0.0) - (cov_bare or 0.0)
    gap_closed = (cov_prod or 0.0) - (cov_bare or 0.0)
    gap_closed_pct = _f(100.0 * gap_closed / gap_total, 1) if gap_total else None
    detection_only_clips = [
        c["clip"] for c in clips if c["first_divergence_bare"]["stage"] == "DETECTION"
    ]
    residual_clips = [
        {
            "clip": c["clip"],
            "stage": c["first_divergence_prod"]["stage"],
            "detail": c["first_divergence_prod"]["detail"],
            "recorded_selected": c["recorded"]["selected_intents"],
            "live_selected": (c["live_prod_parity"].get("resolution") or {}).get(
                "selected_intents"
            ),
        }
        for c in clips
        if c["first_divergence_prod"]["stage"] != "NONE"
    ]
    coverage_cause = (
        "HARNESS_MISMATCH_FORCED_DETECTION"
        if gap_closed_pct is not None and gap_closed_pct >= 95.0
        else "NOT_EXPLAINED_BY_FORCED_DETECTION"
    )
    if not residual_clips:
        residual = "NONE_LIVE_REPRODUCES_RECORDED_EXACTLY"
    elif (
        scores["live_prod_parity"]["wrong_intent"] <= scores["recorded"]["wrong_intent"]
        and abs((cov_prod or 0) - (cov_rec or 0)) <= 1.0 / max(1, scores["recorded"]["gold_parts"])
    ):
        residual = "PRESENT_BUT_AGGREGATE_NEUTRAL"
    else:
        residual = "PRESENT_AND_AGGREGATE_MATERIAL"
    verdict = f"coverage_gap={coverage_cause}; residual={residual}"
    baseline_status = {
        "previous_A_current_live_baseline": "INVALID",
        "reason": (
            "variant A called resolve_compound_question() with no detection, so the "
            "bare detector classified {} of {} labeled-compound clips as SINGLE and the "
            "pipeline returned immediately with used_compound_path=False and no selected "
            "intents. The v4 production harness forces "
            "ComplexityDetection('compound', 0.9, ...) for labeled compound packs. "
            "Variants B-I were additionally fed the RECORDED sub_questions, i.e. the "
            "output of that forced decomposition, so A and B-I never shared a starting "
            "condition."
        ).format(len(detection_only_clips), len(clips)),
        "invalidated_numbers": [
            "A_current_live coverage_by_part",
            "A_current_live wrong_intent (the Phase B guard baseline)",
            "every A-vs-variant delta in V5_COMPOUND_COUNTERFACTUALS",
        ],
    }

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "V5 Phase B2 — measurement parity",
        "scope": "measurement only; no production code touched",
        "environment": env,
        "warm_ms": _f(warm_ms, 1),
        "clip_count": len(clips),
        "scores": scores,
        "first_divergence_tally_bare": stage_bare_tally,
        "first_divergence_tally_prod_parity": stage_prod_tally,
        "clips_where_prod_parity_reproduces_recorded_exactly": prod_matches_recorded,
        "verdict": verdict,
        "coverage_gap_cause": coverage_cause,
        "coverage_gap_closed_pct_by_forced_detection": gap_closed_pct,
        "residual_difference": residual,
        "residual_clips": residual_clips,
        "detection_broken_clips": detection_only_clips,
        "baseline_status": baseline_status,
        "clips": clips,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_MEASUREMENT_PARITY.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# V5_MEASUREMENT_PARITY",
        "",
        f"- generated: {payload['created_at']}",
        f"- semantic_index_ready: **{env['semantic_index_ready']}**   alias_matrix: **{env['alias_matrix_present']}** ({env['alias_matrix_rows']} rows)",
        f"- compound clips: {len(clips)}",
        "",
        "## Coverage on the identical 15 clips",
        "",
        "| run | gold parts hit | coverage_by_part | wrong_intent |",
        "|---|---|---|---|",
    ]
    for k in ("recorded", "live_prod_parity", "live_bare"):
        s = scores[k]
        lines.append(
            f"| {k} | {s['gold_parts_hit']}/{s['gold_parts']} | {s['coverage_by_part']} | {s['wrong_intent']} |"
        )
    lines += [
        "",
        "## First divergence vs the recorded v4 trace",
        "",
        f"- `live_bare` (what variant A did): {stage_bare_tally}",
        f"- `live_prod_parity` (forced detection, as v4 ran): {stage_prod_tally}",
        f"- clips reproduced exactly by prod parity: **{prod_matches_recorded}/{len(clips)}**",
        "",
        f"## VERDICT",
        "",
        f"- coverage gap cause: **{coverage_cause}** "
        f"(forced detection closes {gap_closed_pct}% of the 0.1707 -> 0.3659 gap)",
        f"- residual live-vs-recorded difference: **{residual}** "
        f"({len(residual_clips)} clip(s))",
        f"- previous `A_current_live` baseline: **INVALID**",
        "",
        "| clip | rec type | bare detector | forced | bare stage | prod stage |",
        "|---|---|---|---|---|---|",
    ]
    for c in clips:
        lines.append(
            f"| {c['clip']} | {c['recorded']['question_type']} | "
            f"{c['live_bare']['detector_says']['question_type']} | "
            f"{c['live_prod_parity']['detection_forced']} | "
            f"{c['first_divergence_bare']['stage']} | {c['first_divergence_prod']['stage']} |"
        )
    lines += [
        "",
        "## Stage 1 — detection (the whole coverage gap)",
        "",
        f"The bare detector classifies **{len(detection_only_clips)} of {len(clips)}** "
        "labeled-compound clips as SINGLE. `resolve_compound_question` then returns at "
        "line 230 of `compound_question_pipeline.py` with `used_compound_path=False` "
        "and no selected intents. `interview_e2e_loopback.run_clip` never hits this "
        "because it overrides the detector for labeled packs "
        "(`ComplexityDetection(\"compound\", 0.9, ..., (\"labeled_compound_pack\",))`).",
        "",
        "Clips broken by this: " + ", ".join(f"`{c}`" for c in detection_only_clips),
        "",
        "## Stage 3-4 — residual live-vs-recorded differences under forced detection",
        "",
        "| clip | stage | detail | recorded selected | live selected |",
        "|---|---|---|---|---|",
    ]
    for rc in residual_clips:
        lines.append(
            f"| {rc['clip']} | {rc['stage']} | {rc['detail']} | "
            f"{', '.join(rc['recorded_selected'] or []) or '—'} | "
            f"{', '.join(rc['live_selected'] or []) or '—'} |"
        )
    lines += [
        "",
        "### Fragment-level component breakdown for those clips",
        "",
        "Live `top_matches` on the recorded fragment, showing where the cosine term sits.",
        "",
    ]
    resid_ids = {rc["clip"] for rc in residual_clips}
    for c in clips:
        if c["clip"] not in resid_ids:
            continue
        lines += [f"**{c['clip']}** — `{c['transcript']}`", "",
                  "| fragment | intent | score | semantic | lexical | keyword | mode | accept |",
                  "|---|---|---:|---:|---:|---:|---|---|"]
        for frag, pool in c["live_candidate_pool_by_recorded_fragment"].items():
            for cand in pool[:3]:
                lines.append(
                    f"| {frag} | {cand['intent_id']} | {cand['score']} | {cand['semantic']} | "
                    f"{cand['lexical']} | {cand['keyword']} | {cand['mode']} | "
                    f"{cand['accept']}{'' if cand['accept'] else ' (' + str(cand['drop_reason']) + ')'} |"
                )
        lines.append("")
    lines += [
        "## Consequence for the Phase B baseline",
        "",
        f"`A_current_live` in `V5_COMPOUND_COUNTERFACTUALS` is **INVALID**: {baseline_status['reason']}",
        "",
        "Invalidated: " + "; ".join(baseline_status["invalidated_numbers"]) + ".",
        "",
    ]
    (REPORTS / "V5_MEASUREMENT_PARITY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines[:40]))
    print(f"\nwrote {REPORTS/'V5_MEASUREMENT_PARITY.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
