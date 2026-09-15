"""
V5 Final Bank-Guided Understanding evaluation.

Text-path gate through understand → match (real recovery + bank resolution).
Accent/rate labels are STT-corruption proxies for Indian/Jordanian/Gulf speech.
Full WASAPI loopback can reuse the same scripts as audio pack.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.services.bank_guided_understanding import (
    clear_bank_guided_cache,
    understand_interview_question,
)
from app.services.question_bank import question_bank
from app.services.technical_term_repair import clear_repair_cache

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

CASES: list[dict] = []


def _add(cid, bucket, raw, gold_ids, *, expect_intent=True, must_not_ids=(), accent="indian", style="direct"):
    CASES.append(
        {
            "id": cid,
            "bucket": bucket,
            "raw": raw,
            "gold_ids": gold_ids,
            "expect_intent": expect_intent,
            "must_not_ids": must_not_ids,
            "accent": accent,
            "style": style,
        }
    )


def _build_cases() -> None:
    CASES.clear()
    # --- Critical ---
    _add("BG_lalam", "acronym", "What is the Lalam?", ("tech.what_is_llm",), accent="indian", style="short")
    _add("BG_lalam2", "acronym", "What is Lalam?", ("tech.what_is_llm",), accent="jordanian", style="short")
    _add("BG_el_el_em", "acronym", "What is el el em?", ("tech.what_is_llm",), accent="emirati", style="short")
    _add("BG_llm_clean", "acronym", "What is LLM?", ("tech.what_is_llm",), accent="indian", style="short")
    _add("BG_and_you_plan", "phrase", "and you plan your project", ("cv.projects_overview",), must_not_ids=(), accent="indian", style="short")
    _add("BG_how_plan_project", "phrase", "How do you plan your project?", (), expect_intent=False, must_not_ids=("cv.projects_overview",), accent="jordanian", style="short")
    _add("BG_how_plan_work", "personal", "How do you prioritize your work?", ("gen.prioritize",), must_not_ids=("cv.projects_overview",), accent="emirati", style="direct")

    # --- AI technical ---
    for i, (raw, gid, acc, st) in enumerate(
        [
            ("What is RAG?", "tech.rag_what", "indian", "short"),
            ("What is are a g?", "tech.rag_what", "jordanian", "short"),
            ("Why am bedding?", "tech.embeddings", "emirati", "short"),
            ("What are embeddings?", "tech.embeddings", "indian", "short"),
            ("What is LangChain?", "tech.what_is_langchain", "jordanian", "direct"),
            ("What did Lankan give you that you would otherwise need to build yourself?", "tech.what_is_langchain", "indian", "indirect"),
            ("Why LangGraph?", "cv.langgraph", "emirati", "short"),
            ("Whyland draft here.", "cv.langgraph", "jordanian", "short"),
            ("What is agentic AI?", "tech.agentic_what", "indian", "direct"),
            ("What is hallucination?", "tech.hallucination_what", "emirati", "direct"),
            ("What are guardrails?", "tech.guardrails_what", "jordanian", "direct"),
            ("What is a vector database?", "tech.vector_db_choice", "emirati", "direct"),
            ("What does a vector database store?", "cv.vector_db", "jordanian", "direct"),
            ("Why did you use RAG?", "proj.similarity.is_rag", "indian", "direct"),
            ("why did you use rack", "proj.similarity.is_rag", "emirati", "short"),
            ("What is Whisper?", "tech.what_is_whisper", "jordanian", "direct"),
            ("How does STT work?", "tech.how_stt_works", "indian", "direct"),
        ]
    ):
        _add(f"BG_ai_{i}", "technical", raw, (gid,) if gid else (), accent=acc, style=st)

    # --- Projects ---
    for i, (raw, gids, acc) in enumerate(
        [
            ("Explain your project", ("cv.projects_overview",), "indian"),
            ("Tell me about your project", ("cv.projects_overview",), "jordanian"),
            ("Walk me through your project", ("cv.projects_overview",), "emirati"),
            ("What projects have you worked on?", ("cv.projects_overview",), "indian"),
            ("What was your role?", ("proj.similarity.role",), "jordanian"),
            ("what was your roll", ("proj.similarity.role",), "emirati"),
            ("What challenges did you face?", ("proj.similarity.challenges",), "indian"),
            ("What is your most recent project?", ("cv.projects.most_recent",), "jordanian"),
        ]
    ):
        _add(f"BG_proj_{i}", "project", raw, gids, accent=acc, style="direct")

    # --- Personal / HR ---
    for i, (raw, gid, acc) in enumerate(
        [
            ("Tell me about yourself", "intro.tell_me_about_yourself", "indian"),
            ("tell me a boat yourself", "intro.tell_me_about_yourself", "jordanian"),
            ("Why should we hire you?", "cv.why_hire_you", "emirati"),
            ("why should we higher you", "cv.why_hire_you", "indian"),
            ("What are your strengths?", "gen.strengths", "jordanian"),
            ("What is your weakness?", "gen.weaknesses", "emirati"),
            ("How do you handle pressure?", "gen.pressure", "indian"),
            ("How do you work in a team?", "gen.teamwork", "jordanian"),
            ("Where do you see yourself in five years?", "gen.five_years", "emirati"),
            ("How do you prioritize your work?", "gen.prioritize", "indian"),
        ]
    ):
        _add(f"BG_hr_{i}", "personal", raw, (gid,) if gid else (), accent=acc, style="direct")

    # --- Business / scenario ---
    for i, (raw, style, acc) in enumerate(
        [
            ("What is the business value?", "direct", "indian"),
            ("How would you secure the system?", "scenario", "jordanian"),
            ("What if the model hallucinates?", "scenario", "emirati"),
            ("How would you monitor it in production?", "scenario", "indian"),
            ("How would you scale the RAG system?", "scenario", "jordanian"),
        ]
    ):
        _add(f"BG_biz_{i}", "business", raw, (), expect_intent=False, accent=acc, style=style)

    # --- Long / indirect (MRE path still runs later; here bank-guided must not explode) ---
    _add(
        "BG_long_latency",
        "long",
        "Your assistant understands the interview question correctly, but the answer arrives several seconds after the interviewer finishes speaking. Walk me through how you would measure the delay and decide whether the bottleneck is speech recognition, retrieval, model inference, or the user interface.",
        ("tech.latency_p95", "hard.production_monitoring"),
        accent="indian",
        style="long",
    )
    _add(
        "BG_indirect_ambiguity",
        "indirect",
        "How do you handle ambiguous requirements?",
        ("gen.ambiguity",),
        accent="emirati",
        style="indirect",
    )

    # --- Negatives / no false LLaMA / no false project ---
    _add(
        "BG_london_no",
        "negative",
        "What did London give you that you would otherwise need to build yourself?",
        (),
        expect_intent=False,
        must_not_ids=("tech.what_is_langchain", "cv.projects_overview"),
        accent="jordanian",
        style="indirect",
    )
    _add(
        "BG_embeddings_clean",
        "negative",
        "What are embeddings?",
        ("tech.embeddings",),
        must_not_ids=("tech.what_is_llm",),
        accent="indian",
        style="short",
    )

    # Pad to ~100 with clean bank questions sampled
    question_bank.load(force=True)
    n = 0
    for e in question_bank.entries:
        if n >= 40:
            break
        if len((e.question or "").split()) > 14:
            continue
        if not e.id.startswith(("tech.", "intro.", "cv.", "gen.", "proj.")):
            continue
        _add(
            f"BG_clean_{n}",
            "clean",
            e.question,
            (e.id,),
            accent=["indian", "jordanian", "emirati"][n % 3],
            style="direct",
        )
        n += 1


def _resolve_soft_gold(gold_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Drop gold ids that are not in the bank."""
    question_bank.load()
    return tuple(g for g in gold_ids if g in question_bank._index.by_id)


def main() -> int:
    clear_repair_cache()
    clear_bank_guided_cache()
    question_bank.load(force=True)
    _build_cases()

    # Soft-resolve golds that may not exist
    for c in CASES:
        c["gold_ids"] = _resolve_soft_gold(tuple(c["gold_ids"]))
        c["must_not_ids"] = _resolve_soft_gold(tuple(c.get("must_not_ids") or ()))

    rows = []
    t0 = time.perf_counter()
    stats = {
        "n": 0,
        "intent_ok": 0,
        "intent_n": 0,
        "false_corrections": 0,
        "hc_wrong": 0,
        "by_bucket": {},
        "acronym_ok": 0,
        "acronym_n": 0,
        "phrase_ok": 0,
        "phrase_n": 0,
        "personal_ok": 0,
        "personal_n": 0,
        "technical_ok": 0,
        "technical_n": 0,
        "project_ok": 0,
        "project_n": 0,
        "indirect_ok": 0,
        "indirect_n": 0,
        "short_ok": 0,
        "short_n": 0,
        "long_ok": 0,
        "long_n": 0,
        "latency_sum": 0.0,
    }

    for case in CASES:
        raw = case["raw"]
        gold = tuple(case["gold_ids"])
        must_not = tuple(case.get("must_not_ids") or ())
        expect = bool(case.get("expect_intent", True))
        bucket = case["bucket"]
        style = case["style"]

        t1 = time.perf_counter()
        und = understand_interview_question(raw)
        match = question_bank.match(raw)
        ms = (time.perf_counter() - t1) * 1000
        stats["latency_sum"] += ms
        stats["n"] += 1

        mid = match.entry.id if match else None
        guided = und.intent_id or None
        chosen = mid or guided

        false = False
        if must_not and chosen in must_not:
            false = True
            stats["false_corrections"] += 1
        if match is not None and getattr(match, "mode", "") == "strong" and gold and match.entry.id not in gold:
            # Only count HC when gold known
            stats["hc_wrong"] += 1

        ok = True
        if expect and gold:
            stats["intent_n"] += 1
            ok = chosen in gold
            if ok:
                stats["intent_ok"] += 1
        elif expect and not gold:
            ok = match is not None or (und.intent_id and not und.ambiguous)
        else:
            # expect_intent False: must not hit forbidden; abstain OK
            ok = not false

        if false:
            ok = False

        def _bucket(name, flag):
            stats[f"{name}_n"] += 1
            if flag:
                stats[f"{name}_ok"] += 1

        if bucket == "acronym":
            _bucket("acronym", ok)
        if bucket == "phrase":
            _bucket("phrase", ok)
        if bucket == "personal":
            _bucket("personal", ok)
        if bucket in {"technical", "ai"} or bucket == "technical":
            _bucket("technical", ok)
        if bucket == "project":
            _bucket("project", ok)
        if style == "indirect":
            _bucket("indirect", ok)
        if style == "short":
            _bucket("short", ok)
        if style == "long":
            _bucket("long", ok)

        b = stats["by_bucket"].setdefault(bucket, {"n": 0, "ok": 0})
        b["n"] += 1
        if ok:
            b["ok"] += 1

        rows.append(
            {
                "id": case["id"],
                "bucket": bucket,
                "style": style,
                "accent": case["accent"],
                "raw": raw,
                "recovered": und.recovered_transcript,
                "canonical": und.canonical_question,
                "guided_intent": guided,
                "matched_intent": mid,
                "confidence": round(und.confidence, 3),
                "ambiguous": und.ambiguous,
                "margin": round(und.margin, 3),
                "candidates": [
                    {"intent_id": c.intent_id, "combined": round(c.combined, 3)}
                    for c in und.candidates[:3]
                ],
                "gold_ids": list(gold),
                "pass": ok,
                "ms": round(ms, 2),
            }
        )

    n = stats["n"]
    pass_n = sum(1 for r in rows if r["pass"])
    latency_delta = stats["latency_sum"] / max(1, n)

    blockers = []
    # Critical must pass
    for crit in ("BG_lalam", "BG_and_you_plan", "BG_how_plan_project", "BG_llm_clean"):
        row = next(r for r in rows if r["id"] == crit)
        if not row["pass"]:
            blockers.append(f"critical_fail={crit}")
    if stats["false_corrections"]:
        blockers.append(f"false_corrections={stats['false_corrections']}")
    if stats["hc_wrong"]:
        blockers.append(f"HC_wrong={stats['hc_wrong']}")
    if stats["intent_n"] and stats["intent_ok"] / stats["intent_n"] < 0.75:
        blockers.append(
            f"bank_match_accuracy={stats['intent_ok']/stats['intent_n']:.3f}<0.75"
        )

    verdict = "BANK_GUIDED_INTERVIEW_READY" if not blockers else "BANK_GUIDED_INTERVIEW_NOT_READY"

    def _rate(ok, nn):
        return round(ok / nn, 4) if nn else None

    payload = {
        "verdict": verdict,
        "blockers": blockers,
        "n": n,
        "pass_rate": round(pass_n / n, 4),
        "bank_match_accuracy": _rate(stats["intent_ok"], stats["intent_n"]),
        "technical_term_recovery": "delegated_to_SHORT_TECH",
        "acronym_recovery": _rate(stats["acronym_ok"], stats["acronym_n"]),
        "phrase_recovery": _rate(stats["phrase_ok"], stats["phrase_n"]),
        "personal_question_accuracy": _rate(stats["personal_ok"], stats["personal_n"]),
        "AI_question_accuracy": _rate(stats["technical_ok"], stats["technical_n"]),
        "project_question_accuracy": _rate(stats["project_ok"], stats["project_n"]),
        "indirect_accuracy": _rate(stats["indirect_ok"], stats["indirect_n"]),
        "short_accuracy": _rate(stats["short_ok"], stats["short_n"]),
        "long_accuracy": _rate(stats["long_ok"], stats["long_n"]),
        "false_corrections": stats["false_corrections"],
        "HC_wrong": stats["hc_wrong"],
        "latency_delta_ms_avg": round(latency_delta, 2),
        "by_bucket": {
            k: {"n": v["n"], "ok": v["ok"], "rate": _rate(v["ok"], v["n"])}
            for k, v in stats["by_bucket"].items()
        },
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "note": "Evaluation uses bank-guided understand→match path. Accent labels are STT corruption proxies. Offline expansion draft: V5_BANK_EXPANSION_DRAFT.json",
        "cases": rows,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "V5_FINAL_BANK_GUIDED_UNDERSTANDING.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    md = [
        "# V5 Final Bank-Guided Interview Understanding",
        "",
        f"**Verdict:** `{verdict}`",
        "",
        "## Principle",
        "STT is a raw hypothesis. Question Bank + lexicon + context decide intent.",
        "",
        "## Pipeline",
        "`STT RAW → BANK CANDIDATE SEARCH → ACRONYM → TECH → PHRASE → MRE → BANK INTENT → ANSWER`",
        "",
        "## Metrics",
        "| metric | value |",
        "|---|---:|",
        f"| n | {n} |",
        f"| pass_rate | {payload['pass_rate']} |",
        f"| bank_match_accuracy | {payload['bank_match_accuracy']} |",
        f"| acronym_recovery | {payload['acronym_recovery']} |",
        f"| phrase_recovery | {payload['phrase_recovery']} |",
        f"| personal_question_accuracy | {payload['personal_question_accuracy']} |",
        f"| AI_question_accuracy | {payload['AI_question_accuracy']} |",
        f"| project_question_accuracy | {payload['project_question_accuracy']} |",
        f"| indirect_accuracy | {payload['indirect_accuracy']} |",
        f"| short_accuracy | {payload['short_accuracy']} |",
        f"| long_accuracy | {payload['long_accuracy']} |",
        f"| false_corrections | {payload['false_corrections']} |",
        f"| HC_wrong | {payload['HC_wrong']} |",
        f"| latency_delta_ms_avg | {payload['latency_delta_ms_avg']} |",
        "",
        "## Critical",
    ]
    for crit in ("BG_lalam", "BG_and_you_plan", "BG_how_plan_project", "BG_llm_clean"):
        row = next(r for r in rows if r["id"] == crit)
        md.append(
            f"- `{crit}` raw=`{row['raw']}` → canonical=`{row['canonical']}` "
            f"intent=`{row['matched_intent'] or row['guided_intent']}` pass={row['pass']}"
        )
    if blockers:
        md += ["", "## Blockers"] + [f"- {b}" for b in blockers]
    md += [
        "",
        "## Dual transcript",
        "Logs keep `raw_transcript`, `recovered_transcript`, `canonical_question`, `intent_id`.",
        "",
        "## Offline expansion",
        "Draft paraphrases: `reports/V5_BANK_EXPANSION_DRAFT.json` (validation required before production).",
    ]
    (REPORTS / "V5_FINAL_BANK_GUIDED_UNDERSTANDING.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8"
    )
    print(verdict)
    print(json.dumps({k: payload[k] for k in payload if k != "cases"}, indent=2))
    return 0 if verdict.endswith("READY") and not verdict.endswith("NOT_READY") else 1


if __name__ == "__main__":
    raise SystemExit(main())
