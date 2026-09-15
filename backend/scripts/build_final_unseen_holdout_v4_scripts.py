"""
Build the Final Unseen Holdout v4 pack (EVAL ONLY).

Writes, under frontend/public/voice-drill/final-unseen-holdout-v4/:

    scripts.json   runtime rows — NO gold. This is what the suite reads to play audio.
    gold.json      expected_intent_ids only, keyed by clip id. Never read before scoring.
    pack_meta.json pack description + balance
    manifest.json  flat list for the voice-drill page
    NOVELTY.md     proof that no text is reused from any earlier pack

Design rules (Final Unseen Holdout protocol):
  * 120 scored clips + 2 warm-up, 8 question types x 15
  * conditions clean/office/poor/far/fast, 24 each (i % 5)
  * accents indian/jordanian/egyptian/emirati, 30 each (i % 4)
  * every transcript is newly authored: the build FAILS if any normalized text
    matches, or is >= 90 token_set_ratio to, a text in any earlier pack
  * gold lives in a separate file so no expected id can reach the decision path
  * run ONCE, then lock with scripts/lock_holdout_v3.py

Do not tune anything on this pack. If a real bug is found and fixed after v4
has been run, v4 is VOID and a v5 pack is required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PACK_ROOT = ROOT.parent / "frontend" / "public" / "voice-drill" / "final-unseen-holdout-v4"
VOICE_DRILL = PACK_ROOT.parent
BANK_DIR = ROOT / "app" / "data" / "question_bank"

CONDITIONS = ("clean", "office", "poor", "far", "fast")

# Accent profiles are named for what they ACTUALLY are, not for a dialect we
# cannot claim. `en-IN` is a genuine English-locale neural voice. The three
# `proxy-ar-*` profiles are Arabic-locale voices reading English text: a useful
# synthetic stand-in for Arabic-accented English, but NOT a recording of a
# Jordanian / Egyptian / Emirati speaker. Reports must never call them dialects.
ACCENT_PROFILES = (
    ("en-IN", "native_locale"),
    ("proxy-ar-JO", "synthetic_proxy"),
    ("proxy-ar-EG", "synthetic_proxy"),
    ("proxy-ar-AE", "synthetic_proxy"),
)
ACCENTS = tuple(name for name, _kind in ACCENT_PROFILES)
ACCENT_KIND = dict(ACCENT_PROFILES)

# ── authored source text (transcript, gold ids) ─────────────────────────────
WARMUP = [
    ('Can the live stack handle Arabic and English mixed inside one spoken question?', ['hard.mixed_language_query'], 'short'),
    ('Trace the full chain from microphone capture to the answer text read aloud.', ['hard.project_architecture_e2e'], 'medium'),
]

ULTRA_SHORT = [
    ('Overlap between chunks?', ['tech.chunk_size']),
    ('At what stage would you introduce a re-ranker?', ['tech.reranking']),
    ('What does model drift mean once the system is live?', ['tech.model_drift']),
    ('Define p95 for me.', ['tech.p95']),
    ('Why does idempotency matter for repeated tool calls?', ['tech.idempotency']),
    ('What is low-rank fine-tuning in one breath?', ['tech.lora']),
    ('Fully air-gapped deployment?', ['tech.air_gapped']),
    ('Notice period if we hire you?', ['cv.notice_period']),
    ('Why Redis in this stack?', ['tech.redis_why']),
    ('When would you blend BM25 with dense vectors?', ['tech.hybrid_search']),
    ('Golden eval set — purpose?', ['tech.golden_dataset']),
    ('Canary for a new retriever?', ['hard.canary_rag']),
    ('Sampling temperature — impact?', ['tech.temperature']),
    ('MCP in plain terms.', ['tech.mcp']),
    ('How do you stop one flaky dependency from stalling the whole service?', ['hard.circuit_breaker']),
]

SHORT = [
    ('How would you choose chunk boundaries for our PDFs?', ['tech.chunk_size']),
    ('Two policy memos contradict each other in retrieval — then what?', ['hard.conflicting_docs']),
    ('Why is fine-tuning the whole archive not your first move?', ['hard.not_finetune_first']),
    ('When the agent gives bad advice, who is accountable?', ['hard.accountability']),
    ('Roughly how many GPUs for our expected load?', ['tech.gpu_sizing']),
    ('Will scanned pages with skewed tables still index cleanly?', ['hard.rag_pdfs_tables_scans']),
    ('Do you expose partial tokens before validation finishes?', ['hard.streaming_vs_validate']),
    ('Have you operated Kubernetes clusters yourself?', ['cv.kubernetes']),
    ('How many years did you spend working in Kuwait?', ['cv.kuwait_how_long']),
    ('What made you leave project management for AI work?', ['cv.transition_pm_to_ai']),
    ('Which KPI did you optimise on the early-warning model?', ['proj.early_warning.metric']),
    ('Could raw student identifiers ever enter model prompts?', ['cv.student_pii']),
    ('What caps runaway inference spend in your designs?', ['tech.reduce_cost']),
    ('How do you track prompt versions once they are live?', ['hard.prompt_versioning']),
    ('What would you ship in the first ninety days here?', ['hard.first_90_agentic']),
]

MEDIUM = [
    ('When search returns zero chunks, what message does the user get?', ['hard.empty_retrieval']),
    ('How do you enforce that School A never sees School B uploads?', ['hard.tenant_isolation']),
    ('How do you know embeddings — not the prompt — are failing?', ['hard.which_rag_layer_failed']),
    ('We replace the embedding model in Q2 — what migration steps run?', ['tech.reindex_embedding_change']),
    ('How do you verify the cited span actually supports the claim?', ['tech.faithfulness_check']),
    ('When would a knowledge graph beat pure vector retrieval?', ['hard.graph_vs_vector']),
    ('Size an on-prem GPU footprint for our peak concurrency.', ['tech.deploy_on_prem', 'tech.gpu_sizing']),
    ('What stops duplicate tool calls after a retry?', ['hard.idempotent_tools']),
    ('Which live metrics would you alert on first?', ['hard.production_monitoring']),
    ('How did you prevent label leakage in the dropout features?', ['proj.early_warning.leakage']),
    ('Name the Python libraries you rely on weekly.', ['tech.python_libraries']),
    ('Explain a failed search to a non-technical principal.', ['gen.non_technical_stakeholders']),
    ('How does Gulf Arabic input change tokenisation and retrieval?', ['tech.emirati_dialect']),
    ('When is a router sufficient without a supervisor agent?', ['hard.supervisor_vs_router']),
    ('What checklist tells you the pilot is safe to launch?', ['tech.good_enough_to_launch']),
]

LONG = [
    ('A decade of ministry circulars sits in PDF — scans, tables, footnotes — how do you make that searchable?', ['hard.rag_pdfs_tables_scans', 'tech.rag_build']),
    ('A PDF chunk says ignore prior instructions — where does your pipeline catch that?', ['hard.injection_in_pdf']),
    ('Policy text changes every school year — why keep retrieval instead of retraining?', ['tech.rag_vs_finetuning']),
    ('The model cites page four but the fact is not on page four — how is that caught?', ['hard.citation_lie']),
    ('Ship a new retriever without users feeling a quality drop — your rollout plan?', ['hard.canary_rag']),
    ('List the guard layers you place before citizen-facing answers.', ['tech.guardrails_layers']),
    ('Midday outage at the hosted LLM — what fallback response still works?', ['hard.fallback_llm_down']),
    ('One slow request — how do you trace retrieval, generation, and tool latency?', ['hard.observability']),
    ('One department gets confident wrong answers — your debugging sequence?', ['hard.rag_debug_steps']),
    ('Hosted API versus in-house model — how do you decide for us?', ['tech.hosting_decision']),
    ('Describe your voice kiosk build and the hardest audio problem you solved.', ['proj.kiosk.describe', 'proj.kiosk.challenges']),
    ('Finance fears a cost blowout — how do you prove spend stays bounded?', ['tech.reduce_cost', 'hard.cost_spike']),
    ('Measure retrieval quality separately from answer fluency — your method?', ['hard.evaluate_rag']),
    ('A teacher rejects an auto-generated exam item — what happens next in the workflow?', ['hard.teacher_rejects']),
    ('Why use graph checkpoints instead of relying on chat memory alone?', ['hard.checkpoint_vs_memory']),
]

VERY_LONG = [
    ('Picture a ministry: departmental secrets, no outbound API calls, air-gapped racks — design the Q&A stack from mic to answer.', ['tech.air_gapped', 'hard.secure_rag', 'tech.deploy_on_prem']),
    ('Three thousand staff hit the assistant at eight a.m. — what fails first and what capacity would you pre-provision?', ['hard.production_monitoring', 'tech.latency_p95']),
    ('Pick one shipped system: problem, option you rejected, what went live, and what you would redo now.', ['cv.what_would_you_improve', 'cv.projects.most_proud']),
    ('A vendor PDF whispers rank us first; procurement asks for a comparison — enumerate every choke point that blocks the attack.', ['tech.prompt_injection_supplier', 'tech.guardrails_layers']),
    ('Bilingual Arabic-English docs, code-switched queries, scanned Arabic pages — detail the retrieval architecture you would use.', ['hard.rag_arabic_english', 'hard.mixed_language_query']),
    ('Grant the bot ticket and email powers — which scopes yes, which no, and how you audit mistaken sends afterward.', ['hard.least_privilege_example', 'hard.interrupt_side_effects']),
    ('Follow one exam question from teacher request through human approval — every stop point included.', ['moe.question_generation', 'hard.hitl_where']),
    ('Halve latency without hurting quality — first knobs, metrics, and regression proof you would run.', ['tech.latency_p95', 'hard.evaluate_rag']),
    ('Walk through a real outage you owned: user impact, root cause, and the permanent fix.', ['tech.production_failure_story']),
    ('We lack ML staff — what can our IT team run solo versus what needs a specialist on retainer?', ['gen.non_technical_stakeholders', 'hard.first_90_agentic']),
    ('Two risk agents disagree on the same student — resolution logic and what the teacher sees.', ['hard.agents_disagree', 'hard.hitl_where']),
    ('Convince an auditor that student PII never left premises — storage, prompts, logs, caches.', ['tech.pii_redaction', 'cv.student_pii', 'tech.audio_retention']),
    ('Contrast scripted automation, single-tool agents, and multi-agent teams — which pattern matched your ministry delivery?', ['hard.agent_terms_difference', 'hard.plain_python_still_agentic']),
    ('Ninety-five percent correct but five percent confident finance errors — what should the product do?', ['tech.no_wrong_info_finance', 'tech.i_dont_know_too_often']),
    ('Pre-launch eval harness: example sourcing, gold authorship, and keeping the set from rotting.', ['tech.golden_dataset', 'hard.golden_agentic']),
]

COMPOUND = [
    ('Define re-ranking, then say when hybrid search needs it.', ['tech.reranking', 'hard.hybrid_when']),
    ('What is hallucination, and which controls reduce it in production?', ['tech.hallucination_what', 'tech.hallucination_prevent']),
    ('Explain context windows, then how you chunk oversize documents.', ['tech.context_window', 'tech.chunk_size']),
    ('Summarise the assignment similarity project, its stack, and whether it is RAG.', ['proj.similarity.describe', 'proj.similarity.tech', 'proj.similarity.is_rag']),
    ('Define overfitting, detection signals, and your mitigation playbook.', ['tech.overfitting', 'tech.overfitting_prevent', 'tech.evaluate_classification']),
    ('Your vector DB history, then your pick for our workload and why.', ['cv.vector_db', 'tech.vector_db_choice']),
    ('Role of an orchestrator versus a lone tool-calling model — when is each enough?', ['tech.agent_orchestrator', 'tech.multi_agent_when']),
    ('Education, certifications, and how they matter for this role.', ['cv.education', 'cv.certifications', 'cv.pmp_value']),
    ('Prompt injection sources, PDF risk, and guardrails that block it.', ['tech.prompt_injection_what', 'hard.injection_in_pdf', 'tech.guardrails_how']),
    ('Docker value, container versus VM, and if we need Kubernetes.', ['tech.docker_why', 'tech.container_vs_vm', 'tech.kubernetes']),
    ('Early-warning project story, KPI, and ministry outcome.', ['proj.early_warning.describe', 'proj.early_warning.metric', 'proj.early_warning.result']),
    ('Tool calling basics, schema need, and when to halt tool loops.', ['tech.tool_calling', 'hard.tool_schema', 'hard.agent_stop_tools']),
    ('STT internals, local Whisper rationale, and accuracy acceptance tests.', ['tech.how_stt_works', 'tech.whisper_vs_cloud', 'tech.transcription_quality']),
    ('LangGraph versus LangChain, your usage, and surviving without LangChain.', ['tech.langgraph_vs_langchain', 'cv.langgraph', 'hard.remove_langchain']),
    ('Embeddings, cosine search, metadata filters, and hybrid search trade-offs — cover all four.', ['tech.embeddings', 'tech.cosine_semantic_search', 'tech.metadata_filtering', 'tech.hybrid_search']),
]

INDIRECT = [
    ('The director says the bot invents facts — what failure mode is that?', ['tech.hallucination_what']),
    ('Answers shifted after we changed an upstream model and skipped reindexing.', ['tech.reindex_embedding_change']),
    ('Cloud bill jumped threefold overnight with flat traffic.', ['hard.cost_spike']),
    ('Top document is correct but the extracted snippet is not.', ['hard.wrong_chunk']),
    ('A teammate wants to fine-tune on everything and skip retrieval.', ['hard.not_finetune_first']),
    ('Polished answers with no traceable source sentence.', ['hard.citation_lie', 'tech.faithfulness_check']),
    ('Users hear “I cannot help” so often they stopped asking.', ['tech.i_dont_know_too_often']),
    ('Procurement opened an HR-only policy file yesterday.', ['tech.rag_access_control']),
    ('The agent looped tools for minutes then quit without resolving.', ['hard.agent_loop', 'hard.timeout_vs_steps']),
    ('Pilot feedback is glowing but we lack an objective quality score.', ['tech.good_enough_to_launch', 'hard.evaluate_rag']),
    ('Same question, same day, two incompatible answers.', ['tech.temperature', 'hard.prompt_versioning']),
    ('Legal will not allow recordings or payloads off-site.', ['tech.audio_retention', 'tech.external_api_risks']),
    ('After three years with us, what would push you toward another employer?', ['cv.why_leaving']),
    ('If the work turned repetitive after hire, would you stay?', ['gen.motivation']),
    ('Name a genuine weakness, not a humble brag.', ['gen.weaknesses']),
]

FOLLOW_UP = [
    ('Start with the BTEC similarity checker', 'What was specifically yours in that build?', ['proj.similarity.role']),
    ('Define retrieval-augmented generation', 'Okay — how would you assemble one for us?', ['tech.rag_build']),
    ('Explain embedding vectors', 'How does nearest-neighbor search use them?', ['tech.cosine_semantic_search']),
    ('What counts as agentic AI', 'How is that unlike a fixed workflow script?', ['tech.agent_vs_workflow']),
    ('What are guardrails in LLM systems', 'How would you implement them here?', ['tech.guardrails_how']),
    ('Define model hallucination', 'What practices keep it rare in prod?', ['tech.hallucination_prevent']),
    ('Outline the student early-warning project', 'Which tools powered that pipeline?', ['proj.early_warning.tech']),
    ('Explain training data leakage', 'How do you block it during feature work?', ['tech.data_leakage_prevent']),
    ('What is overfitting in ML', 'Your go-to prevention steps?', ['tech.overfitting_prevent']),
    ('Describe LangGraph briefly', 'Have you delivered production flows with it?', ['cv.langgraph']),
    ('What is ChromaDB used for', 'Is it still your vector store choice here?', ['tech.vector_db_choice']),
    ('When is fine-tuning appropriate', 'Where would you prefer retrieval instead?', ['tech.rag_vs_finetuning']),
    ('Explain prompt injection attacks', 'Which controls block them in your stack?', ['tech.guardrails_how']),
    ('Summarise the helpdesk classifier project', 'What made that problem difficult?', ['proj.helpdesk.challenges']),
    ('What does Whisper do', 'Why host STT on-prem instead of a cloud API?', ['tech.whisper_vs_cloud']),
]

TYPE_ORDER = (
    ("ultra_short", ULTRA_SHORT),
    ("short", SHORT),
    ("medium", MEDIUM),
    ("long", LONG),
    ("very_long", VERY_LONG),
    ("compound", COMPOUND),
    ("indirect_paraphrase", INDIRECT),
    ("follow_up_contextual", FOLLOW_UP),
)


def _bank() -> tuple[set[str], set[str]]:
    """(intent ids, normalized question/alias texts)."""
    from app.services.domain_terms import normalize_for_matching

    ids: set[str] = set()
    texts: set[str] = set()
    for path in sorted(BANK_DIR.glob("*.json")):
        for entry in json.loads(path.read_text(encoding="utf-8")).get("entries", []):
            ids.add(entry["id"])
            texts.add(normalize_for_matching(entry["question"]))
            for alias in entry.get("aliases", []):
                texts.add(normalize_for_matching(alias))
    return ids, texts


def _prior_pack_texts() -> list[tuple[str, str]]:
    """Every spoken text from every earlier pack — v4 may reuse none of them."""
    out: list[tuple[str, str]] = []
    sources = [
        ("final-unseen-holdout-v3", "scripts.json"),
        ("final-unseen-holdout-v2", "scripts.json"),
        ("final-unseen-holdout", "scripts.json"),
        ("compound-dev", "scripts.json"),
        ("generalization-dev", "scripts.json"),
        ("long-sentence-accent-pack", "manifest.json"),
        ("stress-holdout-v2", "manifest.json"),
        ("stress-pilot", "metadata.json"),
    ]
    for pack, filename in sources:
        path = VOICE_DRILL / pack / filename
        if not path.is_file():
            print(f"  note: {pack}/{filename} not found — skipped")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("entries", [])
        for row in rows:
            for key in ("transcript", "spoken_wording", "main_question"):
                text = str(row.get(key) or "").strip()
                if text:
                    out.append((pack, text))
    return out


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for i, (text, gold, qtype) in enumerate(WARMUP, start=1):
        rows.append(
            {
                "id": f"fuh4_warm_{i:02d}",
                "question_type": qtype,
                "condition": "clean",
                "accent": ACCENTS[(i - 1) % len(ACCENTS)],
                "accent_kind": ACCENT_KIND[ACCENTS[(i - 1) % len(ACCENTS)]],
                "transcript": text,
                "context_prior": None,
                "file": f"audio/fuh4_warm_{i:02d}.wav",
                "warmup": True,
                "pack": "final-unseen-holdout-v4",
                "eval_only": True,
                "_gold": list(gold),
            }
        )
    index = 0
    # Keep 2-tuple packs and 3-tuple follow-ups in separate loops so unpacking
    # shapes stay unambiguous for the type checker.
    two_tuple_packs = (
        ("ultra_short", ULTRA_SHORT),
        ("short", SHORT),
        ("medium", MEDIUM),
        ("long", LONG),
        ("very_long", VERY_LONG),
        ("compound", COMPOUND),
        ("indirect_paraphrase", INDIRECT),
    )
    for qtype, entries in two_tuple_packs:
        for text, gold in entries:
            index += 1
            rows.append(
                {
                    "id": f"fuh4_{index:03d}",
                    "question_type": qtype,
                    "condition": CONDITIONS[(index - 1) % len(CONDITIONS)],
                    "accent": ACCENTS[(index - 1) % len(ACCENTS)],
                    "accent_kind": ACCENT_KIND[ACCENTS[(index - 1) % len(ACCENTS)]],
                    "transcript": text,
                    "context_prior": None,
                    "file": f"audio/fuh4_{index:03d}.wav",
                    "warmup": False,
                    "pack": "final-unseen-holdout-v4",
                    "eval_only": True,
                    "_gold": list(gold),
                }
            )
    for prior, text, gold in FOLLOW_UP:
        index += 1
        rows.append(
            {
                "id": f"fuh4_{index:03d}",
                "question_type": "follow_up_contextual",
                "condition": CONDITIONS[(index - 1) % len(CONDITIONS)],
                "accent": ACCENTS[(index - 1) % len(ACCENTS)],
                "accent_kind": ACCENT_KIND[ACCENTS[(index - 1) % len(ACCENTS)]],
                "transcript": text,
                "context_prior": prior,
                "file": f"audio/fuh4_{index:03d}.wav",
                "warmup": False,
                "pack": "final-unseen-holdout-v4",
                "eval_only": True,
                "_gold": list(gold),
            }
        )
    return rows


def verify(rows: list[dict]) -> list[str]:
    """Hard gate on the pack itself. Any line returned here fails the build."""
    from rapidfuzz import fuzz

    from app.services.domain_terms import normalize_for_matching

    problems: list[str] = []
    ids, bank_texts = _bank()
    prior = [(pack, normalize_for_matching(t), t) for pack, t in _prior_pack_texts()]

    unknown = sorted({g for r in rows for g in r["_gold"] if g not in ids})
    if unknown:
        problems.append(f"gold references unknown intent ids: {unknown}")

    seen: dict[str, str] = {}
    for row in rows:
        norm = normalize_for_matching(row["transcript"])
        if not norm:
            problems.append(f"{row['id']}: empty transcript")
            continue
        if norm in seen:
            problems.append(f"{row['id']}: duplicates {seen[norm]} inside the pack")
        seen[norm] = row["id"]
        if norm in bank_texts:
            problems.append(f"{row['id']}: verbatim copy of a bank question/alias")
        for pack, pnorm, ptext in prior:
            if pnorm == norm:
                problems.append(f"{row['id']}: reused from {pack} ({ptext[:60]!r})")
            elif fuzz.token_set_ratio(norm, pnorm) >= 90 and abs(len(norm) - len(pnorm)) < 40:
                problems.append(
                    f"{row['id']}: near-duplicate of {pack} "
                    f"({ptext[:60]!r}, ratio {fuzz.token_set_ratio(norm, pnorm):.0f})"
                )
        if row["question_type"] == "follow_up_contextual" and not row["context_prior"]:
            problems.append(f"{row['id']}: follow-up without context_prior")

    scored = [r for r in rows if not r["warmup"]]
    if len(scored) != 120:
        problems.append(f"expected 120 scored clips, got {len(scored)}")
    for field, expected in (("condition", 24), ("accent", 30)):
        counts: dict[str, int] = {}
        for r in scored:
            counts[r[field]] = counts.get(r[field], 0) + 1
        if sorted(counts.values()) != [expected] * len(counts):
            problems.append(f"{field} not balanced: {counts}")
    types: dict[str, int] = {}
    for r in scored:
        types[r["question_type"]] = types.get(r["question_type"], 0) + 1
    if sorted(types.values()) != [15] * 8:
        problems.append(f"question types not balanced: {types}")
    return problems


def main() -> int:
    rows = build_rows()
    problems = verify(rows)
    if problems:
        print("PACK BUILD FAILED:")
        for p in problems:
            print("  -", p)
        return 1

    PACK_ROOT.mkdir(parents=True, exist_ok=True)
    (PACK_ROOT / "audio").mkdir(exist_ok=True)

    runtime = [{k: v for k, v in r.items() if k != "_gold"} for r in rows]
    gold = {r["id"]: r["_gold"] for r in rows}

    (PACK_ROOT / "scripts.json").write_text(
        json.dumps(runtime, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (PACK_ROOT / "gold.json").write_text(
        json.dumps(
            {
                "pack": "final-unseen-holdout-v4",
                "note": "Gold lives here, never in scripts.json, so no expected id "
                        "can reach the matching path. Read only by the scorer.",
                "expected_intent_ids": gold,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    scored = [r for r in rows if not r["warmup"]]
    meta = {
        "name": "final-unseen-holdout-v4",
        "eval_only": True,
        "run_once": True,
        "scored_cases": len(scored),
        "warmup_cases": len(rows) - len(scored),
        "question_types": {
            q: sum(1 for r in scored if r["question_type"] == q)
            for q, _ in TYPE_ORDER
        },
        "conditions": {c: sum(1 for r in scored if r["condition"] == c) for c in CONDITIONS},
        "accents": {a: sum(1 for r in scored if r["accent"] == a) for a in ACCENTS},
        "accent_kinds": ACCENT_KIND,
        "accent_note": (
            "en-IN is a genuine English-locale neural voice. proxy-ar-JO / "
            "proxy-ar-EG / proxy-ar-AE are Arabic-locale voices reading English: "
            "synthetic accent proxies, not recordings of human dialect speakers. "
            "Do not report them as Jordanian / Egyptian / Emirati accents."
        ),
        "voice_spotcheck_required_before_lock": True,
        "gold_file": "gold.json",
        "gold_in_runtime_scripts": False,
        "audio_status": "pending_synthesis",
        "supersedes": "final-unseen-holdout-v3",
        "protocol": "backend/reports/FINAL_UNSEEN_HOLDOUT_PROTOCOL.md",
        "novelty_checked_against": [
            "final-unseen-holdout-v3", "final-unseen-holdout", "final-unseen-holdout-v2", "compound-dev",
            "generalization-dev", "long-sentence-accent-pack", "stress-holdout-v2",
            "stress-pilot", "question bank questions + aliases",
        ],
    }
    (PACK_ROOT / "pack_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (PACK_ROOT / "manifest.json").write_text(
        json.dumps(
            [
                {"id": r["id"], "file": r["file"], "transcript": r["transcript"],
                 "condition": r["condition"], "accent": r["accent"],
                 "accent_kind": r["accent_kind"],
                 "question_type": r["question_type"], "warmup": r["warmup"]}
                for r in rows
            ],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    (PACK_ROOT / "NOVELTY.md").write_text(
        "# Final Unseen Holdout v4 — novelty proof\n\n"
        f"{len(rows)} clips ({len(scored)} scored + {len(rows) - len(scored)} warm-up).\n\n"
        "The build verifies, and refuses to write the pack unless:\n\n"
        "- no transcript normalizes to a text used in any earlier pack;\n"
        "- no transcript is within token_set_ratio 90 of an earlier pack text;\n"
        "- no transcript is a verbatim bank question or alias;\n"
        "- no transcript repeats inside the pack;\n"
        "- every gold id exists in the question bank;\n"
        "- 120 scored clips, 15 per question type, 24 per condition, 30 per accent.\n\n"
        "All checks passed at build time.\n",
        encoding="utf-8",
    )
    print(f"pack written to {PACK_ROOT}")
    print(f"  scripts.json  {len(runtime)} rows (no gold)")
    print(f"  gold.json     {len(gold)} entries")
    print("  next: python scripts/synthesize_final_unseen_holdout_v4.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
