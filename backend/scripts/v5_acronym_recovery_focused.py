"""Focused TECH_ACRONYM_RECOVERY measurement (30–50 spoken acronym cases)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.services.question_bank import question_bank
from app.services.tech_acronym_recovery import (
    clear_acronym_vocab_cache,
    last_acronym_recovery,
    recover_acronyms,
)
from app.services.technical_term_repair import clear_repair_cache, repair_technical_terms

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

# Gold: raw STT-like → expected recovered acronym / intent family
CASES = [
    # LLM family — critical live bug
    {"id": "ACR_llm_clean", "raw": "What is LLM?", "expect_term": "LLM", "expect_recover": False, "gold_ids": ("tech.what_is_llm",), "must_not": ("llama", "LLaMA")},
    {"id": "ACR_llm_the", "raw": "What is the LLM?", "expect_term": "LLM", "expect_recover": False, "gold_ids": ("tech.what_is_llm",), "must_not": ("llama",)},
    {"id": "ACR_lalam", "raw": "What is the Lalam?", "expect_term": "LLM", "expect_recover": True, "gold_ids": ("tech.what_is_llm",), "must_not": ("llama", "LLaMA", "Ollama")},
    {"id": "ACR_lalam_short", "raw": "What is Lalam?", "expect_term": "LLM", "expect_recover": True, "gold_ids": ("tech.what_is_llm",), "must_not": ("llama",)},
    {"id": "ACR_ellem", "raw": "What is ellem?", "expect_term": "LLM", "expect_recover": True, "gold_ids": ("tech.what_is_llm",), "must_not": ("llama",)},
    {"id": "ACR_el_el_em", "raw": "What is el el em?", "expect_term": "LLM", "expect_recover": True, "gold_ids": ("tech.what_is_llm",), "must_not": ("llama",)},
    {"id": "ACR_l_l_m", "raw": "What is l l m?", "expect_term": "LLM", "expect_recover": True, "gold_ids": ("tech.what_is_llm",), "must_not": ("llama",)},
    {"id": "ACR_why_llm", "raw": "Why LLM?", "expect_term": "LLM", "expect_recover": False, "gold_ids": (), "must_not": ("llama",)},
    # RAG
    {"id": "ACR_rag_clean", "raw": "What is RAG?", "expect_term": "RAG", "expect_recover": False, "gold_ids": ("tech.rag_what",), "must_not": ()},
    {"id": "ACR_are_a_g", "raw": "What is are a g?", "expect_term": "RAG", "expect_recover": True, "gold_ids": ("tech.rag_what",), "must_not": ()},
    {"id": "ACR_r_a_g", "raw": "What is r a g?", "expect_term": "RAG", "expect_recover": True, "gold_ids": ("tech.rag_what",), "must_not": ()},
    {"id": "ACR_why_rag", "raw": "Why RAG?", "expect_term": "RAG", "expect_recover": False, "gold_ids": (), "must_not": ()},
    # NLP
    {"id": "ACR_nlp_clean", "raw": "What is NLP?", "expect_term": "NLP", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "ACR_en_el_pee", "raw": "What is en el pee?", "expect_term": "NLP", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_n_l_p", "raw": "What is n l p?", "expect_term": "NLP", "expect_recover": True, "gold_ids": (), "must_not": ()},
    # CNN / RNN / LSTM
    {"id": "ACR_cnn_clean", "raw": "How does CNN work?", "expect_term": "CNN", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "ACR_see_en_en", "raw": "How does see en en work?", "expect_term": "CNN", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_rnn", "raw": "What is are en en?", "expect_term": "RNN", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_lstm", "raw": "What is el es tee em?", "expect_term": "LSTM", "expect_recover": True, "gold_ids": (), "must_not": ()},
    # GPU / CPU / STT / TTS / VAD
    {"id": "ACR_gpu", "raw": "Why gee pee you?", "expect_term": "GPU", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_cpu", "raw": "What is see pee you?", "expect_term": "CPU", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_stt", "raw": "What is ess tee tee?", "expect_term": "STT", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_tts", "raw": "What is tee tee ess?", "expect_term": "TTS", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_vad", "raw": "What is vee ay dee?", "expect_term": "VAD", "expect_recover": True, "gold_ids": (), "must_not": ()},
    # n8n / ML / DL / AI / API / SQL / ANN
    {"id": "ACR_n8n", "raw": "When would you use en eight en?", "expect_term": "n8n", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_ml", "raw": "What is em el?", "expect_term": "ML", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_dl", "raw": "What is dee el?", "expect_term": "DL", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_ai", "raw": "What is ay eye?", "expect_term": "AI", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_api", "raw": "What is ay pee eye?", "expect_term": "API", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_sql", "raw": "What is ess queue el?", "expect_term": "SQL", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "ACR_ann", "raw": "What is ay en en?", "expect_term": "ANN", "expect_recover": True, "gold_ids": (), "must_not": ()},
    # Negatives / no false LLaMA
    {"id": "ACR_london_no", "raw": "What did London give you that you would otherwise need to build yourself?", "expect_term": "", "expect_recover": False, "gold_ids": (), "must_not": ("LLM", "llama", "LangChain")},
    {"id": "ACR_llama_word", "raw": "Have you run llama on your own servers?", "expect_term": "", "expect_recover": False, "gold_ids": (), "must_not": ("LLM",)},
    {"id": "ACR_embeddings_clean", "raw": "What are embeddings?", "expect_term": "", "expect_recover": False, "gold_ids": ("tech.embeddings",), "must_not": ("LLM",)},
    {"id": "ACR_rag_long", "raw": "Explain how you built the retrieval augmented generation pipeline for BTEC.", "expect_term": "", "expect_recover": False, "gold_ids": (), "must_not": ()},
    # Extra spoken variants
    {"id": "ACR_llm_dots", "raw": "What is L.L.M?", "expect_term": "LLM", "expect_recover": True, "gold_ids": ("tech.what_is_llm",), "must_not": ("llama",)},
    {"id": "ACR_ragas_keep", "raw": "What is RAGAS?", "expect_term": "RAGAS", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "ACR_mcp", "raw": "What is MCP?", "expect_term": "MCP", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "ACR_gpu_clean", "raw": "Do you need a GPU?", "expect_term": "GPU", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "ACR_stt_clean", "raw": "What is STT?", "expect_term": "STT", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "ACR_elem", "raw": "Define elem", "expect_term": "LLM", "expect_recover": True, "gold_ids": ("tech.what_is_llm",), "must_not": ("llama",)},
    {"id": "ACR_why_are_a_g", "raw": "Why are a g?", "expect_term": "RAG", "expect_recover": True, "gold_ids": (), "must_not": ()},
]


def _ok_term(text: str, expect: str) -> bool:
    if not expect:
        return True
    return expect.lower() in (text or "").lower()


def _forbidden(text: str, must_not: tuple[str, ...]) -> list[str]:
    low = (text or "").lower()
    hits = []
    for bad in must_not:
        if bad and bad.lower() in low:
            hits.append(bad)
    return hits


def main() -> int:
    clear_repair_cache()
    clear_acronym_vocab_cache()
    question_bank.load(force=True)

    rows = []
    t0 = time.perf_counter()
    recover_ok = 0
    recover_n = 0
    match_ok = 0
    match_n = 0
    false_llama = 0
    hc_wrong = 0

    for case in CASES:
        raw = case["raw"]
        expect_term = case["expect_term"]
        expect_recover = bool(case["expect_recover"])
        gold_ids = tuple(case.get("gold_ids") or ())
        must_not = tuple(case.get("must_not") or ())

        started = time.perf_counter()
        acr = recover_acronyms(raw)
        repaired = repair_technical_terms(raw)
        match = question_bank.match(raw)
        ms = (time.perf_counter() - started) * 1000

        did_recover = bool(acr.replacements) or (acr.recovered_transcript != acr.raw_transcript)
        term_ok = _ok_term(repaired, expect_term) if expect_term else True
        forbid_hits = _forbidden(repaired, must_not)
        if "llama" in forbid_hits or "LLaMA" in forbid_hits:
            false_llama += 1

        recover_pass = (did_recover == expect_recover) and term_ok and not forbid_hits
        if expect_recover:
            recover_n += 1
            if recover_pass:
                recover_ok += 1
        elif not did_recover and not forbid_hits:
            recover_ok += 0  # counted below in clean_pass
        clean_pass = (not expect_recover and not did_recover and not forbid_hits) or (
            expect_recover and recover_pass
        )

        intent_pass = True
        if gold_ids:
            match_n += 1
            intent_pass = match is not None and match.entry.id in gold_ids
            if intent_pass:
                match_ok += 1
            elif match is not None and getattr(match, "mode", "") == "strong":
                # Strong wrong would be HC-risk
                if match.entry.id not in gold_ids:
                    hc_wrong += 1

        row = {
            "id": case["id"],
            "raw": raw,
            "recovered": acr.recovered_transcript,
            "repaired": repaired,
            "did_recover": did_recover,
            "expect_recover": expect_recover,
            "expect_term": expect_term,
            "term_ok": term_ok,
            "forbid_hits": forbid_hits,
            "matched_intent": (match.entry.id if match else None),
            "acronym_matched_intent": acr.matched_intent or None,
            "candidates": [(c.acronym, round(c.score, 3)) for c in acr.candidates[:4]],
            "intent_pass": intent_pass if gold_ids else None,
            "pass": clean_pass and intent_pass,
            "ms": round(ms, 2),
        }
        rows.append(row)

    # Summary
    n = len(rows)
    passed = sum(1 for r in rows if r["pass"])
    recover_targets = [r for r in rows if r["expect_recover"]]
    recover_hit = sum(1 for r in recover_targets if r["term_ok"] and not r["forbid_hits"] and r["did_recover"])
    clean_targets = [r for r in rows if not r["expect_recover"]]
    clean_ok = sum(1 for r in clean_targets if not r["did_recover"] and not r["forbid_hits"])

    verdict = "ACRONYM_RECOVERY_PASS"
    blockers = []
    if false_llama:
        blockers.append(f"false_llama={false_llama}")
    if recover_targets and recover_hit / len(recover_targets) < 0.85:
        blockers.append(f"recover_rate={recover_hit/len(recover_targets):.3f}<0.85")
    if match_n and match_ok / match_n < 0.80:
        blockers.append(f"intent_rate={match_ok/match_n:.3f}<0.80")
    if hc_wrong:
        blockers.append(f"hc_wrong={hc_wrong}")
    # Critical live cases must pass
    for crit in ("ACR_lalam", "ACR_lalam_short", "ACR_el_el_em", "ACR_llm_clean"):
        row = next(r for r in rows if r["id"] == crit)
        if not row["pass"]:
            blockers.append(f"critical_fail={crit}")
    if blockers:
        verdict = "ACRONYM_RECOVERY_FAIL"

    payload = {
        "verdict": verdict,
        "blockers": blockers,
        "n": n,
        "pass_rate": round(passed / n, 4),
        "recover_targets": len(recover_targets),
        "recover_hit": recover_hit,
        "recover_rate": round(recover_hit / max(1, len(recover_targets)), 4),
        "clean_ok": clean_ok,
        "clean_n": len(clean_targets),
        "intent_ok": match_ok,
        "intent_n": match_n,
        "false_llama": false_llama,
        "hc_wrong": hc_wrong,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "cases": rows,
    }
    REPORTS.mkdir(exist_ok=True)
    out_json = REPORTS / "V5_ACRONYM_RECOVERY.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# V5 TECH_ACRONYM_RECOVERY",
        "",
        f"**Verdict:** `{verdict}`",
        "",
        "## Summary",
        f"| metric | value |",
        f"|---|---:|",
        f"| n | {n} |",
        f"| pass_rate | {payload['pass_rate']} |",
        f"| recover_rate | {payload['recover_rate']} ({recover_hit}/{len(recover_targets)}) |",
        f"| clean unchanged | {clean_ok}/{len(clean_targets)} |",
        f"| intent (gold) | {match_ok}/{match_n} |",
        f"| false_llama | {false_llama} |",
        f"| hc_wrong | {hc_wrong} |",
        "",
        "## Critical",
    ]
    for crit in ("ACR_lalam", "ACR_lalam_short", "ACR_el_el_em", "ACR_llm_clean"):
        row = next(r for r in rows if r["id"] == crit)
        md.append(
            f"- `{crit}` raw=`{row['raw']}` → `{row['repaired']}` "
            f"intent=`{row['matched_intent']}` pass={row['pass']}"
        )
    if blockers:
        md += ["", "## Blockers"] + [f"- {b}" for b in blockers]
    (REPORTS / "V5_ACRONYM_RECOVERY.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(verdict)
    print(json.dumps({k: payload[k] for k in payload if k != "cases"}, indent=2))
    return 0 if verdict.endswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
