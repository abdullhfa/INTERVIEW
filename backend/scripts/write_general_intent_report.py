"""Write GENERAL_INTENT_UNDERSTANDING_REPORT.{html,json} with before/after baselines."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPORTS = Path(__file__).resolve().parents[1] / "reports"


def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    payload = {
        "title": "General Semantic Intent Understanding",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "before": {
            "medium_intent": "1/8 (12.5%)",
            "medium_fail_gate": "intent_score_gate=7 (canonical bank Q fuzz only)",
            "short_intent": "5/8",
            "short_notes": "fast path OK; ultra-short abstain cases",
            "very_long_intent": "5/8",
            "very_long_notes": "last_word_missing=8/8; MAX_UTTERANCE ~30s",
            "long_accent_intent": "40/40 (compound layer)",
            "realistic_intent": "96/100 (post-compound); prior 93/100",
            "realistic_hc_wrong": 0,
        },
        "after_e2e_loopback": {
            "medium_intent": "8/8 (100%)",
            "medium_stt": "8/8",
            "medium_hc_wrong": 0,
            "medium_compound_path_used": 0,
            "medium_intent_ms_avg": 5.0,
            "medium_report": "LENGTH_MEDIUM_REGRESSION_REPORT.html",
            "short_intent": "8/8 (100%)",
            "short_stt": "7/8",
            "short_hc_wrong": 0,
            "short_compound_path_used": 0,
            "short_intent_ms_avg": 4.7,
            "short_report": "LENGTH_SHORT_REGRESSION_REPORT.html",
            "very_long_intent": "8/8 (100%)",
            "very_long_stt": "8/8",
            "very_long_hc_wrong": 0,
            "very_long_last_word_missing": 2,
            "very_long_before_last_word_missing": 8,
            "very_long_report": "LENGTH_VERY_LONG_REGRESSION_REPORT.html",
            "long_accent_intent": "40/40 (100%)",
            "long_accent_hc_wrong": 0,
            "long_accent_report": "LONG_SENTENCE_ACCENT_REPORT.html",
            "realistic_intent": "97/100 (97%)",
            "realistic_hc_wrong": 0,
            "realistic_report": "INTERVIEW_E2E_REALISTIC_REPORT.html",
        },
        "after_offline_gold_transcripts": {
            "medium_intent": "8/8",
            "short_intent": "8/8",
            "short_recovery_triggered": "6/8 (clear definitions skip via strong_agrees)",
            "very_long_intent_on_gold": "8/8",
            "realistic_intent": "100/100",
            "realistic_hc_wrong": 0,
            "realistic_recovery_triggered": "20/100",
            "long_accent_compound": "40/40",
            "long_accent_hc_wrong": 0,
            "unit_tests": "test_semantic_intent_recovery.py — 8 passed",
        },
        "architecture": {
            "modules": [
                "intent_profile.py — IntentProfile + intent_agreement + intent_meaning_ok",
                "semantic_intent_index.py — MiniLM profile index (optional warm)",
                "semantic_intent_recovery.py — conditional hybrid recovery + ultra-short gate",
            ],
            "wiring": [
                "live_audio._bank_match after far + realistic",
                "interview_e2e_loopback intent gate + semantic recovery",
                "compound_question_pipeline per sub-question",
                "answer_generator._match_question_bank",
            ],
            "phase2_continuation": [
                "vad_engine.truncated_by_max on max-duration finalize",
                "speaker_router stash + continuation gap + merge segments (max 3)",
                "E2E fields: segment_count, truncated_by_max, merged_transcript",
            ],
            "frozen_preserved": [
                "No Whisper/EQ changes",
                "No global STRONG_THRESHOLD lowering",
                "Far/realistic recovery paths intact",
                "Embedder never loaded on hot path unless already warm",
            ],
        },
        "acceptance_phase1": {
            "medium_offline": "8/8 >= 90%",
            "short_fast_path": "definitions skip semantic recovery when score+agreement strong",
            "realistic_offline": "100/100 >= 93%, HC=0",
            "long_compound_offline": "40/40 >= 90%",
        },
        "notes": [
            "E2E audio suites still required for STT/VAD validation; offline numbers use gold transcripts.",
            "intent_meaning_ok allows paraphrase agreement >=0.52 with distinctive family consistency.",
            "Do not tune weights on future unseen holdout packs.",
        ],
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS / "GENERAL_INTENT_UNDERSTANDING_REPORT.json"
    json_stamp = REPORTS / f"GENERAL_INTENT_UNDERSTANDING_REPORT_{now}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    json_stamp.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    after = payload["after_offline_gold_transcripts"]
    before = payload["before"]
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>General Intent Understanding</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:2rem;background:#0f1419;color:#e7ecf1}}
h1{{font-size:1.6rem}} h2{{margin-top:1.8rem;color:#9ecbff}}
table{{border-collapse:collapse;width:100%;max-width:920px}}
th,td{{border:1px solid #2a3540;padding:.55rem .7rem;text-align:left}}
th{{background:#1a2330}} .ok{{color:#7ddea0}} .was{{color:#f0b27a}}
code{{background:#1a2330;padding:.1rem .35rem;border-radius:4px}}
li{{margin:.35rem 0}}
</style></head><body>
<h1>General Semantic Intent Understanding</h1>
<p>Generated {payload["generated_at"]}</p>
<h2>Before → After (gold-transcript offline)</h2>
<table>
<tr><th>Suite</th><th>Before</th><th>After</th></tr>
<tr><td>Medium (E2E loopback)</td><td class="was">{before["medium_intent"]}</td><td class="ok">{payload.get("after_e2e_loopback", {}).get("medium_intent", "pending")}</td></tr>
<tr><td>Short (E2E loopback)</td><td class="was">{before["short_intent"]}</td><td class="ok">{payload.get("after_e2e_loopback", {}).get("short_intent", "pending")}</td></tr>
<tr><td>Very long (E2E loopback)</td><td class="was">{before["very_long_intent"]}</td><td class="ok">{payload.get("after_e2e_loopback", {}).get("very_long_intent", "pending")}</td></tr>
<tr><td>Long accent (E2E)</td><td class="was">{before["long_accent_intent"]}</td><td class="ok">{payload.get("after_e2e_loopback", {}).get("long_accent_intent", "pending")}</td></tr>
<tr><td>Realistic (E2E)</td><td class="was">{before["realistic_intent"]}</td><td class="ok">{payload.get("after_e2e_loopback", {}).get("realistic_intent", "pending")}</td></tr>
<tr><td>Medium (gold offline)</td><td class="was">{before["medium_intent"]}</td><td class="ok">{after["medium_intent"]}</td></tr>
<tr><td>Short (gold offline)</td><td class="was">{before["short_intent"]}</td><td class="ok">{after["short_intent"]}</td></tr>
<tr><td>Very long (intent on gold)</td><td class="was">{before["very_long_intent"]}</td><td class="ok">{after["very_long_intent_on_gold"]}</td></tr>
<tr><td>Realistic</td><td class="was">{before["realistic_intent"]}</td><td class="ok">{after["realistic_intent"]} (HC={after["realistic_hc_wrong"]})</td></tr>
<tr><td>Long accent (compound)</td><td class="was">{before["long_accent_intent"]}</td><td class="ok">{after["long_accent_compound"]} (HC={after["long_accent_hc_wrong"]})</td></tr>
</table>
<h2>Root cause fixed</h2>
<p>E2E previously scored intent as RapidFuzz of spoken paraphrase vs <em>canonical bank question only</em>.
Medium failed the gate even with a correct/near-correct match. Agreement now uses aliases, keywords,
listen_for, answer/profile description, plus family-consistent paraphrase threshold.</p>
<h2>Architecture</h2>
<ul>
{"".join(f"<li><code>{m}</code></li>" for m in payload["architecture"]["modules"])}
</ul>
<h2>Phase 2 continuation</h2>
<ul>
{"".join(f"<li>{m}</li>" for m in payload["architecture"]["phase2_continuation"])}
</ul>
<h2>Acceptance</h2>
<ul>
{"".join(f"<li>{k}: {v}</li>" for k, v in payload["acceptance_phase1"].items())}
</ul>
<p class="was">Note: full Windows loopback E2E still validates STT/VAD; this report’s after column is gold-transcript intent regression.</p>
</body></html>
"""
    html_path = REPORTS / "GENERAL_INTENT_UNDERSTANDING_REPORT.html"
    html_path.write_text(html, encoding="utf-8")
    print(json_path)
    print(html_path)


if __name__ == "__main__":
    main()
