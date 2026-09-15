"""Medium paraphrase diagnosis — read-only, no matcher changes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, TypedDict

from app.services.compound_question_detector import detect_question_complexity
from app.services.interview_e2e_loopback import _semantic
from app.services.question_bank import question_bank
from app.services.realistic_recovery import recover_realistic_match
from app.services.stt_confidence import apply_strong_abstain, assess_match_risk

REPORTS = Path(__file__).resolve().parents[1] / "reports"
E2E_JSON = REPORTS / "LENGTH_MEDIUM_REGRESSION_REPORT.json"
OUT_JSON = REPORTS / "MEDIUM_PARAPHRASE_DIAGNOSIS.json"
OUT_MD = REPORTS / "MEDIUM_PARAPHRASE_DIAGNOSIS.md"


class TopMatchRow(TypedDict):
    id: str
    question: str
    score: float
    mode: str
    semantic: float
    lexical: float
    runner_up: Optional[str]
    margin: float
    intent_vs_spoken: float


def main() -> None:
    question_bank.load()
    rep = json.loads(E2E_JSON.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    lines: list[str] = [
        "# Medium paraphrase diagnosis",
        "",
        "Read-only. No matcher / compound changes.",
        "",
        "Gate reminder: E2E `intent_ok` requires `intent_score >= 0.70` where",
        "`intent_score = semantic(bank_question, spoken)`. That fails when the bank",
        "entry is right but its canonical question is much shorter than the paraphrase.",
        "",
    ]

    for i, r in enumerate(rep["results"], 1):
        tr = (r.get("transcript") or "").strip()
        exp = (r.get("expected_question") or "").strip()
        det = detect_question_complexity(tr)
        tops = question_bank.top_matches(tr, top_k=5)
        raw_match = question_bank.match(tr)
        risk = assess_match_risk(tr, raw_match)
        after_abstain = apply_strong_abstain(raw_match, risk)
        rec = recover_realistic_match(tr, after_abstain, conversation_history=None)
        final = rec.match if rec.applied else after_abstain

        top5: list[TopMatchRow] = []
        for m in tops:
            top5.append(
                {
                    "id": m.entry.id,
                    "question": m.entry.question,
                    "score": round(float(m.score), 3),
                    "mode": m.mode,
                    "semantic": round(float(m.semantic), 3),
                    "lexical": round(float(m.lexical), 3),
                    "runner_up": m.runner_up,
                    "margin": round(float(m.score) - float(m.runner_up_score or 0), 3),
                    "intent_vs_spoken": round(
                        max(
                            _semantic(m.entry.question, exp),
                            _semantic(m.entry.question, tr),
                        ),
                        3,
                    ),
                }
            )

        selected = {
            "id": final.entry.id if final else None,
            "score": round(float(final.score), 3) if final else None,
            "mode": final.mode if final else None,
            "intent_score_e2e": r.get("intent_score"),
            "intent_ok_e2e": r.get("intent_ok"),
            "hc_wrong_e2e": r.get("high_confidence_wrong"),
            "match_id_e2e": r.get("match_id"),
            "match_mode_e2e": r.get("match_mode"),
            "match_score_e2e": r.get("match_score"),
        }

        reasons: list[str] = []
        risk_bits = []
        for attr in ("needs_stt_retry", "ambiguous", "weak_transcript", "reason", "bucket"):
            if hasattr(risk, attr):
                val = getattr(risk, attr)
                if val not in (None, False, "", 0):
                    risk_bits.append(f"{attr}={val}")
        if risk_bits:
            reasons.append("risk:" + ",".join(risk_bits))

        if raw_match is not None and after_abstain is None:
            reasons.append("strong_abstain→None")
        elif raw_match is not None and after_abstain is not None and after_abstain.mode != raw_match.mode:
            reasons.append(f"mode {raw_match.mode}→{after_abstain.mode}")
        if rec.applied:
            reasons.append(f"realistic_recovery:{rec.reason}:margin={rec.margin:.3f}")
        if not reasons:
            reasons.append("selected" if final else "no_match")

        if final is None:
            fail_gate = "no_match_after_gates"
        else:
            isc = max(
                _semantic(final.entry.question, exp),
                _semantic(final.entry.question, tr),
            )
            if isc < 0.70:
                fail_gate = (
                    f"intent_score_gate: semantic(bankQ,spoken)={isc:.3f} < 0.70 "
                    "(paraphrase vs short bank question)"
                )
            elif float(final.score) < 0.40:
                fail_gate = f"match_score_gate: {final.score:.3f} < 0.40"
            else:
                fail_gate = "would_pass_current_gate"

        # Best candidate by intent_vs_spoken among top5
        best_intent = max(top5, key=lambda t: t["intent_vs_spoken"]) if top5 else None

        case = {
            "n": i,
            "result_e2e": r.get("result"),
            "transcript": tr,
            "expected_question": exp,
            "detector": {
                "type": det.question_type,
                "confidence": det.confidence,
                "signals": list(det.signals),
            },
            "top5": top5,
            "raw_match": None
            if not raw_match
            else {
                "id": raw_match.entry.id,
                "score": round(float(raw_match.score), 3),
                "mode": raw_match.mode,
            },
            "selected": selected,
            "selected_or_abstain_reason": " | ".join(reasons),
            "fail_gate": fail_gate,
            "best_top5_by_intent_vs_spoken": best_intent,
            "e2e_notes": r.get("notes"),
        }
        cases.append(case)

        lines.append(f"## Case {i} — E2E `{r.get('result')}` | HC={r.get('high_confidence_wrong')}")
        lines.append("")
        lines.append(f"- **transcript:** {tr}")
        lines.append(f"- **expected:** {exp}")
        lines.append(
            f"- **detector:** `{det.question_type}` conf={det.confidence:.2f} signals={list(det.signals)}"
        )
        lines.append("- **top-5 intents:**")
        for j, t in enumerate(top5, 1):
            q = t["question"].replace("|", "/")
            lines.append(
                f"  {j}. `{t['id']}` score={t['score']:.3f} mode={t['mode']} "
                f"intent_vs_spoken={t['intent_vs_spoken']:.3f} margin={t['margin']:.3f} — {q}"
            )
        lines.append(
            f"- **raw match:** `{case['raw_match']}`"
        )
        lines.append(
            f"- **selected (after abstain/recovery):** id=`{selected['id']}` "
            f"score={selected['score']} mode=`{selected['mode']}` "
            f"| e2e intent_score={selected['intent_score_e2e']} intent_ok={selected['intent_ok_e2e']}"
        )
        lines.append(f"- **selected/abstain reason:** {case['selected_or_abstain_reason']}")
        lines.append(f"- **fail gate:** {fail_gate}")
        if best_intent:
            lines.append(
                f"- **top-5 best by intent_vs_spoken:** `{best_intent['id']}` "
                f"({best_intent['intent_vs_spoken']:.3f})"
            )
        lines.append(f"- **e2e notes:** {r.get('notes')}")
        lines.append("")

    # Pattern summary
    gate_counts: dict[str, int] = {}
    for c in cases:
        key = c["fail_gate"].split(":")[0]
        gate_counts[key] = gate_counts.get(key, 0) + 1
    lines.insert(
        5,
        "**Fail-gate tallies:** " + ", ".join(f"{k}={v}" for k, v in gate_counts.items()),
    )
    lines.insert(6, "")

    OUT_JSON.write_text(json.dumps({"cases": cases, "gate_counts": gate_counts}, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print("gate_counts", gate_counts)
    for c in cases:
        print(
            f"CASE {c['n']}: {c['result_e2e']} selected={c['selected']['id']} "
            f"gate={c['fail_gate'][:60]}"
        )


if __name__ == "__main__":
    main()
